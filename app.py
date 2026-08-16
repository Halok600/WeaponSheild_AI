"""
Weapon Detection - Gradio App for Hugging Face Spaces
Model: YOLOv8  |  Framework: Ultralytics
Twilio SMS alerts with mock fallback + 60-second rate limiting
"""

import os
import time
import threading

# Disable Gradio 6's Node.js SSR — set BEFORE importing gradio
os.environ.setdefault("GRADIO_SSR_MODE", "False")

import gradio as gr
from ultralytics import YOLO
from PIL import Image
import numpy as np
import cv2

# ─────────────────────────────────────────────────────────────────
# 1. Load model ONCE at startup (cached globally)
# ─────────────────────────────────────────────────────────────────
MODEL_PATH = "model/best.pt"   # path relative to project root
model = YOLO(MODEL_PATH)

# ─────────────────────────────────────────────────────────────────
# 2. Twilio configuration — reads from environment variables
#    Locally: set these in your terminal before running, e.g.:
#      $env:ACCOUNT_SID="ACxxxx"   (PowerShell)
#    On HF Spaces: set via Settings → Variables and Secrets
# ─────────────────────────────────────────────────────────────────
TWILIO_SID   = os.environ.get("ACCOUNT_SID")
TWILIO_TOKEN = os.environ.get("AUTH_TOKEN")
TWILIO_FROM  = os.environ.get("FROM_PHONE_NUMBER")
TWILIO_TO    = os.environ.get("TO_PHONE_NUMBER")

TWILIO_ENABLED = all([TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM, TWILIO_TO])

if TWILIO_ENABLED:
    from twilio.rest import Client as TwilioClient
    twilio_client = TwilioClient(TWILIO_SID, TWILIO_TOKEN)
    print("[Twilio] ✅ SMS alerts active.")
else:
    twilio_client = None
    print("[Twilio] ⚠️  Keys not found — running in mock/demo mode.")

# ─────────────────────────────────────────────────────────────────
# 3. Rate limiter — at most 1 SMS per COOLDOWN_SECONDS
# ─────────────────────────────────────────────────────────────────
COOLDOWN_SECONDS = 60
_sms_lock        = threading.Lock()
_last_sms_time   = 0.0


def send_sms_alert(detection_count: int, labels: list) -> str:
    """
    Send (or simulate) an SMS alert.
    Returns a status string shown in the Gradio UI.
    """
    global _last_sms_time

    label_str = ", ".join(set(labels))

    # ── Mock mode (no secrets configured) ───────────────────────
    if not TWILIO_ENABLED:
        return (
            "🚨 **Weapon Detected:** Twilio SMS simulated "
            "(API keys not provided)."
        )

    # ── Rate-limit check ─────────────────────────────────────────
    with _sms_lock:
        now     = time.time()
        elapsed = now - _last_sms_time

        if elapsed < COOLDOWN_SECONDS:
            remaining = int(COOLDOWN_SECONDS - elapsed)
            return (
                f"🚨 **Weapon Detected** | SMS suppressed — "
                f"cooldown active ({remaining}s remaining)."
            )

        # Cooldown passed → send real SMS
        try:
            twilio_client.messages.create(
                body=(
                    f"🚨 WEAPON ALERT: {detection_count} weapon(s) detected "
                    f"[{label_str}]. Check your dashboard immediately."
                ),
                from_=TWILIO_FROM,
                to=TWILIO_TO,
            )
            _last_sms_time = now
            return f"📱 **SMS sent** to {TWILIO_TO} — {detection_count} weapon(s): {label_str}"

        except Exception as exc:
            return f"⚠️ **SMS failed:** {exc}"


# ─────────────────────────────────────────────────────────────────
# 4. Inference + alert pipeline
# ─────────────────────────────────────────────────────────────────
def detect_weapons(image: Image.Image, conf_threshold: float = 0.25):
    """
    Run YOLOv8 inference on a PIL image.
    Returns: annotated image, detection summary, SMS status.
    """
    if image is None:
        return None, "⚠️ Please upload an image.", ""

    img_array = np.array(image)

    results = model.predict(
        source=img_array,
        conf=conf_threshold,
        save=False,
        verbose=False,
    )

    result     = results[0]
    detections = result.boxes

    # ── No detections ────────────────────────────────────────────
    if detections is None or len(detections) == 0:
        annotated     = result.plot()
        annotated_pil = Image.fromarray(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB))
        return annotated_pil, "✅ No weapons detected.", ""

    # ── Detections found ─────────────────────────────────────────
    labels = []
    lines  = [f"🔍 **{len(detections)} detection(s) found:**\n"]

    for box in detections:
        cls_id          = int(box.cls[0])
        label           = model.names[cls_id]
        conf            = float(box.conf[0])
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        labels.append(label)
        lines.append(
            f"• **{label}** — confidence: `{conf:.2f}` "
            f"| bbox: `({x1}, {y1}) → ({x2}, {y2})`"
        )

    detection_summary = "\n".join(lines)

    annotated     = result.plot()
    annotated_pil = Image.fromarray(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB))

    sms_status = send_sms_alert(len(detections), labels)

    return annotated_pil, detection_summary, sms_status


# ─────────────────────────────────────────────────────────────────
# 5. Gradio UI
# ─────────────────────────────────────────────────────────────────
_mode_badge = "🟢 Live SMS" if TWILIO_ENABLED else "🟡 Demo Mode (SMS simulated)"

with gr.Blocks(title="🔫 Weapon Detection") as demo:

    gr.Markdown(
        f"""
        # 🔫 Weapon Detection System
        Upload an image and the model will highlight any detected weapons with bounding boxes.
        > **Model:** YOLOv8 custom-trained &nbsp;|&nbsp; **Framework:** Ultralytics &nbsp;|&nbsp; **Alert mode:** {_mode_badge}
        """
    )

    with gr.Row():
        with gr.Column(scale=1):
            input_image = gr.Image(
                type="pil",
                label="📤 Upload Image",
                height=400,
            )
            conf_slider = gr.Slider(
                minimum=0.10,
                maximum=0.95,
                value=0.25,
                step=0.05,
                label="Confidence Threshold",
                info="Lower = more detections; Higher = fewer but more certain",
            )
            run_btn = gr.Button("🚀 Detect Weapons", variant="primary")

        with gr.Column(scale=1):
            output_image = gr.Image(
                type="pil",
                label="📥 Annotated Output",
                height=400,
            )
            output_text = gr.Markdown(label="Detection Summary")
            sms_status  = gr.Markdown(label="📱 SMS Alert Status")

    run_btn.click(
        fn=detect_weapons,
        inputs=[input_image, conf_slider],
        outputs=[output_image, output_text, sms_status],
    )

    input_image.change(
        fn=detect_weapons,
        inputs=[input_image, conf_slider],
        outputs=[output_image, output_text, sms_status],
    )

    gr.Markdown(
        """
        ---
        ### 🔌 API Usage
        Gradio auto-generates a REST API. Send a POST request to `/api/predict`:
        ```bash
        curl -X POST http://127.0.0.1:7860/api/predict \\
             -H "Content-Type: application/json" \\
             -d '{"data": ["<base64_image_string>", 0.25]}'
        ```
        Response: `[annotated_image, detection_summary, sms_status]`
        """
    )

if __name__ == "__main__":
    demo.launch(
        theme=gr.themes.Soft(primary_hue="rose"),
        ssr_mode=False,
        inbrowser=True,   # auto-opens browser tab
    )
