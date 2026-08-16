"""
webcam.py – Browser-captured live detection with multi-frame weapon confirmation.

The user's own browser captures webcam frames (via getUserMedia) and posts
them here one at a time; the server never touches a physical camera, which
is what makes this work on a headless cloud deployment (Render has no
webcam attached, unlike a local dev machine).

Endpoints:
  POST /detect/webcam/frame  – submit one frame, get back detections + threat state
  POST /detect/webcam/stop   – clear a session's buffer when the user stops the feed

Features:
  • Per-session FrameBuffer (K-of-N sliding window) so concurrent visitors
    don't share state with each other.
  • Alert fires only on confirmed detection (not single-frame hits).
  • Stale sessions are swept opportunistically so memory doesn't grow forever.
"""
from __future__ import annotations

import time
from threading import Lock
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from config import WEBCAM_CONFIDENCE_THRESHOLD
from model.detector import Detection, detector
from services.alert import send_weapon_alert
from services.frame_buffer import FrameBuffer

router = APIRouter(prefix="/detect", tags=["Webcam Detection"])

FRAME_WINDOW              = 10   # sliding window size
DETECTION_COUNT_THRESHOLD = 4    # min positive frames to confirm a threat (out of 10)
SESSION_TTL_SECONDS       = 600  # drop sessions idle longer than this

# session_id -> {"buffer": FrameBuffer, "last_seen": float}
_sessions: dict[str, dict[str, Any]] = {}
_lock = Lock()


def _get_session(session_id: str) -> FrameBuffer:
    """Get or create the FrameBuffer for a session, and sweep stale ones."""
    now = time.time()
    with _lock:
        stale = [sid for sid, s in _sessions.items() if now - s["last_seen"] > SESSION_TTL_SECONDS]
        for sid in stale:
            del _sessions[sid]

        session = _sessions.get(session_id)
        if session is None:
            session = {
                "buffer": FrameBuffer(window_size=FRAME_WINDOW, count_threshold=DETECTION_COUNT_THRESHOLD),
                "last_seen": now,
                "alert_sent": False,
            }
            _sessions[session_id] = session
        else:
            session["last_seen"] = now
        return session


@router.post("/webcam/frame")
async def submit_frame(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    alert_email: str | None = Form(None),
) -> JSONResponse:
    """
    Submit one browser-captured frame for detection.

    Args:
        file:        JPEG/PNG frame captured client-side from the user's webcam.
        session_id:  Client-generated ID identifying this viewer's live session.
        alert_email: Optional email to notify once a weapon is confirmed.

    Returns:
        detections, frame_width/height (for overlay scaling), threat_confirmed,
        avg_confidence, positive_frames, window_size, alert.
    """
    raw = await file.read()
    img_array = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=422, detail="Could not decode frame data.")

    h, w = frame.shape[:2]

    dets: list[Detection] = detector.detect(frame, conf=WEBCAM_CONFIDENCE_THRESHOLD)

    session = _get_session(session_id)
    buf: FrameBuffer = session["buffer"]
    buf.push(dets)

    confirmed = buf.is_weapon_confirmed()
    summary = buf.get_window_summary()

    alert_result = {"sent": False, "reason": "not_confirmed", "id": None}
    if confirmed:
        smoothed = buf.get_smoothed_detections()
        top_label = smoothed[0].label if smoothed else "Weapon"
        alert_result = send_weapon_alert(
            timestamp=time.strftime("%H:%M:%S"),
            confidence=buf.get_avg_confidence(),
            to_email=alert_email,
            session_id=session_id,
            label=top_label,
        )

    return JSONResponse(
        {
            "detections":       [d.to_dict() for d in dets],
            "frame_width":      w,
            "frame_height":     h,
            "threat_confirmed": confirmed,
            "avg_confidence":   summary["avg_confidence"],
            "positive_frames":  summary["positive_frames"],
            "window_size":      summary["window_size"],
            "alert":            alert_result,
        }
    )


@router.post("/webcam/stop")
async def stop_session(session_id: str = Form(...)) -> JSONResponse:
    """Clear a session's buffer when the user stops their live feed."""
    with _lock:
        _sessions.pop(session_id, None)
    return JSONResponse({"stopped": True})
