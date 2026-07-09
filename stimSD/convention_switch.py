#!/usr/bin/env python3
"""
convention_switch.py
====================

Renomme les fichiers et dossiers d'une arborescence en faisant passer les
identifiants sujets d'une convention de nommage à une autre, à partir de la
table de correspondance ``STIM-SD_correspondances_conventions.xlsx``.

Les conventions disponibles sont simplement les colonnes de la feuille
``Correspondances`` :

    eCRF, eCRF_ID, sub_eCRF_BIDS, Excel, Excel_ID, CENIR, CENIR_ID

Chaque occurrence d'un identifiant source trouvée dans un nom de fichier/dossier
est remplacée par l'identifiant cible correspondant. L'appariement se fait sur
frontières de token (un identifiant n'est remplacé que s'il n'est pas collé à
un autre caractère alphanumérique), ce qui évite qu'un ID court comme ``0001``
ne matche à l'intérieur de ``10001``.

Exemples
--------
    # Copie de bids_raw/ vers bids_ecrf/, du nom Excel vers la convention BIDS
    python convention_switch.py bids_raw \
        --mode copy --dest bids_ecrf \
        --from Excel --to sub_eCRF_BIDS

    # Transformation sur place (avec prévisualisation d'abord)
    python convention_switch.py /data/study --from CENIR --to eCRF --dry-run
    python convention_switch.py /data/study --from CENIR --to eCRF --mode inplace

Notes
-----
* Faire un ``--dry-run`` avant toute transformation ``inplace``.
* Certaines colonnes ``*_ID`` contiennent des doublons (p. ex. ``Excel_ID`` /
  ``CENIR_ID``) : elles sont donc ambiguës comme convention *source* et le
  script s'arrête avec une erreur explicite si on tente de les utiliser ainsi.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    sys.exit("pandas est requis : pip install pandas openpyxl")


DEFAULT_XLSX = "STIM-SD_correspondances_conventions.xlsx"
DEFAULT_SHEET = "Correspondances"
CONVENTION_COLUMNS = [
    "eCRF", "eCRF_ID", "sub_eCRF_BIDS",
    "Excel", "Excel_ID",
    "CENIR", "CENIR_ID",
]


# --------------------------------------------------------------------------- #
# Construction du mapping
# --------------------------------------------------------------------------- #
def load_mapping(xlsx: Path, sheet: str, src_conv: str, dst_conv: str) -> dict[str, str]:
    """Construit le dictionnaire {valeur_source: valeur_cible} à partir du xlsx.

    Lève une erreur si la convention source contient des valeurs dupliquées
    pointant vers des cibles différentes (mapping ambigu).
    """
    df = pd.read_excel(xlsx, sheet_name=sheet, dtype=str)

    for conv in (src_conv, dst_conv):
        if conv not in df.columns:
            raise SystemExit(
                f"Convention inconnue : {conv!r}.\n"
                f"Colonnes disponibles : {', '.join(c for c in df.columns)}"
            )

    def clean(v: object) -> str:
        s = "" if v is None else str(v).strip()
        return "" if s.lower() in ("nan", "", "—", "xxxx") else s

    mapping: dict[str, str] = {}
    ambiguous: dict[str, set[str]] = defaultdict(set)
    missing_target: list[str] = []

    for src, dst in zip(df[src_conv], df[dst_conv]):
        s, d = clean(src), clean(dst)
        if not s:
            continue
        if not d:
            missing_target.append(s)
            continue
        if s in mapping and mapping[s] != d:
            ambiguous[s].update({mapping[s], d})
        mapping[s] = d

    if ambiguous:
        details = "\n".join(f"  {k!r} -> {sorted(v)}" for k, v in ambiguous.items())
        raise SystemExit(
            f"Convention source {src_conv!r} ambiguë (valeurs dupliquées vers "
            f"des cibles différentes) :\n{details}\n"
            f"Choisis une convention source unique (eCRF, Excel, CENIR, "
            f"sub_eCRF_BIDS ou eCRF_ID)."
        )

    if missing_target:
        print(
            f"[avertissement] {len(missing_target)} sujet(s) sans valeur cible "
            f"en {dst_conv!r} : {', '.join(missing_target)}",
            file=sys.stderr,
        )

    if not mapping:
        raise SystemExit("Mapping vide : rien à faire.")

    return mapping


def build_matcher(mapping: dict[str, str]) -> re.Pattern[str]:
    """Compile un motif unique, alternatives triées par longueur décroissante,
    encadrées par des frontières de token (pas de match au milieu d'un mot)."""
    keys = sorted(mapping, key=len, reverse=True)
    alt = "|".join(re.escape(k) for k in keys)
    return re.compile(rf"(?<![0-9A-Za-z])(?:{alt})(?![0-9A-Za-z])")


def rename_string(name: str, matcher: re.Pattern[str], mapping: dict[str, str]) -> tuple[str, int]:
    """Applique le remplacement en une seule passe. Retourne (nouveau_nom, n_remplacements)."""
    count = 0

    def _sub(m: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return mapping[m.group(0)]

    return matcher.sub(_sub, name), count


# --------------------------------------------------------------------------- #
# Application sur l'arborescence
# --------------------------------------------------------------------------- #
def collect_paths(root: Path, recursive: bool) -> list[Path]:
    """Chemins à traiter, triés du plus profond au moins profond (rename bottom-up)."""
    if recursive:
        paths = list(root.rglob("*"))
    else:
        paths = list(root.iterdir())
    return sorted(paths, key=lambda p: len(p.parts), reverse=True)


def process(
    src_root: Path,
    matcher: re.Pattern[str],
    mapping: dict[str, str],
    recursive: bool,
    dry_run: bool,
) -> None:
    """Renomme in-place l'arborescence sous ``src_root`` (bottom-up)."""
    n_renamed = n_seen = n_conflict = 0

    for path in collect_paths(src_root, recursive):
        n_seen += 1
        new_name, n = rename_string(path.name, matcher, mapping)
        if n == 0 or new_name == path.name:
            continue
        target = path.with_name(new_name)
        if target.exists():
            print(f"[conflit] cible déjà existante, ignoré : {target}", file=sys.stderr)
            n_conflict += 1
            continue
        print(f"  {path}  ->  {target.name}")
        if not dry_run:
            path.rename(target)
        n_renamed += 1

    tag = "[dry-run] " if dry_run else ""
    print(
        f"\n{tag}{n_renamed} élément(s) renommé(s) sur {n_seen} inspecté(s)"
        + (f", {n_conflict} conflit(s)." if n_conflict else ".")
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Renomme fichiers/dossiers d'une convention de nommage sujet à une autre.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("src", type=Path, help="Dossier source contenant les fichiers/dossiers à renommer.")
    p.add_argument("--from", dest="from_conv", required=True, metavar="CONVENTION",
                   help=f"Convention source. Choix : {', '.join(CONVENTION_COLUMNS)}")
    p.add_argument("--to", dest="to_conv", required=True, metavar="CONVENTION",
                   help="Convention cible (même liste que --from).")
    p.add_argument("--mode", choices=("copy", "inplace"), default="copy",
                   help="copy : travaille sur une copie (défaut). inplace : modifie le dossier source.")
    p.add_argument("--dest", type=Path, default=None,
                   help="Dossier de sortie (requis si --mode copy).")
    p.add_argument("--xlsx", type=Path, default=Path(DEFAULT_XLSX),
                   help=f"Table de correspondance (défaut : {DEFAULT_XLSX}).")
    p.add_argument("--sheet", default=DEFAULT_SHEET, help=f"Feuille (défaut : {DEFAULT_SHEET}).")
    p.add_argument("--no-recursive", dest="recursive", action="store_false",
                   help="Ne traiter que le premier niveau (pas de descente récursive).")
    p.add_argument("--dry-run", action="store_true",
                   help="Prévisualise les renommages sans rien modifier.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    if not args.src.is_dir():
        raise SystemExit(f"Dossier source introuvable : {args.src}")
    if not args.xlsx.is_file():
        raise SystemExit(f"Fichier de correspondance introuvable : {args.xlsx}")

    mapping = load_mapping(args.xlsx, args.sheet, args.from_conv, args.to_conv)
    matcher = build_matcher(mapping)
    print(f"{len(mapping)} correspondance(s) chargée(s) : {args.from_conv} -> {args.to_conv}\n")

    # Détermination de la racine de travail
    if args.mode == "copy":
        if args.dest is None:
            raise SystemExit("--dest est requis en --mode copy.")
        if args.dest.exists():
            raise SystemExit(f"Le dossier de destination existe déjà : {args.dest}")
        if not args.dry_run:
            shutil.copytree(args.src, args.dest)
            work_root = args.dest
            print(f"Copie créée : {args.src} -> {args.dest}\n")
        else:
            # En dry-run on ne copie pas : on prévisualise sur la source.
            work_root = args.src
            print("[dry-run] copie non effectuée, prévisualisation sur la source.\n")
    else:  # inplace
        if args.dest is not None:
            print("[info] --dest ignoré en --mode inplace.", file=sys.stderr)
        work_root = args.src

    process(work_root, matcher, mapping, args.recursive, args.dry_run)


if __name__ == "__main__":
    main()
