"""
Display ALL BrainSight samples overlaid on T1 with a temporal color gradient.

Saves a PNG figure with 3 orthogonal views (axial, coronal, sagittal)
centred at the mean sample position, with a color gradient showing
the temporal order of stimulations.
"""

import argparse
import plistlib
import re
import sqlite3
import struct
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np


# ──────────────────────────────────────────────
# Coordinate helpers (same pipeline as 0-test-script.py)
# ──────────────────────────────────────────────

def decode_matrix(blob):
    """Decode a BrainSight plist blob → 4x4 numpy matrix."""
    if not blob:
        return None
    plist_data = plistlib.loads(blob)
    transform_data = plist_data["$objects"][2]
    values = struct.unpack("<16d", transform_data)
    return np.array(values, dtype=float).reshape(4, 4)


def read_brainsight_world_transform(bsproj_path):
    """Read ZCACHEDWORLDTRANSFORM from ZDATASET (voxel → RAS world mm)."""
    con = sqlite3.connect(bsproj_path)
    cur = con.cursor()
    cur.execute(
        "SELECT ZCACHEDWORLDTRANSFORM FROM ZDATASET "
        "WHERE ZLAYER = 1 AND ZPROJECT IS NOT NULL LIMIT 1;"
    )
    row = cur.fetchone()
    con.close()
    if not row or not row[0]:
        raise ValueError("ZCACHEDWORLDTRANSFORM introuvable dans ZDATASET.")
    return decode_matrix(row[0])


def brainsight_vox_to_t1_vox(vox_bs, W_bs, t1_affine):
    """BrainSight voxel → RAS world mm → T1 NIfTI voxel."""
    w_ras = (W_bs @ np.append(vox_bs, 1.0))[:3]
    return (np.linalg.inv(t1_affine) @ np.append(w_ras, 1.0))[:3]


def get_all_samples(bsproj_path):
    """Return all ZSAMPLE rows ordered by ZINDEX."""
    con = sqlite3.connect(bsproj_path)
    cur = con.cursor()
    cur.execute(
        "SELECT ZNAME, ZPOSITION, ZTARGETPOSITION FROM ZSAMPLE ORDER BY ZINDEX ASC;"
    )
    rows = cur.fetchall()
    con.close()
    return [
        {"name": r[0], "zposition": r[1], "ztargetposition": r[2]}
        for r in rows if r[0] is not None
    ]


def extract_subject_id(t1_path):
    match = re.search(r"(sub-[a-zA-Z0-9]+)", str(t1_path))
    return match.group(1) if match else "sub-unknown"


# ──────────────────────────────────────────────
# Plotting helpers
# ──────────────────────────────────────────────

def style_ax(ax, title, xlabel, ylabel):
    """Apply dark theme to an axis."""
    ax.set_facecolor("black")
    ax.set_title(title, color="white", fontsize=11, pad=6)
    ax.set_xlabel(xlabel, color="#888888", fontsize=8)
    ax.set_ylabel(ylabel, color="#888888", fontsize=8)
    ax.tick_params(colors="#666666", labelsize=7)
    for spine in ax.spines.values():
        spine.set_edgecolor("#444444")


def plot_view(ax, bg_slice, xs, ys, colors, dot_size, title, xlabel, ylabel):
    """
    Plot a single orthogonal view.

    bg_slice : 2D array (already transposed so imshow shows correct axes)
    xs, ys   : scatter coordinates in voxel space (match transposed slice axes)
    """
    vmax = np.percentile(bg_slice, 99.5)
    ax.imshow(bg_slice, cmap="gray", origin="lower",
              vmin=0, vmax=vmax, aspect="equal", interpolation="nearest")

    # Trajectory line (thin, low-opacity white)
    ax.plot(xs, ys, color="white", linewidth=0.5, alpha=0.25, zorder=4)

    # Scatter dots with temporal color gradient
    ax.scatter(xs, ys, c=colors, s=dot_size, linewidths=0.4,
               edgecolors="white", zorder=5, alpha=0.9)

    style_ax(ax, title, xlabel, ylabel)


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    try:
        import nibabel as nib
    except ModuleNotFoundError:
        raise ModuleNotFoundError("pip install nibabel")

    parser = argparse.ArgumentParser(
        description="Display all BrainSight samples on T1 with temporal color gradient."
    )
    parser.add_argument("--bsproj", required=True, help="Path to .bsproj file.")
    parser.add_argument("--t1",     required=True, help="Path to T1 NIfTI.")
    parser.add_argument(
        "--source", choices=["target", "coil"], default="target",
        help="ZTARGETPOSITION (cortical target) or ZPOSITION (coil position).",
    )
    parser.add_argument(
        "--out-dir",
        default="/Users/hippolyte.dreyfus/Desktop/_clonesa/clonesaTMS/figures",
    )
    parser.add_argument("--dot-size", type=float, default=18.0)
    parser.add_argument("--cmap",     default="plasma",
                        help="Matplotlib colormap for temporal gradient.")
    args = parser.parse_args()

    # ── Load T1 ──
    t1_img  = nib.load(args.t1)
    t1_data = t1_img.get_fdata()
    t1_aff  = t1_img.affine
    t1_shape = np.array(t1_data.shape[:3])

    W_bs       = read_brainsight_world_transform(args.bsproj)
    subject_id = extract_subject_id(args.t1)
    samples    = get_all_samples(args.bsproj)

    # ── Convert all samples to T1 voxel space ──
    valid = []
    for i, s in enumerate(samples):
        blob = s["ztargetposition"] if args.source == "target" else s["zposition"]
        if blob is None:
            continue
        try:
            M = decode_matrix(blob)
            if M is None:
                continue
            vox_t1 = brainsight_vox_to_t1_vox(M[:3, 3], W_bs, t1_aff)
            if not np.all((vox_t1 >= 0) & (vox_t1 < t1_shape)):
                print(f"  [skip] {s['name']} — hors volume")
                continue
            valid.append({"name": s["name"], "vox": vox_t1, "order": i})
        except Exception as e:
            print(f"  [err]  {s['name']} — {e}")

    if not valid:
        raise RuntimeError("Aucun sample valide trouvé.")

    print(f"\nSamples valides : {len(valid)} / {len(samples)}")

    # ── Centroid (slice centre for background) ──
    voxels   = np.array([s["vox"] for s in valid])
    centroid = np.clip(np.round(voxels.mean(axis=0)).astype(int), 0, t1_shape - 1)
    cx, cy, cz = centroid
    print(f"Centroïde       : vox {centroid}")

    # ── Color mapping (temporal order) ──
    orders = np.array([s["order"] for s in valid])
    norm   = mcolors.Normalize(vmin=orders.min(), vmax=orders.max())
    cmap   = cm.get_cmap(args.cmap)
    colors = [cmap(norm(s["order"])) for s in valid]

    # Sorted for the trajectory line
    valid_sorted = sorted(valid, key=lambda s: s["order"])

    # ── Build figure ──
    fig, axes = plt.subplots(1, 3, figsize=(19, 7))
    fig.patch.set_facecolor("black")

    # ---- Axial (z fixed) ----
    # imshow(data[:,:,z].T, origin='lower') → x-axis = vox_x, y-axis = vox_y
    bg_ax = t1_data[:, :, cz].T
    xs_ax = [s["vox"][0] for s in valid_sorted]
    ys_ax = [s["vox"][1] for s in valid_sorted]
    c_ax  = [cmap(norm(s["order"])) for s in valid_sorted]
    plot_view(axes[0], bg_ax, xs_ax, ys_ax, c_ax, args.dot_size,
              f"Axial  (z = {cz})", "x (vox)", "y (vox)")

    # ---- Coronal (y fixed) ----
    # imshow(data[:,y,:].T, origin='lower') → x-axis = vox_x, y-axis = vox_z
    bg_cor = t1_data[:, cy, :].T
    xs_cor = [s["vox"][0] for s in valid_sorted]
    ys_cor = [s["vox"][2] for s in valid_sorted]
    c_cor  = [cmap(norm(s["order"])) for s in valid_sorted]
    plot_view(axes[1], bg_cor, xs_cor, ys_cor, c_cor, args.dot_size,
              f"Coronal  (y = {cy})", "x (vox)", "z (vox)")

    # ---- Sagittal (x fixed) ----
    # imshow(data[x,:,:].T, origin='lower') → x-axis = vox_y, y-axis = vox_z
    bg_sag = t1_data[cx, :, :].T
    xs_sag = [s["vox"][1] for s in valid_sorted]
    ys_sag = [s["vox"][2] for s in valid_sorted]
    c_sag  = [cmap(norm(s["order"])) for s in valid_sorted]
    plot_view(axes[2], bg_sag, xs_sag, ys_sag, c_sag, args.dot_size,
              f"Sagittal  (x = {cx})", "y (vox)", "z (vox)")

    # ── Colorbar ──
    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=axes.tolist(), orientation="vertical",
                        fraction=0.018, pad=0.02, shrink=0.85)
    cbar.set_label("Sample index  (temporal order →)", color="white", fontsize=9)
    cbar.ax.yaxis.set_tick_params(color="white", labelsize=7)
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")

    fig.suptitle(
        f"{subject_id}   ·   {len(valid)} samples   ·   source: {args.source}\n"
        f"centred at vox {tuple(centroid)}",
        color="white", fontsize=13, y=1.01,
    )

    # ── Save ──
    out_dir = Path(args.out_dir) / subject_id
    out_dir.mkdir(parents=True, exist_ok=True)
    stem     = Path(args.bsproj).stem
    out_path = out_dir / f"{stem}_{args.source}_trajectory.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="black")
    plt.close(fig)
    print(f"Figure sauvegardée : {out_path}")


if __name__ == "__main__":
    main()
