#!/usr/bin/env python3
"""
download_roboflow_dataset.py
----------------------------
Download the Roboflow 'weapon-detection' dataset (yolov7test, ~9,700 images)
and remap its 28 raw classes down to 3 clean classes:

    0 → Pistol   (pistol, handgun, heavy gun, …)
    1 → Rifle    (rifle, shotgun, long guns, larga, …)
    2 → Knife    (knife, blade, pisau, …)

All other classes (Person, Victim, Blood, …) are dropped from labels so they
act as hard negative examples — exactly what the previous dataset lacked.

Usage:
    # Recommended – will prompt for API key interactively
    python scripts/download_roboflow_dataset.py

    # Pass API key directly
    python scripts/download_roboflow_dataset.py --api-key YOUR_KEY

    # Change output directory
    python scripts/download_roboflow_dataset.py --output dataset

Prerequisites:
    pip install roboflow

How to get your Roboflow API key (FREE account):
    1. Go to https://app.roboflow.com  →  Sign Up (free)
    2. Click your profile icon (top-right) → Settings
    3. Go to 'Roboflow API'  →  Copy your Private API Key

After this script:
    python scripts/train_custom_model.py --model yolov8s.pt --epochs 80
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Class remapping ───────────────────────────────────────────────────────────
# Maps raw class-name keywords (lower-case) → our consolidated class ID.
# Any class not matched here is DROPPED from labels (becomes a background region).
#
# Add more keywords if the dataset uses regional names you want to include.
REMAP_RULES: list[tuple[int, list[str]]] = [
    # (target_id, [keyword fragments that match raw class names])
    (0, ["pistol", "handgun", "hand gun", "guns", "gun"]),
    (1, ["rifle", "shotgun", "long gun", "larga", "revolver", "carbine", "smg",
         "heavy gun", "heavy weapon", "heavy-weapon", "heavyweapon", "machine gun"]),
    (2, ["knife", "knive", "blade", "pisau", "dagger", "machete", "cleaver", "stabbing"]),
]

# Final class names  (order matches IDs above)
FINAL_CLASS_NAMES = ["Pistol", "Rifle", "Knife"]

# ── Dataset to download ───────────────────────────────────────────────────────
# NOTE: Roboflow renamed this project's slugs at some point after this script was
# written (yolov7test → yolov7test-u13vc, weapon-detection → weapon-detection-m7qso).
# Same dataset (9,672 images, 28 classes) — https://universe.roboflow.com/yolov7test-u13vc/weapon-detection-m7qso
ROBOFLOW_WORKSPACE = "yolov7test-u13vc"
ROBOFLOW_PROJECT   = "weapon-detection-m7qso"
ROBOFLOW_VERSION   = 16         # largest version: 16,634 images, 21 remapped classes
ROBOFLOW_FORMAT    = "yolov8"


# ── Helpers ──────────────────────────────────────────────────────────────────
def _remap_class(raw_name: str) -> int | None:
    """
    Return a consolidated class ID for a raw class name, or None to drop it.
    Matching is case-insensitive substring search.
    """
    name_lower = raw_name.lower().strip()
    for target_id, keywords in REMAP_RULES:
        for kw in keywords:
            if kw in name_lower:
                return target_id
    return None   # drop


def _remap_label_file(label_path: Path, old_to_new: dict[int, int | None]) -> int:
    """
    Rewrite a YOLO label file using the remapped class IDs.
    Lines whose class has no mapping are silently dropped.

    Returns the number of annotations kept.
    """
    lines = label_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    kept: list[str] = []
    for line in lines:
        parts = line.strip().split()
        if not parts:
            continue
        try:
            old_cls = int(parts[0])
        except ValueError:
            continue
        new_cls = old_to_new.get(old_cls)
        if new_cls is None:
            continue  # dropped class
        kept.append(f"{new_cls} {' '.join(parts[1:])}")
    label_path.write_text("\n".join(kept) + ("\n" if kept else ""),
                          encoding="utf-8")
    return len(kept)


def _parse_class_names_from_yaml(yaml_path: Path) -> list[str]:
    """
    Extract class names from a YOLO data.yaml without importing PyYAML.
    Handles both list format and dict format.
    """
    text = yaml_path.read_text(encoding="utf-8", errors="ignore")
    # Try to find    names: [A, B, C]   or    names:\n  - A\n  - B
    inline = re.search(r"names\s*:\s*\[([^\]]+)\]", text)
    if inline:
        return [n.strip().strip("'\"") for n in inline.group(1).split(",")]
    block = re.findall(r"^\s*-\s+(.+)$", text, re.MULTILINE)
    return [b.strip().strip("'\"") for b in block] if block else []


def _write_data_yaml(output_dir: Path) -> Path:
    """Write the final 3-class data.yaml."""
    abs_path = str(output_dir.resolve()).replace("\\", "/")
    content = f"""# Auto-generated by download_roboflow_dataset.py
# Dataset: Roboflow weapon-detection (yolov7test), remapped to 3 classes

path:  {abs_path}
train: train/images
val:   valid/images
test:  test/images

nc: 3
names: ['Pistol', 'Rifle', 'Knife']
"""
    yaml_path = output_dir / "data.yaml"
    yaml_path.write_text(content, encoding="utf-8")
    print(f"[OK]  data.yaml written → {yaml_path}")
    return yaml_path


def _count(directory: Path, ext: str = "*") -> int:
    return len(list(directory.rglob(f"*.{ext}"))) if directory.exists() else 0


def _print_summary(output_dir: Path, class_counts: dict[str, list[int]]) -> None:
    splits = ["train", "valid", "test"]
    print("\n" + "═" * 56)
    print("  📊  Dataset Summary After Remapping")
    print("═" * 56)
    print(f"  {'Split':<8} {'Images':>8} {'Labels':>8} {'Pistol':>8} {'Rifle':>8} {'Knife':>8}")
    print("  " + "-" * 54)
    for split in splits:
        imgs   = _count(output_dir / split / "images", "jpg") + _count(output_dir / split / "images", "png")
        labels = _count(output_dir / split / "labels", "txt")
        counts = class_counts.get(split, [0, 0, 0])
        print(f"  {split:<8} {imgs:>8} {labels:>8} {counts[0]:>8} {counts[1]:>8} {counts[2]:>8}")
    print("═" * 56 + "\n")


# ── Main download + remap ─────────────────────────────────────────────────────
def _get_user_workspace(rf) -> str:
    """
    Auto-detect the slug of the user's Roboflow workspace from their API key.
    Returns the workspace slug (URL identifier) or empty string on failure.
    """
    try:
        import requests
        resp = requests.get(
            "https://api.roboflow.com/",
            params={"api_key": rf.api_key},
            timeout=10,
        )
        data = resp.json()
        # Roboflow root response includes workspace info
        slug = (
            data.get("workspace", {}).get("url")
            or data.get("workspace", {}).get("id")
            or ""
        )
        return slug.lower().strip()
    except Exception:
        return ""


def download_and_remap(api_key: str, output_dir: Path, workspace_override: str = "", project_override: str = "") -> None:
    try:
        from roboflow import Roboflow
    except ImportError:
        print("\n[FAIL] roboflow package not installed.")
        print("       Run:  pip install roboflow\n")
        sys.exit(1)

    rf = Roboflow(api_key=api_key)

    # ── Resolve which workspace/project to download from ──────────────────────
    target_workspace = workspace_override.strip() or ROBOFLOW_WORKSPACE
    target_project = project_override.strip() or ROBOFLOW_PROJECT

    print("\n" + "═" * 56)
    print("  🔫  WeaponShield AI — Roboflow Dataset Download")
    print("═" * 56)
    print(f"  Workspace : {target_workspace}")
    print(f"  Project   : {target_project}")
    print(f"  Version   : {ROBOFLOW_VERSION}")
    print(f"  Output    : {output_dir.resolve()}")
    print("═" * 56 + "\n")

    # ── Try to download; give clear fork instructions if access denied ────────
    try:
        project = rf.workspace(target_workspace).project(target_project)
        version = project.version(ROBOFLOW_VERSION)
    except Exception as exc:
        err_str = str(exc)

        # Auto-detect the user's actual workspace slug
        user_ws = _get_user_workspace(rf)
        user_ws_info = f"  Your workspace: {user_ws}" if user_ws else ""

        if "does not exist" in err_str or "missing permissions" in err_str or "GraphMethodException" in err_str:
            print("\n[!] Access denied to the public dataset workspace.")
            print("    You need to FORK the dataset to your own workspace first.\n")
            print("  ── How to fork (takes 30 seconds) ───────────────────────")
            print("  1. Open this URL in your browser:")
            print("     https://universe.roboflow.com/yolov7test/weapon-detection")
            print("  2. Click the  [Fork Project]  button (top-right)")
            print("  3. Select your workspace in the popup → click Fork")
            if user_ws_info:
                print(f"\n{user_ws_info}")
            print("\n  ── Then re-run with your workspace slug ─────────────────")
            if user_ws:
                print(f"  python scripts\\download_roboflow_dataset.py --workspace {user_ws}")
            else:
                print("  python scripts\\download_roboflow_dataset.py --workspace YOUR_WORKSPACE_SLUG")
            print("\n  (Your workspace slug is visible in the Roboflow dashboard URL)")
            print("  e.g.  https://app.roboflow.com/MY-SLUG  →  slug = my-slug\n")
        else:
            print(f"\n[FAIL] Unexpected error: {exc}\n")
        sys.exit(1)

    # Download to a temp location, then move to output_dir
    tmp_dir = output_dir.parent / f"_rf_tmp_{target_project}"
    print(f"[DL]  Downloading dataset to temporary folder: {tmp_dir} ...")
    dataset = version.download(ROBOFLOW_FORMAT, location=str(tmp_dir), overwrite=True)
    dl_path = Path(dataset.location)
    print(f"[OK]  Downloaded to: {dl_path}")

    # ── Read original class names from yaml ───────────────────────────────────
    orig_yaml = dl_path / "data.yaml"
    if not orig_yaml.exists():
        orig_yaml_candidates = list(dl_path.rglob("data.yaml"))
        orig_yaml = orig_yaml_candidates[0] if orig_yaml_candidates else None

    if orig_yaml is None:
        print("[FAIL] Could not find data.yaml in the downloaded dataset.")
        sys.exit(1)

    raw_class_names = _parse_class_names_from_yaml(orig_yaml)
    if not raw_class_names:
        print("[WARN] Could not parse class names from data.yaml — using positional index only.")
        raw_class_names = [str(i) for i in range(100)]

    print(f"\n[INFO] Original classes ({len(raw_class_names)}): {raw_class_names}")

    # ── Build old→new class ID mapping ───────────────────────────────────────
    old_to_new: dict[int, int | None] = {}
    print("\n[INFO] Class remapping:")
    for i, name in enumerate(raw_class_names):
        new_id = _remap_class(name)
        old_to_new[i] = new_id
        mapped_name = FINAL_CLASS_NAMES[new_id] if new_id is not None else "⚠ DROPPED"
        print(f"         [{i:02d}] {name:<22} → {mapped_name}")

    kept_ids   = {k for k, v in old_to_new.items() if v is not None}
    dropped_ids = {k for k, v in old_to_new.items() if v is None}
    print(f"\n[INFO] Keeping {len(kept_ids)} source classes, dropping {len(dropped_ids)} (background).")

    # ── Move files to output_dir ──────────────────────────────────────────────
    print(f"\n[MOVE] Copying to final output directory: {output_dir} ...")
    if output_dir.exists():
        print(f"[WARN] Output directory already exists — clearing it.")
        shutil.rmtree(output_dir)
    shutil.copytree(dl_path, output_dir)
    print(f"[OK]  Files moved.")

    # ── Remap all label files ─────────────────────────────────────────────────
    splits = ["train", "valid", "test"]
    class_counts: dict[str, list[int]] = {}

    for split in splits:
        label_dir = output_dir / split / "labels"
        if not label_dir.exists():
            continue

        label_files = list(label_dir.glob("*.txt"))
        split_counts = [0, 0, 0]
        total_kept = 0

        print(f"[REMAP] {split}: processing {len(label_files)} label files ...")
        for lf in label_files:
            # Count per class before remap for stats
            try:
                for line in lf.read_text(encoding="utf-8", errors="ignore").splitlines():
                    parts = line.strip().split()
                    if parts:
                        try:
                            old_cls = int(parts[0])
                            new_cls = old_to_new.get(old_cls)
                            if new_cls is not None:
                                split_counts[new_cls] += 1
                        except ValueError:
                            pass
            except Exception:
                pass

            kept = _remap_label_file(lf, old_to_new)
            total_kept += kept

        class_counts[split] = split_counts
        print(f"         Kept {total_kept} annotations in {split}.")

    # ── Cleanup temp dir ──────────────────────────────────────────────────────
    try:
        shutil.rmtree(tmp_dir)
        print(f"[OK]  Temp directory cleaned up.")
    except Exception:
        pass

    # ── Write final data.yaml ─────────────────────────────────────────────────
    _write_data_yaml(output_dir)

    # ── Summary ───────────────────────────────────────────────────────────────
    _print_summary(output_dir, class_counts)

    print("[NEXT] Steps:")
    print("    1. Verify the dataset summary above looks reasonable.")
    print("    2. Run training:")
    print("       python scripts/train_custom_model.py --model yolov8s.pt --epochs 80 --batch 8")
    print("    3. After training update backend/.env:")
    print("       WEAPON_CLASS_IDS=0,1,2")
    print("       CONFIDENCE_THRESHOLD=0.55")
    print("    4. Restart backend: uvicorn main:app --reload\n")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download Roboflow weapon detection dataset (9,700 images, 3 classes)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--api-key", "--api_key",
        default="",
        help="Your Roboflow Private API Key (get it free at https://app.roboflow.com)",
    )
    parser.add_argument(
        "--output",
        default="dataset",
        help="Output directory for the dataset (default: dataset/)",
    )
    parser.add_argument(
        "--version",
        type=int,
        default=ROBOFLOW_VERSION,
        help=f"Roboflow project version to download (default: {ROBOFLOW_VERSION})",
    )
    parser.add_argument(
        "--workspace",
        default="",
        help="Your Roboflow workspace slug (required after forking the dataset). "
             "Find it in your dashboard URL: https://app.roboflow.com/YOUR-SLUG",
    )
    parser.add_argument(
        "--project",
        default="",
        help="Override the Roboflow project slug (default: the built-in weapon-detection project).",
    )
    args = parser.parse_args()

    api_key = args.api_key.strip()
    if not api_key:
        print("\n[INFO] No API key provided via --api-key.")
        print("       Get your FREE key at: https://app.roboflow.com → Settings → Roboflow API")
        api_key = input("       Paste your Roboflow Private API Key: ").strip()
        if not api_key:
            print("[FAIL] API key is required.")
            sys.exit(1)

    ROBOFLOW_VERSION = args.version
    download_and_remap(
        api_key=api_key,
        output_dir=Path(args.output),
        workspace_override=args.workspace,
        project_override=args.project,
    )
