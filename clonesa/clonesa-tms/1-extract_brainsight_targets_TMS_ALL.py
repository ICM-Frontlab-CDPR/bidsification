#!/usr/bin/env python3
"""
2-extract_brainsight_targets_TMS_ALL.py
========================================
Boucle sur tous les .bsproj du dossier TMS sourcedata et extrait
targets + samples pour chaque sujet.

Réutilise BrainsightExtractor de 1-extract_brainsight_targets_ALL.py.

Source  : ClonesaTMS/sourcedata/__mri__/
Sortie  : ClonesaTMS/derivatives/brainsight/sub-XXXX/
            sub-XXXX_<bsproj_stem>_targets.tsv
            sub-XXXX_<bsproj_stem>_samples.tsv
"""
import logging
import re
import sys
import csv
from datetime import datetime
from pathlib import Path

# ── Import de la classe existante ─────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(_SCRIPT_DIR))
from extract_brainsight_targets_ALL import BrainsightExtractor  # noqa: E402

# ── Chemins ──────────────────────────────────────────────────────────────────
SRC_ROOT = Path(
    "/Volumes/levy/raw/valerocabre/clonesa/Data/ClonesaTMS/sourcedata/__mri__"
)
OUT_ROOT = Path(
    "/Volumes/levy/raw/valerocabre/clonesa/Data/ClonesaTMS/derivatives/brainsight"
)

# ── Logging ──────────────────────────────────────────────────────────────────
_LOG_DIR = Path("/Users/hippolyte.dreyfus/Documents/bidsification/clonesa/_log")
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_log_file = _LOG_DIR / f"extract-brainsight-TMS_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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

# ── Mapping sujet ─────────────────────────────────────────────────────────────
CLONESA_RE = re.compile(r"^CLONESA_002_(\d{4})$")
SUBJ_RE    = re.compile(r"^SUBJ_(\d+)$", re.IGNORECASE)

# Dossiers avec un ID non standard (mappés manuellement)
_MANUAL = {
    "sub_49":  "0049",
    "subj_48": "0048",
    "subj_50": "0050",
}
# Dossiers vraiment hors-sujet
_SKIP = {"Other", "TONI MRI", "CLONESA_mislabbeled_Xnat", "sub-001", "sub_032"}


def folder_to_sub_id(name: str) -> str | None:
    m = CLONESA_RE.match(name)
    if m:
        return m.group(1)
    m2 = SUBJ_RE.match(name)
    if m2:
        return m2.group(1).zfill(4)
    return _MANUAL.get(name)


# ── Export helpers ────────────────────────────────────────────────────────────
def export_targets_tsv(extractor: BrainsightExtractor, out_path: Path) -> int:
    targets = extractor.extract_targets()
    valid = [t for t in targets if t["position"] is not None]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["name", "x", "y", "z"])
        for t in valid:
            x, y, z = t["position"]
            w.writerow([t["name"], f"{x:.4f}", f"{y:.4f}", f"{z:.4f}"])
    return len(valid)


def export_samples_tsv(extractor: BrainsightExtractor, out_path: Path) -> int:
    samples = extractor.extract_samples()
    valid = [s for s in samples if s["position"] is not None]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["index", "name", "target_name", "x", "y", "z", "power_a", "power_b"])
        for s in valid:
            x, y, z = s["position"]
            w.writerow([
                s["index"],
                s["name"] or "",
                s["target_name"] or "",
                f"{x:.4f}", f"{y:.4f}", f"{z:.4f}",
                s["power_a"] or "",
                s["power_b"] or "",
            ])
    return len(valid)


# ── Découverte des .bsproj ────────────────────────────────────────────────────
# Collect: sub_id → [bsproj_path, ...]
from collections import defaultdict
sub_to_files: dict[str, list[Path]] = defaultdict(list)

for entry in sorted(SRC_ROOT.iterdir()):
    if not entry.is_dir() or entry.name in _SKIP:
        continue

    sub_id = folder_to_sub_id(entry.name)
    if sub_id is None:
        log.warning(f"  ⚠️  Dossier non reconnu, ignoré : {entry.name}")
        continue

    # Cherche tous les .bsproj dans le dossier du sujet (récursif, skip macOS hidden)
    for bp in sorted(entry.rglob("*.bsproj")):
        if bp.name.startswith("._"):
            continue
        sub_to_files[sub_id].append(bp)

log.info(f"🔍 {len(sub_to_files)} sujets avec .bsproj ({sum(len(v) for v in sub_to_files.values())} fichiers)\n")

# ── Boucle principale ─────────────────────────────────────────────────────────
OUT_ROOT.mkdir(parents=True, exist_ok=True)
n_ok = 0
n_err = 0

for sub_id in sorted(sub_to_files):
    bsproj_list = sub_to_files[sub_id]
    sub_dir = OUT_ROOT / f"sub-{sub_id}"
    sub_dir.mkdir(exist_ok=True)
    log.info(f"▶ sub-{sub_id}  ({len(bsproj_list)} fichier(s))")

    for bp in bsproj_list:
        # Nom de sortie : sub-XXXX_<stem>_targets.tsv
        stem = re.sub(r"[^a-zA-Z0-9_-]", "_", bp.stem).strip("_")
        prefix = f"sub-{sub_id}_{stem}"

        try:
            ext = BrainsightExtractor(str(bp))

            n_targets = export_targets_tsv(ext, sub_dir / f"{prefix}_targets.tsv")
            n_samples = export_samples_tsv(ext, sub_dir / f"{prefix}_samples.tsv")

            ext.close()
            log.info(f"  ✓ {bp.name}  →  {n_targets} targets, {n_samples} samples")
            n_ok += 1

        except Exception as e:
            import traceback
            log.error(f"  ❌ {bp.name}: {e}")
            log.debug(traceback.format_exc())
            n_err += 1

log.info(f"\n✅ Terminé : {n_ok} extractions OK, {n_err} erreurs")
log.info(f"   Sortie : {OUT_ROOT}")
log.info(f"📝 Log   : {_log_file}")
