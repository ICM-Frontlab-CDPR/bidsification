#!/usr/bin/env python3
import re
import pandas as pd
from pathlib import Path

# Chemins
PATIENTS_DIR = Path("/Volumes/levy/raw/valerocabre/stimSD/Data/sourcedata/1_DATA/1_RAW/1_PATIENTS")
BIDS_ROOT = Path("/Volumes/levy/raw/valerocabre/stimSD/Data/derivatives/bidsV4/")
RANDO_XLSX = Path("/Volumes/levy/raw/valerocabre/stimSD/Data/STIM_SD_Randomization_List_Nov_2025_Full.xlsx")

# Charger le mapping Excel File Name -> eCRF Name
_rando = pd.read_excel(RANDO_XLSX)
_rando.columns = _rando.columns.str.strip()
_rando["Excel File Name"] = _rando["Excel File Name"].astype(str).str.strip()
_rando["eCRF Name"]       = _rando["eCRF Name"].astype(str).str.strip()
ECRF_MAP: dict[str, str] = {
    re.sub(r"[^a-zA-Z0-9]", "", row["Excel File Name"]).lower(): row["eCRF Name"]
    for _, row in _rando.iterrows()
    if row["Excel File Name"] not in ("nan", "") and row["eCRF Name"] not in ("nan", "")
}

# Exceptions manuelles : xlsx stem normalisé (sans ponctuation, lowercase) -> eCRF Name
# Ces fichiers ont des noms mal formés qui ne matchent pas la liste de randomisation.
MANUAL_EXCEPTIONS: dict[str, str] = {
    "001001cm":       "001-0001-CMC",  # 001-001-CM         -> 001-0001-CMC
    "001003ls":       "001-0005-LS",   # 001-003-LS         -> 001-0005-LS
    "001004ma":       "001-0004-MA",   # 001-004-MA         -> 001-0004-MA
    "0001005ls":      "001-0005-LS",   # 0_001-005-LS       -> 001-0005-LS
    "01006cv":        "001-0006-CV",   # 01-006-CV          -> 001-0006-CV
    "001008ld":       "001-0008-LD",   # 001-008-LD         -> 001-0008-LD
    "001009lm":       "001-0010-LM",   # 001-009-LM         -> 001-0010-LM
    "010024llm":      "001-0022-LM",   # 01-0024LLM         -> 001-0022-LM
    "0010032eg3der":  "001-0030-GE",   # 001-0032-EG (3)der -> 001-0030-GE
}

# Les exceptions manuelles priment sur le mapping automatique
ECRF_MAP.update(MANUAL_EXCEPTIONS)

# Feuilles cibles -> label BIDS task
TASK_SHEETS = {
    "AS verbale":   "asverbale",
    "AS visuelle":  "asvisuelle",
}

# Colonnes attendues dans chaque bloc (dans l'ordre)
BLOCK_COLS = [
    "participant_id",
    "version",
    "session",
    "trial",
    "target",
    "condition_target",
    "accuracy",
    "response_time",
]

TASK_SHEETS = {
    "AS verbale":  "asverbale",
    "AS visuelle": "asvisuelle",
}

# Colonnes attendues dans chaque bloc (dans l'ordre)
BLOCK_COLS = [
    "participant_id",
    "version",
    "session",
    "trial",
    "target",
    "condition_target",
    "accuracy",
    "response_time",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def subject_from_stem(stem: str) -> str:
    """001-009-LM  ->  sub-001009LM"""
    return "sub-" + re.sub(r"[^a-zA-Z0-9]", "", stem)


def subject_from_ecrf(ecrf_name: str) -> str:
    """'001-0001-CMC'  ->  'sub-001-0001-CMC'  (tirets conservés)"""
    return "sub-" + ecrf_name.strip()


def session_label(value) -> str:
    """'1' / 'Session 2' / NaN  ->  'ses-01' / 'ses-02' / 'ses-00'"""
    if pd.isna(value):
        return "ses-00"
    m = re.search(r"(\d+)", str(value))
    return f"ses-{int(m.group(1)):02d}" if m else "ses-00"


def find_block_starts(columns) -> list[int]:
    """Indices des colonnes dont le header commence par 'PAT' (insensible à la casse)."""
    return [i for i, c in enumerate(columns) if re.match(r"pat", str(c).strip(), re.I)]


def read_blocks(df: pd.DataFrame) -> list[pd.DataFrame]:
    """
    Découpe le DataFrame en blocs de 8 colonnes côte-à-côte,
    chacun commençant par une colonne PAT...
    Retourne une liste de DataFrames nettoyés avec les colonnes BLOCK_COLS.
    """
    cols = list(df.columns)
    starts = find_block_starts(cols)
    blocks = []

    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(cols)
        chunk = df.iloc[:, start:end].copy()

        # On ne garde que les 8 premières colonnes utiles
        chunk = chunk.dropna(axis=1, how="all")
        if chunk.shape[1] < len(BLOCK_COLS):
            continue  # bloc incomplet, skip

        chunk = chunk.iloc[:, :len(BLOCK_COLS)].copy()
        chunk.columns = BLOCK_COLS
        chunk = chunk.dropna(how="all")

        # Garder uniquement les lignes dont 'trial' est numérique (élimine les métadonnées)
        chunk = chunk[pd.to_numeric(chunk["trial"], errors="coerce").notna()]
        if chunk.empty:
            continue

        # Extraire la session avant de supprimer la colonne
        ses_values = chunk["session"].dropna().unique()
        session_val = ses_values[0] if len(ses_values) > 0 else None

        # Supprimer les colonnes déjà encodées dans le nom de fichier BIDS
        chunk = chunk.drop(columns=["participant_id", "version", "session"])
        chunk = chunk.reset_index(drop=True)

        blocks.append((session_val, chunk))

    return blocks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Trouver tous les XLSX : 1 ou 2 niveaux sous chaque dossier patient
print(f"🔎 Scan du dossier {PATIENTS_DIR} ...", flush=True)
xlsx_files = sorted(
    f
    for pat_dir in PATIENTS_DIR.iterdir()
    if pat_dir.is_dir()
    for f in list(pat_dir.glob("*.xlsx")) + list(pat_dir.glob("*/*.xlsx"))
    if not f.name.startswith("~$") and not f.name.startswith("._")
)

print(f"🔍 {len(xlsx_files)} fichiers XLSX trouvés")
for f in xlsx_files:
    print(f"  - {f.parent.name}/{f.name}")
print()

response = input(f"⚠️  Voulez-vous convertir ces {len(xlsx_files)} fichiers en BIDS beh? (o/n): ")
if response.lower() not in ["o", "oui", "y", "yes"]:
    print("❌ Conversion annulée.")
    exit(0)

overwrite = input("🔄 Écraser les fichiers déjà existants? (o/n): ").lower() in ["o", "oui", "y", "yes"]
print()

files_processed = 0
files_skipped = 0
files_failed = 0

for xlsx in xlsx_files:
    stem_norm = re.sub(r"[^a-zA-Z0-9]", "", xlsx.stem).lower()
    ecrf_name = ECRF_MAP.get(stem_norm)
    if ecrf_name:
        subject = subject_from_ecrf(ecrf_name)
    else:
        print(f"  ⚠️  Pas de correspondance eCRF pour '{xlsx.stem}', fichier ignoré")
        files_failed += 1
        continue
    print(f"📂 {subject}  ({xlsx.parent.name}/{xlsx.name})", flush=True)

    try:
        print(f"  📖 Ouverture du fichier Excel...", flush=True)
        xl = pd.ExcelFile(xlsx)
    except Exception as e:
        print(f"  ❌ Impossible d'ouvrir: {e}")
        files_failed += 1
        continue

    for sheet_name, task_label in TASK_SHEETS.items():
        if sheet_name not in xl.sheet_names:
            print(f"  ⏭️  Feuille '{sheet_name}' absente")
            continue

        try:
            print(f"  ⏳ Lecture de la feuille '{sheet_name}'...", flush=True)
            df = pd.read_excel(xlsx, sheet_name=sheet_name, dtype=str)
            blocks = read_blocks(df)

            if not blocks:
                print(f"  ⚠️  '{sheet_name}': aucun bloc valide trouvé")
                continue

            print(f"  📋 '{sheet_name}': {len(blocks)} bloc(s) détecté(s)", flush=True)

            for block_idx, (session_val, block) in enumerate(blocks, start=1):
                # Déduire la session depuis la valeur extraite ou l'index du bloc
                ses = session_label(session_val) if session_val is not None else f"ses-{block_idx:02d}"

                out_dir = BIDS_ROOT / subject / ses / "beh"
                out_file = out_dir / f"{subject}_{ses}_task-{task_label}_beh.tsv"

                if out_file.exists() and not overwrite:
                    print(f"    ⏭️  {out_file.name} (déjà existant)")
                    files_skipped += 1
                    continue

                out_dir.mkdir(parents=True, exist_ok=True)
                print(f"    💾 Écriture de {out_file.name}...", flush=True)
                block.to_csv(out_file, sep="\t", index=False)
                print(f"    ✓ {out_file.name}")
                files_processed += 1

        except Exception as e:
            print(f"  ❌ '{sheet_name}': {e}")
            files_failed += 1

# Rapport final
print()
print("=" * 70)
print("📊 RAPPORT FINAL")
print("=" * 70)
print(f"  Fichiers XLSX traités : {len(xlsx_files)}")
print(f"  TSV écrits            : {files_processed} ✓")
if files_skipped:
    print(f"  Déjà existants        : {files_skipped} ⏭️")
if files_failed:
    print(f"  Erreurs               : {files_failed} ❌")
