#!/usr/bin/env python3
"""
mri-bids_TMS_FROM_sourcedata.py
================================
Bidsifie les IRM CLONESA-TMS : un seul T1w par sujet.

Source  : ClonesaTMS/sourcedata/__mri__/
Sortie  : ClonesaTMS/bids/sub-XXXX/anat/sub-XXXX_T1w.nii.gz

Priorité de sélection du T1w :
  1. v_*_UNI_Images.nii       (MP2RAGE brut, meilleure qualité)
  2. v_*_MPRAGEised.nii       (MP2RAGE post-traité)
  3. Premier .nii anatomique  (T1 Brainsight, ex. clonesa_g2_004_dlPFC.nii)
  + JSON sidecar si présent

Découverte des sujets :
  CLONESA_002_XXXX/ → sub-XXXX   (prioritaire)
  SUBJ_XX/          → sub-00XX   (complément si non déjà couvert)
  sub-001, sub_032, sub_49, subj_48, subj_50, TONI MRI, Other/ → ignorés
"""
import gzip
import logging
import re
import shutil
import traceback
from datetime import datetime
from pathlib import Path

# ── Chemins ──────────────────────────────────────────────────────────────────
SRC_ROOT = Path(
    "/Volumes/levy/raw/valerocabre/clonesa/Data/ClonesaTMS/sourcedata/__mri__"
)
BIDS_ROOT = Path(
    "/Volumes/levy/raw/valerocabre/clonesa/Data/ClonesaTMS/bids"
)

# ── Logging ──────────────────────────────────────────────────────────────────
_LOG_DIR = Path("/network/iss/home/hippolyte.dreyfus/Documents/bidsification/clonesa/_log")
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_log_file = _LOG_DIR / f"mri-bids-TMS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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

# Préfixes SPM/FreeSurfer indiquant des dérivés à exclure
_DERIVED_PREFIX = re.compile(r"^(mean|iy_|mwp|p0|wm|y_|rv_|wrv|ww|target|wtarget)")

# Sous-dossiers d'artefacts à exclure de la recherche
_EXCLUDE_DIRS = {
    "mri", "surf", "label", "report",
    "presurf_MPRAGEise", "presurf_biascorrect",
}


def _is_excluded(path: Path, subject_root: Path) -> bool:
    relative = path.relative_to(subject_root)
    return any(part in _EXCLUDE_DIRS for part in relative.parts[:-1])


def _find_nii(subject_root: Path, pattern: str,
              exclude_pattern: str | None = None) -> list[Path]:
    """
    Cherche les .nii correspondant à pattern dans subject_root (récursif).
    Exclut les sous-dossiers d'artefacts et les noms contenant exclude_pattern.
    Résultats triés par profondeur croissante (fichiers les moins profonds en premier).
    """
    hits = []
    for p in subject_root.rglob("*.nii"):
        if not re.search(pattern, p.name, re.IGNORECASE):
            continue
        if exclude_pattern and re.search(exclude_pattern, p.name, re.IGNORECASE):
            continue
        if _is_excluded(p, subject_root):
            continue
        hits.append(p)
    return sorted(hits, key=lambda p: len(p.parts))


def _compress_copy(src: Path, dst: Path) -> None:
    """Lit src, écrit dst.gz compressé. Ne touche pas src."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(src, "rb") as f_in, gzip.open(dst, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)


def _copy_json(src_nii: Path, dst_nii_gz: Path) -> None:
    json_src = src_nii.with_suffix(".json")
    if json_src.exists():
        shutil.copy2(json_src, dst_nii_gz.with_suffix("").with_suffix(".json"))


def process_subject(subject_dir: Path, sub_id: str) -> bool:
    """
    Bidsifie un sujet en cherchant UN seul T1w. Retourne True si trouvé.
    Priorité : UNI brut > MPRAGEised > premier .nii anatomique (Brainsight).
    """
    anat_dir = BIDS_ROOT / f"sub-{sub_id}" / "anat"
    prefix = f"sub-{sub_id}"

    src: Path | None = None
    label: str = ""

    # 1. MP2RAGE UNI brut
    uni = _find_nii(subject_dir, r"UNI_Images", exclude_pattern=r"MPRAGEised")
    if uni:
        src, label = uni[0], "UNI"

    # 2. MPRAGEised (v_ uniquement, pas les dérivés SPM)
    if src is None:
        mprage = _find_nii(subject_dir, r"MPRAGEised")
        mprage = [p for p in mprage if not _DERIVED_PREFIX.match(p.name)]
        if mprage:
            src, label = mprage[0], "MPRAGEised"

    # 3. Fallback : premier .nii anatomique non-dérivé du dossier sujet
    if src is None:
        candidates = [
            p for p in subject_dir.rglob("*.nii")
            if not _is_excluded(p, subject_dir)
            and not _DERIVED_PREFIX.match(p.name)
            and not re.search(r"INV[12]", p.name, re.IGNORECASE)
            and not re.search(r"MPRAGEised", p.name)
            and not p.suffix == ".zip"
        ]
        candidates.sort(key=lambda p: len(p.parts))
        if candidates:
            src, label = candidates[0], "T1-Brainsight"

    if src is None:
        log.warning(f"  ⚠️  Aucun T1w trouvé")
        return False

    dst = anat_dir / f"{prefix}_T1w.nii.gz"
    _compress_copy(src, dst)
    _copy_json(src, dst)
    log.info(f"  ✓ T1w [{label}] {src.name}")
    return True


# ── Découverte des sujets ─────────────────────────────────────────────────────
CLONESA_RE = re.compile(r"^CLONESA_002_(\d{4})$")
SUBJ_RE    = re.compile(r"^SUBJ_(\d+)$", re.IGNORECASE)

# Doublons ou dossiers non-sujets à ignorer explicitement
_SKIP = {"sub-001", "sub_032", "sub_49", "subj_48", "subj_50",
         "TONI MRI", "Other", "CLONESA_mislabbeled_Xnat"}

id_to_dir: dict[str, Path] = {}

for entry in sorted(SRC_ROOT.iterdir()):
    if not entry.is_dir() or entry.name in _SKIP:
        continue

    m = CLONESA_RE.match(entry.name)
    if m:
        id_to_dir[m.group(1)] = entry
        continue

    m2 = SUBJ_RE.match(entry.name)
    if m2:
        sub_id = m2.group(1).zfill(4)
        if sub_id not in id_to_dir:
            id_to_dir[sub_id] = entry
        else:
            log.debug(f"  ⏭️  {entry.name} → sub-{sub_id} déjà couvert par {id_to_dir[sub_id].name}")
        continue

    log.warning(f"  ⚠️  Dossier non reconnu, ignoré : {entry.name}")

subject_list = sorted(id_to_dir.items())
log.info(f"🔍 {len(subject_list)} sujets candidats\n")

# ── Boucle principale ─────────────────────────────────────────────────────────
BIDS_ROOT.mkdir(parents=True, exist_ok=True)
n_ok = 0
n_empty = 0

for sub_id, subject_dir in subject_list:
    log.info(f"▶ sub-{sub_id}  ({subject_dir.name})")
    try:
        found = process_subject(subject_dir, sub_id)
        if found:
            n_ok += 1
        else:
            n_empty += 1
            log.info(f"  –  Aucune IRM MP2RAGE dans ce dossier")
    except Exception as e:
        log.error(f"  ❌ {e}")
        log.error(traceback.format_exc())

log.info(f"\n✅ Terminé : {n_ok} sujets bidsifiés, {n_empty} sans IRM MP2RAGE")
log.info(f"   BIDS : {BIDS_ROOT}")
log.info(f"📝 Log  : {_log_file}")
