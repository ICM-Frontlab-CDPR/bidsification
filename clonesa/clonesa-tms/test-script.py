"""
Extract a BrainSight sample position and create a spherical NIfTI mask on a T1.

Coordinate pipeline (correct):
  BrainSight voxel
    → BrainSight world (LPS) via ZCACHEDWORLDTRANSFORM
    → RAS world (negate X and Y)
    → T1 NIfTI voxel (via inverse T1 affine)
"""

import argparse
import plistlib
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
    This is the affine that maps BrainSight voxel indices → LPS world mm.
    """
    con = sqlite3.connect(bsproj_path)
    cur = con.cursor()
    # The anatomical dataset (T1) has ZLAYER=1 and a non-null ZPROJECT.
    cur.execute(
        "SELECT ZCACHEDWORLDTRANSFORM FROM ZDATASET WHERE ZLAYER = 1 AND ZPROJECT IS NOT NULL LIMIT 1;"
    )
    row = cur.fetchone()
    con.close()
    if not row or not row[0]:
        raise ValueError("ZCACHEDWORLDTRANSFORM introuvable dans ZDATASET.")
    return decode_matrix(row[0])


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
        description="Extract BrainSight sample position and create spherical NIfTI on T1."
    )
    parser.add_argument("--bsproj", required=True, help="Path to .bsproj file.")
    parser.add_argument("--sample", default="Sample 5", help="Sample name in ZSAMPLE.")
    parser.add_argument("--t1", required=True, help="Path to T1 NIfTI.")
    parser.add_argument(
        "--source",
        choices=["target", "coil"],
        default="target",
        help="ZTARGETPOSITION (cortical target) or ZPOSITION (coil position).",
    )
    parser.add_argument(
        "--out-dir",
        default="/Users/hippolyte.dreyfus/Desktop/_clonesa/clonesaTMS/extracted_targets",
    )
    parser.add_argument("--radius-mm", type=float, default=5.0, help="Sphere radius in mm.")
    args = parser.parse_args()

    # --- Load data ---
    con = sqlite3.connect(args.bsproj)
    cur = con.cursor()
    cur.execute(
        "SELECT ZNAME, ZPOSITION, ZTARGETPOSITION FROM ZSAMPLE WHERE ZNAME = ? LIMIT 1;",
        (args.sample,),
    )
    row = cur.fetchone()
    con.close()
    if not row:
        raise ValueError(f"Sample introuvable: {args.sample}")

    name, zposition, ztargetposition = row
    source_blob = ztargetposition if args.source == "target" else zposition
    M = decode_matrix(source_blob)
    if M is None:
        raise ValueError(f"Blob vide pour source={args.source}.")

    # BrainSight stores voxel position in the last column of the 4x4 matrix.
    vox_bs = M[:3, 3]

    # BrainSight world transform (voxel → LPS world mm).
    W_bs = read_brainsight_world_transform(args.bsproj)

    # Convert to T1 NIfTI voxel space.
    t1_img = nib.load(args.t1)
    vox_t1 = brainsight_vox_to_t1_vox(vox_bs, W_bs, t1_img.affine)

    w_ras = (W_bs @ np.append(vox_bs, 1.0))[:3]

    print(f"Sample           : {name}  (source: {args.source})")
    print(f"BrainSight vox   : {np.round(vox_bs, 3)}")
    print(f"World RAS  [mm]  : {np.round(w_ras, 3)}")
    print(f"T1 voxel         : {np.round(vox_t1, 3)}")

    shape = t1_img.shape[:3]
    inside = bool(np.all((vox_t1 >= 0) & (vox_t1 < np.array(shape))))
    print(f"Inside T1 volume : {inside}  (shape {shape})")
    if not inside:
        raise RuntimeError(
            "Centre hors du volume T1. Vérifiez que le .bsproj et la T1 correspondent au même sujet."
        )

    # Build sphere mask.
    mask = create_sphere_mask(shape, t1_img.affine, vox_t1, args.radius_mm)
    n_vox = int(mask.sum())
    print(f"Voxels sphere    : {n_vox}")

    # Save.
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{name.replace(' ', '_')}_{args.source}_r{args.radius_mm:g}mm.nii.gz"
    out_path = out_dir / fname

    sphere_img = nib.Nifti1Image(mask, t1_img.affine, t1_img.header)
    sphere_img.set_data_dtype(np.uint8)
    nib.save(sphere_img, str(out_path))
    print(f"Sauvegardé       : {out_path}")


if __name__ == "__main__":
    main()
