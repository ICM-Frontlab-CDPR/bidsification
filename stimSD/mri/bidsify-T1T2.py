#!/usr/bin/env python3
"""
Bidsification des T1w et FLAIR depuis les sourcedata stimSD.
Découverte des fichiers directement sur disque par pattern glob,
sans dépendre du CSV (qui contient des chemins avec espaces).

Patterns :
  T1   : *Sag_3D-T1w_BRAVO_1mm_*.nii
  FLAIR: *Sag_cube_FLAIR_*.nii

Destination : /Volumes/levy/raw/valerocabre/stimSD/Data/bids-mri_tmp/
  sub-XXXX/anat/sub-XXXX_T1w.nii
  sub-XXXX/anat/sub-XXXX_FLAIR.nii
"""
import re
import shutil
from pathlib import Path

SRC_ROOT = Path("/network/iss/levy/raw/valerocabre/stimSD/Data/sourcedata/1_DATA/1_RAW/1_PATIENTS")
DST_ROOT = Path("/network/iss/levy/raw/valerocabre/stimSD/Data/bids-mri_tmp")

# Pattern pour extraire le numéro de sujet depuis le dossier "001-XXXX-YYY"
FOLDER_RE = re.compile(r"^\d{3}-(\d{4})-[A-Z]+$")

for patient_dir in sorted(SRC_ROOT.iterdir()):
    if not patient_dir.is_dir():
        continue
    m = FOLDER_RE.match(patient_dir.name)
    if not m:
        continue
    sub_id = m.group(1)
    bids_sub = f"sub-{sub_id}"

    nifti_dir = patient_dir / "2_TEP-IRM" / "Baseline" / "Nifti"
    if not nifti_dir.exists():
        print(f"[SKIP] no Nifti dir: {nifti_dir}")
        continue

    sub_out = DST_ROOT / bids_sub / "anat"
    sub_out.mkdir(parents=True, exist_ok=True)

    # T1
    t1_matches = list(nifti_dir.glob("*Sag_3D-T1w_BRAVO_1mm_*.nii"))
    if t1_matches:
        src = t1_matches[0]
        dst = sub_out / f"{bids_sub}_T1w.nii"
        shutil.copy2(src, dst)
        print(f"[OK] T1   : {bids_sub}  <-  {src.name}")
    else:
        print(f"[MISS] T1 : {bids_sub}  (no match in {nifti_dir})")

    # FLAIR
    flair_matches = list(nifti_dir.glob("*Sag_cube_FLAIR_*.nii"))
    if flair_matches:
        src = flair_matches[0]
        dst = sub_out / f"{bids_sub}_FLAIR.nii"
        shutil.copy2(src, dst)
        print(f"[OK] FLAIR: {bids_sub}  <-  {src.name}")
    else:
        print(f"[MISS] FLAIR: {bids_sub}  (no match in {nifti_dir})")
