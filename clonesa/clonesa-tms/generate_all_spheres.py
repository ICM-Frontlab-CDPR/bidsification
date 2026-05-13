"""
Generate all candidate sphere NIfTIs from a BrainSight .bsproj sample.

One file per (source x axis_flip) combination that falls inside the T1 volume.
Load them all in your viewer alongside the T1 to identify which one is correct.
"""

import argparse
import itertools
import plistlib
import sqlite3
import struct
from pathlib import Path

import numpy as np


def parse_blob(blob):
    if not blob:
        return None
    plist_data = plistlib.loads(blob)
    transform_data = plist_data["$objects"][2]
    values = struct.unpack("<16d", transform_data)
    return np.array([values[3], values[7], values[11]], dtype=float)


def make_sphere(shape, center_vox, radius_vox):
    bbox_min = np.floor(center_vox - radius_vox - 1).astype(int)
    bbox_max = np.ceil(center_vox + radius_vox + 1).astype(int)
    bbox_min = np.maximum(bbox_min, 0)
    bbox_max = np.minimum(bbox_max, np.array(shape) - 1)
    if np.any(bbox_max < bbox_min):
        return None

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
    mask[
        bbox_min[0]: bbox_max[0] + 1,
        bbox_min[1]: bbox_max[1] + 1,
        bbox_min[2]: bbox_max[2] + 1,
    ] = (d2 <= 1.0).astype(np.uint8)
    return mask


def main():
    parser = argparse.ArgumentParser(description="Generate all candidate spheres for visual inspection.")
    parser.add_argument("--bsproj", required=True)
    parser.add_argument("--sample", required=True)
    parser.add_argument("--t1", required=True)
    parser.add_argument(
        "--out-dir",
        default="/Users/hippolyte.dreyfus/Desktop/_clonesa/clonesaTMS/extracted_targets",
    )
    parser.add_argument("--radius-mm", type=float, default=5.0)
    args = parser.parse_args()

    try:
        import nibabel as nib
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("pip install nibabel") from exc

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

    img = nib.load(args.t1)
    shape = img.shape[:3]
    affine = img.affine
    voxel_sizes = nib.affines.voxel_sizes(affine)
    radius_vox = args.radius_mm / voxel_sizes

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sample_tag = name.replace(" ", "_")

    saved = []

    for source_name, blob in [("coil", zposition), ("target", ztargetposition)]:
        pos_mm = parse_blob(blob)
        if pos_mm is None:
            print(f"[{source_name}] blob absent, skipped.")
            continue

        # Base voxel position: direct mm-from-corner (pos / voxel_sizes)
        base_vox = pos_mm / voxel_sizes

        for signs in itertools.product([1, -1], repeat=3):
            s = np.array(signs, dtype=float)
            # Mirror axes with sign=-1 around the volume center
            center_vox = np.where(s == -1, (np.array(shape) - 1) + s * base_vox, s * base_vox)

            inside = bool(np.all((center_vox >= 0) & (center_vox < np.array(shape))))
            if not inside:
                continue

            mask = make_sphere(shape, center_vox, radius_vox)
            if mask is None or mask.sum() == 0:
                continue

            world_mm = (affine @ np.append(center_vox, 1.0))[:3]
            flip_label = "".join("p" if s == 1 else "n" for s in signs)  # p=plus n=minus
            fname = f"{sample_tag}_{source_name}_flip{flip_label}_r{args.radius_mm:g}mm.nii.gz"
            out_path = out_dir / fname

            sphere_img = nib.Nifti1Image(mask, affine, img.header)
            sphere_img.set_data_dtype(np.uint8)
            nib.save(sphere_img, str(out_path))

            print(
                f"[OK] {fname}\n"
                f"     vox={np.round(center_vox,1)} "
                f"world_RAS={np.round(world_mm,1)} nvox={int(mask.sum())}"
            )
            saved.append(fname)

    print(f"\n{len(saved)} spheres sauvees dans: {out_dir}")
    print("Chargez-les dans votre viewer avec la T1 pour identifier la bonne.")


if __name__ == "__main__":
    main()
