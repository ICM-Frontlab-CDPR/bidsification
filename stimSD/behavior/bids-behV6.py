#!/usr/bin/env python3
"""
bids-behV6.py  —  Bidsification comportementale stimSD
=======================================================
Delta avec V5 :
  • 8 nouvelles feuilles (noms exacts tels qu'ils apparaissent dans les xlsx) :
      'EXE verb.'    → task-exeverb
      'EXE visu.'    → task-exevisu
      'FLUENCE cat.' → task-fluencecat
      'FLUENCE verb.'→ task-fluenceverb
      'DC cat.'      → task-dccat
      'DENO'         → task-deno
      'LECTURE'      → task-lecture
      'BIP'          → task-bip
  • Architecture orientée SheetConfig : chaque feuille déclare ses patterns
    de colonnes, ses colonnes requises, l'ordre de sortie, et le filtre
    d'extension de fichier stimulus.
  • Deux lecteurs génériques :
      read_trial_blocks(df, cfg)   — tâches avec numéro de trial (toutes sauf FLUENCE)
      read_fluence_blocks(df, cfg) — FLUENCE cat. et FLUENCE verb. (liste d'items)
  • Filtres hérités de V5 (filtre entier/trial, extension fichier, dédup trial).
  • Sortie dans bids-V6-eCRF/ (distinct de V5).
"""
import logging
import re
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
import pandas as pd


# ── Logging ───────────────────────────────────────────────────────────────────
_LOG_DIR = Path("/Users/hippolyte.dreyfus/Documents/bidsification/stimSD/_log")
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_log_file = _LOG_DIR / f"bids-behV6_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

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

_rando = pd.read_excel(RANDO_XLSX)
_rando.columns = _rando.columns.str.strip()
_rando["Excel File Name"] = _rando["Excel File Name"].astype(str).str.strip()
_rando["eCRF Name"]       = _rando["eCRF Name"].astype(str).str.strip()
ECRF_MAP: dict[str, str] = {
    re.sub(r"[^a-zA-Z0-9]", "", row["Excel File Name"]).lower(): row["eCRF Name"]
    for _, row in _rando.iterrows()
    if row["Excel File Name"] not in ("nan", "") and row["eCRF Name"] not in ("nan", "")
}
# Exceptions manuelles (noms xlsx non conformes à la liste de rando)
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


# ── SheetConfig ───────────────────────────────────────────────────────────────
@dataclass
class SheetConfig:
    task_label:  str
    col_patterns: list          # [(bids_name, compiled_re), ...]
    required:    list           # noms BIDS obligatoires
    optional:    dict           # {bids_name: valeur par défaut}
    output_cols: list           # colonnes de sortie dans l'ordre
    file_col:    Optional[str]  # colonne contenant le fichier stimulus (filtre ext)
    file_ext:    Optional[str]  # extension attendue : ".bmp" / ".tif" / None
    reader:      str = "trial_based"   # "trial_based" | "fluence"


def _c(task, pats_raw, req, opt, out,
       file_col=None, file_ext=None, reader="trial_based"):
    """Raccourci : compile les regex et instancie SheetConfig."""
    pats = [(n, re.compile(p, re.I)) for n, p in pats_raw]
    return SheetConfig(task, pats, req, opt, out, file_col, file_ext, reader)


# Patterns partagés
_BASE = [
    ("participant_id", r"^pat"),
    ("version",        r"^version"),
    ("session",        r"^session"),
    ("trial",          r"^trial"),
]
_IMG = [  # ImageDisplay2 (AS, EXE)
    ("accuracy",       r"imagedisplay2.*\.acc"),
    ("response_time",  r"imagedisplay2.*\.rt"),
]
_TXT = [  # TextDisplay2 (DC cat.)
    ("accuracy",       r"textdisplay2.*\.acc"),
    ("response_time",  r"textdisplay2.*\.rt"),
]

SHEET_CONFIGS: dict[str, SheetConfig] = {

    # ── Appariement Sémantique ────────────────────────────────────────────────
    "AS verbale": _c(
        "asverbale",
        _BASE + [("target", r"^target"), ("condition_target", r"^cond")] + _IMG,
        req=["session", "trial", "condition_target", "accuracy"],
        opt={"target": "n/a", "response_time": "n/a"},
        out=["trial", "target", "condition_target", "accuracy",
             "response_time", "test_version"],
        file_col="target", file_ext=".bmp",
    ),
    "AS visuelle": _c(
        "asvisuelle",
        _BASE + [("target", r"^target"), ("condition_target", r"^cond")] + _IMG,
        req=["session", "trial", "condition_target", "accuracy"],
        opt={"target": "n/a", "response_time": "n/a"},
        out=["trial", "target", "condition_target", "accuracy",
             "response_time", "test_version"],
        file_col="target", file_ext=".bmp",
    ),

    # ── Exécution ─────────────────────────────────────────────────────────────
    # Target = fichiers .tif (ex : Mot7v1.tif, Fig11v1.tif)
    "EXE verb.": _c(
        "exeverb",
        _BASE + [("target", r"^target")] + _IMG,
        req=["session", "trial", "accuracy"],
        opt={"target": "n/a", "response_time": "n/a"},
        out=["trial", "target", "accuracy", "response_time", "test_version"],
        file_col="target", file_ext=".tif",
    ),
    "EXE visu.": _c(
        "exevisu",
        _BASE + [("target", r"^target")] + _IMG,
        req=["session", "trial", "accuracy"],
        opt={"target": "n/a", "response_time": "n/a"},
        out=["trial", "target", "accuracy", "response_time", "test_version"],
        file_col="target", file_ext=".tif",
    ),

    # ── Fluences ──────────────────────────────────────────────────────────────
    # Structure atypique : liste d'items produits (pas de numéro de trial).
    # Colonnes : PAT / Version / Session / [n°] / Items / Nombre
    "FLUENCE cat.": _c(
        "fluencecat",
        [("participant_id", r"^pat"),
         ("version",        r"^version"),
         ("session",        r"^session"),
         ("item_text",      r"^items?"),
         ("score",          r"^nombre")],
        req=["session", "item_text"],
        opt={"score": "n/a"},
        out=["item_n", "item_text", "score", "test_version"],
        reader="fluence",
    ),
    "FLUENCE verb.": _c(
        "fluenceverb",
        [("participant_id", r"^pat"),
         ("version",        r"^version"),
         ("session",        r"^session"),
         # "item_n_col" = colonne n° (n suivi d'un non-alphanumérique)
         # → distingue "n°" de "Nombre" (qui commence par Na)
         ("item_n_col",     r"^n\W"),
         ("item_text",      r"^items?"),
         ("score",          r"^nombre")],
        req=["session", "item_text"],
        opt={"score": "n/a"},
        out=["item_n", "item_text", "score", "test_version"],
        reader="fluence",
    ),

    # ── DC Catégorielle ───────────────────────────────────────────────────────
    # Stimulus = mot (pas de fichier), colonnes TextDisplay2
    "DC cat.": _c(
        "dccat",
        _BASE + [
            ("status",    r"^status"),
            ("stimulus",  r"^stimulus"),
        ] + _TXT,
        req=["session", "trial", "accuracy"],
        opt={"stimulus": "n/a", "status": "n/a", "response_time": "n/a"},
        out=["trial", "stimulus", "status", "accuracy",
             "response_time", "test_version"],
    ),

    # ── Dénomination ──────────────────────────────────────────────────────────
    # Stimulus = image .bmp, colonnes Slide1
    # Réponse = transcription verbale du patient
    # score_manual = SCORE : bonne réponse (cotation humaine)
    "DENO": _c(
        "deno",
        _BASE + [
            ("status",        r"^status"),
            ("stimulus",      r"^stimulus"),
            ("accuracy",      r"slide1.*\.acc"),
            ("response_time", r"slide1.*\.rt"),
            ("response",      r"^r[ée]ponse$"),        # "Réponse" exact (≠ "Réponse après coup")
            ("score_manual",  r"^score"),
        ],
        req=["session", "trial", "accuracy"],
        opt={"stimulus": "n/a", "status": "n/a", "response_time": "n/a",
             "response": "n/a", "score_manual": "n/a"},
        out=["trial", "stimulus", "status", "accuracy", "response_time",
             "response", "score_manual", "test_version"],
        file_col="stimulus", file_ext=".bmp",
    ),

    # ── Lecture ───────────────────────────────────────────────────────────────
    # Stimulus = mot écrit, Réponse = 0/1 (précision de lecture)
    # API erreurs = erreurs phonémiques transcrites
    "LECTURE": _c(
        "lecture",
        _BASE + [
            ("status",     r"^status"),
            ("stimulus",   r"^stimulus"),
            ("accuracy",   r"^r[ée]ponse$"),
            ("api_errors", r"^api"),
        ],
        req=["session", "trial", "accuracy"],
        opt={"stimulus": "n/a", "status": "n/a", "api_errors": "n/a"},
        out=["trial", "stimulus", "status", "accuracy",
             "api_errors", "test_version"],
    ),

    # ── BIP ───────────────────────────────────────────────────────────────────
    # Reconnaissance de personnalités célèbres — pas de RT
    "BIP": _c(
        "bip",
        _BASE + [
            ("category",               r"^cat"),
            ("nom",                    r"^(nom|name)"),
            ("personnalites_reconnues", r"personnali"),
            ("accuracy",               r"bip.*acc"),
        ],
        req=["session", "trial", "accuracy"],
        opt={"category": "n/a", "nom": "n/a",
             "personnalites_reconnues": "n/a"},
        out=["trial", "category", "nom", "personnalites_reconnues",
             "accuracy", "test_version"],
    ),
}


# ── Helpers ────────────────────────────────────────────────────────────────────
def subject_from_ecrf(ecrf_name: str) -> str:
    return "sub-" + ecrf_name.strip()


def session_label(value) -> str:
    if pd.isna(value):
        return "ses-00"
    m = re.search(r"(\d+)", str(value))
    return f"ses-{int(m.group(1)):02d}" if m else "ses-00"


def find_block_starts(columns) -> list[int]:
    """Indices des colonnes dont le header commence par 'PAT' (insensible à la casse)."""
    return [i for i, c in enumerate(columns)
            if re.match(r"^pat", str(c).strip(), re.I)]


def map_block_cols(chunk_cols: list, col_patterns: list) -> dict[str, int]:
    """
    Retourne {bids_name: index_dans_le_chunk}.
    Pour chaque champ, retient la première colonne dont le nom matche le pattern.
    """
    mapping: dict[str, int] = {}
    for bids_name, pattern in col_patterns:
        for i, col in enumerate(chunk_cols):
            if pattern.search(str(col).strip()):
                mapping[bids_name] = i
                break
    return mapping


# ── Lecteur trial-based ────────────────────────────────────────────────────────
def read_trial_blocks(df: pd.DataFrame, cfg: SheetConfig) -> list[tuple]:
    """
    Découpe df en blocs (un par session, chaque bloc commence sur une colonne PAT*).
    Applique les filtres trial-entier, extension fichier, déduplication.
    Retourne [(session_val, block_df), ...].
    """
    cols   = list(df.columns)
    starts = find_block_starts(cols)
    blocks = []

    for i, start in enumerate(starts):
        end        = starts[i + 1] if i + 1 < len(starts) else len(cols)
        chunk      = df.iloc[:, start:end].copy()
        chunk      = chunk.dropna(axis=1, how="all")
        chunk_cols = list(chunk.columns)

        col_map = map_block_cols(chunk_cols, cfg.col_patterns)

        # Colonnes obligatoires
        missing = [r for r in cfg.required if r not in col_map]
        if missing:
            log.warning(f"    ⚠️  bloc {i}: colonnes introuvables {missing} → ignoré")
            log.warning(f"         noms détectés : {[str(c) for c in chunk_cols]}")
            continue

        # Colonnes facultatives manquantes (avertissement non bloquant)
        missing_opt = [c for c in cfg.optional if c not in col_map]
        if missing_opt:
            log.warning(f"    ⚠️  bloc {i}: facultatives absentes {missing_opt} → n/a")

        # ── Filtre 1 : trial doit être un entier ≥ 1 ─────────────────────────
        # Rejette les décimaux (ex: 5281.6 = moyenne RT en ligne récap)
        trial_s = chunk.iloc[:, col_map["trial"]]
        num_t   = pd.to_numeric(trial_s, errors="coerce")
        valid   = num_t.notna() & (num_t % 1 == 0) & (num_t >= 1)
        if not valid.any():
            continue

        # ── Filtre 2 : extension de fichier stimulus ──────────────────────────
        # Les vrais stimuli ont une extension (.bmp, .tif).
        # Les lignes récap avec un trial entier (ex: n=5143) ont des valeurs numériques
        # dans la colonne stimulus → ce filtre les élimine.
        if cfg.file_col and cfg.file_ext and cfg.file_col in col_map:
            ftxt    = chunk.iloc[:, col_map[cfg.file_col]].astype(str).str.lower()
            has_ext = ftxt.str.contains(re.escape(cfg.file_ext), na=False)
            removed = valid & ~has_ext
            if removed.any():
                log.warning(
                    f"    ⚠️  bloc {i}: {removed.sum()} ligne(s) récap supprimée(s) "
                    f"(pas de '{cfg.file_ext}' dans {ftxt[removed].tolist()})"
                )
            valid = valid & has_ext

        if not valid.any():
            continue

        # ── Filtre 3 : déduplication sur trial (sécurité résiduelle) ─────────
        first_occ = ~num_t[valid].duplicated(keep="first")
        valid_idx = valid[valid].index[first_occ]
        dup       = valid.sum() - len(valid_idx)
        if dup > 0:
            log.warning(f"    ⚠️  bloc {i}: {dup} doublon(s) de trial supprimé(s)")
        valid = pd.Series(False, index=chunk.index)
        valid[valid_idx] = True

        # ── Version et session ────────────────────────────────────────────────
        ver_val = None
        if "version" in col_map:
            vs = chunk.iloc[:, col_map["version"]].dropna()
            ver_val = vs.iloc[0] if not vs.empty else None

        ss      = chunk.iloc[:, col_map["session"]].dropna()
        ses_val = ss.iloc[0] if not ss.empty else None

        # ── Construction du bloc de sortie ────────────────────────────────────
        n = int(valid.sum())

        def _col(name):
            if name in col_map:
                return chunk.iloc[:, col_map[name]][valid].values
            return [cfg.optional.get(name, "n/a")] * n

        data = {}
        for c in cfg.output_cols:
            data[c] = ver_val if c == "test_version" else _col(c)

        block = pd.DataFrame(data)
        if block.empty:
            continue

        blocks.append((ses_val, block))

    return blocks


# ── Lecteur fluence ────────────────────────────────────────────────────────────
def read_fluence_blocks(df: pd.DataFrame, cfg: SheetConfig) -> list[tuple]:
    """
    Lecteur pour FLUENCE cat. et FLUENCE verb. :
    - Pas de numéro de trial — utilise la colonne 'n°' si présente, sinon séquentiel.
    - Lignes valides = celles où la colonne Items n'est pas vide/NaN.
    - La ligne 'Score X' dans la colonne PAT n'interrompt pas les items (filtre sur Items).
    Retourne [(session_val, block_df), ...].
    """
    cols   = list(df.columns)
    starts = find_block_starts(cols)
    blocks = []

    for i, start in enumerate(starts):
        end        = starts[i + 1] if i + 1 < len(starts) else len(cols)
        chunk      = df.iloc[:, start:end].copy()
        chunk      = chunk.dropna(axis=1, how="all")
        chunk_cols = list(chunk.columns)

        col_map = map_block_cols(chunk_cols, cfg.col_patterns)

        missing = [r for r in cfg.required if r not in col_map]
        if missing:
            log.warning(f"    ⚠️  bloc {i}: colonnes introuvables {missing} → ignoré")
            log.warning(f"         noms détectés : {[str(c) for c in chunk_cols]}")
            continue

        # Session et version
        ss      = chunk.iloc[:, col_map["session"]].dropna()
        ses_val = ss.iloc[0] if not ss.empty else None

        ver_val = None
        if "version" in col_map:
            vs = chunk.iloc[:, col_map["version"]].dropna()
            ver_val = vs.iloc[0] if not vs.empty else None

        # Lignes valides : Items non vide
        item_s = chunk.iloc[:, col_map["item_text"]].astype(str)
        valid  = (item_s.str.strip() != "") & (~item_s.str.lower().isin(["nan", "none", ""]))

        if not valid.any():
            log.info(f"    ℹ️  bloc {i}: aucun item produit → TSV vide (en-têtes seulement)")
            block = pd.DataFrame(columns=cfg.output_cols)
            blocks.append((ses_val, block))
            continue

        items   = chunk.iloc[:, col_map["item_text"]][valid].values
        n_items = len(items)

        # item_n : colonne n° si mappée et non-vide, sinon séquentiel
        src_n = "item_n_col" if "item_n_col" in col_map else (
                "item_n"     if "item_n" in col_map else None)
        if src_n:
            raw_n = pd.to_numeric(
                chunk.iloc[:, col_map[src_n]][valid], errors="coerce"
            )
            # Si tous NaN, fallback séquentiel
            if raw_n.notna().any():
                item_n = raw_n.fillna(
                    pd.Series(range(1, n_items + 1), index=raw_n.index)
                ).values
            else:
                item_n = list(range(1, n_items + 1))
        else:
            item_n = list(range(1, n_items + 1))

        # score (Nombre)
        if "score" in col_map:
            score = chunk.iloc[:, col_map["score"]][valid].values
        else:
            score = ["n/a"] * n_items

        block = pd.DataFrame({
            "item_n":       item_n,
            "item_text":    items,
            "score":        score,
            "test_version": ver_val,
        })

        blocks.append((ses_val, block))

    return blocks


# ── Boucle principale ──────────────────────────────────────────────────────────
log.info(f"🔎 Scan de {PATIENTS_DIR} ...")
xlsx_files = sorted(
    f
    for pat_dir in PATIENTS_DIR.iterdir() if pat_dir.is_dir()
    for f in list(pat_dir.glob("*.xlsx")) + list(pat_dir.glob("*/*.xlsx"))
    if not f.name.startswith("~$") and not f.name.startswith("._")
)

log.info(f"🔍 {len(xlsx_files)} fichiers XLSX trouvés")
for f in xlsx_files:
    log.info(f"  - {f.parent.name}/{f.name}")
log.info("")

resp = input(f"⚠️  Convertir {len(xlsx_files)} fichiers en BIDS beh ? (o/n) : ")
if resp.lower() not in ["o", "oui", "y", "yes"]:
    print("❌ Annulé.")
    exit(0)

overwrite = input("🔄 Écraser les fichiers déjà existants ? (o/n) : ").lower() in [
    "o", "oui", "y", "yes"
]
print()

files_processed = files_skipped = files_failed = 0

READERS = {
    "trial_based": read_trial_blocks,
    "fluence":     read_fluence_blocks,
}

for xlsx in xlsx_files:
    stem_norm = re.sub(r"[^a-zA-Z0-9]", "", xlsx.stem).lower()
    ecrf_name = ECRF_MAP.get(stem_norm)
    if not ecrf_name:
        log.warning(f"  ⚠️  Pas de correspondance eCRF pour '{xlsx.stem}' (norm='{stem_norm}') → ignoré")
        files_failed += 1
        continue

    subject = subject_from_ecrf(ecrf_name)
    log.info(f"📂 {subject}  ({xlsx.parent.name}/{xlsx.name})")

    try:
        xl = pd.ExcelFile(xlsx)
    except Exception as e:
        log.error(f"  ❌ Impossible d'ouvrir : {e}")
        files_failed += 1
        continue

    for sheet_name, cfg in SHEET_CONFIGS.items():
        if sheet_name not in xl.sheet_names:
            log.debug(f"  ⏭️  '{sheet_name}' absente")
            continue

        try:
            log.info(f"  ⏳ '{sheet_name}' → task-{cfg.task_label}")
            df     = pd.read_excel(xlsx, sheet_name=sheet_name, dtype=str)
            reader = READERS[cfg.reader]
            blocks = reader(df, cfg)

            if not blocks:
                log.warning(f"  ⚠️  '{sheet_name}': aucun bloc valide trouvé")
                continue

            log.info(f"  📋 '{sheet_name}': {len(blocks)} bloc(s) détecté(s)")

            seen: dict[str, int] = {}
            for bidx, (ses_val, block) in enumerate(blocks, 1):
                ses = session_label(ses_val) if ses_val is not None else f"ses-{bidx:02d}"

                if ses in seen:
                    log.warning(
                        f"    ⚠️  DOUBLON de session : {ses} déjà vu au bloc "
                        f"{seen[ses]} → bloc {bidx} va écraser le précédent"
                    )
                seen[ses] = bidx

                out_dir  = BIDS_ROOT / subject / ses / "beh"
                out_file = out_dir / f"{subject}_{ses}_task-{cfg.task_label}_beh.tsv"

                if out_file.exists() and not overwrite:
                    log.info(f"    ⏭️  {out_file.name} (déjà existant)")
                    files_skipped += 1
                    continue

                out_dir.mkdir(parents=True, exist_ok=True)
                block.to_csv(out_file, sep="\t", index=False)
                ver = (block["test_version"].iloc[0]
                       if not block.empty and "test_version" in block.columns
                       else "?")
                log.info(f"    ✓ {out_file.name}  [v={ver}, n={len(block)}]")
                files_processed += 1

        except Exception as e:
            log.error(f"  ❌ '{sheet_name}': {e}")
            log.error(traceback.format_exc())
            files_failed += 1

# ── Rapport final ──────────────────────────────────────────────────────────────
log.info("")
log.info("=" * 70)
log.info("📊 RAPPORT FINAL")
log.info("=" * 70)
log.info(f"  XLSX traités    : {len(xlsx_files)}")
log.info(f"  TSV écrits      : {files_processed} ✓")
if files_skipped:
    log.info(f"  Déjà existants  : {files_skipped} ⏭️")
if files_failed:
    log.warning(f"  Erreurs/ignorés : {files_failed} ❌")
log.info(f"  Log sauvegardé  : {_log_file}")
