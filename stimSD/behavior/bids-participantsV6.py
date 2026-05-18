#!/usr/bin/env python3
"""
bids-participantsV6.py
======================
Génère le fichier BIDS participants.tsv à la racine de bids-V6-eCRF/
en extrayant les données démographiques et cliniques de la feuille
'Patiente' (ou 'Patient') de chaque xlsx sourcedata.

Format de sortie (BIDS + champs cliniques stimSD) :
  participant_id  age  sex  handedness  education  disease_onset_year
  diagnosis_year  mms  madrs  bref  mattis  bdae_severity  do80_score
  consent_date

Colonnes BIDS standard :
  - participant_id : sub-<eCRF>
  - age            : entier
  - sex            : F / M
  - handedness     : R / L / A

Structure de la feuille (8 colonnes, 3 sections) :
  cols 0,1 → section Identification
  cols 3,4 → section Examen Clinique
  cols 6,7 → section Langage
"""
import logging
import re
import traceback
from datetime import datetime
from pathlib import Path
import pandas as pd

# ── Logging ───────────────────────────────────────────────────────────────────
_LOG_DIR = Path("/Users/hippolyte.dreyfus/Documents/bidsification/stimSD/_log")
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_log_file = _LOG_DIR / f"bids-participantsV6_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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

# ── Chemins ───────────────────────────────────────────────────────────────────
PATIENTS_DIR = Path(
    "/Volumes/levy/raw/valerocabre/stimSD/Data/sourcedata/1_DATA/1_RAW/1_PATIENTS"
)
BIDS_ROOT = Path(
    "/Volumes/levy/raw/valerocabre/stimSD/Data/derivatives/bids-V6-eCRF"
)
RANDO_XLSX = Path(
    "/Volumes/levy/raw/valerocabre/stimSD/Data/STIM_SD_Randomization_List_Nov_2025_Full.xlsx"
)

# ── Mapping eCRF (identique à V6) ─────────────────────────────────────────────
_rando = pd.read_excel(RANDO_XLSX)
_rando.columns = _rando.columns.str.strip()
_rando["Excel File Name"] = _rando["Excel File Name"].astype(str).str.strip()
_rando["eCRF Name"]       = _rando["eCRF Name"].astype(str).str.strip()
ECRF_MAP: dict[str, str] = {
    re.sub(r"[^a-zA-Z0-9]", "", row["Excel File Name"]).lower(): row["eCRF Name"]
    for _, row in _rando.iterrows()
    if row["Excel File Name"] not in ("nan", "") and row["eCRF Name"] not in ("nan", "")
}
ECRF_MAP.update({
    "001001cm":       "001-0001-CMC",
    "001003ls":       "001-0005-LS",
    "001004ma":       "001-0004-MA",
    "0001005ls":      "001-0005-LS",
    "01006cv":        "001-0006-CV",
    "001008ld":       "001-0008-LD",
    "001009lm":       "001-0010-LM",
    "010024llm":      "001-0022-LM",
    "0010032eg3der":  "001-0030-GE",
})


# ── Extraction de la feuille Patiente/Patient ─────────────────────────────────
def _val(kv: dict, *keys) -> str:
    """Retourne la première valeur non vide parmi les clés fournies, ou 'n/a'."""
    for k in keys:
        v = kv.get(k, "")
        if v and str(v).strip() not in ("nan", "NaN", "None", ""):
            return str(v).strip()
    return "n/a"


def _year(raw: str) -> str:
    """Extrait l'année d'une date ISO ou d'une chaîne libre."""
    if raw == "n/a":
        return "n/a"
    m = re.search(r"\b(19|20)\d{2}\b", raw)
    return m.group(0) if m else raw


def _sex(raw: str) -> str:
    raw = raw.lower()
    if re.search(r"\bfem|^f$", raw):
        return "F"
    if re.search(r"\bhom|^m$", raw):
        return "M"
    return raw


def _hand(raw: str) -> str:
    raw = raw.lower()
    if re.search(r"droit", raw):
        return "R"
    if re.search(r"gauch", raw):
        return "L"
    if re.search(r"ambi", raw):
        return "A"
    return raw


def extract_patient_info(df: pd.DataFrame) -> dict:
    """
    Parcourt la feuille Patiente/PAT.
    Deux layouts possibles :
      - 8 colonnes : paires (0,1), (3,4), (6,7)  → anciens xlsx avec colonne NaN séparatrice
      - 6 colonnes : paires (0,1), (2,3), (4,5)  → xlsx récents feuille 'PAT'
    Retourne un dict {clé_normalisée: valeur}.
    """
    kv: dict[str, str] = {}
    n_cols = df.shape[1]
    if n_cols >= 8:
        pairs = [(0, 1), (3, 4), (6, 7)]
    else:  # 6 colonnes (format PAT récent)
        pairs = [(0, 1), (2, 3), (4, 5)]

    for _, row in df.iterrows():
        row = row.tolist()
        for kcol, vcol in pairs:
            if kcol >= len(row) or vcol >= len(row):
                continue
            k = str(row[kcol]).strip()
            v = str(row[vcol]).strip()
            if k not in ("nan", "NaN", "None", "") and v not in ("nan", "NaN", "None", ""):
                # Normaliser la clé : minuscules, sans accents basiques, espaces → _
                k_norm = k.lower()
                kv[k_norm] = v

    return kv


def build_row(ecrf_name: str, kv: dict) -> dict:
    """Construit une ligne du participants.tsv à partir du dict clé-valeur."""
    sex_raw  = _val(kv, "sexe", "sex")
    hand_raw = _val(kv, "lateralité", "lateralite", "latéralité")

    return {
        "participant_id":     f"sub-{ecrf_name}",
        "age":                _val(kv, "âge", "age"),
        "sex":                _sex(sex_raw) if sex_raw != "n/a" else "n/a",
        "handedness":         _hand(hand_raw) if hand_raw != "n/a" else "n/a",
        "education":          _val(kv, "niveau d'études", "niveau d etudes"),
        "disease_onset_year": _year(_val(kv, "premiers signes de la maladie",
                                         "premiers signes")),
        "diagnosis_year":     _year(_val(kv, "date du diagnostic")),
        "consent_date":       _year(_val(kv, "signature du consentement")),
        "mms":                _val(kv, "mms"),
        "madrs":              _val(kv, "madrs"),
        "bref":               _val(kv, "bref"),
        "mattis":             _val(kv, "mattis"),
        "bdae_severity":      _val(kv,
                                   "echelle de sévérité de l'aphasie (bdae)",
                                   "echelle de severite de l'aphasie (bdae)"),
        "do80_score":         _val(kv, "do 80 score"),
    }


# ── Boucle principale ──────────────────────────────────────────────────────────
log.info(f"🔎 Scan de {PATIENTS_DIR} ...")
xlsx_files = sorted(
    f
    for pat_dir in PATIENTS_DIR.iterdir() if pat_dir.is_dir()
    for f in list(pat_dir.glob("*.xlsx")) + list(pat_dir.glob("*/*.xlsx"))
    if not f.name.startswith("~$") and not f.name.startswith("._")
)
log.info(f"🔍 {len(xlsx_files)} fichiers XLSX trouvés\n")

rows = []
seen_ecrf: set[str] = set()

for xlsx in xlsx_files:
    stem_norm = re.sub(r"[^a-zA-Z0-9]", "", xlsx.stem).lower()
    ecrf_name = ECRF_MAP.get(stem_norm)
    if not ecrf_name:
        log.warning(f"  ⚠️  Pas de correspondance eCRF pour '{xlsx.stem}' → ignoré")
        continue

    if ecrf_name in seen_ecrf:
        log.debug(f"  ⏭️  {ecrf_name} déjà traité")
        continue

    try:
        xl = pd.ExcelFile(xlsx)
        sheet = next(
            (s for s in xl.sheet_names
             if re.match(r"^pat(ient|$)", s.strip(), re.I)),
            None,
        )
        if sheet is None:
            log.warning(f"  ⚠️  {ecrf_name}: feuille Patient/Patiente/PAT absente dans {xlsx.name}")
            # Ajouter quand même une ligne minimaliste
            rows.append({"participant_id": f"sub-{ecrf_name}"})
            seen_ecrf.add(ecrf_name)
            continue

        df  = pd.read_excel(xlsx, sheet_name=sheet, dtype=str, header=None)
        kv  = extract_patient_info(df)
        row = build_row(ecrf_name, kv)
        rows.append(row)
        seen_ecrf.add(ecrf_name)
        log.info(
            f"  ✓ {ecrf_name:<20s}  age={row['age']:>3}  sex={row['sex']}  "
            f"hand={row['handedness']}  mms={row['mms']}"
        )

    except Exception as e:
        log.error(f"  ❌ {ecrf_name} ({xlsx.name}): {e}")
        log.error(traceback.format_exc())

# ── Écriture du participants.tsv ───────────────────────────────────────────────
if not rows:
    log.error("❌ Aucune ligne extraite — participants.tsv non écrit.")
else:
    out_df   = pd.DataFrame(rows).sort_values("participant_id").reset_index(drop=True)
    out_file = BIDS_ROOT / "participants.tsv"
    BIDS_ROOT.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_file, sep="\t", index=False)
    log.info("")
    log.info(f"✅ {out_file}")
    log.info(f"   {len(out_df)} participants  |  colonnes : {list(out_df.columns)}")

log.info(f"\n📝 Log : {_log_file}")
