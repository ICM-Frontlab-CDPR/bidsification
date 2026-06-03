#!/usr/bin/env python3
"""
1-extract_brainsight_targets_TMS_ALL.py
========================================
Boucle sur tous les .bsproj du dossier TMS sourcedata et extrait
targets + samples pour chaque sujet.

Source  : ClonesaTMS/sourcedata/__mri__/
Sortie  : ClonesaTMS/bids-brainsight/sub-XXXX/
            sub-XXXX_<bsproj_stem>_targets.tsv
            sub-XXXX_<bsproj_stem>_samples.tsv
"""
import csv
import logging
import plistlib
import re
import sqlite3
import struct
import traceback
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# ── Chemins ──────────────────────────────────────────────────────────────────
SRC_ROOT = Path(
    "/network/iss/levy/raw/valerocabre/clonesa/Data/ClonesaTMS/sourcedata/__mri__"
)
OUT_ROOT = Path(
    "/network/iss/levy/raw/valerocabre/clonesa/Data/ClonesaTMS/bids-brainsight"
)

# ── Logging ──────────────────────────────────────────────────────────────────
_LOG_DIR = Path("/network/iss/home/hippolyte.dreyfus/Documents/bidsification/clonesa/_log")
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


# ── Parsing des blobs NSKeyedArchiver ─────────────────────────────────────────
def _parse_position(blob: bytes) -> Optional[List[float]]:
    """
    Extrait (x, y, z) depuis un blob Brainsight.
    Le blob est un NSKeyedArchiver plist contenant $objects[2] = 128 bytes
    = 16 doubles little-endian (matrice 4x4 colonne-major).
    Translation = indices [12, 13, 14].
    """
    if not blob:
        return None
    try:
        p = plistlib.loads(blob)
        matrix_bytes = p["$objects"][2]
        if isinstance(matrix_bytes, bytes) and len(matrix_bytes) == 128:
            vals = struct.unpack("<16d", matrix_bytes)
            return [vals[12], vals[13], vals[14]]
    except Exception:
        pass
    return None


def _parse_rotation(blob: bytes) -> Optional[List[List[float]]]:
    """Extrait la matrice de rotation 3x3 depuis le blob."""
    if not blob:
        return None
    try:
        p = plistlib.loads(blob)
        matrix_bytes = p["$objects"][2]
        if isinstance(matrix_bytes, bytes) and len(matrix_bytes) == 128:
            vals = struct.unpack("<16d", matrix_bytes)
            return [[vals[i * 4 + j] for j in range(3)] for i in range(3)]
    except Exception:
        pass
    return None


# ── Extraction SQLite ─────────────────────────────────────────────────────────
def extract_targets(bsproj_path: Path) -> List[Dict]:
    conn = sqlite3.connect(bsproj_path)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT ZNAME, ZPOSITION, ZTRANSFORM FROM ZTARGETNODE "
            "WHERE ZNAME IS NOT NULL ORDER BY ZINDEXX, ZINDEXY"
        )
        rows = cur.fetchall()
    except sqlite3.Error:
        rows = []
    conn.close()
    results = []
    for name, pos_blob, trans_blob in rows:
        pos = _parse_position(pos_blob)
        rot = _parse_rotation(trans_blob) or _parse_rotation(pos_blob)
        results.append({"name": name, "position": pos, "rotation": rot})
    return results


def extract_samples(bsproj_path: Path) -> List[Dict]:
    conn = sqlite3.connect(bsproj_path)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT ZINDEX, ZNAME, ZTARGETNAME, ZPOSITION, "
            "ZSTIMULATORPOWERA, ZSTIMULATORPOWERB "
            "FROM ZSAMPLE WHERE ZPOSITION IS NOT NULL ORDER BY ZINDEX"
        )
        rows = cur.fetchall()
    except sqlite3.Error:
        rows = []
    conn.close()
    results = []
    for idx, name, target_name, pos_blob, power_a, power_b in rows:
        pos = _parse_position(pos_blob)
        rot = _parse_rotation(pos_blob)
        results.append({
            "index": idx,
            "name": name or "",
            "target_name": target_name or "",
            "position": pos,
            "rotation": rot,
            "power_a": power_a,
            "power_b": power_b,
        })
    return results


# ── Export TSV ────────────────────────────────────────────────────────────────
def export_targets_tsv(bsproj_path: Path, out_path: Path) -> int:
    targets = extract_targets(bsproj_path)
    valid = [t for t in targets if t["position"] is not None]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["name", "x", "y", "z"])
        for t in valid:
            x, y, z = t["position"]
            w.writerow([t["name"], f"{x:.4f}", f"{y:.4f}", f"{z:.4f}"])
    return len(valid)


def export_samples_tsv(bsproj_path: Path, out_path: Path) -> int:
    samples = extract_samples(bsproj_path)
    valid = [s for s in samples if s["position"] is not None]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["index", "name", "target_name", "x", "y", "z", "power_a", "power_b"])
        for s in valid:
            x, y, z = s["position"]
            w.writerow([
                s["index"],
                s["name"],
                s["target_name"],
                f"{x:.4f}", f"{y:.4f}", f"{z:.4f}",
                s["power_a"] or "",
                s["power_b"] or "",
            ])
    return len(valid)


# ── Mapping sujet ─────────────────────────────────────────────────────────────
CLONESA_RE = re.compile(r"^CLONESA_002_(\d{4})$")
SUBJ_RE    = re.compile(r"^SUBJ_(\d+)$", re.IGNORECASE)
_MANUAL    = {"sub_49": "0049", "subj_48": "0048", "subj_50": "0050"}
_SKIP      = {"Other", "TONI MRI", "CLONESA_mislabbeled_Xnat", "sub-001", "sub_032"}


def folder_to_sub_id(name: str) -> Optional[str]:
    m = CLONESA_RE.match(name)
    if m:
        return m.group(1)
    m2 = SUBJ_RE.match(name)
    if m2:
        return m2.group(1).zfill(4)
    return _MANUAL.get(name)


# ── Découverte des .bsproj ────────────────────────────────────────────────────
sub_to_files: Dict[str, List[Path]] = defaultdict(list)

for entry in sorted(SRC_ROOT.iterdir()):
    if not entry.is_dir() or entry.name in _SKIP:
        continue
    sub_id = folder_to_sub_id(entry.name)
    if sub_id is None:
        log.warning(f"  ⚠️  Dossier non reconnu, ignoré : {entry.name}")
        continue
    for bp in sorted(entry.rglob("*.bsproj")):
        if bp.name.startswith("._"):
            continue
        sub_to_files[sub_id].append(bp)

log.info(f"🔍 {len(sub_to_files)} sujets avec .bsproj "
         f"({sum(len(v) for v in sub_to_files.values())} fichiers)\n")

# ── Boucle principale ─────────────────────────────────────────────────────────
OUT_ROOT.mkdir(parents=True, exist_ok=True)
n_ok = n_err = 0

for sub_id in sorted(sub_to_files):
    bsproj_list = sub_to_files[sub_id]
    sub_dir = OUT_ROOT / f"sub-{sub_id}"
    sub_dir.mkdir(exist_ok=True)
    log.info(f"▶ sub-{sub_id}  ({len(bsproj_list)} fichier(s))")

    for bp in bsproj_list:
        stem = re.sub(r"[^a-zA-Z0-9_-]", "_", bp.stem).strip("_")
        prefix = f"sub-{sub_id}_{stem}"
        try:
            n_t = export_targets_tsv(bp, sub_dir / f"{prefix}_targets.tsv")
            n_s = export_samples_tsv(bp, sub_dir / f"{prefix}_samples.tsv")
            log.info(f"  ✓ {bp.name}  →  {n_t} targets, {n_s} samples")
            n_ok += 1
        except Exception as e:
            log.error(f"  ❌ {bp.name}: {e}")
            log.debug(traceback.format_exc())
            n_err += 1

log.info(f"\n✅ Terminé : {n_ok} OK, {n_err} erreurs")
log.info(f"   Sortie : {OUT_ROOT}")
log.info(f"📝 Log   : {_log_file}")
