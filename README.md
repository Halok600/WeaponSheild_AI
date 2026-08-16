# ⚔️WeaponShield🛡️ AI — Weapon Detection System

> **Final-Year Engineering Project** | YOLOv8 · FastAPI · React · OpenCV · Twilio

An AI-powered weapon detection system that identifies guns and knives in **uploaded CCTV videos**, **static images**, and **live webcam streams** using the YOLOv8 deep learning model.

---

## Project Structure

```
Major_II/
├── backend/               FastAPI Python backend
│   ├── main.py            App entry point
│   ├── config.py          Environment-based configuration
│   ├── .env.template      Credential template (copy → .env)
│   ├── requirements.txt
│   ├── model/
│   │   └── detector.py    YOLOv8 singleton + annotation
│   ├── routers/
│   │   ├── image.py       POST /detect/image
│   │   ├── video.py       POST /detect/video  +  GET /detect/video/{id}
│   │   └── webcam.py      GET /detect/webcam/stream  (MJPEG)
│   ├── services/
│   │   ├── alert.py       Twilio SMS with rate-limiting
│   │   └── processing.py  Frame resize, noise/blur, video writer
│   └── outputs/           Saved annotated images & videos
│
├── frontend/              React + Vite dashboard
│   └── src/
│       ├── App.jsx
│       ├── api/axiosClient.js
│       └── components/
│           ├── ImageDetection.jsx
│           ├── VideoDetection.jsx
│           ├── WebcamDetection.jsx
│           ├── DetectionLog.jsx
│           └── AlertBadge.jsx
│
├── model/                 Place fine-tuned weights here
├── dataset/               Kaggle dataset storage
├── scripts/
│   ├── download_kaggle_dataset.py
│   └── train_custom_model.py
└── outputs/               (mirror of backend/outputs for direct access)
```

---

## Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- (Optional) NVIDIA GPU + CUDA for faster inference
- (Optional) Twilio account for SMS alerts

---

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate         # Windows
# source venv/bin/activate    # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure credentials
copy .env.template .env       # Windows
# cp .env.template .env       # Linux/Mac
# Then edit .env with your Twilio credentials and model path
```

#### `.env` key settings

| Variable | Default | Description |
|---|---|---|
| `TWILIO_ACCOUNT_SID` | *(empty)* | From console.twilio.com |
| `TWILIO_AUTH_TOKEN`  | *(empty)* | From console.twilio.com |
| `TWILIO_FROM_NUMBER` | *(empty)* | Your Twilio number |
| `TWILIO_TO_NUMBER`   | *(empty)* | Alert recipient number |
| `MODEL_PATH`         | `yolov8n.pt` | Path to YOLO weights |
| `CONFIDENCE_THRESHOLD` | `0.45` | Min confidence to flag |
| `FRAME_SKIP`         | `2`    | Frames between inferences |
| `WEAPON_CLASS_IDS`   | *(empty = all)* | Comma-separated class IDs |

> **Note:** `yolov8n.pt` is auto-downloaded from Ultralytics on first run.  
> After fine-tuning, set `MODEL_PATH=../model/weapon_detector.pt`.

---

### 2. Start the Backend

```bash
# From the backend/ directory with venv active
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Visit **http://localhost:8000/docs** for the interactive Swagger UI.

---

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Visit **http://localhost:5173** to open the dashboard.

---

## Testing All 3 Modes

### Mode 1 — CCTV Video Detection (Main Mode)
1. Open the **CCTV Video** tab
2. Upload any `.mp4` / `.avi` file
3. (Optional) Toggle "Stop on first detection" or adjust frame skip
4. Click **▶ Start Detection**
5. Watch the progress bar update live as frames are processed
6. Once complete, the output video plays inline and the detection timeline appears below

### Mode 2 — Image Detection
1. Open the **Image** tab
2. Drag & drop or click to upload a JPEG/PNG/WebP image
3. Click **🔍 Detect Weapons**
4. The annotated output image appears side-by-side with bounding boxes, labels, and confidence scores

### Mode 3 — Live Webcam
1. Open the **Live Webcam** tab
2. Select camera index (0 = default webcam)
3. Click **▶ Start Live Feed**
4. The MJPEG stream from the backend appears with real-time overlays

---

## Dataset Download

```bash
# Install kaggle CLI
pip install kaggle

# Place kaggle.json from https://www.kaggle.com/settings → API
# Windows: C:\Users\<user>\.kaggle\kaggle.json
# Linux:   ~/.kaggle/kaggle.json

python scripts/download_kaggle_dataset.py --dataset "owner/dataset-name" --output dataset/
```

Recommended public datasets:
- `ultralytics/weapon-detection-6sczo`
- Search Roboflow Universe for "weapon detection" YOLO format datasets

---

## Fine-Tuning

```bash
# After dataset is downloaded and data.yaml is ready:
python scripts/train_custom_model.py \
    --data  dataset/data.yaml \
    --model yolov8n.pt \
    --epochs 50 \
    --imgsz 640

# Best weights saved to model/weapon_detector.pt
# Update backend/.env: MODEL_PATH=../model/weapon_detector.pt
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/health` | Backend health + model status |
| `POST` | `/detect/image` | Upload image → annotated result |
| `POST` | `/detect/video` | Upload video → start async job |
| `GET`  | `/detect/video/{job_id}` | Poll job status / get result |
| `GET`  | `/detect/webcam/stream` | MJPEG webcam stream |
| `GET`  | `/detect/webcam/status` | Current FPS + detections JSON |
| `POST` | `/detect/webcam/stop` | Stop webcam capture thread |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| ML Model | YOLOv8 (Ultralytics) |
| Backend | Python 3.10, FastAPI, Uvicorn |
| CV       | OpenCV (opencv-python-headless) |
| Alerts   | Twilio REST API |
| Frontend | React 18, Vite 5, Axios |
| Styling  | Vanilla CSS (dark glassmorphism) |

---

## Performance Tips

- Use `yolov8s.pt` (small) or `yolov8m.pt` (medium) for better accuracy at the cost of speed
- Enable GPU by setting `DEVICE=0` in env / `--device 0` in training
- Increase `FRAME_SKIP` (e.g. 4–8) to speed up long CCTV video processing
- Lower `CONFIDENCE_THRESHOLD` to catch more detections (more false positives)

---

*Built for academic demonstration. For production deployment, add authentication, secure CORS, and rate-limiting.*
