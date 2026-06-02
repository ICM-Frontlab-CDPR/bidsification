#!/usr/bin/env python3
"""
mri-bids.py
===========
Bidsifie les IRM MP2RAGE CLONESA vers bids/ BIDS.

Source  : CLONESA_FOLDER_organized/CLONESA_tACS/MRIs/CLONESA_001_XXXX/
Sortie  : bids/sub-XXXX/anat/

Fichiers copiés (compressés en .nii.gz) :
  v_*_UNI_Images.nii   → sub-XXXX_UNIT1.nii.gz   (raw UNI, fallback MPRAGEised)
  v_*_INV1.nii         → sub-XXXX_inv-1_MP2RAGE.nii.gz
  v_*_INV2.nii         → sub-XXXX_inv-2_MP2RAGE.nii.gz
  + JSON sidecars si présents
"""
import gzip
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

# ── Chemins ──────────────────────────────────────────────────────────────────
SRC_ROOT = Path(
    "/network/iss/levy/raw/valerocabre/clonesa/Data/_CLONESA_MRI/sourcedata"
    "/CLONESA_FOLDER_organized/CLONESA_tACS/MRIs"
)
BIDS_ROOT = Path(
    "/network/iss/levy/raw/valerocabre/clonesa/Data/ClonesaTMS/bids"
)

# ── Logging ──────────────────────────────────────────────────────────────────
_LOG_DIR = Path("/network/iss/home/hippolyte.dreyfus/bidsification/clonesa/_log")
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_log_file = _LOG_DIR / f"mri-bids_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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

# Dossiers contenant des artefacts SPM / FreeSurfer à exclure
_EXCLUDE_DIRS = {"mri", "surf", "label", "report", "presurf_MPRAGEise", "presurf_biascorrect"}


def _is_excluded(path: Path, subject_root: Path) -> bool:
    """True si le fichier est sous un sous-dossier d'artefacts."""
    relative = path.relative_to(subject_root)
    return any(part in _EXCLUDE_DIRS for part in relative.parts[:-1])


def _find_nii(subject_root: Path, pattern: str, exclude_pattern: str | None = None) -> list[Path]:
    """
    Cherche les .nii correspondant à pattern dans subject_root (récursif),
    en excluant les sous-dossiers d'artefacts et les noms contenant exclude_pattern.
    Résultats triés par profondeur croissante (préférer les fichiers les moins profonds).
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
    """Copie src → dst.gz (compresse si nécessaire)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(src, "rb") as f_in, gzip.open(dst, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)


def _copy_json(src_nii: Path, dst_nii_gz: Path) -> None:
    """Copie le JSON sidecar si présent."""
    json_src = src_nii.with_suffix(".json")
    if json_src.exists():
        shutil.copy2(json_src, dst_nii_gz.with_suffix("").with_suffix(".json"))


def process_subject(subject_dir: Path, sub_id: str) -> None:
    """Bidsifie un sujet donné."""
    anat_dir = BIDS_ROOT / f"sub-{sub_id}" / "anat"
    prefix = f"sub-{sub_id}"

    # ── UNI (UNIT1) ───────────────────────────────────────────────────────────
    uni_candidates = _find_nii(subject_dir, r"UNI_Images", exclude_pattern=r"MPRAGEised")
    if not uni_candidates:
        # Fallback : MPRAGEised (préférer v_ > DICOM_ > autres)
        mprage_cands = _find_nii(subject_dir, r"MPRAGEised")
        mprage_cands = [p for p in mprage_cands if not re.match(r"(mean|iy_|mwp|p0|wm|y_|wrv|rv_|ww)", p.name)]
        uni_candidates = mprage_cands

    if uni_candidates:
        src = uni_candidates[0]
        dst = anat_dir / f"{prefix}_UNIT1.nii.gz"
        _compress_copy(src, dst)
        _copy_json(src, dst)
        label = "MPRAGEised" if "MPRAGEised" in src.name else "UNI"
        log.info(f"  ✓ UNIT1  [{label}] {src.name}")
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
    else:
        log.debug(f"  –  INV2 absent")


# ── Découverte des sujets ─────────────────────────────────────────────────────
# Pattern standard : CLONESA_001_0021, CLONESA_002_0017, etc.
SUBJ_RE = re.compile(r"^CLONESA_\d{3}_(\d{4})$")

subject_dirs: list[tuple[Path, str]] = []

for entry in sorted(SRC_ROOT.iterdir()):
    if not entry.is_dir():
        continue
    m = SUBJ_RE.match(entry.name)
    if m:
        subject_dirs.append((entry, m.group(1)))
        continue
    # Sous-dossier mislabbeled_Xnat
    if entry.name == "CLONESA_mislabbeled_Xnat":
        for sub_entry in sorted(entry.iterdir()):
            if not sub_entry.is_dir():
                continue
            m2 = SUBJ_RE.match(sub_entry.name.split("_20")[0])  # strip date suffix
            if m2:
                subject_dirs.append((sub_entry, m2.group(1)))
            else:
                log.warning(f"  ⚠️  Ignoré (ID non résolu) : {sub_entry.name}")

log.info(f"🔍 {len(subject_dirs)} sujets trouvés\n")

# ── Boucle principale ─────────────────────────────────────────────────────────
BIDS_ROOT.mkdir(parents=True, exist_ok=True)

for subject_dir, sub_id in subject_dirs:
    log.info(f"▶ sub-{sub_id}  ({subject_dir.name})")
    try:
        process_subject(subject_dir, sub_id)
    except Exception as e:
        import traceback
        log.error(f"  ❌ {e}")
        log.error(traceback.format_exc())

log.info(f"\n✅ Terminé. BIDS : {BIDS_ROOT}")
log.info(f"📝 Log : {_log_file}")
