"""
video.py – Video upload detection router with multi-frame weapon confirmation.

Endpoints:
  POST /detect/video          – upload video, start background processing job
  GET  /detect/video/{job_id} – poll job status / results

Features:
  • Multi-frame FrameBuffer confirmation (K-of-N sliding window)
  • Per-frame detection log: {frame, timestamp, confidence, label, confirmed}
  • STOP_ON_DETECTION: stop processing as soon as weapon confirmed
  • Alert fires only on confirmed detection, not single-frame hits
  • Temporal smoothing via FrameBuffer.get_smoothed_detections()
  • GPU-accelerated inference (auto-detect)
  • Performance: configurable frame skip
"""
from __future__ import annotations

import logging
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from config import CONFIDENCE_THRESHOLD, FRAME_SKIP, OUTPUTS_DIR, STOP_ON_DETECTION
from model.detector import Detection, detector
from services.frame_buffer import FrameBuffer
from services.processing import (
    draw_status_overlay,
    draw_timestamp,
    frames_to_video,
    preprocess_frame,
    seconds_to_ts,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/detect", tags=["Video Detection"])


# ── In-memory job store ───────────────────────────────────────────────────────
class JobStatus(str, Enum):
    QUEUED     = "queued"
    PROCESSING = "processing"
    DONE       = "done"
    ERROR      = "error"


# job_id → state dict
_jobs: dict[str, dict[str, Any]] = {}


def _get_job_or_404(job_id: str) -> dict:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job


# ── Background processor ──────────────────────────────────────────────────────
def _process_video(
    job_id: str,
    video_path: Path,
    stop_on_detection: bool,
    frame_skip: int,
    add_noise: bool,
    blur_strength: int,
    low_res: bool,
    conf_threshold: float = CONFIDENCE_THRESHOLD,
) -> None:
    """
    Frame-by-frame video processing running in a thread pool.
    Updates _jobs[job_id] progressively so the poll endpoint can stream progress.

    Multi-frame logic:
      - A FrameBuffer maintains the last N frames.
      - Weapon is "confirmed" when detected in ≥ K frames or avg confidence > threshold.
      - Alert fires only on first confirmation.
      - If stop_on_detection is True, processing halts immediately after confirmation.
    """
    job = _jobs[job_id]
    job["status"] = JobStatus.PROCESSING
    job["started_at"] = time.time()

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        job["status"] = JobStatus.ERROR
        job["error"] = "Could not open video file."
        return

    fps_src = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    job["total_frames"] = total_frames

    annotated_frames: list[np.ndarray] = []
    detection_log: list[dict] = []

    frame_idx = 0
    alert_sent = False
    first_confirmed_at: str | None = None
    confirmed_count = 0

    # Per-job FrameBuffer
    buf = FrameBuffer()
    buf.reset()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            timestamp_sec = frame_idx / fps_src
            timestamp_str = seconds_to_ts(timestamp_sec)

            # ── Preprocess ────────────────────────────────────────────────────
            processed = preprocess_frame(
                frame,
                add_noise=add_noise,
                blur_strength=blur_strength,
                low_res=low_res,
            )

            # ── Inference (frame-skip for performance) ────────────────────────
            # frame_skip=0 → every frame; frame_skip=2 → every 3rd frame
            should_infer = (frame_skip == 0) or (frame_idx % (frame_skip + 1) == 0)
            if should_infer:
                dets: list[Detection] = detector.detect(processed, conf=conf_threshold)
                if dets:
                    logger.info(
                        "[video/%s] frame %d → %d detection(s) | confs: %s",
                        job_id[:8], frame_idx, len(dets),
                        [round(d.confidence, 3) for d in dets],
                    )
                # ── Push to FrameBuffer ONLY on inferred frames ───────────────
                # Skipped frames must NOT push empty results — that would
                # decrement the decay counter and prevent confirmation.
                buf.push(dets)
            else:
                dets = []

            confirmed = buf.is_weapon_confirmed()
            summary = buf.get_window_summary()

            if confirmed:
                confirmed_count += 1
                if first_confirmed_at is None:
                    first_confirmed_at = timestamp_str

            # ── Annotate with smoothed detections ─────────────────────────────
            # Use smoothed_dets (from buffer) to reduce flicker
            smoothed_dets = buf.get_smoothed_detections() if confirmed else dets
            annotated = detector.annotate(processed, smoothed_dets)

            # ── HUD overlay ───────────────────────────────────────────────────
            draw_status_overlay(
                annotated,
                confirmed=confirmed,
                fps=fps_src,
                avg_confidence=buf.get_avg_confidence(),
                positive_frames=summary["positive_frames"],
                window_size=summary["window_size"],
            )
            draw_timestamp(annotated, timestamp_str)
            annotated_frames.append(annotated)

            # ── Log confirmed detections ──────────────────────────────────────
            if dets:
                for d in dets:
                    detection_log.append(
                        {
                            "frame":         frame_idx,
                            "timestamp":     timestamp_str,
                            "timestamp_sec": round(timestamp_sec, 2),
                            "label":         d.label,
                            "confidence":    round(d.confidence, 4),
                            "bbox":          [d.x1, d.y1, d.x2, d.y2],
                            "confirmed":     confirmed,
                        }
                    )

            # ── No SMS alert for recorded video (webcam-only) ─────────────────
            if confirmed and not alert_sent:
                job["alert"] = {"sent": False, "reason": "not_applicable_for_video", "sid": None}
                alert_sent = True

            # ── Stop-on-detection ─────────────────────────────────────────────
            if confirmed and stop_on_detection:
                job["stopped_early"] = True
                break

            frame_idx += 1
            job["processed_frames"] = frame_idx

    finally:
        cap.release()

    # ── Write output video ────────────────────────────────────────────────────
    out_filename = f"video_{job_id}.mp4"
    out_path = OUTPUTS_DIR / out_filename
    try:
        frames_to_video(annotated_frames, fps_src, str(out_path))
    except Exception as exc:
        job["status"] = JobStatus.ERROR
        job["error"] = f"Video write failed: {exc}"
        return

    # Cleanup temp upload
    try:
        video_path.unlink(missing_ok=True)
    except Exception:
        pass

    job["status"]               = JobStatus.DONE
    job["output_url"]           = f"/outputs/{out_filename}"
    job["detection_log"]        = detection_log
    job["weapon_detected"]      = bool(detection_log)
    job["confirmed_detections"] = confirmed_count
    job["first_confirmed_at"]   = first_confirmed_at
    job["completed_at"]         = time.time()
    job["processed_frames"]     = frame_idx

    if not alert_sent:
        job["alert"] = {"sent": False, "reason": "no_confirmed_detection", "sid": None}


# ── Routes ────────────────────────────────────────────────────────────────────
@router.post("/video")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    stop_on_detection: bool = Form(STOP_ON_DETECTION),
    frame_skip: int = Form(FRAME_SKIP),
    add_noise: bool = Form(False),
    blur_strength: int = Form(0),
    low_res: bool = Form(False),
    conf_threshold: float = Form(CONFIDENCE_THRESHOLD),
) -> JSONResponse:
    """
    Upload a video file and start asynchronous weapon detection.

    Returns a job_id. Poll GET /detect/video/{job_id} for results.

    Body params (all optional):
      stop_on_detection – stop processing on first confirmed detection (default: from .env)
      frame_skip        – process every Nth frame (default: from .env)
      add_noise         – simulate CCTV Gaussian noise
      blur_strength     – simulate CCTV blur (kernel size)
      low_res           – simulate low-resolution CCTV feed
    """
    allowed_ext = {".mp4", ".avi", ".mov", ".mkv"}
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed_ext:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported video format '{suffix}'. Use MP4/AVI/MOV/MKV.",
        )

    # Save upload to a temp path inside outputs
    job_id = uuid.uuid4().hex
    tmp_path = OUTPUTS_DIR / f"upload_{job_id}{suffix}"
    raw = await file.read()
    tmp_path.write_bytes(raw)

    # Register job
    _jobs[job_id] = {
        "job_id":               job_id,
        "status":               JobStatus.QUEUED,
        "processed_frames":     0,
        "total_frames":         0,
        "detection_log":        [],
        "weapon_detected":      False,
        "confirmed_detections": 0,
        "first_confirmed_at":   None,
        "stopped_early":        False,
        "output_url":           None,
        "alert":                None,
        "error":                None,
    }

    background_tasks.add_task(
        _process_video,
        job_id,
        tmp_path,
        stop_on_detection,
        frame_skip,
        add_noise,
        blur_strength,
        low_res,
        conf_threshold,
    )

    return JSONResponse({"job_id": job_id, "status": JobStatus.QUEUED}, status_code=202)


@router.get("/video/{job_id}")
async def get_video_job(job_id: str) -> JSONResponse:
    """Poll processing status and retrieve results when done."""
    job = _get_job_or_404(job_id)
    return JSONResponse(job)
