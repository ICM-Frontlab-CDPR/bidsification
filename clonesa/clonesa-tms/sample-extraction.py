"""
Extract ALL BrainSight sample positions and create spherical NIfTI masks on a T1,
or export them as BIDS-compliant TSV files (with full orientation), or both.
Outputs are organized by subject (extracted from the T1 path).

Coordinate pipeline (correct):
  BrainSight voxel
    → BrainSight world (RAS) via ZCACHEDWORLDTRANSFORM
    → T1 NIfTI voxel (via inverse T1 affine)
    
python /Users/hippolyte.dreyfus/Documents/bidsification/clonesa/clonesa-tms/0-test-script.py \    
  --bsproj /Volumes/levy/raw/valerocabre/clonesa/Data/ClonesaTMS/sourcedata/__mri__/CLONESA_002_0001/Clonesa_G2_001.bsproj \
  --t1 /Volumes/levy/raw/valerocabre/clonesa/Data/ClonesaTMS/bids_mri/sub-0001/anat/sub-0001_T1w.nii.gz \
  --source target
"""

import argparse
import json
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


def extract_orientation_ras(M_bs, W_bs):
    """
    Convert the BrainSight coil/target orientation to RAS world space.

    M_bs[:3, :3] is the rotation matrix in BrainSight voxel space.
    W_bs[:3, :3] maps BrainSight voxel axes → RAS mm (includes voxel-size scaling).

    Steps:
      1. Apply the world-transform rotation  : R_unnorm = W_bs[:3,:3] @ M_bs[:3,:3]
      2. Normalise columns to remove voxel-size scaling, yielding a pure rotation.
    """
    R_unnorm = W_bs[:3, :3] @ M_bs[:3, :3]
    col_norms = np.linalg.norm(R_unnorm, axis=0, keepdims=True)
    col_norms[col_norms == 0] = 1.0
    return R_unnorm / col_norms


def save_samples_as_txt(samples_data, out_dir_txt, subject_id):
    """
    Save samples as a BIDS-compatible TSV + JSON sidecar.

    Parameters
    ----------
    samples_data : list of dict
        Each dict must contain: name, source, x, y, z (RAS mm), R_ras (3×3 ndarray).
    out_dir_txt : str or Path
        Root output directory for text files.
    subject_id : str
        E.g. 'sub-0001'.

    Returns
    -------
    Path to the written TSV file.
    """
    sub_dir = Path(out_dir_txt) / subject_id
    sub_dir.mkdir(parents=True, exist_ok=True)

    tsv_path  = sub_dir / f"{subject_id}_samples.tsv"
    json_path = sub_dir / f"{subject_id}_samples.json"

    # ---- TSV ----
    header = [
        "sample_name", "source",
        "x", "y", "z",
        "rot_00", "rot_01", "rot_02",
        "rot_10", "rot_11", "rot_12",
        "rot_20", "rot_21", "rot_22",
    ]
    with open(tsv_path, "w") as f:
        f.write("\t".join(header) + "\n")
        for s in samples_data:
            R = s["R_ras"]
            row = [
                s["name"], s["source"],
                f"{s['x']:.4f}", f"{s['y']:.4f}", f"{s['z']:.4f}",
                f"{R[0, 0]:.6f}", f"{R[0, 1]:.6f}", f"{R[0, 2]:.6f}",
                f"{R[1, 0]:.6f}", f"{R[1, 1]:.6f}", f"{R[1, 2]:.6f}",
                f"{R[2, 0]:.6f}", f"{R[2, 1]:.6f}", f"{R[2, 2]:.6f}",
            ]
            f.write("\t".join(row) + "\n")

    # ---- JSON sidecar ----
    sidecar = {
        "CoordinateSystem": "RAS",
        "CoordinateUnits": "mm",
        "CoordinateSystemDescription": (
            "Right-Anterior-Superior world coordinates derived from the BrainSight "
            "ZCACHEDWORLDTRANSFORM affine."
        ),
        "Columns": {
            "sample_name": "BrainSight sample name (ZNAME).",
            "source": (
                "'target' = cortical target (ZTARGETPOSITION); "
                "'coil'   = coil position (ZPOSITION)."
            ),
            "x": "RAS X coordinate in mm.",
            "y": "RAS Y coordinate in mm.",
            "z": "RAS Z coordinate in mm.",
            "rot_ij": (
                "Element [i, j] of the 3×3 rotation matrix in RAS world space. "
                "Columns correspond to the X, Y, Z axes of the coil/target frame "
                "expressed in RAS mm (unit vectors)."
            ),
        },
    }
    with open(json_path, "w") as f:
        json.dump(sidecar, f, indent=2)

    return tsv_path


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
        "--save-as",
        choices=["nifti", "txt", "both"],
        default="nifti",
        help=(
            "Output format: 'nifti' = spherical NIfTI masks, "
            "'txt' = BIDS-compliant TSV with position + orientation, "
            "'both' = save both formats."
        ),
    )
    parser.add_argument(
        "--out-dir",
        default="/Users/hippolyte.dreyfus/Desktop/_clonesa/clonesaTMS/extracted_targets",
        help="Output directory for NIfTI spheres (used with --save-as nifti or both).",
    )
    parser.add_argument(
        "--out-dir-txt",
        default="/Users/hippolyte.dreyfus/Desktop/_clonesa/clonesaTMS/brainsight",
        help="Output directory for TSV text files (used with --save-as txt or both).",
    )
    parser.add_argument("--radius-mm", type=float, default=5.0, help="Sphere radius in mm (NIfTI only).")
    args = parser.parse_args()

    # --- Setup ---
    nib_t1 = nib.load(args.t1)
    t1_shape = nib_t1.shape[:3]
    t1_affine = nib_t1.affine
    W_bs = read_brainsight_world_transform(args.bsproj)
    subject_id = extract_subject_id(args.t1)

    save_nifti = args.save_as in ("nifti", "both")
    save_txt   = args.save_as in ("txt",   "both")

    # Output directories organised by subject
    if save_nifti:
        out_dir = Path(args.out_dir) / subject_id
        out_dir.mkdir(parents=True, exist_ok=True)
    if save_txt:
        out_dir_txt = Path(args.out_dir_txt) / subject_id
        out_dir_txt.mkdir(parents=True, exist_ok=True)

    # --- Detect all samples ---
    samples = get_all_samples(args.bsproj)
    print(f"\n{'='*60}")
    print(f"Subject          : {subject_id}")
    print(f"Samples detected : {len(samples)}")
    print(f"Source           : {args.source}")
    print(f"Save as          : {args.save_as}")
    if save_nifti:
        print(f"NIfTI dir        : {out_dir}")
    if save_txt:
        print(f"TSV dir          : {out_dir_txt}")
    print(f"{'='*60}\n")

    sources = ["target", "coil"] if args.source == "both" else [args.source]

    n_ok, n_skip, n_err = 0, 0, 0
    txt_rows = []  # accumulated rows for TSV output

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
                w_ras  = (W_bs @ np.append(vox_bs, 1.0))[:3]
                R_ras  = extract_orientation_ras(M, W_bs)

                inside = bool(np.all((vox_t1 >= 0) & (vox_t1 < np.array(t1_shape))))
                if not inside:
                    print(f"  [SKIP] {name} ({source}) — hors volume T1  vox={np.round(vox_t1, 1)}")
                    n_skip += 1
                    continue

                # ---- NIfTI sphere ----
                if save_nifti:
                    mask  = create_sphere_mask(t1_shape, t1_affine, vox_t1, args.radius_mm)
                    n_vox = int(mask.sum())
                    fname = f"{name.replace(' ', '_')}_{source}_r{args.radius_mm:g}mm.nii.gz"
                    sphere_img = nib.Nifti1Image(mask, t1_affine, nib_t1.header)
                    sphere_img.set_data_dtype(np.uint8)
                    nib.save(sphere_img, str(out_dir / fname))
                else:
                    n_vox = None

                # ---- TSV row ----
                if save_txt:
                    txt_rows.append({
                        "name":   name,
                        "source": source,
                        "x":      w_ras[0],
                        "y":      w_ras[1],
                        "z":      w_ras[2],
                        "R_ras":  R_ras,
                    })

                nvox_str = f"  nvox={n_vox}" if n_vox is not None else ""
                print(f"  [OK]   {name} ({source})  RAS={np.round(w_ras, 1)}  vox_T1={np.round(vox_t1, 1)}{nvox_str}")
                n_ok += 1

            except Exception as e:
                print(f"  [ERR]  {name} ({source}) — {e}")
                n_err += 1

    # ---- Write TSV once, after all samples have been processed ----
    if save_txt and txt_rows:
        tsv_path = save_samples_as_txt(txt_rows, args.out_dir_txt, subject_id)
        print(f"  [TSV]  {len(txt_rows)} ligne(s) sauvegardées → {tsv_path}")

    print(f"\n{'='*60}")
    print(f"Terminé : {n_ok} OK  |  {n_skip} skippés  |  {n_err} erreurs")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
