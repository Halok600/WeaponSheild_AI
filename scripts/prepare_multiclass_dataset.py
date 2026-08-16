#!/usr/bin/env python3
"""
prepare_multiclass_dataset.py
------------------------------
Build the final 3-class (Pistol / Rifle / Knife) training dataset by combining:

  1. dataset_roboflow/       - yolov7test weapon-detection v16 (Pistol + Rifle heavy)
  2. dataset_roboflow_edi/   - EDI Detection weapon-yolo8 (balanced Pistol/Rifle/Knife)
  3. val2017/                - COCO background negatives (no weapon -> empty labels)

Both Roboflow sources were already remapped to the same 3-class scheme
(0=Pistol, 1=Rifle, 2=Knife) by download_roboflow_dataset.py, so labels can be
copied through unchanged.

All images are pooled together and reshuffled into fresh 80/10/10 train/val/test
splits (rather than preserving each source's original split), since the source
datasets' own splits were unevenly distributed across classes.

Usage:
    python scripts/prepare_multiclass_dataset.py
"""
from __future__ import annotations

import random
import shutil
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CLASS_NAMES = ["Pistol", "Rifle", "Knife"]
SPLIT_RATIOS = {"train": 0.80, "val": 0.10, "test": 0.10}
IMG_EXTS = (".jpg", ".jpeg", ".png")


def _collect_source(source_dir: Path) -> list[tuple[Path, Path | None]]:
    """Collect (image, label) pairs from every split subfolder of a Roboflow source."""
    pairs: list[tuple[Path, Path | None]] = []
    for split_dir in sorted(source_dir.iterdir()):
        if not split_dir.is_dir():
            continue
        img_dir = split_dir / "images"
        lbl_dir = split_dir / "labels"
        if not img_dir.exists():
            continue
        for img in sorted(img_dir.iterdir()):
            if img.suffix.lower() not in IMG_EXTS:
                continue
            lbl = lbl_dir / img.with_suffix(".txt").name
            pairs.append((img, lbl if lbl.exists() else None))
    return pairs


def _collect_negatives(bg_dir: Path, n: int) -> list[Path]:
    images: list[Path] = []
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        images.extend(sorted(bg_dir.glob(ext)))
    random.seed(42)
    random.shuffle(images)
    return images[:n] if n else images


def _split(items: list, ratios: dict[str, float], seed: int) -> dict[str, list]:
    random.seed(seed)
    shuffled = items[:]
    random.shuffle(shuffled)
    n = len(shuffled)
    n_train = int(n * ratios["train"])
    n_val = int(n * ratios["val"])
    return {
        "train": shuffled[:n_train],
        "val": shuffled[n_train:n_train + n_val],
        "test": shuffled[n_train + n_val:],
    }


def build(output_dir: Path, sources: list[Path], bg_dir: Path, n_negatives: int) -> None:
    print("\n" + "=" * 60)
    print("  Multi-class Dataset Preparation (Pistol / Rifle / Knife)")
    print("=" * 60)

    all_pairs: list[tuple[Path, Path | None]] = []
    for src in sources:
        pairs = _collect_source(src)
        print(f"  {src.name:<22}: {len(pairs)} images")
        all_pairs.extend(pairs)

    print(f"  {'TOTAL positives':<22}: {len(all_pairs)} images")

    negatives = _collect_negatives(bg_dir, n_negatives)
    print(f"  {'COCO negatives':<22}: {len(negatives)} images")
    print("=" * 60)

    pos_split = _split(all_pairs, SPLIT_RATIOS, seed=42)
    neg_split = _split(negatives, SPLIT_RATIOS, seed=99)

    if output_dir.exists():
        print(f"\n[WARN] Clearing existing {output_dir}")
        shutil.rmtree(output_dir)

    class_totals = {c: [0, 0, 0] for c in ("train", "val", "test")}

    for split in SPLIT_RATIOS:
        img_out = output_dir / "images" / split
        lbl_out = output_dir / "labels" / split
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)

        for idx, (img_path, lbl_path) in enumerate(pos_split[split]):
            dst_img = img_out / f"pos_{idx:06d}{img_path.suffix.lower()}"
            shutil.copy2(img_path, dst_img)
            dst_lbl = lbl_out / f"pos_{idx:06d}.txt"
            if lbl_path:
                shutil.copy2(lbl_path, dst_lbl)
                for line in dst_lbl.read_text(encoding="utf-8", errors="ignore").splitlines():
                    parts = line.strip().split()
                    if parts:
                        try:
                            cls = int(parts[0])
                            if 0 <= cls < 3:
                                class_totals[split][cls] += 1
                        except ValueError:
                            pass
            else:
                dst_lbl.write_text("")

        for idx, bg_path in enumerate(neg_split[split]):
            dst_img = img_out / f"neg_{idx:06d}{bg_path.suffix.lower()}"
            shutil.copy2(bg_path, dst_img)
            (lbl_out / f"neg_{idx:06d}.txt").write_text("")

        n_pos = len(pos_split[split])
        n_neg = len(neg_split[split])
        print(f"  {split:<6}: {n_pos + n_neg:>6} total  ({n_pos} weapon + {n_neg} background)")

    abs_path = str(output_dir.resolve()).replace("\\", "/")
    yaml_content = f"""# Auto-generated by scripts/prepare_multiclass_dataset.py

path:  {abs_path}
train: images/train
val:   images/val
test:  images/test

nc: 3
names: ['Pistol', 'Rifle', 'Knife']
"""
    yaml_path = output_dir / "data.yaml"
    yaml_path.write_text(yaml_content, encoding="utf-8")
    print(f"\n[OK] data.yaml written -> {yaml_path}")

    print("\n" + "=" * 60)
    print("  Per-class instance counts")
    print("=" * 60)
    print(f"  {'Split':<8}{'Pistol':>10}{'Rifle':>10}{'Knife':>10}")
    for split in ("train", "val", "test"):
        c = class_totals[split]
        print(f"  {split:<8}{c[0]:>10}{c[1]:>10}{c[2]:>10}")
    print("=" * 60)

    print("\n[NEXT] Run training:")
    print(f"    python scripts/train_custom_model.py --data {yaml_path} --model yolov8s.pt --epochs 80 --batch 16")


if __name__ == "__main__":
    sources = [Path("dataset_roboflow"), Path("dataset_roboflow_edi")]
    kaggle_relabeled = Path("dataset_kaggle_relabeled")
    if kaggle_relabeled.exists():
        sources.append(kaggle_relabeled)

    build(
        output_dir=Path("dataset_multiclass"),
        sources=sources,
        bg_dir=Path("val2017"),
        n_negatives=5000,
    )
