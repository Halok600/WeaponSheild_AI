"""
webcam.py – Live webcam MJPEG streaming with multi-frame weapon confirmation.

Endpoints:
  GET  /detect/webcam/stream  – MJPEG stream (point <img> src here)
  GET  /detect/webcam/status  – JSON: fps, detections, threat_confirmed, avg_confidence
  POST /detect/webcam/stop    – Stop the capture thread

Features:
  • Multi-frame FrameBuffer confirmation (K-of-N sliding window)
  • HUD overlay: SAFE / ⚠️ THREAT CONFIRMED status banner
  • FPS counter + confidence bar on every frame
  • Frame-window indicator [3/5 frames]
  • Alert fires only on confirmed detection (not single-frame hits)
  • Frame skip for CPU performance
  • Thread-safe shared state
"""
from __future__ import annotations

import time
from threading import Event, Lock, Thread
from typing import Generator

import cv2
import numpy as np
from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from config import FRAME_SKIP, WEAPON_CLASS_IDS, WEBCAM_CONFIDENCE_THRESHOLD
from model.detector import Detection, detector
from services.alert import clear_event_cache, reset_cooldown, send_weapon_alert
from services.frame_buffer import FrameBuffer
from services.processing import draw_status_overlay, preprocess_frame

# ── Constants ─────────────────────────────────────────────────────────────────
FRAME_WINDOW              = 10   # sliding window size
DETECTION_COUNT_THRESHOLD = 4   # min positive frames to confirm a threat (out of 10)

router = APIRouter(prefix="/detect", tags=["Webcam Detection"])

# ── Shared webcam state ───────────────────────────────────────────────────────
_lock              = Lock()
_latest_jpeg: bytes = b""
_latest_detections: list[dict] = []
_fps: float         = 0.0
_running            = False
_threat_confirmed   = False
_avg_confidence     = 0.0
_positive_frames    = 0
_window_size        = 0
_stop_event         = Event()
_thread: Thread | None = None


def _capture_loop(camera_index: int, frame_skip: int) -> None:
    """
    Background thread: captures frames, runs YOLO inference (with frame skip),
    updates the FrameBuffer, applies HUD overlay, encodes to JPEG.
    """
    global _latest_jpeg, _latest_detections, _fps, _running
    global _threat_confirmed, _avg_confidence, _positive_frames, _window_size

    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        # Try without backend flag (Linux/Mac)
        cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        _running = False
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    buf = FrameBuffer()
    buf.reset()
    reset_cooldown("webcam")
    clear_event_cache()   # clear stale dedup entries from previous sessions

    prev_time  = time.time()
    frame_idx  = 0
    alert_sent = False

    while not _stop_event.is_set():
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue

        # ── FPS calculation ───────────────────────────────────────────────────
        now = time.time()
        fps = 1.0 / max(now - prev_time, 1e-6)
        prev_time = now

        # ── Inference with frame skip ─────────────────────────────────────────
        if frame_idx % max(frame_skip + 1, 1) == 0:
            processed = preprocess_frame(frame)
            dets: list[Detection] = detector.detect(processed, conf=WEBCAM_CONFIDENCE_THRESHOLD)
        else:
            processed = preprocess_frame(frame)
            dets = []

        # ── Multi-frame buffer ────────────────────────────────────────────────
        buf.push(dets)
        confirmed = buf.is_weapon_confirmed()
        summary   = buf.get_window_summary()
        avg_conf  = buf.get_avg_confidence()

        # Debug: per-frame state
        print(
            f"[WEBCAM] frame_det={bool(dets)} | "
            f"pos={summary['positive_frames']}/{summary['window_size']} | "
            f"confirmed={confirmed} | avg_conf={avg_conf:.2f}"
        )

        # ── Temporal smoothing on annotation ──────────────────────────────────
        smoothed_dets = buf.get_smoothed_detections() if confirmed else dets
        annotated = detector.annotate(processed, smoothed_dets)

        # ── HUD overlay ───────────────────────────────────────────────────────
        draw_status_overlay(
            annotated,
            confirmed=confirmed,
            fps=fps,
            avg_confidence=avg_conf,
            positive_frames=summary["positive_frames"],
            window_size=summary["window_size"],
        )

        # ── Alert on first multi-frame confirmation ───────────────────────────
        # Run Twilio in a background thread so it never blocks the capture loop.
        if confirmed and not alert_sent:
            ts    = time.strftime("%H:%M:%S")
            label = smoothed_dets[0].label if smoothed_dets else "Weapon"
            conf  = avg_conf
            print(f"[WEBCAM ALERT] Firing SMS → label={label} conf={conf:.2f} ts={ts}")

            def _send(ts=ts, label=label, conf=conf):
                try:
                    result = send_weapon_alert(
                        timestamp=ts,
                        confidence=conf,
                        session_id="webcam",
                        label=label,
                    )
                    print(f"[WEBCAM ALERT] SMS result: sent={result['sent']} reason={result['reason']} sid={result.get('sid')}")
                except Exception as exc:
                    print(f"[WEBCAM ALERT] Exception during SMS send: {exc}")

            Thread(target=_send, daemon=True).start()
            alert_sent = True
        elif not confirmed and summary["positive_frames"] == 0:
            # Re-arm alert only after decay fully clears (no positives left in window)
            alert_sent = False

        # ── Encode to JPEG ────────────────────────────────────────────────────
        _, jpeg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 78])

        with _lock:
            _latest_jpeg       = jpeg.tobytes()
            _latest_detections = [d.to_dict() for d in smoothed_dets]
            _fps               = round(fps, 1)
            _threat_confirmed  = confirmed
            _avg_confidence    = avg_conf
            _positive_frames   = summary["positive_frames"]
            _window_size       = summary["window_size"]

        frame_idx += 1

    cap.release()
    _running = False


def _start_camera(camera_index: int = 0, frame_skip: int = FRAME_SKIP) -> None:
    global _running, _thread, _stop_event
    if _running:
        return
    _stop_event.clear()
    _running = True
    _thread = Thread(
        target=_capture_loop,
        args=(camera_index, frame_skip),
        daemon=True,
    )
    _thread.start()


def _stream_generator() -> Generator[bytes, None, None]:
    """Yield MJPEG frames as multipart/x-mixed-replace boundary chunks."""
    while True:
        with _lock:
            frame = _latest_jpeg
        if frame:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
        time.sleep(0.03)


# ── Routes ─────────────────────────────────────────────────────────────────────
@router.get("/webcam/stream")
def webcam_stream(camera: int = 0, frame_skip: int = FRAME_SKIP) -> StreamingResponse:
    """
    Start (or reuse) webcam capture thread and return MJPEG stream.
    Point an <img> src or <video> tag at this URL in the browser.

    Query params:
      camera     – camera device index (default: 0)
      frame_skip – process every Nth frame (default: from .env)
    """
    _start_camera(camera, frame_skip)
    return StreamingResponse(
        _stream_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/webcam/status")
def webcam_status() -> JSONResponse:
    """
    Return current detection state.

    Response fields:
      running          – whether capture thread is active
      fps              – current frames per second
      detections       – list of current detection dicts
      threat_confirmed – True if multi-frame confirmation triggered
      avg_confidence   – smoothed confidence across window
      positive_frames  – frames with detections in current window
      window_size      – sliding window size
      status_label     – 'SAFE' or 'THREAT CONFIRMED'
    """
    with _lock:
        return JSONResponse(
            {
                "running":         _running,
                "fps":             _fps,
                "detections":      _latest_detections,
                "threat_confirmed": _threat_confirmed,
                "avg_confidence":  _avg_confidence,
                "positive_frames": _positive_frames,
                "window_size":     _window_size,
                "status_label":    "THREAT CONFIRMED" if _threat_confirmed else "SCANNING...",
            }
        )


@router.post("/webcam/stop")
def webcam_stop() -> JSONResponse:
    """Signal the webcam thread to stop."""
    _stop_event.set()
    return JSONResponse({"stopped": True})
