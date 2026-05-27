#!/usr/bin/env python3
"""
Bidsification des T1w et FLAIR depuis les derivatives stimSD-mathilde.
Structure source : STIM_SD_001_XXXX_YY_P / <date> / S_*_Sag_3D-T1w_BRAVO_1mm / v_*.nii
                                                      S_*_Sag_cube_FLAIR*     / v_*.nii

Destination : /Volumes/levy/raw/valerocabre/stimSD/Data/bids-mri_tmp/
  sub-XXXX/anat/sub-XXXX_T1w.nii
  sub-XXXX/anat/sub-XXXX_FLAIR.nii
"""
import re
import shutil
from pathlib import Path

SRC_ROOT = Path("/Volumes/levy/raw/valerocabre/stimSD/Data/derivatives/stimSD-mathilde/Database_STIM-SD_diffusion/STIM-SD_baseline")
DST_ROOT = Path("/Volumes/levy/raw/valerocabre/stimSD/Data/bids-mri_tmp")

# Pattern: STIM_SD_001_XXXX_YY_P → extract XXXX
FOLDER_RE = re.compile(r"^STIM_SD_\d{3}_(\d{4})_[A-Z]+_[A-Z]+$")

for patient_dir in sorted(SRC_ROOT.iterdir()):
    if not patient_dir.is_dir():
        continue
    m = FOLDER_RE.match(patient_dir.name)
    if not m:
        continue
    sub_id = m.group(1)
    bids_sub = f"sub-{sub_id}"

    date_dirs = [d for d in sorted(patient_dir.iterdir()) if d.is_dir()]
    if not date_dirs:
        print(f"[SKIP] no session dir: {patient_dir.name}")
        continue
    session_dir = date_dirs[0]

    sub_out = DST_ROOT / bids_sub / "anat"
    sub_out.mkdir(parents=True, exist_ok=True)

    # T1
    t1_series = sorted(session_dir.glob("S_*_Sag_3D-T1w_BRAVO_1mm"))
    if t1_series:
        t1_niis = list(t1_series[0].glob("v_*.nii"))
        if t1_niis:
            src = t1_niis[0]
            dst = sub_out / f"{bids_sub}_T1w.nii"
            shutil.copy2(src, dst)
            print(f"[OK] T1   : {bids_sub}  <-  {src.name}")
        else:
            print(f"[MISS] T1 : {bids_sub}  (no v_*.nii in {t1_series[0].name})")
    else:
        print(f"[MISS] T1 : {bids_sub}  (no T1w series in {session_dir.name})")

    # FLAIR
    flair_series = sorted(session_dir.glob("S_*_Sag_cube_FLAIR*"))
    if flair_series:
        flair_niis = list(flair_series[0].glob("v_*.nii"))
        if flair_niis:
            src = flair_niis[0]
            dst = sub_out / f"{bids_sub}_FLAIR.nii"
            shutil.copy2(src, dst)
            print(f"[OK] FLAIR: {bids_sub}  <-  {src.name}")
        else:
            print(f"[MISS] FLAIR: {bids_sub}  (no v_*.nii in {flair_series[0].name})")
    else:
        print(f"[MISS] FLAIR: {bids_sub}  (no FLAIR series in {session_dir.name})")
