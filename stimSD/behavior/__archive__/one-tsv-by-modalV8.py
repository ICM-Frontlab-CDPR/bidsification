#!/usr/bin/env python3
"""
Rassemble tous les TSV BIDS beh (bids-V8-eCRF) en un seul fichier par tâche,
en ajoutant les colonnes participant_id et session extraites du nom de fichier.

Output :
  /Volumes/.../beh/task-<label>_beh_eCRF_V8.tsv   (toutes les tâches V8)
"""
import logging
import re
import pandas as pd
from datetime import datetime
from pathlib import Path

BIDS_ROOT = Path("/Volumes/levy/raw/valerocabre/stimSD/Data/bids-V8-eCRF/")
OUT_DIR   = Path("/Volumes/levy/raw/valerocabre/stimSD/Data/derivatives/beh/")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_LOG_DIR = Path("/Users/hippolyte.dreyfus/Documents/bidsification/stimSD/_log")
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_log_file = _LOG_DIR / f"one-tsv-by-modalV8_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    handlers=[
        logging.FileHandler(_log_file, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger()
log.info(f"📝 Log : {_log_file}\n")

# Toutes les tâches produites par bids-behV6.py
TASKS = [
    "asverbale",
    "asvisuelle",
    "exeverb",
    "exevisu",
    "fluencecat",
    "fluenceverb",
    "dccat",
    "deno",
    "lecture",
    "bip",
]

# Regex pour parser le nom de fichier BIDS
# ex: sub-001001CM_ses-01_task-asverbale_beh.tsv
FNAME_RE = re.compile(r"^(sub-[^_]+)_(ses-[^_]+)_task-([^_]+)_beh\.tsv$")

log.info(f"🔎 Scan de {BIDS_ROOT} ...")
tsv_files = sorted(BIDS_ROOT.glob("sub-*/ses-*/beh/*_beh.tsv"))
log.info(f"   {len(tsv_files)} fichiers TSV trouvés\n")

# Grouper par tâche
by_task: dict[str, list[pd.DataFrame]] = {t: [] for t in TASKS}

for tsv in tsv_files:
    m = FNAME_RE.match(tsv.name)
    if not m:
        log.warning(f"  ⚠️  Nom inattendu, ignoré : {tsv.name}")
        continue

    subject, session, task = m.group(1), m.group(2), m.group(3)
    if task not in by_task:
        log.debug(f"  ⏭️  Tâche inconnue '{task}', ignorée : {tsv.name}")
        continue

    df = pd.read_csv(tsv, sep="\t", dtype=str)
    group = "temoin" if subject.upper().endswith("-T") else "patient"
    df.insert(0, "participant_id", subject)
    df.insert(1, "session", session)
    df.insert(2, "group", group)
    by_task[task].append(df)

OUT_DIR.mkdir(parents=True, exist_ok=True)

for task in TASKS:
    frames = by_task[task]
    if not frames:
        log.info(f"  ─  task-{task} : aucun fichier trouvé")
        continue

    combined = pd.concat(frames, ignore_index=True)
    out_file = OUT_DIR / f"task-{task}_beh_eCRF_V8.tsv"
    combined.to_csv(out_file, sep="\t", index=False)
    log.info(
        f"✓ {out_file.name}  "
        f"({len(combined)} lignes, {combined['participant_id'].nunique()} sujets)"
    )
log.info(f"\n📝 Log sauvegardé dans : {_log_file}")
