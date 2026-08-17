"""
detector.py – Singleton weapon detector running on ONNX Runtime.

Loads the model once at app startup and exposes:
  • detect(frame)         → list of Detection dicts
  • annotate(frame, dets) → annotated BGR frame
  • draw_fps()            → overlay FPS counter

Uses ONNX Runtime instead of full PyTorch/Ultralytics for inference — ONNX
Runtime has no autograd/training machinery, so its memory footprint is far
smaller, which matters on constrained hosts (e.g. Render's free tier, 512MB).
Since ONNX Runtime doesn't provide YOLO's pre/post-processing convenience
methods, letterbox resizing, box decoding, and NMS are implemented here
manually.

Model loading follows a priority fallback chain (configured in config.py):
  1. MODEL_PATH env var (if file exists)
  2. ../model/best.onnx   (custom fine-tuned weights, ONNX export)
"""
from __future__ import annotations

import ast
import logging
import time
from dataclasses import dataclass
from typing import ClassVar

import cv2
import numpy as np
import onnxruntime as ort

from config import CONFIDENCE_THRESHOLD, MODEL_PATH, WEAPON_CLASS_IDS

logger = logging.getLogger(__name__)

NMS_IOU_THRESHOLD = 0.7  # matches Ultralytics' own default predict() IoU

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
        Load the ONNX model following the fallback chain resolved by config.py.
        Called once during FastAPI startup via the lifespan context manager.
        """
        if self._loaded:
            return

        logger.info("Loading ONNX model from: %s", MODEL_PATH)
        start = time.perf_counter()

        self._session = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])
        input_meta = self._session.get_inputs()[0]
        self._input_name = input_meta.name
        self._input_size = int(input_meta.shape[2])  # square input, e.g. 640
        self._output_name = self._session.get_outputs()[0].name

        # Class names are embedded in the ONNX export's metadata by Ultralytics,
        # e.g. "{0: 'Pistol', 1: 'Rifle', 2: 'Knife'}"
        meta = self._session.get_modelmeta().custom_metadata_map
        names_raw = meta.get("names", "{}")
        self.class_names: dict[int, str] = ast.literal_eval(names_raw)

        elapsed = time.perf_counter() - start
        self.model_path = MODEL_PATH
        self._loaded = True

        logger.info(
            "Model loaded in %.2fs — %d classes. Weapon filter: %s.",
            elapsed,
            len(self.class_names),
            WEAPON_CLASS_IDS if WEAPON_CLASS_IDS else "ALL (fine-tuned model)",
        )

    # ── Preprocessing ────────────────────────────────────────────────────────
    def _letterbox(self, frame: np.ndarray) -> tuple[np.ndarray, float, int, int]:
        """Resize+pad frame to a square input, preserving aspect ratio."""
        h0, w0 = frame.shape[:2]
        size = self._input_size
        scale = min(size / w0, size / h0)
        nw, nh = int(round(w0 * scale)), int(round(h0 * scale))
        resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)

        pad_w, pad_h = size - nw, size - nh
        top, left = pad_h // 2, pad_w // 2
        bottom, right = pad_h - top, pad_w - left
        padded = cv2.copyMakeBorder(
            resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114)
        )

        img = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        img = img.transpose(2, 0, 1)[None]  # (1, 3, size, size)
        return np.ascontiguousarray(img), scale, left, top

    # ── Core inference ───────────────────────────────────────────────────────
    def detect(self, frame: np.ndarray, conf: float | None = None) -> list[Detection]:
        """
        Run inference on a single BGR frame.
        Returns list of Detection objects that pass confidence + class filters.

        Args:
            frame: BGR image as numpy array.
            conf:  Optional confidence threshold override. Defaults to CONFIDENCE_THRESHOLD
                   from config. Use a lower value (e.g. 0.35) for video frames which
                   have compression artifacts and motion blur.
        """
        if not self._loaded:
            raise RuntimeError("Detector not loaded. Call .load() first.")

        threshold = conf if conf is not None else CONFIDENCE_THRESHOLD
        h0, w0 = frame.shape[:2]

        input_tensor, scale, pad_x, pad_y = self._letterbox(frame)
        raw = self._session.run([self._output_name], {self._input_name: input_tensor})[0]

        # raw shape: (1, 4+nc, num_anchors) -> (num_anchors, 4+nc)
        preds = raw[0].T
        boxes_cxcywh = preds[:, :4]
        class_scores = preds[:, 4:]
        class_ids = np.argmax(class_scores, axis=1)
        confidences = class_scores[np.arange(len(class_scores)), class_ids]

        mask = confidences >= threshold
        if WEAPON_CLASS_IDS:
            mask &= np.isin(class_ids, WEAPON_CLASS_IDS)

        boxes_cxcywh = boxes_cxcywh[mask]
        confidences = confidences[mask]
        class_ids = class_ids[mask]

        if len(boxes_cxcywh) == 0:
            return []

        cx, cy, bw, bh = boxes_cxcywh[:, 0], boxes_cxcywh[:, 1], boxes_cxcywh[:, 2], boxes_cxcywh[:, 3]
        x1 = cx - bw / 2
        y1 = cy - bh / 2

        nms_boxes = np.stack([x1, y1, bw, bh], axis=1).tolist()
        indices = cv2.dnn.NMSBoxes(nms_boxes, confidences.tolist(), threshold, NMS_IOU_THRESHOLD)
        if len(indices) == 0:
            return []
        indices = np.array(indices).flatten()

        detections: list[Detection] = []
        for i in indices:
            # Undo letterbox padding/scaling to map back to original frame coords
            ox1 = (x1[i] - pad_x) / scale
            oy1 = (y1[i] - pad_y) / scale
            ox2 = (x1[i] + bw[i] - pad_x) / scale
            oy2 = (y1[i] + bh[i] - pad_y) / scale
            ox1 = max(0, min(w0, ox1))
            oy1 = max(0, min(h0, oy1))
            ox2 = max(0, min(w0, ox2))
            oy2 = max(0, min(h0, oy2))

            cls_id = int(class_ids[i])
            detections.append(
                Detection(
                    label=self.class_names.get(cls_id, str(cls_id)),
                    class_id=cls_id,
                    confidence=float(confidences[i]),
                    x1=int(ox1),
                    y1=int(oy1),
                    x2=int(ox2),
                    y2=int(oy2),
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
