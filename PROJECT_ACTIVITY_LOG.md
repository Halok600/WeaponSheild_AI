# WeaponShield AI — Project Activity Log
# Raw dev log. Not a report. Written for internal reference / future report conversion.
# Last updated: 2026-04-28

---

## PROJECT OVERVIEW

- **Name:** WeaponShield AI — Real-Time Weapon Detection System
- **Type:** Final-year engineering major project (Major II)
- **Objective:** Build an end-to-end AI system that detects weapons (guns/firearms) in three modes:
  1. Static image upload
  2. Pre-recorded CCTV/surveillance video
  3. Live webcam feed
- **Alert system:** On confirmed weapon detection, send an SMS alert via Twilio
- **Stack decided:** YOLOv8 (object detection) + FastAPI (backend) + React/Vite (frontend)
- **Hardware:** Windows PC with NVIDIA GeForce RTX 3050 6GB Laptop GPU

---

## PHASE 1 — INITIAL SYSTEM DESIGN & SETUP

### Project structure decided
```
Major_II/
├── backend/          ← FastAPI server
├── frontend/         ← React/Vite dashboard
├── model/            ← trained .pt weights stored here
├── dataset/          ← raw weapon dataset
├── dataset_combined/ ← merged weapon + background dataset
├── scripts/          ← dataset download, preparation, training scripts
├── runs/             ← YOLO training output (auto-generated)
└── outputs/          ← annotated images/videos served to frontend
```

### Backend environment setup
- Python 3.10 used (already installed)
- Created virtual environment: `python -m venv venv`
- Activated via `venv\Scripts\activate`
- Installed dependencies:
  ```
  fastapi==0.111.0
  uvicorn[standard]==0.29.0
  python-multipart==0.0.9
  python-dotenv==1.0.1
  opencv-python-headless==4.9.0.80
  ultralytics==8.2.18
  Pillow==10.3.0
  numpy==1.26.4
  twilio==9.0.5
  aiofiles==23.2.1
  httpx==0.27.0
  ```
- Saved to `backend/requirements.txt`

### Frontend setup
- Scaffolded with Vite + React: `npm create vite@latest frontend -- --template react`
- Installed deps: `npm install`
- Key packages: `axios ^1.15.1`, `react ^19.2.4`, `react-dom ^19.2.4`
- Dev server runs on `http://localhost:5173`

### Config / .env setup
- Created `backend/.env` and `backend/.env.template`
- Environment variables defined:
  - `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER` / `TWILIO_TO_NUMBER`
  - `MODEL_PATH=../model/best.pt`
  - `CONFIDENCE_THRESHOLD` (video mode)
  - `IMAGE_CONFIDENCE_THRESHOLD`
  - `WEBCAM_CONFIDENCE_THRESHOLD`
  - `WEAPON_CLASS_IDS=0`
  - `FRAME_WINDOW=10`
  - `DETECTION_COUNT_THRESHOLD=3`
  - `STOP_ON_DETECTION=false`
  - `FRAME_SKIP=0`
  - `INFERENCE_WIDTH=640`
  - `OUTPUTS_DIR=outputs`

- Created `backend/config.py` to centralise all env reads with fallback defaults
- Model path has a fallback chain: `MODEL_PATH env var → model/best.pt → yolov8n.pt (auto-download)`

---

## PHASE 2 — DATASET HANDLING

### Source 1: Kaggle weapon dataset
- Script: `scripts/download_kaggle_dataset.py`
- Required Kaggle API credentials (`~/.kaggle/kaggle.json`)
- Downloaded a weapon image dataset with YOLO-format labels
- Dataset structure after download: `dataset/images/train/`, `dataset/images/val/`, `dataset/labels/train/`, `dataset/labels/val/`
- Multiple weapon classes present: Pistol, Rifle, Knife (3 classes)
- Class IDs varied across sources — normalisation needed

### Source 2: Roboflow dataset
- Script: `scripts/download_roboflow_dataset.py`
- Downloaded via Roboflow API
- Layout was "split-first" (Roboflow standard): `train/images/`, `valid/images/`, `test/images/`
- Used "valid" folder name — had to map → "val" in scripts
- Dataset saved to `dataset_roboflow/`

### Problem: Class ID inconsistency
- Kaggle dataset had class IDs 0,1,2 (Pistol, Rifle, Knife)
- Roboflow dataset had different class ordering
- Decision: normalise ALL weapon types to a single class (class 0 = "weapon") for simplicity
- This was done in `prepare_dataset.py` by writing single-class data.yaml with `nc: 1`

### Background negatives (COCO val2017)
- Problem discovered: training only on weapon images → massive false positives on normal scenes
- Solution: add background-only (no weapon) images to teach the model what is NOT a weapon
- Downloaded COCO val2017 dataset: `http://images.cocodataset.org/zips/val2017.zip` (~800 MB)
- Extracted to `val2017/` folder at project root
- COCO images contain everyday objects, people, rooms — no weapons

### Dataset preparation script: `scripts/prepare_dataset.py`
- Merges weapon positives + COCO negatives into a single YOLO dataset
- Auto-detects dataset layout (Roboflow split-first vs Kaggle images-first)
- Split ratios: train=80%, val=15%, test=5%
- Background images: randomly sampled, assigned empty label files (= no detection)
- Output: `dataset_combined/` with proper YOLO structure + `data.yaml`
- Default: 1000 background images (configurable with `--n-negatives`)
- Usage: `python scripts/prepare_dataset.py --bg-dir D:/val2017 --n-negatives 1000`

### Final combined dataset stats (approximate)
- Weapon positive images: ~7000+ (from Kaggle + Roboflow)
- Background negative images: 1000 (from COCO val2017)
- Negative ratio: ~12-15%  (noted as lower than ideal 40%, but balance between training time and accuracy)

---

## PHASE 3 — MODEL DEVELOPMENT

### Algorithm chosen: YOLOv8
- Reasons:
  - State-of-the-art real-time object detector
  - Excellent community support via `ultralytics` library
  - GPU acceleration via PyTorch/CUDA
  - Easy to fine-tune on custom data
  - Supports export to various formats if needed

### Base model chosen: `yolov8s.pt` (small)
- Nano (`yolov8n.pt`) also tested but had lower accuracy
- Small (`yolov8s.pt`) gave better mAP with acceptable speed on RTX 3050

### Attempt 1 — Roboflow pre-trained model (HuggingFace)
- Pulled `Subh775/Firearm_Detection_Yolov8n` from HuggingFace
- Claimed 89% mAP@0.5, trained on 7000+ diverse real-world firearm images
- Saved as `model/best.pt`
- **Problem found:** model performed well on clean/cropped weapon photos (up to 92% confidence) but dropped to 1-3% confidence on real CCTV/surveillance video frames
- Root cause: domain gap — training images were clean studio-style, deployment was noisy/compressed video
- This was identified as the main bottleneck

### Attempt 2 — Custom training on combined dataset
- Script: `scripts/train_custom_model.py`
- Training parameters:
  ```
  Base model:  yolov8s.pt
  Epochs:      80
  Image size:  640×640
  Batch size:  8 (tuned for 6GB VRAM)
  Device:      GPU 0 (NVIDIA RTX 3050 6GB)
  Patience:    20 (early stopping)
  LR schedule: cosine (cos_lr=True)
  Augmentation: enabled (augment=True)
  Workers:     4
  ```
- Training output saved to `runs/detect/weapon_detector/`
- Best weights automatically copied to `model/best.pt` after training
- Training took several hours on RTX 3050

### Training metrics (final epoch)
- Precision, Recall, mAP@0.5 tracked via ultralytics built-in logging
- Plots saved to `runs/detect/weapon_detector/` (confusion matrix, PR curve, F1 curve)

### Problem — torch.load compatibility issue
- PyTorch >=2.6 changed default `weights_only=True` in `torch.load`
- YOLOv8 `.pt` files contain Python objects (not just tensors), require `weights_only=False`
- Fix: patched `torch.load` temporarily at model load time in `detector.py`:
  ```python
  @functools.wraps(_original_torch_load)
  def _patched_torch_load(f, *args, **kwargs):
      kwargs.setdefault("weights_only", False)
      return _original_torch_load(f, *args, **kwargs)
  torch.load = _patched_torch_load
  self.model = YOLO(MODEL_PATH)
  # restore original after loading
  torch.load = _original_torch_load
  ```

### Problem — Pydantic DLL import error (Windows)
- Windows Application Control policy blocked `pydantic_core` DLL
- Error: `ImportError: DLL load failed while importing pydantic_core`
- Fix: re-installed pydantic in venv, confirmed binary was signed/trusted by system
- Backend worked after fix

### Problem — YOLO conf parameter not filtering correctly
- Discovered that the custom `best.pt` model was returning low-confidence boxes even when `conf=0.75` was passed to YOLO
- YOLO's internal `conf` parameter wasn't reliably enforced by these custom weights
- Fix: added explicit **hard post-inference filter** inside `detector.py`:
  ```python
  threshold = conf if conf is not None else CONFIDENCE_THRESHOLD
  results = self.model(frame, conf=threshold, verbose=False)[0]
  for box in results.boxes:
      box_conf = float(box.conf[0])
      if box_conf < threshold:   # ← explicit reject
          continue
      # ... append to detections
  ```

---

## PHASE 4 — BACKEND DEVELOPMENT

### Framework: FastAPI
- Why: async support, automatic OpenAPI docs, clean routing, fast

### Entry point: `backend/main.py`
- App created with lifespan context manager
- Model loaded once at startup via `detector.load()` — singleton pattern
- CORS middleware: allow all origins during development
- Static files mounted at `/outputs` to serve annotated images/videos
- Routers registered: image, video, webcam
- Health endpoint: `GET /health` → returns `{status, model_loaded, model_path}`

### `backend/model/detector.py` — WeaponDetector singleton
- Singleton pattern: `__new__` checks `_instance` before creating
- `load()`: initialises YOLO model, detects GPU, patches torch.load
- `detect(frame, conf)`: runs inference, applies class filter, applies hard conf filter
- `annotate(frame, detections)`: draws bounding boxes + confidence labels on frame copy
- GPU auto-detected via `torch.cuda.is_available()`
- Class filter: `WEAPON_CLASS_IDS` from env (empty = treat all detections as weapons)

### `backend/config.py`
- Reads all env vars with typed defaults
- Model path fallback chain resolved here
- Per-mode confidence thresholds: `CONFIDENCE_THRESHOLD` (video), `IMAGE_CONFIDENCE_THRESHOLD`, `WEBCAM_CONFIDENCE_THRESHOLD`
- Frame window and confirmation count configurable

### `backend/services/frame_buffer.py` — Multi-frame confirmation
- Purpose: prevent false positives by requiring weapon to appear in K-of-N consecutive frames
- Uses a sliding deque of frame snapshots
- Decay counter (not hard reset): increments on positive frames, decrements by 1 on negative frames
  - This prevents a single missed frame from killing the running count
- `is_weapon_confirmed()`: checks decay count ≥ threshold OR positive frames in window ≥ threshold
- `get_smoothed_detections()`: returns detections from most recent positive frame (reduces flicker)
- `get_avg_confidence()`: average confidence across all positive frames in window
- Thread-safe via `threading.Lock`
- `reset()`: clears buffer + decay counter (called at start of each new job/session)

### `backend/services/alert.py` — Twilio SMS alerting
- Lazy import of `twilio` — app boots even if package missing
- `send_weapon_alert()`: convenience wrapper, builds formatted SMS message
  - Format: `"⚠️ Gun detected at 00:01:23 with confidence 87% — WeaponShield AI Surveillance System"`
- `send_alert()`: core dispatcher with:
  - Cooldown guard: 60 seconds between alerts per session (prevents SMS flooding)
  - Event deduplication via MD5 hash of `session_id|label|timestamp` — same event won't fire twice
  - Graceful degradation: if Twilio not configured, logs to console, doesn't crash
- `reset_cooldown()`: called at start of each new upload job
- Per-session rate limiting: `{session_id: last_alert_time}` dict

### `backend/services/processing.py` — Frame preprocessing
- `preprocess_frame()`: resize, optional Gaussian noise, optional blur, optional pixelate (low-res sim)
- `draw_status_overlay()`: draws SAFE/THREAT CONFIRMED banner + FPS + confidence + window counter on frame
- `draw_timestamp()`: overlays timestamp on video frames
- `frames_to_video()`: writes list of annotated frames to MP4 output file using OpenCV VideoWriter
- `seconds_to_ts()`: converts float seconds → "HH:MM:SS" string

### `backend/routers/image.py` — POST /detect/image
- Accepts JPEG/PNG/BMP/WebP upload
- Validates content-type, decodes with OpenCV
- Runs `preprocess_frame()` → `detector.detect()` with `IMAGE_CONFIDENCE_THRESHOLD`
- Double-filter: image router also does `[d for d in detections if d.confidence >= IMAGE_CONFIDENCE_THRESHOLD]` after detect()
- Saves annotated image to `outputs/image_{job_id}.jpg`
- Fires Twilio alert if weapon detected
- Returns: `{job_id, output_url, detections, detected_classes, max_confidence, weapon_detected, alert}`

### `backend/routers/video.py` — POST /detect/video + GET /detect/video/{job_id}
- Upload video → save temp file → start background processing task → return `job_id`
- Frontend polls `GET /detect/video/{job_id}` every 1.5 seconds for progress
- Background task `_process_video()`:
  - Reads video with OpenCV `VideoCapture`
  - Loops frame-by-frame
  - Frame skip: only infers on every Nth frame (default 0 = every frame)
    - IMPORTANT: skipped frames do NOT push to FrameBuffer — only inferred frames do
    - (Bug fix: original code was pushing empty results for skipped frames, resetting decay counter)
  - Each inferred frame: `preprocess_frame()` → `detector.detect(conf=conf_threshold)` → `buf.push(dets)`
  - Checks `buf.is_weapon_confirmed()` each frame
  - Logs all detections to `detection_log` list with frame, timestamp, confidence, bbox, confirmed flag
  - Fires Twilio alert on first multi-frame confirmation
  - If `stop_on_detection=True`: breaks loop immediately after first confirmation
  - Writes annotated frames to output video via `frames_to_video()`
  - Job state dict updated progressively in `_jobs[job_id]`
- In-memory job store: `_jobs: dict[str, dict]` (no persistence)
- Job states: queued → processing → done | error

### `backend/routers/webcam.py` — GET /detect/webcam/stream + /status + POST /stop
- MJPEG streaming endpoint — browser points `<img src>` at `/detect/webcam/stream`
- Starts background capture thread via `_start_camera()`
- Thread runs `_capture_loop()`:
  - Opens webcam with `cv2.VideoCapture(0, cv2.CAP_DSHOW)` (Windows DirectShow)
  - Resolution set to 640×480
  - Per-frame: infer → push to FrameBuffer → annotate → encode JPEG → update shared state
  - HUD overlay: SAFE / THREAT CONFIRMED banner, FPS, confidence, window indicator
  - Alert fires on first multi-frame confirmation, re-arms after window fully clears
- `GET /detect/webcam/status` polls current state: `{running, fps, detections, threat_confirmed, avg_confidence, positive_frames, window_size, status_label}`
- `POST /detect/webcam/stop` sets stop event → thread exits gracefully
- Thread-safe shared state via `threading.Lock`
- Webcam window: 10 frames, needs 4 positive frames to confirm

---

## PHASE 5 — FRONTEND DEVELOPMENT

### Framework: React 19 + Vite 8
- Why: fast dev server, HMR, component-based UI, minimal setup
- No CSS framework — pure vanilla CSS in `src/index.css`
- Dark theme, glassmorphism cards, red accent colour scheme
- Google Fonts not used (system fonts for speed)

### `frontend/src/api/axiosClient.js`
- Axios instance with `baseURL = http://localhost:8000`
- All API calls go through this instance

### `frontend/src/App.jsx`
- Tab-based navigation: Image / Video / Webcam
- Three detection mode components rendered conditionally

### `frontend/src/components/ImageDetection.jsx`
- Drag-and-drop + click-to-browse image upload
- Sends `multipart/form-data` POST to `/detect/image`
- Displays annotated output image inline
- Shows detection table: label, confidence bar, bounding box
- Confidence threshold fixed to `IMAGE_CONFIDENCE_THRESHOLD` on backend (60%)

### `frontend/src/components/VideoDetection.jsx`
- Drag-and-drop + click-to-browse video upload (MP4/AVI/MOV/MKV)
- Processing options:
  - Stop on first detection (checkbox)
  - CCTV noise simulation (checkbox)
  - Low-res pixelate (checkbox)
  - Frame skip slider (0–10)
  - Blur strength slider (0–21px)
  - Confidence threshold slider (1–90%)
- All options sent as `FormData` fields on upload
- Polls job status every 1500ms via `GET /detect/video/{job_id}`
- Shows live progress bar (processed frames / total frames)
- On completion: plays annotated video, shows stats (total frames, detections, SMS alert status)
- Detection timeline table: timestamp, frame number, label badge, confidence bar
- CSV export button on timeline table
- Confidence threshold state management fixes (iterative):
  - Original bug: default was 5%, slider moved AFTER job submit didn't affect already-running job
  - Fix 1: raised default to 15%, added "last run: X%" label next to slider
  - Fix 2: added yellow warning banner if slider changed after job completes: "⚡ Threshold changed — click Start Detection to re-run with X%"
  - Fix 3: threshold snapshotted at submit time (`submittedConf = confThreshold`) — prevents race condition

### `frontend/src/components/WebcamDetection.jsx`
- Starts webcam stream by pointing `<img src>` to `/detect/webcam/stream` (MJPEG)
- Polls `/detect/webcam/status` every 1000ms
- Displays: FPS counter, threat confirmed status, confidence, frame window progress
- Stop button calls `POST /detect/webcam/stop`
- Alert badge shown when threat confirmed

### `frontend/src/components/AlertBadge.jsx`
- Reusable component — red pulsing badge shown when `active=true`

### `frontend/src/components/DetectionLog.jsx`
- Reusable table component used in video and image modes
- Shows timestamp, frame, label, confidence bar, confirmed status
- Supports CSV download

---

## PHASE 6 — INTEGRATION

### Frontend → Backend communication
- All requests go via Axios to `http://localhost:8000`
- CORS: backend allows all origins (`allow_origins=["*"]`) during dev
- Video upload: `multipart/form-data` POST with file + options as form fields
- Image upload: `multipart/form-data` POST with file
- Webcam stream: native browser `<img>` tag pointing at MJPEG stream endpoint
- Webcam status: Axios GET polling every 1 second

### Outputs served as static files
- FastAPI mounts `outputs/` directory at `/outputs`
- Frontend requests annotated images/videos via relative URL (`/outputs/image_xxx.jpg`)
- No separate file server needed

### Model → Backend integration
- `WeaponDetector` singleton loaded once at FastAPI lifespan startup
- All three routers import and use the same `detector` instance
- No model reloading needed between requests

---

## PHASE 7 — BUGS & FIXES (chronological)

### Bug 1 — NameError: logger not defined in video.py
- `video.py` referenced `logger` without importing `logging`
- Fix: added `import logging` and `logger = logging.getLogger(__name__)` at top of file

### Bug 2 — Skipped frames emptying FrameBuffer (video mode)
- In the original loop: skipped frames were pushing empty `[]` to `buf.push()`
- This decremented the decay counter on every skipped frame → weapon confirmation never reached threshold
- Fix: moved `buf.push(dets)` inside the `if should_infer:` block — only inferred frames update the buffer

### Bug 3 — Variable shadowing in detector.py
- Loop variable `conf` inside `detect()` shadowed the function argument `conf`
- Fix: renamed loop variable to `box_conf`

### Bug 4 — stop_on_first vs stop_on_detection naming mismatch
- Frontend was sending `stop_on_first` in FormData
- Backend expected `stop_on_detection`
- Fix: renamed frontend form field to `stop_on_detection`

### Bug 5 — False positives in webcam mode
- System was confirming threats with just 2 of 5 frames, and at very low confidence (1%)
- A tablet/phone on a desk was triggering "THREAT CONFIRMED"
- Root cause: all modes shared the same 1% threshold set for video mode
- Fix: introduced separate thresholds per mode:
  - `CONFIDENCE_THRESHOLD=0.01` — video only (low threshold, multi-frame confirmation prevents FP)
  - `IMAGE_CONFIDENCE_THRESHOLD=0.60` — single-shot, needs high precision
  - `WEBCAM_CONFIDENCE_THRESHOLD=0.25` (later raised to 0.55) — live feed, balanced
  - Webcam window changed to 10 frames, 4 needed to confirm (was 5/2)

### Bug 6 — Confidence slider appearing to not work (video mode)
- User set slider to 81% but still saw detections at 46%
- Root cause: those results were from a previous job submitted at 5% (the old default)
  - Slider was moved AFTER the job was already complete — no effect on past results
- Fixes applied:
  - Default threshold raised from 5% → 15% (matches hint text)
  - Threshold snapshotted at submit time (not read at render time)
  - "Last run: X%" label shows what threshold was actually used
  - Yellow warning banner appears if slider changed after job done

### Bug 7 — YOLO conf parameter not filtering custom model (most critical)
- After fixing Bug 6, user re-ran at 75% but detections at 27% still appeared
- "LAST RUN: 75%" confirmed threshold was correctly sent to backend
- Root cause: custom `best.pt` weights bypass YOLO's built-in `conf` filtering — returns low-confidence boxes regardless
- Fix: added explicit hard post-inference filter in `detector.py`:
  ```python
  if box_conf < threshold:
      continue
  ```
  This guarantees the threshold is enforced regardless of model behaviour

### Bug 8 — Port 8000 conflict on backend restart
- Old backend process still holding port 8000 when trying to restart
- Fix command:
  ```powershell
  Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000 | Select-Object -ExpandProperty OwningProcess) -Force
  ```

---

## PHASE 8 — CONFIGURATION ITERATIONS

### Threshold evolution (video mode)
- Started at: `CONFIDENCE_THRESHOLD=0.35` (too high — zero detections on surveillance footage)
- Lowered to: `0.05` → still some domain gap issues
- Further lowered to: `0.01` — kept low intentionally because multi-frame confirmation prevents FPs
- `DETECTION_COUNT_THRESHOLD`: started at 3, lowered to 1 during debugging, back to 3 after multi-frame logic was fixed

### Frame window evolution
- Started: `FRAME_WINDOW=5`, `DETECTION_COUNT_THRESHOLD=2`
- Webcam false positive issue → changed webcam to: `FRAME_WINDOW=10`, `DETECTION_COUNT_THRESHOLD=4`
- Video kept at: `FRAME_WINDOW=10`, `DETECTION_COUNT_THRESHOLD=3`

### Frame skip
- `FRAME_SKIP=2` initially (process every 3rd frame for speed)
- Changed to `FRAME_SKIP=0` for accuracy — every frame processed
- Frame skip bug (Bug 2) made this critical — skipping was killing detection regardless

---

## TECHNOLOGIES USED

### Languages
- Python 3.10 (backend, scripts)
- JavaScript/JSX (frontend — React)

### Backend libraries
- FastAPI 0.111.0 — web framework
- Uvicorn 0.29.0 — ASGI server
- OpenCV (opencv-python-headless 4.9.0.80) — video/image processing
- Ultralytics 8.2.18 — YOLOv8 model loading and inference
- PyTorch (via ultralytics dependency) — deep learning runtime
- CUDA — GPU acceleration (RTX 3050)
- Twilio 9.0.5 — SMS alerts
- python-dotenv — env config loading
- numpy 1.26.4 — array ops

### Frontend libraries
- React 19.2.4
- Vite 8.0.4 — build tool / dev server
- Axios 1.15.1 — HTTP client

### Tools / Platforms
- Kaggle API — dataset download
- Roboflow — dataset download + format
- HuggingFace Hub — pre-trained model source (`Subh775/Firearm_Detection_Yolov8n`)
- COCO dataset (val2017) — background negative images
- Twilio Console — SMS API credentials
- Windows PowerShell — dev environment
- NVIDIA RTX 3050 6GB — GPU training + inference

---

## CURRENT STATUS (as of 2026-04-28)

### What is working
- ✅ Backend API running on `http://localhost:8000`
- ✅ GPU inference active (RTX 3050)
- ✅ `GET /health` returns `{status: ok, model_loaded: true}`
- ✅ Image detection: upload image → get annotated result with bounding boxes
- ✅ Video detection: upload video → background processing → progress polling → annotated output video
- ✅ Webcam detection: MJPEG stream → live annotations → multi-frame threat confirmation
- ✅ Multi-frame confirmation logic working (FrameBuffer with decay)
- ✅ Twilio SMS alert fires on first multi-frame confirmation (rate-limited)
- ✅ Confidence threshold slider on video page — properly sent to backend, hard-filtered in detector
- ✅ Detection timeline with CSV export
- ✅ Per-mode confidence thresholds (video/image/webcam all independent)
- ✅ Frontend HMR running (`npm run dev` on port 5173)

### What is not fully working / known issues
- ⚠️ Model accuracy on real surveillance footage still limited — the custom trained model shows lower confidence than expected on low-quality CCTV frames (domain gap partially mitigated by low threshold + multi-frame confirmation)
- ⚠️ No persistent job storage — server restart clears all job history (in-memory only)
- ⚠️ No authentication on API — `allow_origins=["*"]` CORS is dev-only, not production safe
- ⚠️ Webcam MJPEG stream has no auth — any local network user can access it
- ⚠️ Output files (annotated videos) accumulate in `outputs/` — no automatic cleanup
- ⚠️ Frontend has no error recovery if backend goes down mid-poll
- ⚠️ Dataset negative ratio (~12%) is lower than recommended (≥40%) — may still cause some false positives

---

## FUTURE SCOPE / NEXT STEPS

- Retrain model with more negative images (increase to 3000–5000 COCO backgrounds)
- Try YOLOv8m (medium) for better accuracy at cost of some inference speed
- Add data augmentation specific to surveillance: motion blur, compression artifacts, low-light simulation
- Add user authentication (JWT or basic auth) before production deployment
- Add persistent storage for job results (SQLite or PostgreSQL)
- Add automatic cleanup job for old output files
- Deploy backend to cloud (AWS EC2 or Azure VM with GPU)
- Deploy frontend to Vercel or Netlify
- Add multi-camera support for webcam mode
- Add export to other formats (PDF report, CSV summary)
- Consider ONNX export of model for faster CPU inference on deployment targets without GPU
- Add confidence calibration (temperature scaling) to fix the low-confidence issue on custom weights

---

*End of log.*
