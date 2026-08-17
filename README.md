# WeaponShield AI — Weapon Detection System

> **Final-Year Engineering Project** | YOLOv8 · FastAPI · React · OpenCV · ONNX Runtime

An AI-powered weapon detection system that identifies and **bifurcates weapon types — Pistol, Rifle, and Knife** — in **uploaded CCTV videos**, **static images**, and **live webcam streams**, using a custom fine-tuned YOLOv8 model.

---

## Live Demo

- **Frontend:** https://weapon-sheild-ai.vercel.app
- **Backend:** currently running on a free Google Colab GPU, tunneled via ngrok

> **The live demo only works while the Colab notebook is actively running.** The backend isn't an always-on server — it's a Colab session someone has to start manually, and Colab's free tier disconnects after periods of inactivity or a fixed session length. If the frontend shows "Backend offline," it most likely means the Colab notebook isn't currently running. See [Backend Deployment Options](#backend-deployment-options) below for why, and how to spin it back up.

---

## Project Structure

```
Major_II/
├── backend/                     FastAPI Python backend
│   ├── main.py                  App entry point
│   ├── config.py                Environment-based configuration
│   ├── .env.template            Credential template (copy → .env)
│   ├── requirements.txt
│   ├── model/
│   │   └── detector.py          Dual-engine detector (PyTorch .pt / ONNX Runtime .onnx)
│   ├── routers/
│   │   ├── image.py             POST /detect/image
│   │   ├── video.py             POST /detect/video  +  GET /detect/video/{id}
│   │   └── webcam.py            POST /detect/webcam/frame  +  POST /detect/webcam/stop
│   ├── services/
│   │   ├── alert.py             Resend email alerts (fixed operator address)
│   │   ├── frame_buffer.py      Multi-frame confirmation (K-of-N sliding window)
│   │   └── processing.py        Frame resize/noise/blur, H.264 video writer
│   └── outputs/                 Saved annotated images & videos
│
├── frontend/                    React + Vite dashboard
│   └── src/
│       ├── App.jsx
│       ├── api/axiosClient.js
│       ├── hooks/useMediaBlobUrl.js   Loads output media through authenticated fetch
│       └── components/
│           ├── ImageDetection.jsx
│           ├── VideoDetection.jsx
│           ├── WebcamDetection.jsx    Browser-side capture via getUserMedia
│           ├── DetectionLog.jsx
│           └── AlertBadge.jsx
│
├── model/
│   ├── best.pt                  Fine-tuned PyTorch weights (source of truth)
│   └── best.onnx                ONNX export of the same weights (lightweight deploy target)
├── scripts/                     Dataset download/relabel/merge + training scripts
├── render.yaml                  Render Blueprint (backend, ONNX Runtime)
├── Dockerfile                   Alternative container deploy target
└── frontend/vercel.json         Vercel build config (frontend)
```

---

## The Model

A YOLOv8s model, fine-tuned in two stages:

1. **Base training** on ~31,600 images merged from two Roboflow weapon-detection datasets plus COCO background negatives (Pistol / Rifle / Knife, 80 epochs).
2. **Follow-up fine-tune** on the same data plus 559 relabeled images recovered from a local Kaggle dataset (filenames like `Knife_42.jpeg` carried a real category that a prior export had collapsed into one generic class), specifically to boost Knife — the weakest class from stage 1.

**Held-out test-set results** (never seen during training):

| Class | Precision | Recall | mAP50 | mAP50-95 |
|---|---|---|---|---|
| Pistol | 0.912 | 0.856 | 0.908 | 0.691 |
| Rifle | 0.946 | 0.913 | 0.954 | 0.744 |
| Knife | 0.783 | 0.592 | 0.636 | 0.405 |
| **Overall** | **0.881** | **0.787** | **0.833** | **0.613** |

Knife remains the hardest class — genuinely less training data is available for it across public datasets than for guns.

---

## Backend Deployment Options

The backend can run on either inference engine, auto-selected by `MODEL_PATH`'s file extension — see `backend/model/detector.py`.

| | PyTorch (`best.pt`) | ONNX Runtime (`best.onnx`) |
|---|---|---|
| **Where it's used** | Local dev, Colab (free T4 GPU) | Render (deployed) |
| **Speed/accuracy** | Full accuracy, GPU-fast | Identical accuracy (validated to match exactly), CPU-only |
| **Always-on?** | No — Colab sessions are manual and time-limited | Yes, but... |
| **Catch** | URL changes every restart, must be updated in Vercel manually | Free tier (512MB RAM) is slow and cold-starts after ~15 min idle |

Neither option is a "just works forever, free, fast" deployment — that combination doesn't exist on free infrastructure for a GPU-hungry model like this. Render is the more stable default (always reachable, just slower and occasionally needs a cold-start wait); Colab is faster and more accurate but needs a human to keep it running and to update the frontend's backend URL after every restart.

### Restarting the Colab backend

1. Open the Colab notebook, run **Cell 1** (setup — only needed once per fresh runtime) then **Cell 2** (starts the server + ngrok tunnel)
2. Cell 2 prints a new `https://xxxx.ngrok-free.app` URL each time
3. Copy that URL into Vercel → **Settings** → **Environment Variables** → `VITE_API_URL`, then **redeploy**

### Switching Vercel back to the Render backend

If Colab isn't running and you just need *something* live, point `VITE_API_URL` at the Render deployment instead (see `render.yaml` for its config) — it's slower but doesn't need to be manually started.

---

## Setup (local development)

### Prerequisites
- Python 3.10+
- Node.js 18+
- (Optional) NVIDIA GPU + CUDA for full-speed PyTorch inference
- A free [Resend](https://resend.com) account for email alerts

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate         # Windows
# source venv/bin/activate    # Linux/Mac

# Install dependencies
pip install -r requirements.txt
# For local PyTorch inference (recommended if you have a GPU), also:
pip install ultralytics

# Configure credentials
copy .env.template .env       # Windows
# cp .env.template .env       # Linux/Mac
# Then edit .env — see the key settings below
```

#### `.env` key settings

| Variable | Default | Description |
|---|---|---|
| `RESEND_API_KEY` | *(empty)* | From resend.com → API Keys |
| `RESEND_FROM_EMAIL` | `onboarding@resend.dev` | Works without a verified domain |
| `ALERT_TO_EMAIL` | *(empty)* | Fixed recipient(s) for weapon alerts — comma-separate for multiple. With the sandbox sender above, this **must** be the email that owns the Resend account, or sends get rejected with a 403 |
| `MODEL_PATH` | `../model/best.onnx` | `.pt` → PyTorch engine, `.onnx` → ONNX Runtime engine |
| `WEAPON_CLASS_IDS` | `0,1,2` | Comma-separated class IDs to treat as weapons |
| `IMAGE_CONFIDENCE_THRESHOLD` | `0.60` | Single-shot image scans — stricter, avoids false positives |
| `WEBCAM_CONFIDENCE_THRESHOLD` | `0.45` | Live feed — looser, tuned for real-world lighting/blur/compression |
| `CORS_ORIGINS` | *(empty = allow all)* | Comma-separated frontend origins in production |

### 2. Start the Backend

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Visit **http://localhost:8000/docs** for the interactive Swagger UI.

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Visit **http://localhost:5173** to open the dashboard. For pointing the local frontend at a remote backend, set `VITE_API_URL` in `frontend/.env` (see `frontend/.env.example`).

---

## Testing All 3 Modes

### Mode 1 — CCTV Video Detection
Upload an `.mp4`/`.avi`/`.mov`/`.mkv` file, optionally toggle CCTV noise/blur simulation or "stop on first detection," then start. Output plays inline with a detection timeline below once processing finishes.

### Mode 2 — Image Detection
Drag & drop or upload a JPEG/PNG/BMP/WebP image. The annotated result appears side-by-side with bounding boxes, labels, and confidence scores.

### Mode 3 — Live Webcam
Your **browser** captures frames locally via `getUserMedia` and posts them to the backend roughly twice a second — the server never touches a camera directly, which is what makes this work identically whether the backend is local, on Render, or on Colab.

---

## Dataset & Training

See `scripts/` for the full pipeline:
- `download_roboflow_dataset.py` — pulls and remaps a Roboflow weapon-detection dataset to Pistol/Rifle/Knife
- `relabel_kaggle_dataset.py` — recovers per-category labels from a Kaggle dataset's filenames
- `prepare_multiclass_dataset.py` — merges all sources + COCO negatives into the final training set
- `train_custom_model.py` — fine-tunes YOLOv8s on the merged dataset

```bash
python scripts/train_custom_model.py --data dataset_multiclass/data.yaml --model yolov8s.pt --epochs 80
```

To deploy a freshly trained model, export it to ONNX for the lightweight deploy path:

```bash
yolo export model=model/best.pt format=onnx
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/health` | Backend health + model status |
| `POST` | `/detect/image` | Upload image → annotated result |
| `POST` | `/detect/video` | Upload video → start async job |
| `GET`  | `/detect/video/{job_id}` | Poll job status / get result |
| `POST` | `/detect/webcam/frame` | Submit one browser-captured frame → detections |
| `POST` | `/detect/webcam/stop` | Clear a webcam session's state |
| `POST` | `/test-alert` | Send a test email via Resend |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| ML Model | YOLOv8s (Ultralytics), fine-tuned |
| Inference | PyTorch (local/Colab) or ONNX Runtime (deployed) |
| Backend | Python 3.10, FastAPI, Uvicorn |
| CV / Video | OpenCV, imageio + ffmpeg (H.264 encoding) |
| Alerts | Resend (transactional email) |
| Frontend | React 18, Vite, Axios |
| Hosting | Vercel (frontend), Render / Google Colab (backend) |

---

*Built for academic demonstration. For production deployment, add authentication, tighten CORS to specific origins, and move off free-tier infrastructure for anything beyond a demo.*
