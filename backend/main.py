"""
main.py – FastAPI application entry point.

Run with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import CORS_ORIGINS, OUTPUTS_DIR, RESEND_ENABLED, RESEND_FROM_EMAIL
from model.detector import detector
from routers import image as image_router
from routers import video as video_router
from routers import webcam as webcam_router
from services.alert import send_alert

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan: model loaded once at startup ────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Weapon Detection API …")
    detector.load()
    logger.info("✅ YOLO model ready.")
    yield
    logger.info("🛑 Shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Weapon Detection System",
    description=(
        "AI-powered weapon detection API supporting image uploads, "
        "CCTV video processing, and live webcam streaming."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────────────────
# With specific origins configured (production), credentials are allowed.
# With no origins configured (local dev), fall back to wildcard — browsers
# reject wildcard + credentials together, so credentials are disabled then.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["*"],
    allow_credentials=bool(CORS_ORIGINS),
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files (serve processed outputs) ───────────────────────────────────
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(image_router.router)
app.include_router(video_router.router)
app.include_router(webcam_router.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
def health() -> dict:
    return {
        "status":         "ok",
        "model_loaded":   detector._loaded,
        "model_path":     str(detector.model.ckpt_path) if detector._loaded else None,
        "model_classes":  list(detector.class_names.values()) if detector._loaded else None,
        "resend_enabled": RESEND_ENABLED,
        "resend_from":    RESEND_FROM_EMAIL if RESEND_ENABLED else None,
    }


# ── Manual email alert test ──────────────────────────────────────────────────
@app.post("/test-alert", tags=["System"])
def test_alert(email: str) -> dict:
    """
    Send a test email to verify Resend configuration.
    Visit http://localhost:8000/docs and click POST /test-alert → Try it out.
    """
    result = send_alert(
        subject="WeaponShield AI - Test Alert",
        html="<p>&#128276; WeaponShield AI &ndash; Test alert. Resend is configured correctly!</p>",
        to_email=email,
        session_id="__test__",
    )
    # Reset cooldown so it can be retried immediately
    from services.alert import reset_cooldown
    reset_cooldown("__test__")
    return result

# End of main configuration
