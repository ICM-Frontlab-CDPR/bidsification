#!/usr/bin/env python3
"""
mri-bids_TMS_FROM_sourcedata.py
================================
Bidsifie les IRM MP2RAGE CLONESA-TMS vers bids/ BIDS.

Source  : ClonesaTMS/sourcedata/__mri__/
Sortie  : ClonesaTMS/bids/sub-XXXX/anat/

Fichiers copiés (compressés en .nii.gz) :
  v_*_UNI_Images.nii   → sub-XXXX_UNIT1.nii.gz   (raw UNI, fallback MPRAGEised)
  v_*_INV1.nii         → sub-XXXX_inv-1_MP2RAGE.nii.gz
  v_*_INV2.nii         → sub-XXXX_inv-2_MP2RAGE.nii.gz
  + JSON sidecars si présents

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
    "/network/iss/levy/raw/valerocabre/clonesa/Data/ClonesaTMS/sourcedata/__mri__"
)
BIDS_ROOT = Path(
    "/network/iss/levy/raw/valerocabre/clonesa/Data/ClonesaTMS/bids"
)

# ── Logging ──────────────────────────────────────────────────────────────────
_LOG_DIR = Path("/Users/hippolyte.dreyfus/Documents/bidsification/clonesa/_log")
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

# Sous-dossiers SPM/FreeSurfer/SimNIBS à exclure de la recherche
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
    Bidsifie un sujet. Retourne True si au moins un fichier a été trouvé.
    """
    anat_dir = BIDS_ROOT / f"sub-{sub_id}" / "anat"
    prefix = f"sub-{sub_id}"
    found_any = False

    # ── UNI (UNIT1) ───────────────────────────────────────────────────────────
    uni_candidates = _find_nii(subject_dir, r"UNI_Images", exclude_pattern=r"MPRAGEised")
    if not uni_candidates:
        # Fallback : MPRAGEised (préférer v_ vs dérivés mean/rv/wrv)
        mprage = _find_nii(subject_dir, r"MPRAGEised")
        mprage = [p for p in mprage
                  if not re.match(r"(mean|iy_|mwp|p0|wm|y_|rv_|wrv|ww)", p.name)]
        uni_candidates = mprage

    if uni_candidates:
        src = uni_candidates[0]
        dst = anat_dir / f"{prefix}_UNIT1.nii.gz"
        _compress_copy(src, dst)
        _copy_json(src, dst)
        label = "MPRAGEised" if "MPRAGEised" in src.name else "UNI"
        log.info(f"  ✓ UNIT1  [{label}] {src.name}")
        found_any = True
    else:
        log.warning(f"  ⚠️  UNIT1 introuvable")

    # ── INV1 ─────────────────────────────────────────────────────────────────
    inv1_cands = _find_nii(subject_dir, r"INV1", exclude_pattern=r"MPRAGEised")
    if inv1_cands:
        src = inv1_cands[0]
        dst = anat_dir / f"{prefix}_inv-1_MP2RAGE.nii.gz"
        _compress_copy(src, dst)
        _copy_json(src, dst)
        log.info(f"  ✓ INV1   {src.name}")
        found_any = True
    else:
        log.debug(f"  –  INV1 absent")

    # ── INV2 ─────────────────────────────────────────────────────────────────
    inv2_cands = _find_nii(subject_dir, r"INV2", exclude_pattern=r"MPRAGEised")
    if inv2_cands:
        src = inv2_cands[0]
        dst = anat_dir / f"{prefix}_inv-2_MP2RAGE.nii.gz"
        _compress_copy(src, dst)
        _copy_json(src, dst)
        log.info(f"  ✓ INV2   {src.name}")
        found_any = True
    else:
        log.debug(f"  –  INV2 absent")

    return found_any


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
