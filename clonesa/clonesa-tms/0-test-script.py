"""
Extract ALL BrainSight sample positions and create spherical NIfTI masks on a T1.
Outputs are organized by subject (extracted from the T1 path).

Coordinate pipeline (correct):
  BrainSight voxel
    → BrainSight world (RAS) via ZCACHEDWORLDTRANSFORM
    → T1 NIfTI voxel (via inverse T1 affine)
"""

import argparse
import plistlib
import re
import sqlite3
import struct
from pathlib import Path

import numpy as np


def load_nibabel():
    try:
        import importlib
        return importlib.import_module("nibabel")
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("pip install nibabel") from exc


def decode_matrix(blob):
    """Decode a BrainSight plist blob containing a 4x4 double matrix."""
    if not blob:
        return None
    plist_data = plistlib.loads(blob)
    transform_data = plist_data["$objects"][2]
    values = struct.unpack("<16d", transform_data)
    return np.array(values, dtype=float).reshape(4, 4)


def read_brainsight_world_transform(bsproj_path):
    """
    Read ZCACHEDWORLDTRANSFORM from ZDATASET (the anatomical dataset, ZLAYER=1, ZPROJECT not NULL).
    This is the affine that maps BrainSight voxel indices → RAS world mm.
    """
    con = sqlite3.connect(bsproj_path)
    cur = con.cursor()
    cur.execute(
        "SELECT ZCACHEDWORLDTRANSFORM FROM ZDATASET WHERE ZLAYER = 1 AND ZPROJECT IS NOT NULL LIMIT 1;"
    )
    row = cur.fetchone()
    con.close()
    if not row or not row[0]:
        raise ValueError("ZCACHEDWORLDTRANSFORM introuvable dans ZDATASET.")
    return decode_matrix(row[0])


def get_all_samples(bsproj_path):
    """
    Fetch all sample names and their position blobs from ZSAMPLE.
    Returns a list of dicts with keys: name, zposition, ztargetposition.
    """
    con = sqlite3.connect(bsproj_path)
    cur = con.cursor()
    cur.execute(
        "SELECT ZNAME, ZPOSITION, ZTARGETPOSITION FROM ZSAMPLE ORDER BY ZINDEX ASC;"
    )
    rows = cur.fetchall()
    con.close()
    return [
        {"name": r[0], "zposition": r[1], "ztargetposition": r[2]}
        for r in rows
        if r[0] is not None
    ]


def extract_subject_id(t1_path):
    """
    Extract subject ID (e.g. sub-0001) from the T1 path.
    Falls back to 'sub-unknown' if not found.
    """
    match = re.search(r"(sub-[a-zA-Z0-9]+)", str(t1_path))
    return match.group(1) if match else "sub-unknown"


def brainsight_vox_to_t1_vox(vox_bs, W_bs, t1_affine):
    """
    Convert a position in BrainSight voxel space to T1 NIfTI voxel space.

    BrainSight's ZCACHEDWORLDTRANSFORM is a NIfTI-style affine that maps
    voxel indices directly to RAS world mm — no LPS conversion needed.

    Steps:
      1. BrainSight vox → RAS world mm  : w_ras = W_bs @ [vox, 1]
      2. RAS world → T1 NIfTI voxel     : vox_t1 = inv(t1_affine) @ [w_ras, 1]
    """
    w_ras = (W_bs @ np.append(vox_bs, 1.0))[:3]
    vox_t1 = (np.linalg.inv(t1_affine) @ np.append(w_ras, 1.0))[:3]
    return vox_t1


def create_sphere_mask(shape, affine, center_vox, radius_mm):
    nib = load_nibabel()
    voxel_sizes = nib.affines.voxel_sizes(affine)
    radius_vox = radius_mm / voxel_sizes

    bbox_min = np.floor(center_vox - radius_vox - 1).astype(int)
    bbox_max = np.ceil(center_vox + radius_vox + 1).astype(int)
    bbox_min = np.maximum(bbox_min, 0)
    bbox_max = np.minimum(bbox_max, np.array(shape) - 1)

    if np.any(bbox_max < bbox_min):
        return np.zeros(shape, dtype=np.uint8)

    xs = np.arange(bbox_min[0], bbox_max[0] + 1)
    ys = np.arange(bbox_min[1], bbox_max[1] + 1)
    zs = np.arange(bbox_min[2], bbox_max[2] + 1)
    xx, yy, zz = np.meshgrid(xs, ys, zs, indexing="ij")

    d2 = (
        ((xx - center_vox[0]) / radius_vox[0]) ** 2
        + ((yy - center_vox[1]) / radius_vox[1]) ** 2
        + ((zz - center_vox[2]) / radius_vox[2]) ** 2
    )
    mask = np.zeros(shape, dtype=np.uint8)
    mask[bbox_min[0]:bbox_max[0] + 1,
         bbox_min[1]:bbox_max[1] + 1,
         bbox_min[2]:bbox_max[2] + 1] = (d2 <= 1.0).astype(np.uint8)
    return mask


def main():
    nib = load_nibabel()

    parser = argparse.ArgumentParser(
        description="Extract ALL BrainSight sample positions and create spherical NIfTI masks on a T1."
    )
    parser.add_argument("--bsproj", required=True, help="Path to .bsproj file.")
    parser.add_argument("--t1", required=True, help="Path to T1 NIfTI.")
    parser.add_argument(
        "--source",
        choices=["target", "coil", "both"],
        default="target",
        help="ZTARGETPOSITION (cortical target), ZPOSITION (coil position), or both.",
    )
    parser.add_argument(
        "--out-dir",
        default="/Users/hippolyte.dreyfus/Desktop/_clonesa/clonesaTMS/extracted_targets",
    )
    parser.add_argument("--radius-mm", type=float, default=5.0, help="Sphere radius in mm.")
    args = parser.parse_args()

    # --- Setup ---
    nib_t1 = nib.load(args.t1)
    t1_shape = nib_t1.shape[:3]
    t1_affine = nib_t1.affine
    W_bs = read_brainsight_world_transform(args.bsproj)
    subject_id = extract_subject_id(args.t1)

    # Output directory organised by subject
    out_dir = Path(args.out_dir) / subject_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Detect all samples ---
    samples = get_all_samples(args.bsproj)
    print(f"\n{'='*60}")
    print(f"Subject          : {subject_id}")
    print(f"Samples detected : {len(samples)}")
    print(f"Source           : {args.source}")
    print(f"Output dir       : {out_dir}")
    print(f"{'='*60}\n")

    sources = ["target", "coil"] if args.source == "both" else [args.source]

    n_ok, n_skip, n_err = 0, 0, 0

    for sample in samples:
        name = sample["name"]
        for source in sources:
            blob = sample["ztargetposition"] if source == "target" else sample["zposition"]

            if blob is None:
                print(f"  [SKIP] {name} ({source}) — blob absent")
                n_skip += 1
                continue

            try:
                M = decode_matrix(blob)
                if M is None:
                    print(f"  [SKIP] {name} ({source}) — décodage échoué")
                    n_skip += 1
                    continue

                vox_bs = M[:3, 3]
                vox_t1 = brainsight_vox_to_t1_vox(vox_bs, W_bs, t1_affine)
                w_ras = (W_bs @ np.append(vox_bs, 1.0))[:3]

                inside = bool(np.all((vox_t1 >= 0) & (vox_t1 < np.array(t1_shape))))
                if not inside:
                    print(f"  [SKIP] {name} ({source}) — hors volume T1  vox={np.round(vox_t1, 1)}")
                    n_skip += 1
                    continue

                mask = create_sphere_mask(t1_shape, t1_affine, vox_t1, args.radius_mm)
                n_vox = int(mask.sum())

                fname = f"{name.replace(' ', '_')}_{source}_r{args.radius_mm:g}mm.nii.gz"
                out_path = out_dir / fname
                sphere_img = nib.Nifti1Image(mask, t1_affine, nib_t1.header)
                sphere_img.set_data_dtype(np.uint8)
                nib.save(sphere_img, str(out_path))

                print(f"  [OK]   {name} ({source})  RAS={np.round(w_ras, 1)}  vox_T1={np.round(vox_t1, 1)}  nvox={n_vox}")
                n_ok += 1

            except Exception as e:
                print(f"  [ERR]  {name} ({source}) — {e}")
                n_err += 1

    print(f"\n{'='*60}")
    print(f"Terminé : {n_ok} OK  |  {n_skip} skippés  |  {n_err} erreurs")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
