#!/bin/bash

BSPROJ_ROOT="/Volumes/levy/raw/valerocabre/clonesa/Data/ClonesaTMS/sourcedata/__mri__"
BIDS_ROOT="/Volumes/levy/raw/valerocabre/clonesa/Data/ClonesaTMS/bids_mri"
SCRIPT="/Users/hippolyte.dreyfus/Documents/bidsification/clonesa/clonesa-tms/sample-extraction.py"

find "$BSPROJ_ROOT" -name "*.bsproj" | while read -r bsproj; do
    # Extract subject folder name (e.g. CLONESA_002_0001)
    subj_folder=$(basename "$(dirname "$bsproj")")

    # Extract 4-digit subject number from folder name (e.g. 0001 from CLONESA_002_0001)
    subj_num=$(echo "$subj_folder" | grep -oE '[0-9]{4}$')

    if [ -z "$subj_num" ]; then
        echo "[WARN] Could not extract subject number from: $subj_folder — skipping"
        continue
    fi

    t1="${BIDS_ROOT}/sub-${subj_num}/anat/sub-${subj_num}_T1w.nii.gz"

    if [ ! -f "$t1" ]; then
        echo "[WARN] T1 not found for sub-${subj_num}: $t1 — skipping"
        continue
    fi

    echo "=============================="
    echo "Processing: $bsproj"
    echo "Subject   : sub-${subj_num}"
    echo "T1        : $t1"
    echo "=============================="

    python "$SCRIPT" \
        --bsproj "$bsproj" \
        --t1 "$t1" \
        --source both \
        --save-as both

done