"""
detector.py – Singleton YOLO weapon detector.

Loads the model once at app startup and exposes:
  • detect(frame)         → list of Detection dicts
  • annotate(frame, dets) → annotated BGR frame
  • draw_fps()            → overlay FPS counter

Model loading follows a priority fallback chain (configured in config.py):
  1. MODEL_PATH env var (if file exists)
  2. ../model/best.pt     (custom fine-tuned weights)
  3. yolov8n.pt           (base model, auto-downloaded by ultralytics)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import ClassVar

import cv2
import numpy as np
from ultralytics import YOLO

from config import CONFIDENCE_THRESHOLD, MODEL_PATH, WEAPON_CLASS_IDS

logger = logging.getLogger(__name__)

# ── Colour palette (BGR) per class index ────────────────────────────────────
_PALETTE = [
    (0,   50, 220),   # red
    (0,  165, 255),   # orange
    (0,  255, 255),   # yellow
    (255,  0,   0),   # blue
    (255,  0, 255),   # magenta
    (0,  200,  80),   # green
]


def _colour(class_id: int) -> tuple[int, int, int]:
    return _PALETTE[class_id % len(_PALETTE)]


# ── Data model ───────────────────────────────────────────────────────────────
@dataclass
class Detection:
    label: str
    class_id: int
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "class_id": self.class_id,
            "confidence": round(self.confidence, 4),
            "bbox": [self.x1, self.y1, self.x2, self.y2],
        }


# ── Singleton detector ────────────────────────────────────────────────────────
class WeaponDetector:
    _instance: ClassVar[WeaponDetector | None] = None

    def __new__(cls) -> WeaponDetector:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def load(self) -> None:
        """
        Load YOLO model following the fallback chain resolved by config.py.
        Called once during FastAPI startup via the lifespan context manager.
        """
        if self._loaded:
            return

        # Check GPU availability and log
        try:
            import torch
            gpu_available = torch.cuda.is_available()
            device_name = torch.cuda.get_device_name(0) if gpu_available else "CPU"
            logger.info("Compute device: %s", device_name)
        except ImportError:
            gpu_available = False
            logger.info("PyTorch not installed — GPU check skipped.")

        logger.info("Loading YOLO model from: %s", MODEL_PATH)
        start = time.perf_counter()

        # PyTorch >=2.6 changed the default of torch.load to weights_only=True.
        # YOLOv8 .pt checkpoints contain Python objects (DetectionModel etc.) and
        # require weights_only=False. Since best.pt is our own trained model we
        # trust it, so we patch torch.load temporarily to preserve old behaviour.
        try:
            import torch
            import functools
            _original_torch_load = torch.load

            @functools.wraps(_original_torch_load)
            def _patched_torch_load(f, *args, **kwargs):
                kwargs.setdefault("weights_only", False)
                return _original_torch_load(f, *args, **kwargs)

            torch.load = _patched_torch_load
            self.model = YOLO(MODEL_PATH)
        finally:
            # Always restore the original torch.load after model is loaded
            torch.load = _original_torch_load
        elapsed = time.perf_counter() - start

        self.class_names: dict[int, str] = self.model.names  # {0: 'person', …}
        self._loaded = True
        self._gpu_available = gpu_available

        logger.info(
            "Model loaded in %.2fs — %d classes. Weapon filter: %s. GPU: %s",
            elapsed,
            len(self.class_names),
            WEAPON_CLASS_IDS if WEAPON_CLASS_IDS else "ALL (fine-tuned model)",
            "yes" if gpu_available else "no (CPU mode)",
        )

    # ── Core inference ───────────────────────────────────────────────────
    def detect(self, frame: np.ndarray, conf: float | None = None) -> list[Detection]:
        """
        Run inference on a single BGR frame.
        Returns list of Detection objects that pass confidence + class filters.

        Args:
            frame: BGR image as numpy array.
            conf:  Optional confidence threshold override. Defaults to CONFIDENCE_THRESHOLD
                   from config. Use a lower value (e.g. 0.35) for video frames which
                   have compression artifacts and motion blur.

        Note:
            A hard post-inference filter is applied in addition to YOLO's internal
            `conf` parameter. Custom-trained weights sometimes bypass the model-level
            conf filter, so we enforce the threshold explicitly on every result box.
        """
        if not self._loaded:
            raise RuntimeError("Detector not loaded. Call .load() first.")

        # Resolve threshold once — used both for YOLO and the hard post-filter
        threshold = conf if conf is not None else CONFIDENCE_THRESHOLD

        results = self.model(
            frame,
            conf=threshold,
            verbose=False,
        )[0]

        detections: list[Detection] = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            if WEAPON_CLASS_IDS and cls_id not in WEAPON_CLASS_IDS:
                continue
            box_conf = float(box.conf[0])

            # ── Hard post-inference filter ────────────────────────────────────
            # Custom best.pt weights can bypass YOLO's built-in conf parameter
            # and return low-confidence boxes regardless. This guarantees the
            # user-specified threshold is always enforced.
            if box_conf < threshold:
                logger.debug(
                    "Skipping box: conf=%.3f below threshold=%.3f",
                    box_conf, threshold,
                )
                continue

            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
            label = self.class_names.get(cls_id, str(cls_id))
            detections.append(
                Detection(
                    label=label,
                    class_id=cls_id,
                    confidence=box_conf,
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                )
            )
        return detections

    # ── Annotation ──────────────────────────────────────────────────────────
    def annotate(self, frame: np.ndarray, detections: list[Detection]) -> np.ndarray:
        """Draw bounding boxes + labels onto a copy of the frame."""
        annotated = frame.copy()
        for det in detections:
            colour = _colour(det.class_id)
            # Bounding box
            cv2.rectangle(annotated, (det.x1, det.y1), (det.x2, det.y2), colour, 2)
            # Label pill background
            label_text = f"{det.label}  {det.confidence:.0%}"
            (tw, th), baseline = cv2.getTextSize(
                label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1
            )
            pill_y1 = max(det.y1 - th - baseline - 6, 0)
            cv2.rectangle(
                annotated,
                (det.x1, pill_y1),
                (det.x1 + tw + 6, det.y1),
                colour,
                cv2.FILLED,
            )
            # Label text
            cv2.putText(
                annotated,
                label_text,
                (det.x1 + 3, det.y1 - baseline - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
        return annotated

    # ── FPS helper ───────────────────────────────────────────────────────────
    @staticmethod
    def draw_fps(frame: np.ndarray, fps: float) -> np.ndarray:
        cv2.putText(
            frame,
            f"FPS: {fps:.1f}",
            (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        return frame


# Module-level singleton instance
detector = WeaponDetector()
