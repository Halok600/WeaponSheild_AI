"""
image.py – POST /detect/image

Accepts an uploaded image, runs YOLO detection, returns:
  • annotated image URL
  • per-detection label, confidence score, bounding box
  • weapon_detected flag
  • alert dispatch result (email via Resend)

Alert fires when any detection passes the confidence threshold — it always
goes to the fixed operator address configured via ALERT_TO_EMAIL.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from config import IMAGE_CONFIDENCE_THRESHOLD, OUTPUTS_DIR
from model.detector import Detection, detector
from services.alert import send_weapon_alert
from services.processing import preprocess_frame

router = APIRouter(prefix="/detect", tags=["Image Detection"])


@router.post("/image")
async def detect_image(file: UploadFile = File(...)) -> JSONResponse:
    """
    Upload an image (jpeg/png/bmp/webp) and receive weapon detections.

    Args:
        file: Image file to scan.

    Returns:
        job_id:          Unique identifier for this request.
        output_url:      Relative URL of the annotated image.
        detections:      List of {label, class_id, confidence, bbox}.
        detected_classes: Distinct class names found.
        max_confidence:  Highest confidence score in this image.
        weapon_detected: True if detections pass the weapon filter.
        alert:           Email alert dispatch result.
    """
    # ── Validate ─────────────────────────────────────────────────────────────
    allowed = {"image/jpeg", "image/png", "image/bmp", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported media type: {file.content_type}. Use JPEG/PNG/BMP/WebP.",
        )

    raw = await file.read()
    img_array = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=422, detail="Could not decode image data.")

    # ── Preprocess + Detect ───────────────────────────────────────────────────
    processed = preprocess_frame(frame)
    detections: list[Detection] = detector.detect(processed)

    # Filter to only those above the threshold (detector already does this,
    # but re-check ensures we respect per-request overrides)
    detections = [d for d in detections if d.confidence >= IMAGE_CONFIDENCE_THRESHOLD]

    annotated = detector.annotate(processed, detections)

    # ── Derived metrics ───────────────────────────────────────────────────────
    detected_classes = sorted({d.label for d in detections})
    max_confidence = round(max((d.confidence for d in detections), default=0.0), 4)

    # weapon_detected: True if any detection found
    # With a fine-tuned model (WEAPON_CLASS_IDS=empty), all detections are weapons.
    weapon_detected = bool(detections)

    # ── Save output ───────────────────────────────────────────────────────────
    job_id = uuid.uuid4().hex
    out_filename = f"image_{job_id}.jpg"
    out_path: Path = OUTPUTS_DIR / out_filename
    cv2.imwrite(str(out_path), annotated, [cv2.IMWRITE_JPEG_QUALITY, 92])

    # ── Alert ─────────────────────────────────────────────────────────────────
    alert_result = {"sent": False, "reason": "no_weapon_detected", "id": None}
    if weapon_detected:
        top = max(detections, key=lambda d: d.confidence)
        alert_result = send_weapon_alert(
            timestamp=time.strftime("%H:%M:%S"),
            confidence=top.confidence,
            session_id=job_id,
            label=top.label,
        )

    return JSONResponse(
        {
            "job_id":           job_id,
            "output_url":       f"/outputs/{out_filename}",
            "detections":       [d.to_dict() for d in detections],
            "detected_classes": detected_classes,
            "max_confidence":   max_confidence,
            "weapon_detected":  weapon_detected,
            "alert":            alert_result,
        }
    )
