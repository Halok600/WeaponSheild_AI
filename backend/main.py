"""
main.py – FastAPI application entry point.

Run with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import OUTPUTS_DIR, TWILIO_ENABLED, TWILIO_FROM_NUMBER, TWILIO_TO_NUMBER
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

# ── CORS (allow all origins during development) ───────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
    from_ = TWILIO_FROM_NUMBER.split("#")[0].strip()
    to_   = TWILIO_TO_NUMBER.split("#")[0].strip()
    return {
        "status":         "ok",
        "model_loaded":   detector._loaded,
        "model_path":     str(detector.model.ckpt_path) if detector._loaded else None,
        "twilio_enabled": TWILIO_ENABLED,
        "twilio_from":    from_ if TWILIO_ENABLED else None,
        "twilio_to":      to_   if TWILIO_ENABLED else None,
    }


# ── Manual SMS test ────────────────────────────────────────────────────────────
@app.post("/test-alert", tags=["System"])
def test_alert() -> dict:
    """
    Send a test SMS to verify Twilio configuration.
    Visit http://localhost:8000/docs and click POST /test-alert → Execute.
    """
    result = send_alert(
        message="🔔 WeaponShield AI – Test alert. Twilio is configured correctly!",
        session_id="__test__",
    )
    # Reset cooldown so it can be retried immediately
    from services.alert import reset_cooldown
    reset_cooldown("__test__")
    return result
