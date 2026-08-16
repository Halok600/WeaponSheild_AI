#!/usr/bin/env python3
"""
prepare_dataset.py
------------------
Build a combined weapon-detection training dataset from two sources:

  POSITIVE examples (weapons):
      Existing Kaggle weapon dataset in dataset/ folder.

  NEGATIVE examples (backgrounds — no weapons):
      Any local folder of images (e.g. COCO val2017).
      Download once (no login): http://images.cocodataset.org/zips/val2017.zip

Usage:
    # After downloading and extracting val2017.zip to D:/val2017/
    python scripts/prepare_dataset.py --bg-dir D:/val2017

    # Limit to 1000 background images
    python scripts/prepare_dataset.py --bg-dir D:/val2017 --n-negatives 1000

Prerequisites:
    pip install requests
"""
from __future__ import annotations

import argparse
import random
import shutil
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Configuration ─────────────────────────────────────────────────────────────
DEFAULT_N_NEGATIVES = 1000
SPLIT_RATIOS = {"train": 0.80, "val": 0.15, "test": 0.05}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _count_files(directory: Path, ext: str) -> int:
    return len(list(directory.rglob(f"*.{ext}"))) if directory.exists() else 0


def _ensure_weapon_dataset(weapon_dir: Path) -> bool:
    train_imgs = weapon_dir / "images" / "train"
    n = _count_files(train_imgs, "jpg") + _count_files(train_imgs, "png")
    if n > 0:
        print(f"[OK]  Weapon dataset found: {n} training images in {train_imgs}")
        return True
    print(f"\n[!] No weapon images found in {train_imgs}")
    print("    Run first:  python scripts\\download_kaggle_dataset.py")
    return False


def _collect_weapon_examples(weapon_dir: Path) -> dict[str, list[tuple[Path, Path | None]]]:
    """
    Auto-detects two common dataset layouts:

    Layout A — Roboflow YOLOv8 download (split-first):
        weapon_dir/train/images/*.jpg   weapon_dir/train/labels/*.txt
        weapon_dir/valid/images/*.jpg   weapon_dir/valid/labels/*.txt

    Layout B — Kaggle / images-first:
        weapon_dir/images/train/*.jpg   weapon_dir/labels/train/*.txt
        weapon_dir/images/val/*.jpg     weapon_dir/labels/val/*.txt

    Output always normalises to keys: train / val / test
    """
    # Map Roboflow's "valid" → standard "val"
    SPLIT_ALIASES = {"train": "train", "valid": "val", "val": "val", "test": "test"}
    result: dict[str, list[tuple[Path, Path | None]]] = {"train": [], "val": [], "test": []}

    # ── Detect layout ─────────────────────────────────────────────────────────
    # Layout A: weapon_dir/train/images/ exists
    layout_a = (weapon_dir / "train" / "images").exists()
    # Layout B: weapon_dir/images/train/ exists
    layout_b = (weapon_dir / "images" / "train").exists()

    if not layout_a and not layout_b:
        print(f"[WARN] Could not detect dataset layout in {weapon_dir}")
        print("       Expected either:")
        print("         train/images/ and train/labels/  (Roboflow layout)")
        print("         images/train/ and labels/train/  (Kaggle/standard layout)")
        return result

    if layout_a:
        print(f"[INFO] Detected Roboflow layout (split-first) in {weapon_dir}")
        for raw_split, norm_split in SPLIT_ALIASES.items():
            img_dir = weapon_dir / raw_split / "images"
            lbl_dir = weapon_dir / raw_split / "labels"
            if not img_dir.exists():
                continue
            for img in sorted(img_dir.iterdir()):
                if img.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                    continue
                lbl = lbl_dir / img.with_suffix(".txt").name
                result[norm_split].append((img, lbl if lbl.exists() else None))
    else:
        print(f"[INFO] Detected Kaggle/standard layout (images-first) in {weapon_dir}")
        for raw_split, norm_split in SPLIT_ALIASES.items():
            img_dir = weapon_dir / "images" / raw_split
            lbl_dir = weapon_dir / "labels" / raw_split
            if not img_dir.exists():
                continue
            for img in sorted(img_dir.iterdir()):
                if img.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                    continue
                lbl = lbl_dir / img.with_suffix(".txt").name
                result[norm_split].append((img, lbl if lbl.exists() else None))

    total = sum(len(v) for v in result.values())
    for split, items in result.items():
        if items:
            print(f"         {split}: {len(items)} images")
    return result



def _load_bg_images(bg_dir: Path, n: int) -> list[Path]:
    images: list[Path] = []
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        images.extend(sorted(bg_dir.rglob(ext)))
    if not images:
        return []
    random.seed(42)
    random.shuffle(images)
    return images[:n] if n else images


def _split_backgrounds(bg_images: list[Path]) -> dict[str, list[Path]]:
    random.seed(99)
    random.shuffle(bg_images)
    n = len(bg_images)
    n_train = int(n * SPLIT_RATIOS["train"])
    n_val   = int(n * SPLIT_RATIOS["val"])
    return {
        "train": bg_images[:n_train],
        "val":   bg_images[n_train: n_train + n_val],
        "test":  bg_images[n_train + n_val:],
    }


def _build_dataset(
    weapon_examples: dict[str, list[tuple[Path, Path | None]]],
    bg_split: dict[str, list[Path]],
    output_dir: Path,
) -> None:
    print(f"\n[MERGE] Building combined dataset in {output_dir} ...")
    if output_dir.exists():
        print(f"[WARN] Clearing existing {output_dir}")
        shutil.rmtree(output_dir)

    for split in SPLIT_RATIOS:
        img_out = output_dir / "images" / split
        lbl_out = output_dir / "labels" / split
        img_out.mkdir(parents=True, exist_ok=True)
        lbl_out.mkdir(parents=True, exist_ok=True)

        # Weapon positives
        for idx, (img_path, lbl_path) in enumerate(weapon_examples.get(split, [])):
            shutil.copy2(img_path, img_out / f"weapon_{idx:05d}{img_path.suffix}")
            dst_lbl = lbl_out / f"weapon_{idx:05d}.txt"
            shutil.copy2(lbl_path, dst_lbl) if lbl_path else dst_lbl.write_text("")

        # Background negatives — empty label files
        for idx, bg_path in enumerate(bg_split.get(split, [])):
            shutil.copy2(bg_path, img_out / f"bg_{idx:05d}{bg_path.suffix}")
            (lbl_out / f"bg_{idx:05d}.txt").write_text("")   # empty = no weapon

        w  = len(weapon_examples.get(split, []))
        bg = len(bg_split.get(split, []))
        print(f"  {split:<6}: {w+bg:>5} total  ({w} weapon + {bg} background)")


def _write_yaml(output_dir: Path) -> Path:
    abs_path = str(output_dir.resolve()).replace("\\", "/")
    content = f"""# Combined weapon + background dataset
# Generated by scripts/prepare_dataset.py

path:  {abs_path}
train: images/train
val:   images/val
test:  images/test

nc: 1
names: ['weapon']
"""
    yaml_path = output_dir / "data.yaml"
    yaml_path.write_text(content, encoding="utf-8")
    print(f"\n[OK]  data.yaml written → {yaml_path}")
    return yaml_path


# ── Main ──────────────────────────────────────────────────────────────────────
def prepare(weapon_dir: Path, output_dir: Path, bg_dir: Path | None, n: int) -> None:
    print("\n" + "═" * 60)
    print("  🔫  WeaponShield AI — Combined Dataset Preparation")
    print("═" * 60)
    print(f"  Weapon source : {weapon_dir.resolve()}")
    print(f"  Background dir: {bg_dir.resolve() if bg_dir else 'none (no negatives!)'}")
    print(f"  Max negatives : {n}")
    print(f"  Output        : {output_dir.resolve()}")
    print("═" * 60)

    if not _ensure_weapon_dataset(weapon_dir):
        sys.exit(1)

    weapon_examples = _collect_weapon_examples(weapon_dir)
    total_weapons = sum(len(v) for v in weapon_examples.values())
    print(f"[OK]  {total_weapons} weapon examples collected.\n")

    # Load background images
    bg_images: list[Path] = []
    if bg_dir and bg_dir.exists():
        bg_images = _load_bg_images(bg_dir, n)
        print(f"[OK]  {len(bg_images)} background images loaded from {bg_dir}")
    else:
        print("\n[WARN] No --bg-dir provided or directory not found.")
        print("       The dataset will be weapons-only → false positives WILL occur.")
        print("\n  ── To fix, download COCO val2017 (free, no login): ──────────")
        print("     http://images.cocodataset.org/zips/val2017.zip  (800 MB)")
        print("     Extract it, then re-run:")
        print("     python scripts\\prepare_dataset.py --bg-dir C:\\path\\to\\val2017\n")

    bg_split = _split_backgrounds(bg_images)
    _build_dataset(weapon_examples, bg_split, output_dir)
    yaml_path = _write_yaml(output_dir)

    # Summary
    print("\n" + "═" * 60)
    print("  📊  Final Dataset Summary")
    print("═" * 60)
    for split in SPLIT_RATIOS:
        n_img = _count_files(output_dir / "images" / split, "jpg") + \
                _count_files(output_dir / "images" / split, "png")
        print(f"  {split:<6}: {n_img:>5} images")
    print("═" * 60)

    bg_pct = len(bg_images) / (total_weapons + len(bg_images)) * 100 if bg_images else 0
    print(f"\n  Negative ratio : {bg_pct:.0f}%  (recommended ≥ 40%)")

    print("\n[NEXT] Run training:")
    print(f"       python scripts\\train_custom_model.py --data {yaml_path} --model yolov8s.pt --epochs 80 --batch 8")
    print("\n       After training update backend\\.env:")
    print("       WEAPON_CLASS_IDS=0")
    print("       CONFIDENCE_THRESHOLD=0.55\n")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build combined weapon + background dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--weapon-dir", default="dataset",
                        help="Existing weapon dataset directory (default: dataset/)")
    parser.add_argument("--output", default="dataset_combined",
                        help="Output directory (default: dataset_combined/)")
    parser.add_argument("--bg-dir", default="",
                        help="LOCAL folder of background images (e.g. extracted val2017/). "
                             "Download: http://images.cocodataset.org/zips/val2017.zip")
    parser.add_argument("--n-negatives", type=int, default=DEFAULT_N_NEGATIVES,
                        help=f"Max background images to use (default: {DEFAULT_N_NEGATIVES})")
    args = parser.parse_args()

    prepare(
        weapon_dir=Path(args.weapon_dir),
        output_dir=Path(args.output),
        bg_dir=Path(args.bg_dir) if args.bg_dir else None,
        n=args.n_negatives,
    )
