#!/usr/bin/env python3
"""
Rassemble tous les TSV BIDS beh en un seul fichier par tâche (modalité),
en ajoutant les colonnes participant_id et session extraites du nom de fichier.

Output :
  /Volumes/.../beh-preprocess/task-asverbale_beh.tsv
  /Volumes/.../beh-preprocess/task-asvisuelle_beh.tsv
"""
import re
import pandas as pd
from pathlib import Path

BIDS_ROOT = Path("/Volumes/levy/raw/valerocabre/stimSD/Data/derivatives/bids/")
OUT_DIR   = Path("/Volumes/levy/raw/valerocabre/stimSD/Data/derivatives/beh-preprocess/")

TASKS = ["asverbale", "asvisuelle"]

# Regex pour parser le nom de fichier BIDS
# ex: sub-001001CM_ses-01_task-asverbale_beh.tsv
FNAME_RE = re.compile(r"^(sub-[^_]+)_(ses-[^_]+)_task-([^_]+)_beh\.tsv$")

print(f"🔎 Scan de {BIDS_ROOT} ...", flush=True)
tsv_files = sorted(BIDS_ROOT.glob("sub-*/ses-*/beh/*_beh.tsv"))
print(f"   {len(tsv_files)} fichiers TSV trouvés\n")

# Grouper par tâche
by_task: dict[str, list[pd.DataFrame]] = {t: [] for t in TASKS}

for tsv in tsv_files:
    m = FNAME_RE.match(tsv.name)
    if not m:
        print(f"  ⚠️  Nom inattendu, ignoré : {tsv.name}")
        continue

    subject, session, task = m.group(1), m.group(2), m.group(3)
    if task not in by_task:
        continue

    df = pd.read_csv(tsv, sep="\t", dtype=str)
    df.insert(0, "participant_id", subject)
    df.insert(1, "session", session)
    by_task[task].append(df)

OUT_DIR.mkdir(parents=True, exist_ok=True)

for task, frames in by_task.items():
    if not frames:
        print(f"  ⚠️  Aucun fichier pour task-{task}")
        continue

    combined = pd.concat(frames, ignore_index=True)
    out_file = OUT_DIR / f"task-{task}_beh.tsv"
    combined.to_csv(out_file, sep="\t", index=False)
    print(f"✓ {out_file.name}  ({len(combined)} lignes, {combined['participant_id'].nunique()} sujets)")
