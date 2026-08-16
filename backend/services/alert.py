"""
alert.py – Resend email alert dispatcher with per-session rate-limiting and
           event-deduplication.

Features:
  • send_weapon_alert()  – convenience wrapper with correct alert email format
  • send_alert()         – low-level dispatcher (message, session_id, to_email)
  • reset_cooldown()     – reset per-session timer (call on new upload)
  • Cooldown guard       – prevents flooding for the same session
  • Event-hash dedup     – same timestamp+confidence won't fire twice
  • Graceful degradation – logs to console if Resend is unconfigured or no
                            recipient email was given

Unlike the old Twilio integration (fixed phone number from .env), the
recipient email is supplied per-request by the user via the frontend, since
each visitor can ask to be alerted at their own address.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from threading import Lock

import httpx

from config import ALERT_COOLDOWN_SECONDS, RESEND_API_KEY, RESEND_ENABLED, RESEND_FROM_EMAIL

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_RESEND_URL = "https://api.resend.com/emails"

# Per-session last-alert timestamps  {session_id: epoch_float}
_last_alert: dict[str, float] = {}
# Event hashes already alerted – prevents duplicate alerts for same event
_alerted_events: set[str] = set()
_lock = Lock()


def _is_valid_email(email: str | None) -> bool:
    return bool(email and _EMAIL_RE.match(email.strip()))


# ── Convenience weapon-alert wrapper ─────────────────────────────────────────
def send_weapon_alert(
    *,
    timestamp: str,
    confidence: float,
    to_email: str | None,
    session_id: str = "global",
    label: str = "Weapon",
) -> dict:
    """
    Fire a Resend email alert:
        Subject: Weapon Alert - Pistol detected
        Body:    Pistol detected at 00:01:23 with confidence 87%

    Args:
        timestamp:  Human-readable timestamp string e.g. '00:01:23'.
        confidence: Detection confidence 0.0–1.0.
        to_email:   Recipient email address supplied by the user. If missing
                    or invalid, the alert is skipped (no email configured).
        session_id: Per-session rate-limit key.
        label:      Detected weapon class name.

    Returns:
        dict with keys: sent, reason, id
    """
    conf_pct = int(round(confidence * 100))
    subject = f"Weapon Alert - {label} detected"
    html = f"""
        <div style="font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 480px;">
          <h2 style="color:#c62828; margin-bottom: 4px;">&#9888; Weapon Detected</h2>
          <p style="font-size: 15px; color:#333;">
            <strong>{label}</strong> was detected at <strong>{timestamp}</strong>
            with <strong>{conf_pct}%</strong> confidence.
          </p>
          <p style="font-size: 13px; color:#777; margin-top: 24px;">
            &mdash; WeaponShield AI Surveillance System
          </p>
        </div>
    """
    # Build a deduplication hash: same label + timestamp is one event
    event_key = hashlib.md5(f"{session_id}|{label}|{timestamp}".encode()).hexdigest()

    with _lock:
        if event_key in _alerted_events:
            logger.debug("Duplicate event skipped: %s", event_key)
            return {"sent": False, "reason": "duplicate_event", "id": None}

    result = send_alert(subject=subject, html=html, session_id=session_id, to_email=to_email)

    if result["sent"]:
        with _lock:
            _alerted_events.add(event_key)

    return result


# ── Core dispatcher ───────────────────────────────────────────────────────────
def send_alert(
    *,
    subject: str,
    html: str,
    to_email: str | None,
    session_id: str = "global",
) -> dict:
    """
    Send an email alert via Resend if:
      1. Resend is configured.
      2. A valid recipient email was supplied.
      3. Cooldown period has elapsed for the given session.

    Args:
        subject:    Email subject line.
        html:       Email HTML body.
        to_email:   Recipient email address.
        session_id: Unique key for rate-limiting (e.g. job_id or webcam session id).

    Returns:
        dict with keys: sent (bool), reason (str), id (str | None)
    """
    if not _is_valid_email(to_email):
        logger.debug("[ALERT] No valid recipient email provided — skipping.")
        return {"sent": False, "reason": "no_email_provided", "id": None}

    now = time.time()

    with _lock:
        last = _last_alert.get(session_id, 0.0)
        if now - last < ALERT_COOLDOWN_SECONDS:
            remaining = int(ALERT_COOLDOWN_SECONDS - (now - last))
            logger.debug("Alert throttled for session %s (%ds remaining).", session_id, remaining)
            return {"sent": False, "reason": f"cooldown ({remaining}s left)", "id": None}

        _last_alert[session_id] = now

    if not RESEND_ENABLED:
        logger.warning("[ALERT – Resend not configured] %s -> %s", subject, to_email)
        return {"sent": False, "reason": "resend_not_configured", "id": None}

    try:
        logger.info("[RESEND] Sending email to %s", to_email)
        resp = httpx.post(
            _RESEND_URL,
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": RESEND_FROM_EMAIL,
                "to": [to_email.strip()],
                "subject": subject,
                "html": html,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("[RESEND] Email sent. id=%s", data.get("id"))
        return {"sent": True, "reason": "ok", "id": data.get("id")}
    except Exception as exc:
        err_str = str(exc)
        logger.error("[RESEND] Send FAILED: %s  to=%s", err_str, to_email)
        return {"sent": False, "reason": err_str, "id": None}


def reset_cooldown(session_id: str = "global") -> None:
    """Reset the cooldown timer for a session (e.g. new upload job)."""
    with _lock:
        _last_alert.pop(session_id, None)


def clear_event_cache() -> None:
    """Clear deduplication event cache (call between distinct sessions if needed)."""
    with _lock:
        _alerted_events.clear()
