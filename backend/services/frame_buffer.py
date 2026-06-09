"""
frame_buffer.py – Sliding-window multi-frame weapon confirmation with decay logic.

Prevents false positives by requiring a weapon to appear in at least K out
of the last N frames before raising an alert. A decay counter replaces hard
reset: it increments on positive frames and decrements (min 0) on negative
frames, so brief disappearances don't instantly kill the running count.

Usage:
    buf = FrameBuffer()
    buf.push(detections)          # call once per processed frame
    if buf.is_weapon_confirmed():
        alert(...)
    smoothed = buf.get_smoothed_detections()
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from model.detector import Detection

from config import (
    CONFIDENCE_THRESHOLD,
    DETECTION_COUNT_THRESHOLD,
    FRAME_WINDOW,
)

logger = logging.getLogger(__name__)


# ── Internal snapshot ─────────────────────────────────────────────────────────
@dataclass
class _FrameSnapshot:
    """A single frame's detection result stored in the buffer."""
    has_detection: bool
    detections: list = field(default_factory=list)   # list[Detection]
    max_confidence: float = 0.0


# ── FrameBuffer ───────────────────────────────────────────────────────────────
class FrameBuffer:
    """
    Thread-safe sliding-window buffer for multi-frame weapon confirmation.

    Args:
        window_size:         Number of recent frames to retain (default: FRAME_WINDOW).
        count_threshold:     Frames with detections needed to confirm (default: DETECTION_COUNT_THRESHOLD).
        confidence_threshold: Alternative trigger — confirm if avg conf exceeds this (default: CONFIDENCE_THRESHOLD).
    """

    def __init__(
        self,
        window_size: int = FRAME_WINDOW,
        count_threshold: int = DETECTION_COUNT_THRESHOLD,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
    ) -> None:
        self._window_size = window_size
        self._count_threshold = count_threshold
        self._conf_threshold = confidence_threshold
        self._buffer: deque[_FrameSnapshot] = deque(maxlen=window_size)
        self._lock = Lock()
        # Decay counter: goes up on positive frames, down by 1 on negative frames
        self._decay_count: int = 0

    # ── Public API ────────────────────────────────────────────────────────────
    def push(self, detections: list) -> None:
        """
        Add the detection results of one frame to the buffer.

        Only counts detections that meet CONFIDENCE_THRESHOLD.
        Uses decay logic: count increments on positive frames, decrements by 1
        (not reset to 0) on negative frames, keeping confirmation stable.

        Args:
            detections: list[Detection] — may be empty if no objects found.
        """
        # Filter by confidence threshold before deciding positivity
        qualified = [d for d in detections if d.confidence >= self._conf_threshold]
        has_det = bool(qualified)
        max_conf = max((d.confidence for d in qualified), default=0.0)

        snapshot = _FrameSnapshot(
            has_detection=has_det,
            detections=list(detections),   # keep all for annotation
            max_confidence=max_conf,
        )

        with self._lock:
            self._buffer.append(snapshot)
            # ── Decay logic (replaces hard reset to 0) ────────────────────────
            if has_det:
                self._decay_count += 1
            else:
                # Decay rather than reset — prevents single missed frame killing count
                self._decay_count = max(0, self._decay_count - 1)

        # ── Debug output ──────────────────────────────────────────────────────
        logger.debug(
            "[FrameBuffer] detected=%s | decay_count=%d | max_conf=%.2f",
            has_det, self._decay_count, max_conf,
        )
        print(
            f"[WEBCAM] detected={has_det} | "
            f"decay_count={self._decay_count} | "
            f"conf={max_conf:.2f} | "
            f"threshold={self._conf_threshold}"
        )

    def is_weapon_confirmed(self) -> bool:
        """
        Return True if weapon presence is confirmed by EITHER:
          • decay-count : _decay_count >= DETECTION_COUNT_THRESHOLD (primary), OR
          • sliding-window count: positive frames in window >= threshold (fallback)
        """
        with self._lock:
            frames = list(self._buffer)
            decay = self._decay_count

        if not frames:
            return False

        # Primary: decay-based count
        if decay >= self._count_threshold:
            return True

        # Fallback: count-based sliding window
        positive_frames = sum(1 for f in frames if f.has_detection)
        if positive_frames >= self._count_threshold:
            return True

        return False

    def get_avg_confidence(self) -> float:
        """Return the smoothed average confidence across all positive frames in the window."""
        with self._lock:
            confs = [f.max_confidence for f in self._buffer if f.has_detection]
        return round(sum(confs) / len(confs), 4) if confs else 0.0

    def get_positive_frame_count(self) -> int:
        """Number of frames in the current window that contain detections."""
        with self._lock:
            return sum(1 for f in self._buffer if f.has_detection)

    def get_smoothed_detections(self) -> list:
        """
        Return detections from the most-recent positive frame,
        representing the temporally smoothed view.
        """
        with self._lock:
            for snap in reversed(self._buffer):
                if snap.has_detection:
                    return snap.detections
        return []

    def get_window_summary(self) -> dict:
        """Diagnostic summary of the current window state."""
        with self._lock:
            frames = list(self._buffer)
        positive = sum(1 for f in frames if f.has_detection)
        confs = [f.max_confidence for f in frames if f.has_detection]
        return {
            "window_size": self._window_size,
            "frames_in_buffer": len(frames),
            "positive_frames": positive,
            "count_threshold": self._count_threshold,
            "avg_confidence": round(sum(confs) / len(confs), 4) if confs else 0.0,
            "confirmed": self.is_weapon_confirmed(),
        }

    def reset(self) -> None:
        """Clear the buffer and decay counter (call at the start of each new session)."""
        with self._lock:
            self._buffer.clear()
            self._decay_count = 0
        logger.debug("FrameBuffer reset.")
