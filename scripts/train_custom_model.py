#!/usr/bin/env python3
"""
train_custom_model.py
---------------------
Fine-tune YOLOv8 on a weapon detection dataset and save best weights.

Simple usage (reads dataset/data.yaml automatically):
    python scripts/train_custom_model.py

Full usage:
    python scripts/train_custom_model.py \\
        --data    dataset/data.yaml \\
        --model   yolov8s.pt \\
        --epochs  80 \\
        --imgsz   640 \\
        --batch   8 \\
        --output  model/

After training:
  • Best weights are saved to  model/best.pt
  • Update backend/.env:       MODEL_PATH=../model/best.pt
  • Restart backend:           uvicorn main:app --reload

Expected dataset/data.yaml format (YOLO standard) — 3-class Roboflow dataset:
    path:  /absolute/path/to/dataset
    train: images/train
    val:   images/valid
    test:  images/test
    nc: 3
    names: ['Pistol', 'Rifle', 'Knife']
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _detect_device() -> str:
    """Auto-detect best available compute device."""
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / 1e9
            print(f"🎮  GPU detected: {name} ({vram:.1f} GB VRAM) → using device 0")
            return "0"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            print("🍎  Apple MPS detected → using device mps")
            return "mps"
        else:
            print("🖥️   No GPU found → using CPU (training will be slow)")
            return "cpu"
    except ImportError:
        print("⚠️   PyTorch not found, defaulting to CPU.")
        return "cpu"


def _validate_data_yaml(data_yaml: str) -> None:
    """Check the data.yaml file exists and has required keys."""
    p = Path(data_yaml)
    if not p.exists():
        print(f"\n❌  data.yaml not found at: {p.resolve()}")
        print("   Run first:  python scripts/download_kaggle_dataset.py")
        sys.exit(1)

    content = p.read_text()
    required = ["train", "val", "nc", "names"]
    missing  = [k for k in required if k not in content]
    if missing:
        print(f"⚠️   data.yaml may be incomplete. Missing keys: {missing}")
    else:
        print(f"✅  data.yaml validated: {p.resolve()}")


def _print_metrics(results_dict: dict) -> None:
    """Print a formatted training metrics table."""
    metrics = {
        "Precision  (P)":  results_dict.get("metrics/precision(B)",   "N/A"),
        "Recall     (R)":  results_dict.get("metrics/recall(B)",      "N/A"),
        "mAP @ 0.50    ":  results_dict.get("metrics/mAP50(B)",       "N/A"),
        "mAP @ 0.50:0.95": results_dict.get("metrics/mAP50-95(B)",   "N/A"),
        "Box Loss      ":  results_dict.get("train/box_loss",         "N/A"),
        "Cls Loss      ":  results_dict.get("train/cls_loss",         "N/A"),
    }

    print("\n" + "═" * 44)
    print("  📊  Final Training Metrics")
    print("═" * 44)
    for name, val in metrics.items():
        if isinstance(val, float):
            print(f"  {name} :  {val:.4f}")
        else:
            print(f"  {name} :  {val}")
    print("═" * 44 + "\n")


def train(
    data_yaml:  str,
    base_model: str,
    epochs:     int,
    imgsz:      int,
    batch:      int,
    output_dir: Path,
    device:     str,
    workers:    int = 4,
    cache:      bool = False,
) -> None:
    try:
        from ultralytics import YOLO
    except ImportError:
        print("❌  ultralytics not installed. Run:  pip install ultralytics")
        sys.exit(1)

    _validate_data_yaml(data_yaml)

    if not device:
        device = _detect_device()

    print("\n" + "═" * 50)
    print("  🚀  WeaponShield AI — YOLOv8 Training")
    print("═" * 50)
    print(f"  Dataset    : {Path(data_yaml).resolve()}")
    print(f"  Base model : {base_model}")
    print(f"  Epochs     : {epochs}")
    print(f"  Image size : {imgsz}")
    print(f"  Batch size : {batch}")
    print(f"  Device     : {device}")
    print(f"  Output     : {output_dir.resolve() / 'best.pt'}")
    print("═" * 50 + "\n")

    model = YOLO(base_model)

    start = time.time()
    results = model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        project="runs/detect",
        name="weapon_detector",
        save=True,
        plots=True,
        verbose=True,
        patience=20,        # Early stopping: stop if no improvement for 20 epochs
        cos_lr=True,        # Cosine LR schedule for smoother convergence
        augment=True,       # Enable online augmentation
        cache=cache,        # Set to True if you have enough RAM (faster training)
        workers=workers,
        exist_ok=True,      # Overwrite previous run if same name
    )
    elapsed = time.time() - start
    print(f"\n⏱️   Training completed in {elapsed/60:.1f} minutes.")

    # ── Copy best weights to model/ ───────────────────────────────────────────
    # Use glob to find best.pt regardless of ultralytics nesting the run dir
    best_candidates = sorted(Path("runs").glob("**/weapon_detector*/weights/best.pt"))
    if not best_candidates:
        best_candidates = sorted(Path("runs").glob("**/best.pt"))

    copied = False
    for candidate in best_candidates:
        output_dir.mkdir(parents=True, exist_ok=True)
        dest = output_dir / "best.pt"
        shutil.copy2(candidate, dest)
        print(f"[OK]  Best weights saved to: {dest.resolve()}")
        copied = True
        break

    if not copied:
        print("[WARN] best.pt not found under runs/ — check the runs/ directory manually.")

    # ── Print metrics ─────────────────────────────────────────────────────────
    try:
        _print_metrics(results.results_dict)
    except Exception:
        print("⚠️   Could not read results_dict (metrics may still be in runs/ folder).")

    # ── Post-training instructions ─────────────────────────────────────────────
    print("[NEXT] Steps:")
    print("    1. Open backend/.env and update:")
    print("       MODEL_PATH=../model/best.pt")
    print("       WEAPON_CLASS_IDS=0,1,2     # Pistol=0, Rifle=1, Knife=2")
    print("       CONFIDENCE_THRESHOLD=0.55  # raise from 0.40 — new model is more precise")
    print("    2. Restart the backend:")
    print("       cd backend && uvicorn main:app --reload")
    print("    3. Check /health endpoint to confirm new model is loaded.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fine-tune YOLOv8 for weapon detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--data",   default="dataset_combined/data.yaml", help="Path to data.yaml (use dataset_combined/ from prepare_dataset.py)")
    parser.add_argument("--model",  default="yolov8s.pt",        help="Base YOLO weights (yolov8s.pt recommended for 3-class dataset)")
    parser.add_argument("--epochs", type=int, default=80,         help="Training epochs (80 recommended for 9,700 images)")
    parser.add_argument("--imgsz",  type=int, default=640,        help="Input image size")
    parser.add_argument("--batch",  type=int, default=8,          help="Batch size (8 for 6GB GPU, 4 for smaller VRAM)")
    parser.add_argument("--output", default="model/",             help="Output dir for best.pt")
    parser.add_argument(
        "--device",
        default="",
        help="Device: '' (auto-detect), 'cpu', '0' (GPU 0), '0,1' (multi-GPU)",
    )
    parser.add_argument("--workers", type=int, default=4, help="DataLoader worker processes (lower this if you hit host RAM errors)")
    parser.add_argument("--cache", action="store_true", help="Cache images in RAM for faster training (needs plenty of free RAM)")
    args = parser.parse_args()
    train(
        data_yaml=args.data,
        base_model=args.model,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        output_dir=Path(args.output),
        workers=args.workers,
        cache=args.cache,
        device=args.device,
    )
