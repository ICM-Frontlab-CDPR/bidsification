import argparse
import itertools
import plistlib
import sqlite3
import struct

import numpy as np


def parse_blob(blob):
    if not blob:
        return None, None
    plist_data = plistlib.loads(blob)
    transform_data = plist_data["$objects"][2]
    values = struct.unpack("<16d", transform_data)
    matrix = np.array(values, dtype=float).reshape(4, 4)
    pos = np.array([values[3], values[7], values[11]], dtype=float)
    return matrix, pos


def main():
    parser = argparse.ArgumentParser(description="Diagnostic BrainSight -> T1 coordinate space")
    parser.add_argument("--bsproj", required=True, help="Path to .bsproj")
    parser.add_argument("--sample", required=True, help="Sample name in ZSAMPLE")
    parser.add_argument("--t1", required=True, help="Path to T1 NIfTI")
    parser.add_argument("--radius-mm", type=float, default=5.0, help="Sphere radius in mm")
    args = parser.parse_args()

    try:
        import nibabel as nib
        import nibabel.orientations as nio
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("Le package 'nibabel' est requis: pip install nibabel") from exc

    con = sqlite3.connect(args.bsproj)
    cur = con.cursor()
    cur.execute("SELECT ZNAME, ZPOSITION, ZTARGETPOSITION FROM ZSAMPLE WHERE ZNAME = ? LIMIT 1;", (args.sample,))
    row = cur.fetchone()
    con.close()
    if not row:
        raise ValueError(f"Sample introuvable: {args.sample}")
    _, zposition, ztargetposition = row

    img = nib.load(args.t1)
    shape = np.array(img.shape[:3], dtype=int)
    affine = img.affine
    inv_affine = np.linalg.inv(affine)
    voxel_sizes = nib.affines.voxel_sizes(affine)
    radius_vox = args.radius_mm / voxel_sizes

    # --- Print T1 info ---
    axcodes = nio.aff2axcodes(affine)
    print("=" * 60)
    print(f"T1 shape : {tuple(shape.tolist())}")
    print(f"Voxel sizes [mm]: {np.round(voxel_sizes, 4)}")
    print(f"Orientation codes : {axcodes}  (should be RAS for standard NIfTI)")
    print("Affine:")
    for r in affine:
        print(f"  [{r[0]:10.4f} {r[1]:10.4f} {r[2]:10.4f} {r[3]:10.4f}]")
    print("=" * 60)

    def estimate_voxels(center_vox):
        bbox_min = np.floor(center_vox - radius_vox - 1).astype(int)
        bbox_max = np.ceil(center_vox + radius_vox + 1).astype(int)
        bbox_min = np.maximum(bbox_min, 0)
        bbox_max = np.minimum(bbox_max, shape - 1)
        if np.any(bbox_max < bbox_min):
            return 0
        xs = np.arange(bbox_min[0], bbox_max[0] + 1)
        ys = np.arange(bbox_min[1], bbox_max[1] + 1)
        zs = np.arange(bbox_min[2], bbox_max[2] + 1)
        xx, yy, zz = np.meshgrid(xs, ys, zs, indexing="ij")
        d2 = (
            ((xx - center_vox[0]) / radius_vox[0]) ** 2
            + ((yy - center_vox[1]) / radius_vox[1]) ** 2
            + ((zz - center_vox[2]) / radius_vox[2]) ** 2
        )
        return int((d2 <= 1.0).sum())

    for source_name, blob in [("coil (ZPOSITION)", zposition), ("target (ZTARGETPOSITION)", ztargetposition)]:
        matrix, pos_mm = parse_blob(blob)
        if matrix is None:
            print(f"\n[{source_name}] absent\n")
            continue

        print(f"\n[{source_name}]")
        print(f"  Position extraite [mm] (last col): {np.round(pos_mm, 3)}")

        # --- Candidate 1: BrainSight position directly in NIfTI world space (RAS) ---
        vox_ras = (inv_affine @ np.append(pos_mm, 1.0))[:3]
        inside_ras = bool(np.all((vox_ras >= 0) & (vox_ras < shape)))
        nvox_ras = estimate_voxels(vox_ras)
        print(f"\n  [A] Interpretation RAS world (inv_affine @ pos):")
        print(f"      vox={np.round(vox_ras,2)} inside={inside_ras} est_nvox={nvox_ras}")

        # --- Candidate 2: BrainSight in LPS (DICOM) -> convert to RAS first ---
        pos_lps2ras = pos_mm * np.array([-1, -1, 1])
        vox_lps = (inv_affine @ np.append(pos_lps2ras, 1.0))[:3]
        inside_lps = bool(np.all((vox_lps >= 0) & (vox_lps < shape)))
        nvox_lps = estimate_voxels(vox_lps)
        print(f"\n  [B] Interpretation LPS->RAS (negate X,Y then inv_affine):")
        print(f"      pos_RAS={np.round(pos_lps2ras,2)} vox={np.round(vox_lps,2)} inside={inside_lps} est_nvox={nvox_lps}")

        # --- Candidate 3: direct mm from voxel corner (no affine, divide by voxel sizes) ---
        vox_direct = pos_mm / voxel_sizes
        inside_direct = bool(np.all((vox_direct >= 0) & (vox_direct < shape)))
        nvox_direct = estimate_voxels(vox_direct)
        world_direct = (affine @ np.append(vox_direct, 1.0))[:3]
        print(f"\n  [C] Direct mm-from-corner (pos / voxel_sizes):")
        print(f"      vox={np.round(vox_direct,2)} inside={inside_direct} est_nvox={nvox_direct}")
        print(f"      -> world-space via T1 affine: {np.round(world_direct,2)}")

        # --- Candidate 4: brute-force 8 axis flips on the direct-mm-from-corner ---
        print(f"\n  [D] Brute-force axis flips (direct-mm-from-corner):")
        print(f"      (shape={tuple(shape.tolist())})")
        for signs in itertools.product([1, -1], repeat=3):
            flipped = np.array(signs, dtype=float) * vox_direct
            flipped_shifted = np.where(np.array(signs) == -1, (shape - 1) + flipped, flipped)
            inside_f = bool(np.all((flipped_shifted >= 0) & (flipped_shifted < shape)))
            nvox_f = estimate_voxels(flipped_shifted)
            world_f = (affine @ np.append(flipped_shifted, 1.0))[:3]
            if inside_f:
                flip_label = "(" + ",".join(("+" if s == 1 else "-") for s in signs) + ")"
                print(
                    f"      flip {flip_label}: vox={np.round(flipped_shifted,1)} "
                    f"est_nvox={nvox_f} world={np.round(world_f,1)}"
                )

        print()


if __name__ == "__main__":
    main()
