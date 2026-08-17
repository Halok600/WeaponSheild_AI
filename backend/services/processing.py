"""
processing.py – Frame preprocessing utilities, video I/O helpers, and HUD overlays.

Provides:
  • preprocess_frame()        – resize + optional CCTV simulation (noise/blur)
  • frames_to_video()         – write annotated frames to an output video file
  • seconds_to_ts()           – format seconds as HH:MM:SS
  • draw_timestamp()          – burn timestamp watermark onto frame in-place
  • draw_status_overlay()     – draw SAFE / ⚠️ THREAT HUD with FPS + confidence
"""
from __future__ import annotations

import cv2
import imageio
import numpy as np

from config import INFERENCE_WIDTH

# ── Colour constants (BGR) ────────────────────────────────────────────────────
_GREEN  = (0, 220, 80)
_RED    = (0, 50, 220)
_WHITE  = (255, 255, 255)
_BLACK  = (0, 0, 0)
_YELLOW = (0, 200, 255)


def seconds_to_ts(seconds: float) -> str:
    """Convert fractional seconds → 'HH:MM:SS' string."""
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def preprocess_frame(
    frame: np.ndarray,
    *,
    target_width: int = INFERENCE_WIDTH,
    add_noise: bool = False,
    blur_strength: int = 0,
    low_res: bool = False,
) -> np.ndarray:
    """
    Resize frame so the long edge equals `target_width`, preserving AR.
    Optionally simulate CCTV conditions (low-res pixelation, Gaussian noise, blur).
    """
    h, w = frame.shape[:2]
    if w == 0 or h == 0:
        return frame

    # Resize
    scale = target_width / max(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    # Low-res pixelation (CCTV sim)
    if low_res:
        small = cv2.resize(resized, (new_w // 4, new_h // 4), interpolation=cv2.INTER_NEAREST)
        resized = cv2.resize(small, (new_w, new_h), interpolation=cv2.INTER_NEAREST)

    # Gaussian blur
    if blur_strength > 0:
        k = blur_strength if blur_strength % 2 == 1 else blur_strength + 1
        resized = cv2.GaussianBlur(resized, (k, k), 0)

    # Additive Gaussian noise
    if add_noise:
        noise = np.random.normal(0, 15, resized.shape).astype(np.int16)
        resized = np.clip(resized.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    return resized


def frames_to_video(
    frames: list[np.ndarray],
    fps: float,
    output_path: str,
) -> None:
    """
    Write a list of BGR frames to an H.264-encoded MP4 output file.

    Args:
        frames:      List of annotated BGR frames (all same shape).
        fps:         Frames per second of the output video.
        output_path: Absolute path for the output file.

    Note:
        Uses imageio's ffmpeg backend (imageio-ffmpeg ships a portable,
        static ffmpeg binary — no system install needed) to encode real
        H.264, not cv2.VideoWriter's "mp4v" fourcc. mp4v produces an .mp4
        container browsers can't actually play — they expect H.264/VP9,
        and OpenCV's own H.264 encoder isn't reliably available across
        platforms (fails outright on this project's Windows dev machine).
    """
    if not frames:
        raise ValueError("No frames to write.")

    writer = imageio.get_writer(
        output_path,
        fps=fps,
        codec="libx264",
        pixelformat="yuv420p",
        macro_block_size=1,  # preserve exact frame dimensions, no auto-padding
    )
    try:
        for f in frames:
            writer.append_data(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
    finally:
        writer.close()


def draw_timestamp(frame: np.ndarray, timestamp: str) -> None:
    """
    Burn a timestamp string into the bottom-left corner of the frame (in-place).

    Args:
        frame:     BGR frame to annotate.
        timestamp: String like '00:01:23'.
    """
    h = frame.shape[0]
    cv2.putText(
        frame,
        timestamp,
        (10, h - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (200, 200, 200),
        1,
        cv2.LINE_AA,
    )


def draw_status_overlay(
    frame: np.ndarray,
    *,
    confirmed: bool,
    fps: float = 0.0,
    avg_confidence: float = 0.0,
    positive_frames: int = 0,
    window_size: int = 0,
) -> None:
    """
    Draw a surveillance-style HUD in the top-left corner of the frame (in-place).

    Shows:
      • SAFE ●  or  ⚠ THREAT CONFIRMED  status banner
      • FPS counter
      • Confidence bar + percentage
      • Frame-window indicator  e.g.  [3/5 frames]

    Args:
        frame:          BGR frame to annotate.
        confirmed:      Whether weapon is confirmed by multi-frame logic.
        fps:            Current frames-per-second (0 to hide).
        avg_confidence: Smoothed confidence value 0-1.
        positive_frames: Positive frames count in current window.
        window_size:     Total window size.
    """
    overlay = frame.copy()
    panel_h = 80
    panel_w = 280
    # Semi-transparent dark panel
    cv2.rectangle(overlay, (0, 0), (panel_w, panel_h), _BLACK, cv2.FILLED)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    if confirmed:
        status_text = "!! THREAT CONFIRMED"
        status_colour = _RED
    else:
        status_text = "SCANNING..."
        status_colour = _GREEN

    # Status text
    cv2.putText(frame, status_text, (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, status_colour, 2, cv2.LINE_AA)

    # Status dot
    dot_x = 8 + cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)[0][0] + 6
    cv2.circle(frame, (dot_x, 16), 5, status_colour, cv2.FILLED)

    # FPS
    if fps > 0:
        cv2.putText(frame, f"FPS: {fps:.1f}", (8, 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, _WHITE, 1, cv2.LINE_AA)

    # Confidence bar
    if avg_confidence > 0:
        conf_pct = int(avg_confidence * 100)
        bar_w = 180
        bar_x, bar_y = 8, 52
        # Background track
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + 10), (60, 60, 60), cv2.FILLED)
        # Fill
        fill_w = int(bar_w * avg_confidence)
        bar_colour = _RED if confirmed else (_YELLOW if avg_confidence > 0.35 else _GREEN)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill_w, bar_y + 10), bar_colour, cv2.FILLED)
        cv2.putText(frame, f"Conf: {conf_pct}%", (bar_x + bar_w + 6, bar_y + 9),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, _WHITE, 1, cv2.LINE_AA)

    # Window indicator
    if window_size > 0:
        cv2.putText(frame, f"[{positive_frames}/{window_size} frames]", (8, 72),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 180, 180), 1, cv2.LINE_AA)
