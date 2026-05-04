#!/usr/bin/env python3
"""
Switch participant_id in aggregated beh TSVs from Excel-file-based IDs
to eCRF-based IDs, using the randomization list mapping.

Input TSVs  (beh-preprocess):
    task-asverbale_beh.tsv
    task-asvisuelle_beh.tsv

Output TSVs (same folder, eCRF in filename):
    task-asverbale_eCRF_beh.tsv
    task-asvisuelle_eCRF_beh.tsv
"""

import re
import pandas as pd
from pathlib import Path

# ---- Paths ----
MAPPING_XLSX = Path(
    "/Volumes/levy/raw/valerocabre/stimSD/Data/"
    "STIM_SD_Randomization_List_Nov_2025_Full.xlsx"
)
BEH_DIR = Path(
    "/Volumes/levy/raw/valerocabre/stimSD/Data/derivatives/beh-preprocess"
)
TSV_FILES = [
    BEH_DIR / "task-asverbale_beh.tsv",
    BEH_DIR / "task-asvisuelle_beh.tsv",
]

# ---- Same ID generation as bids-behV2.py ----
def subject_from_stem(stem: str) -> str:
    """'001-009-LM'  ->  'sub-001009LM'"""
    return "sub-" + re.sub(r"[^a-zA-Z0-9]", "", stem.strip())


# ---- Build mapping dict: excel_sub_id -> ecrf_sub_id ----
print(f"Reading mapping from {MAPPING_XLSX.name} ...")
mapping_df = pd.read_excel(MAPPING_XLSX)

# Strip whitespace from column names and values
mapping_df.columns = mapping_df.columns.str.strip()
mapping_df["Excel File Name"] = mapping_df["Excel File Name"].astype(str).str.strip()
mapping_df["eCRF Name"]       = mapping_df["eCRF Name"].astype(str).str.strip()

sub_mapping = {
    subject_from_stem(row["Excel File Name"]): subject_from_stem(row["eCRF Name"])
    for _, row in mapping_df.iterrows()
    if row["Excel File Name"] not in ("nan", "") and row["eCRF Name"] not in ("nan", "")
}

print(f"  {len(sub_mapping)} participant mappings loaded")
for k, v in sorted(sub_mapping.items()):
    print(f"    {k}  ->  {v}")
print()

# ---- Process each TSV ----
for tsv_path in TSV_FILES:
    if not tsv_path.exists():
        print(f"SKIP (not found): {tsv_path}")
        continue

    df = pd.read_csv(tsv_path, sep="\t")

    before = set(df["participant_id"].unique())
    df["participant_id"] = df["participant_id"].map(
        lambda pid: sub_mapping.get(pid, pid)
    )
    after = set(df["participant_id"].unique())

    unmapped = [p for p in before if sub_mapping.get(p, p) == p and p not in sub_mapping]
    if unmapped:
        print(f"  WARNING: {len(unmapped)} participant_id(s) had no mapping entry:")
        for p in sorted(unmapped):
            print(f"    {p}")

    out_path = tsv_path.with_name(tsv_path.stem.replace("_beh", "_eCRF_beh") + ".tsv")
    df.to_csv(out_path, sep="\t", index=False)
    print(f"Written: {out_path.name}  ({len(df)} rows, {len(after)} unique participants)")

print("\nDone.")
