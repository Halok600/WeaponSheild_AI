"""
alert.py – Twilio SMS alert dispatcher with per-session rate-limiting and
           event-deduplication.

Features:
  • send_weapon_alert()  – convenience wrapper with correct CCTV message format
  • send_alert()         – low-level dispatcher (message, session_id)
  • reset_cooldown()     – reset per-session timer (call on new upload)
  • Cooldown guard       – prevents flooding for the same session
  • Event-hash dedup     – same timestamp+confidence won't fire twice
  • Graceful degradation – logs to console if Twilio is unconfigured/unavailable

If Twilio credentials are missing the alert is silently logged to console
so the rest of the application continues to work without configuration.

COMMON FAILURE REASONS:
  • TWILIO_FROM_NUMBER must be a Twilio-provisioned number (not a personal number).
  • Trial accounts can only send to verified numbers and must use a Twilio number.
  • Inline comments in .env values (e.g. +1234 # comment) are stripped automatically.
"""
from __future__ import annotations

import hashlib
import logging
import time
from threading import Lock

logger = logging.getLogger(__name__)

# Lazy import so the app boots even if twilio isn't installed
try:
    from twilio.rest import Client as TwilioClient  # type: ignore
    _twilio_available = True
except ImportError:
    _twilio_available = False

from config import (
    ALERT_COOLDOWN_SECONDS,
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_ENABLED,
    TWILIO_MESSAGING_SERVICE_SID,
    TWILIO_TO_NUMBER,
)

# Strip inline comments from the TO number
_TO = TWILIO_TO_NUMBER.split("#")[0].strip()
_MSG_SID = TWILIO_MESSAGING_SERVICE_SID.strip()

# Per-session last-alert timestamps  {session_id: epoch_float}
_last_alert: dict[str, float] = {}
# Event hashes already alerted – prevents duplicate alerts for same event
_alerted_events: set[str] = set()
_lock = Lock()

# Twilio client (initialised once if credentials present)
_client: TwilioClient | None = None
if TWILIO_ENABLED and _twilio_available:
    try:
        _client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        logger.info("Twilio client initialised successfully.")
        logger.info("Twilio MessagingServiceSid=%s  TO=%s", _MSG_SID, _TO)
    except Exception as exc:  # pragma: no cover
        logger.warning("Twilio client init failed: %s", exc)
elif not TWILIO_ENABLED:
    logger.warning(
        "Twilio NOT configured. Check TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / "
        "TWILIO_MESSAGING_SERVICE_SID / TWILIO_TO_NUMBER in backend/.env"
    )


# ── Convenience weapon-alert wrapper ─────────────────────────────────────────
def send_weapon_alert(
    *,
    timestamp: str,
    confidence: float,
    session_id: str = "global",
    label: str = "Weapon",
) -> dict:
    """
    Fire a Twilio SMS alert in the standard CCTV format:
        ⚠️ Weapon detected at 00:01:23 with confidence 87%

    Args:
        timestamp:  Human-readable timestamp string e.g. '00:01:23'.
        confidence: Detection confidence 0.0–1.0.
        session_id: Per-session rate-limit key.
        label:      Detected weapon class name.

    Returns:
        dict with keys: sent, reason, sid
    """
    conf_pct = int(round(confidence * 100))
    message = (
        f"⚠️ {label} detected at {timestamp} with confidence {conf_pct}% "
        f"— WeaponShield AI Surveillance System"
    )
    # Build a deduplication hash: same label + timestamp is one event
    event_key = hashlib.md5(f"{session_id}|{label}|{timestamp}".encode()).hexdigest()

    with _lock:
        if event_key in _alerted_events:
            logger.debug("Duplicate event skipped: %s", event_key)
            return {"sent": False, "reason": "duplicate_event", "sid": None}

    result = send_alert(message=message, session_id=session_id)

    if result["sent"]:
        with _lock:
            _alerted_events.add(event_key)

    return result


# ── Core dispatcher ───────────────────────────────────────────────────────────
def send_alert(
    *,
    message: str,
    session_id: str = "global",
) -> dict:
    """
    Send an SMS alert via Twilio if:
      1. Twilio is configured and available.
      2. Cooldown period has elapsed for the given session.

    Args:
        message:    Alert body, e.g. "⚠️ Weapon detected at 00:01:23 with confidence 87%".
        session_id: Unique key for rate-limiting (e.g. job_id or 'webcam').

    Returns:
        dict with keys: sent (bool), reason (str), sid (str | None)
    """
    now = time.time()

    with _lock:
        last = _last_alert.get(session_id, 0.0)
        if now - last < ALERT_COOLDOWN_SECONDS:
            remaining = int(ALERT_COOLDOWN_SECONDS - (now - last))
            logger.debug("Alert throttled for session %s (%ds remaining).", session_id, remaining)
            return {"sent": False, "reason": f"cooldown ({remaining}s left)", "sid": None}

        _last_alert[session_id] = now

    # Attempt Twilio dispatch
    if not TWILIO_ENABLED:
        logger.warning("[ALERT – Twilio not configured] %s", message)
        return {"sent": False, "reason": "twilio_not_configured", "sid": None}

    if not _twilio_available:
        logger.warning("[ALERT – twilio package missing] %s", message)
        return {"sent": False, "reason": "twilio_package_missing", "sid": None}

    if _client is None:
        logger.warning("[ALERT – client init failed] %s", message)
        return {"sent": False, "reason": "client_init_failed", "sid": None}

    try:
        logger.info("[TWILIO] Sending SMS via MessagingService=%s to %s", _MSG_SID, _TO)
        msg = _client.messages.create(
            body=message,
            messaging_service_sid=_MSG_SID,
            to=_TO,
        )
        logger.info("[TWILIO] SMS sent. SID=%s status=%s", msg.sid, msg.status)
        return {"sent": True, "reason": "ok", "sid": msg.sid}
    except Exception as exc:
        err_str = str(exc)
        logger.error(
            "[TWILIO] Send FAILED: %s\n"
            "  MessagingServiceSid=%s  TO=%s",
            err_str, _MSG_SID, _TO,
        )
        return {"sent": False, "reason": err_str, "sid": None}


def reset_cooldown(session_id: str = "global") -> None:
    """Reset the cooldown timer for a session (e.g. new upload job)."""
    with _lock:
        _last_alert.pop(session_id, None)


def clear_event_cache() -> None:
    """Clear deduplication event cache (call between distinct sessions if needed)."""
    with _lock:
        _alerted_events.clear()
