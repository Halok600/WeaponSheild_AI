"""
detector.py – Singleton weapon detector supporting two inference engines,
              selected automatically from MODEL_PATH's file extension:

  • .pt   → PyTorch/Ultralytics YOLO (full accuracy, needs a GPU/CPU with
            plenty of RAM — used for local dev where there's no memory
            constraint and a real GPU is available).
  • .onnx → ONNX Runtime (much lighter footprint, no autograd/training
            machinery — used for the deployed backend on Render's
            constrained free tier, which OOMs under full PyTorch).

Both engines expose the same detect()/annotate()/draw_fps() interface so
the rest of the app doesn't need to know which one is active.

Model loading follows a priority fallback chain (configured in config.py):
  1. MODEL_PATH env var (if it exists on disk)
  2. ../model/best.onnx (default fallback)
"""
from __future__ import annotations

import ast
import logging
import time
from dataclasses import dataclass
from typing import ClassVar

import cv2
import numpy as np

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
        Load the model, picking the engine from MODEL_PATH's extension.
        Called once during FastAPI startup via the lifespan context manager.
        """
        if self._loaded:
            return

        self._engine = "pytorch" if MODEL_PATH.lower().endswith(".pt") else "onnx"
        logger.info("Loading %s model from: %s", self._engine, MODEL_PATH)
        start = time.perf_counter()

        if self._engine == "pytorch":
            self._load_pytorch()
        else:
            self._load_onnx()

        elapsed = time.perf_counter() - start
        self.model_path = MODEL_PATH
        self._loaded = True

        logger.info(
            "Model loaded in %.2fs via %s — %d classes. Weapon filter: %s.",
            elapsed,
            self._engine,
            len(self.class_names),
            WEAPON_CLASS_IDS if WEAPON_CLASS_IDS else "ALL (fine-tuned model)",
        )

    # ── PyTorch engine ───────────────────────────────────────────────────────
    def _load_pytorch(self) -> None:
        from ultralytics import YOLO

        try:
            import torch
            gpu_available = torch.cuda.is_available()
            logger.info(
                "Compute device: %s",
                torch.cuda.get_device_name(0) if gpu_available else "CPU",
            )
        except ImportError:
            gpu_available = False

        # PyTorch >=2.6 changed the default of torch.load to weights_only=True.
        # YOLOv8 .pt checkpoints contain Python objects (DetectionModel etc.)
        # and require weights_only=False. Since best.pt is our own trained
        # model we trust it, so we patch torch.load temporarily.
        import functools
        import torch
        _original_torch_load = torch.load

        @functools.wraps(_original_torch_load)
        def _patched_torch_load(f, *args, **kwargs):
            kwargs.setdefault("weights_only", False)
            return _original_torch_load(f, *args, **kwargs)

        torch.load = _patched_torch_load
        try:
            self._yolo = YOLO(MODEL_PATH)
        finally:
            torch.load = _original_torch_load

        self.class_names: dict[int, str] = self._yolo.names
        self._gpu_available = gpu_available

    def _detect_pytorch(self, frame: np.ndarray, threshold: float) -> list[Detection]:
        results = self._yolo(frame, conf=threshold, verbose=False)[0]

        detections: list[Detection] = []
        for box in results.boxes:
            cls_id = int(box.cls[0])
            if WEAPON_CLASS_IDS and cls_id not in WEAPON_CLASS_IDS:
                continue
            box_conf = float(box.conf[0])

            # Hard post-inference filter — custom weights can bypass the
            # model-level conf parameter and return low-confidence boxes.
            if box_conf < threshold:
                continue

            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
            detections.append(
                Detection(
                    label=self.class_names.get(cls_id, str(cls_id)),
                    class_id=cls_id,
                    confidence=box_conf,
                    x1=x1, y1=y1, x2=x2, y2=y2,
                )
            )
        return detections

    # ── ONNX Runtime engine ──────────────────────────────────────────────────
    def _load_onnx(self) -> None:
        import onnxruntime as ort

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

    def _detect_onnx(self, frame: np.ndarray, threshold: float) -> list[Detection]:
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
            ox1 = max(0, min(w0, (x1[i] - pad_x) / scale))
            oy1 = max(0, min(h0, (y1[i] - pad_y) / scale))
            ox2 = max(0, min(w0, (x1[i] + bw[i] - pad_x) / scale))
            oy2 = max(0, min(h0, (y1[i] + bh[i] - pad_y) / scale))

            cls_id = int(class_ids[i])
            detections.append(
                Detection(
                    label=self.class_names.get(cls_id, str(cls_id)),
                    class_id=cls_id,
                    confidence=float(confidences[i]),
                    x1=int(ox1), y1=int(oy1), x2=int(ox2), y2=int(oy2),
                )
            )
        return detections

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
        if self._engine == "pytorch":
            return self._detect_pytorch(frame, threshold)
        return self._detect_onnx(frame, threshold)

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
