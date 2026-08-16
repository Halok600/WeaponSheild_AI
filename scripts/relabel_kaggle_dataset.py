#!/usr/bin/env python3
"""
relabel_kaggle_dataset.py
--------------------------
The local Kaggle weapon dataset (dataset/) was exported to YOLO format with
every box collapsed into a single generic class 0 ("weapon"). But each image's
real category is recoverable from its filename prefix (e.g. "Knife_42.jpeg"),
which dataset/metadata.csv also records under the "imagefile" column.

This script re-derives the real category per image and rewrites its label
file with the correct class ID in our 3-class scheme (0=Pistol, 1=Rifle,
2=Knife), copying the result into dataset_kaggle_relabeled/all/. Categories
outside that scheme (Grenade Launcher, Bazooka) are skipped entirely.

Usage:
    python scripts/relabel_kaggle_dataset.py
"""
from __future__ import annotations

import csv
import re
import shutil
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CATEGORY_TO_CLASS: dict[str, int] = {
    "handgun": 0,
    "automatic rifle": 1,
    "smg": 1,
    "sniper": 1,
    "shotgun": 1,
    "knife": 2,
    "sword": 2,
    # "grenade launcher" and "bazooka" are intentionally omitted -> dropped
}
CLASS_NAMES = ["Pistol", "Rifle", "Knife"]

_PREFIX_RE = re.compile(r"^(.*)_\d+\.(jpeg|jpg|png)$", re.IGNORECASE)


def _category_from_filename(filename: str) -> str | None:
    m = _PREFIX_RE.match(filename)
    return m.group(1).strip().lower() if m else None


def relabel(dataset_dir: Path, output_dir: Path) -> None:
    metadata_path = dataset_dir / "metadata.csv"
    if not metadata_path.exists():
        print(f"[FAIL] metadata.csv not found at {metadata_path}")
        sys.exit(1)

    img_out = output_dir / "all" / "images"
    lbl_out = output_dir / "all" / "labels"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    img_out.mkdir(parents=True, exist_ok=True)
    lbl_out.mkdir(parents=True, exist_ok=True)

    kept_counts = {name: 0 for name in CLASS_NAMES}
    dropped = 0
    missing = 0

    with metadata_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        image_name = row["imagefile"]
        label_name = row["labelfile"]
        category = _category_from_filename(image_name)
        class_id = CATEGORY_TO_CLASS.get(category) if category else None
        if class_id is None:
            dropped += 1
            continue

        # Images live under images/train/ or images/val/ (mirrored for labels/)
        img_src = None
        lbl_src = None
        for split in ("train", "val"):
            candidate_img = dataset_dir / "images" / split / image_name
            candidate_lbl = dataset_dir / "labels" / split / label_name
            if candidate_img.exists():
                img_src, lbl_src = candidate_img, candidate_lbl
                break

        if img_src is None or not lbl_src.exists():
            missing += 1
            continue

        # Rewrite label file: every box in this image belongs to `class_id`
        lines = lbl_src.read_text(encoding="utf-8", errors="ignore").splitlines()
        new_lines = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            new_lines.append(f"{class_id} {' '.join(parts[1:])}")
        if not new_lines:
            missing += 1
            continue

        dst_img = img_out / image_name
        dst_lbl = lbl_out / (Path(image_name).stem + ".txt")
        shutil.copy2(img_src, dst_img)
        dst_lbl.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

        kept_counts[CLASS_NAMES[class_id]] += 1

    total_kept = sum(kept_counts.values())
    print("\n" + "=" * 50)
    print("  Kaggle Dataset Relabel Summary")
    print("=" * 50)
    for name, count in kept_counts.items():
        print(f"  {name:<10}: {count}")
    print(f"  {'Dropped':<10}: {dropped} (outside 3-class scope)")
    print(f"  {'Missing':<10}: {missing} (file not found / empty label)")
    print(f"  {'TOTAL kept':<10}: {total_kept}")
    print("=" * 50)
    print(f"\n[OK] Relabeled dataset written -> {output_dir}\\all\\")


if __name__ == "__main__":
    relabel(
        dataset_dir=Path("dataset"),
        output_dir=Path("dataset_kaggle_relabeled"),
    )
