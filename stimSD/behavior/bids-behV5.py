#!/usr/bin/env python3
"""
bids-behV5.py  —  Bidsification comportementale stimSD
=======================================================
Différences avec V4 :
  1. Mapping des colonnes par NOM plutôt que par position.
     → corrige le décalage pour les fichiers qui ont une colonne extra
       'Bonne réponse' entre 'Condition Target' et 'ImageDisplay2.ACC'
       (ex : 001-0016-BJC, 001-0014-BS pour certaines sessions).
  2. La colonne 'Version' (version du test administré par session) est
     conservée dans le TSV de sortie sous le nom 'test_version'.
  3. Répertoire de sortie : bids-V5-eCRF (distinct de bids-V4-eCRF).
"""
import logging
import re
import traceback
from datetime import datetime
from pathlib import Path
import pandas as pd

# ---------------------------------------------------------------------------
# Logging : fichier horodaté + console en parallèle
# ---------------------------------------------------------------------------
_LOG_DIR = Path("/Users/hippolyte.dreyfus/Documents/bidsification/stimSD/_log")
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_log_file = _LOG_DIR / f"bids-behV5_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    handlers=[
        logging.FileHandler(_log_file, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger()
print(f"📝 Log : {_log_file}\n")

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------
PATIENTS_DIR = Path("/Volumes/levy/raw/valerocabre/stimSD/Data/sourcedata/1_DATA/1_RAW/1_PATIENTS")
BIDS_ROOT    = Path("/Volumes/levy/raw/valerocabre/stimSD/Data/derivatives/bids-V5bis-eCRF")
RANDO_XLSX   = Path("/Volumes/levy/raw/valerocabre/stimSD/Data/STIM_SD_Randomization_List_Nov_2025_Full.xlsx")

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

# ---------------------------------------------------------------------------
# Feuilles cibles
# ---------------------------------------------------------------------------
TASK_SHEETS = {
    "AS verbale":  "asverbale",
    "AS visuelle": "asvisuelle",
}

# ---------------------------------------------------------------------------
# Patterns de reconnaissance des colonnes par nom (insensible à la casse)
#
# Colonnes connues dans les xlsx :
#   PAT001-001-CM, PAT001-004-MA-P, PAT001-00-17-BJC … → participant_id
#   Version, Version.1 …                                → version (test)
#   Session, Session.1 …                                → session
#   Trial, Trial.1 …                                    → trial
#   Target, target, target.1 …                          → target
#   Condition Target, Condition Taget, condtarget …     → condition_target
#   ImageDisplay2.ACC, ImageDisplay2.ACC.1 …            → accuracy
#   ImageDisplay2.RT,  ImageDisplay2.RT.1 …             → response_time
#
# Colonnes IGNORÉES (ne matchent aucun pattern) :
#   Bonne réponse  (réponse attendue ≠ réponse patient)
#   RT correct, RT, RT.1  (RT filtré sur bonnes réponses)
#   Unnamed: N            (séparateurs entre blocs)
# ---------------------------------------------------------------------------
_COL_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("participant_id",   re.compile(r"^pat",                 re.I)),
    ("version",          re.compile(r"^version",             re.I)),
    ("session",          re.compile(r"^session",             re.I)),
    ("trial",            re.compile(r"^trial",               re.I)),
    ("target",           re.compile(r"^target",              re.I)),
    ("condition_target", re.compile(r"^cond",                re.I)),
    ("accuracy",         re.compile(r"imagedisplay2.*\.acc", re.I)),
    ("response_time",    re.compile(r"imagedisplay2.*\.rt",  re.I)),
]

# Colonnes obligatoires pour qu'un bloc soit valide
# participant_id est facultatif (l'identifiant vient du nom de fichier Excel/eCRF)
_REQUIRED = ["session", "trial", "condition_target", "accuracy"]
# Colonnes facultatives avec valeur de remplacement si absentes
_OPTIONAL_FALLBACK = {"target": "n/a", "response_time": "n/a"}


def map_block_cols(chunk_cols: list) -> dict[str, int]:
    """
    Retourne {bids_name: index_dans_le_chunk} en cherchant chaque champ
    par son pattern de nom. La première colonne correspondante est retenue.
    """
    mapping: dict[str, int] = {}
    for bids_name, pattern in _COL_PATTERNS:
        for i, col in enumerate(chunk_cols):
            if pattern.search(str(col).strip()):
                mapping[bids_name] = i
                break
    return mapping


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def read_blocks(df: pd.DataFrame) -> list[tuple]:
    """
    Découpe le DataFrame en blocs (un par session), chacun commençant
    par une colonne PAT*.

    Utilise le NOM des colonnes (pas leur position) pour mapper les champs
    BIDS — ce qui corrige le décalage causé par les colonnes extra comme
    'Bonne réponse' présentes dans certains fichiers.

    Retourne une liste de (session_val, block_df) où block_df a les colonnes :
      trial, target, condition_target, test_version, accuracy, response_time
    """
    cols   = list(df.columns)
    starts = find_block_starts(cols)
    blocks = []

    for i, start in enumerate(starts):
        end        = starts[i + 1] if i + 1 < len(starts) else len(cols)
        chunk      = df.iloc[:, start:end].copy()
        chunk      = chunk.dropna(axis=1, how="all")
        chunk_cols = list(chunk.columns)

        col_map = map_block_cols(chunk_cols)

        # Vérifier que toutes les colonnes obligatoires sont présentes
        missing = [r for r in _REQUIRED if r not in col_map]
        if missing:
            log.warning(f"    ⚠️  bloc {i}: colonnes introuvables {missing} → bloc ignoré")
            log.warning(f"         (noms détectés : {[str(c) for c in chunk_cols]})")
            continue
        # Avertissement (non bloquant) pour les colonnes facultatives manquantes
        missing_opt = [c for c in _OPTIONAL_FALLBACK if c not in col_map]
        if missing_opt:
            log.warning(f"    ⚠️  bloc {i}: colonnes facultatives absentes {missing_opt} → remplacées par n/a")
            log.warning(f"         (noms détectés : {[str(c) for c in chunk_cols]})")

        # Lignes avec un numéro de trial valide (filtre les lignes de métadonnées)
        trial_series = chunk.iloc[:, col_map["trial"]]
        valid        = pd.to_numeric(trial_series, errors="coerce").notna()
        if not valid.any():
            continue

        # Version du test (valeur de session, 1er non-NaN)
        if "version" in col_map:
            ver_series  = chunk.iloc[:, col_map["version"]].dropna()
            version_val = ver_series.iloc[0] if not ver_series.empty else None
        else:
            version_val = None

        # Session (pour nommage du fichier BIDS)
        ses_series  = chunk.iloc[:, col_map["session"]].dropna()
        session_val = ses_series.iloc[0] if not ses_series.empty else None

        # Construire le bloc de sortie (fallback n/a pour colonnes facultatives absentes)
        def _col(name):
            if name in col_map:
                return chunk.iloc[:, col_map[name]][valid].values
            return _OPTIONAL_FALLBACK.get(name, "n/a")

        block = pd.DataFrame({
            "trial":            _col("trial"),
            "target":           _col("target"),
            "condition_target": _col("condition_target"),
            "test_version":     version_val,   # constante sur tous les essais
            "accuracy":         _col("accuracy"),
            "response_time":    _col("response_time"),
        })

        if block.empty:
            continue

        blocks.append((session_val, block))

    return blocks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Trouver tous les XLSX : 1 ou 2 niveaux sous chaque dossier patient
log.info(f"🔎 Scan du dossier {PATIENTS_DIR} ...")
xlsx_files = sorted(
    f
    for pat_dir in PATIENTS_DIR.iterdir()
    if pat_dir.is_dir()
    for f in list(pat_dir.glob("*.xlsx")) + list(pat_dir.glob("*/*.xlsx"))
    if not f.name.startswith("~$") and not f.name.startswith("._")
)

log.info(f"🔍 {len(xlsx_files)} fichiers XLSX trouvés")
for f in xlsx_files:
    log.info(f"  - {f.parent.name}/{f.name}")
log.info("")

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
        log.warning(f"  ⚠️  Pas de correspondance eCRF pour '{xlsx.stem}' (norm='{stem_norm}'), fichier ignoré")
        files_failed += 1
        continue
    log.info(f"📂 {subject}  ({xlsx.parent.name}/{xlsx.name})")

    try:
        xl = pd.ExcelFile(xlsx)
    except Exception as e:
        log.error(f"  ❌ Impossible d'ouvrir: {e}")
        files_failed += 1
        continue

    for sheet_name, task_label in TASK_SHEETS.items():
        if sheet_name not in xl.sheet_names:
            log.info(f"  ⏭️  Feuille '{sheet_name}' absente")
            continue

        try:
            log.info(f"  ⏳ Lecture de '{sheet_name}'...")
            df     = pd.read_excel(xlsx, sheet_name=sheet_name, dtype=str)
            blocks = read_blocks(df)

            if not blocks:
                log.warning(f"  ⚠️  '{sheet_name}': aucun bloc valide trouvé")
                continue

            log.info(f"  📋 '{sheet_name}': {len(blocks)} bloc(s) détecté(s)")

            seen_sessions: dict[str, int] = {}  # ses_label → block_idx (pour détecter les doublons)
            for block_idx, (session_val, block) in enumerate(blocks, start=1):
                # Déduire la session depuis la valeur extraite ou l'index du bloc
                ses = session_label(session_val) if session_val is not None else f"ses-{block_idx:02d}"

                # Avertissement si deux blocs partagent le même label de session
                if ses in seen_sessions:
                    log.warning(f"    ⚠️  DOUBLON de session : {ses} déjà vu au bloc {seen_sessions[ses]} → "
                                f"bloc {block_idx} va écraser le précédent")
                seen_sessions[ses] = block_idx

                out_dir  = BIDS_ROOT / subject / ses / "beh"
                out_file = out_dir / f"{subject}_{ses}_task-{task_label}_beh.tsv"

                if out_file.exists() and not overwrite:
                    log.info(f"    ⏭️  {out_file.name} (déjà existant)")
                    files_skipped += 1
                    continue

                out_dir.mkdir(parents=True, exist_ok=True)
                block.to_csv(out_file, sep="\t", index=False)
                log.info(f"    ✓ {out_file.name}  [test_version={block['test_version'].iloc[0]}]")
                files_processed += 1

        except Exception as e:
            log.error(f"  ❌ '{sheet_name}': {e}")
            log.error(traceback.format_exc())
            files_failed += 1

# Rapport final
log.info("")
log.info("=" * 70)
log.info("📊 RAPPORT FINAL")
log.info("=" * 70)
log.info(f"  Fichiers XLSX traités : {len(xlsx_files)}")
log.info(f"  TSV écrits            : {files_processed} ✓")
if files_skipped:
    log.info(f"  Déjà existants        : {files_skipped} ⏭️")
if files_failed:
    log.warning(f"  Erreurs / ignorés     : {files_failed} ❌")
log.info(f"  Log sauvegardé dans   : {_log_file}")
