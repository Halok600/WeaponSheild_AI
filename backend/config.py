"""
config.py – Centralised configuration loaded from environment variables.
Copy .env.template → .env and fill in your credentials before running.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env located next to this file
load_dotenv(Path(__file__).parent / ".env")

# ── Resend (email alerts) ────────────────────────────────────────────────────
# Resend's shared sandbox sender (onboarding@resend.dev, used when no custom
# domain is verified) only allows sending to the email address that owns the
# Resend account — sending to arbitrary visitor-supplied addresses gets a 403.
# So alerts go to one fixed operator address rather than a per-visitor one.
RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL: str = os.getenv("RESEND_FROM_EMAIL", "WeaponShield AI <onboarding@resend.dev>")
# Comma-separate multiple addresses if more than one person should be notified.
ALERT_TO_EMAILS: list[str] = [e.strip() for e in os.getenv("ALERT_TO_EMAIL", "").split(",") if e.strip()]
RESEND_ENABLED: bool = bool(RESEND_API_KEY and ALERT_TO_EMAILS)

# ── Model — fallback chain: best.pt → yolov8n.pt ─────────────────────────────
BASE_DIR: Path = Path(__file__).parent
PROJECT_ROOT: Path = BASE_DIR.parent

def _resolve_model_path() -> str:
    """
    Resolve model weights with a priority fallback chain:
      1. Path from MODEL_PATH env var (if it exists on disk)
      2. ../model/best.pt  (custom fine-tuned weights)
      3. yolov8n.pt        (base model, auto-downloaded by ultralytics)
    """
    env_path = os.getenv("MODEL_PATH", "").strip()

    # Normalise relative paths relative to project root
    candidates: list[Path] = []
    if env_path:
        p = Path(env_path)
        candidates.append(p if p.is_absolute() else (PROJECT_ROOT / p).resolve())

    # Always try fine-tuned best.pt as second option
    candidates.append((PROJECT_ROOT / "model" / "best.pt").resolve())

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    # Fallback: let ultralytics auto-download the nano base model
    return "yolov8n.pt"


MODEL_PATH: str = _resolve_model_path()

# Optional: comma-separated integer class IDs treated as weapons.
# Leave empty to flag ALL detected classes as weapons (use with a finetuned model).
_weapon_ids_raw = os.getenv("WEAPON_CLASS_IDS", "")
WEAPON_CLASS_IDS: list[int] | None = (
    [int(c) for c in _weapon_ids_raw.split(",") if c.strip()]
    if _weapon_ids_raw.strip()
    else None
)

CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.50"))

# Per-mode overrides — fall back to CONFIDENCE_THRESHOLD if not explicitly set.
# IMAGE: single-shot, high precision required → default 0.60
IMAGE_CONFIDENCE_THRESHOLD: float = float(
    os.getenv("IMAGE_CONFIDENCE_THRESHOLD", str(max(CONFIDENCE_THRESHOLD, 0.60)))
)
# WEBCAM: live feed has noise, but shouldn't be as strict as images → default 0.25
WEBCAM_CONFIDENCE_THRESHOLD: float = float(
    os.getenv("WEBCAM_CONFIDENCE_THRESHOLD", "0.25")
)

# ── Multi-Frame Confirmation ──────────────────────────────────────────────────
# Rolling window of frames used for weapon confirmation
FRAME_WINDOW: int = int(os.getenv("FRAME_WINDOW", "5"))
# Minimum number of positive frames within the window to confirm a weapon
DETECTION_COUNT_THRESHOLD: int = int(os.getenv("DETECTION_COUNT_THRESHOLD", "3"))
# Stop video processing once weapon is confirmed
STOP_ON_DETECTION: bool = os.getenv("STOP_ON_DETECTION", "true").lower() in ("1", "true", "yes")

# ── Processing ───────────────────────────────────────────────────────────────
INFERENCE_WIDTH: int = int(os.getenv("INFERENCE_WIDTH", "640"))
FRAME_SKIP: int = int(os.getenv("FRAME_SKIP", "2"))  # 0 = process every frame

# ── Paths ────────────────────────────────────────────────────────────────────
OUTPUTS_DIR: Path = BASE_DIR / os.getenv("OUTPUTS_DIR", "outputs")
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Alert rate-limit: seconds between successive alerts for the same session
ALERT_COOLDOWN_SECONDS: int = 60

# ── CORS ─────────────────────────────────────────────────────────────────────
# Comma-separated list of allowed frontend origins in production, e.g.:
#   CORS_ORIGINS=https://weaponshield.vercel.app,https://weaponshield-preview.vercel.app
# Leave empty for local dev — falls back to allowing all origins (no credentials).
_cors_origins_raw = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS: list[str] = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
