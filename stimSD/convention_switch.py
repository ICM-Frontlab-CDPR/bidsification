#!/usr/bin/env python3
"""
Copie un dossier en renommant fichiers et sous-dossiers selon une table Excel.

Exemple :
    python convention_switch.py dossier_source \
        --dest dossier_cible \
        --from Excel \
        --to sub_eCRF_BIDS \
        --xlsx STIM-SD_correspondances_conventions.xlsx \
        --on-ambiguous interactive
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
except ImportError:
    sys.exit("Installe les dépendances : pip install pandas openpyxl")


DEFAULT_XLSX = "STIM-SD_correspondances_conventions.xlsx"
DEFAULT_SHEET = "Correspondances"


def clean(value: object) -> str:
    """Transforme une cellule Excel en texte exploitable."""
    text = "" if value is None else str(value).strip()

    if text.lower() in {"", "nan", "none", "xxxx", "—"}:
        return ""

    return text


def choose_target(source: str, targets: list[str], strategy: str) -> str:
    """Choisit une cible lorsqu'une valeur source correspond à plusieurs cibles."""
    if len(targets) == 1:
        return targets[0]

    if strategy == "first":
        return targets[0]

    if strategy == "last":
        return targets[-1]

    if strategy == "error":
        choices = ", ".join(repr(target) for target in targets)
        raise SystemExit(
            f"Ambiguïté pour {source!r} : plusieurs cibles possibles : {choices}\n"
            "Utilise --on-ambiguous interactive, first ou last."
        )

    print(f"\nAmbiguïté pour {source!r} :", file=sys.stderr)
    for index, target in enumerate(targets, start=1):
        print(f"  {index}. {target}", file=sys.stderr)

    while True:
        answer = input(f"Choix (1-{len(targets)}) : ").strip()

        if answer.isdigit() and 1 <= int(answer) <= len(targets):
            return targets[int(answer) - 1]

        print("Choix invalide.", file=sys.stderr)


def load_mapping(
    xlsx: Path,
    sheet: str,
    source_convention: str,
    target_convention: str,
    ambiguity_strategy: str,
) -> dict[str, str]:
    """Construit {identifiant_source: identifiant_cible} depuis le fichier Excel."""
    table = pd.read_excel(xlsx, sheet_name=sheet, dtype=str)

    for convention in (source_convention, target_convention):
        if convention not in table.columns:
            available = ", ".join(str(column) for column in table.columns)
            raise SystemExit(
                f"Convention inconnue : {convention!r}\n"
                f"Colonnes disponibles : {available}"
            )

    candidates: dict[str, list[str]] = defaultdict(list)

    for source, target in zip(
        table[source_convention],
        table[target_convention],
    ):
        source = clean(source)
        target = clean(target)

        if source and target:
            candidates[source].append(target)

    mapping = {}

    for source, targets in candidates.items():
        unique_targets = list(dict.fromkeys(targets))
        mapping[source] = choose_target(
            source,
            unique_targets,
            ambiguity_strategy,
        )

    if not mapping:
        raise SystemExit("Aucune correspondance valide trouvée dans le fichier Excel.")

    return mapping


def build_pattern(mapping: dict[str, str]) -> re.Pattern[str]:
    """Crée un motif qui trouve les identifiants sans matcher dans un autre mot."""
    identifiers = sorted(mapping, key=len, reverse=True)
    alternatives = "|".join(re.escape(identifier) for identifier in identifiers)

    return re.compile(rf"(?<![0-9A-Za-z])({alternatives})(?![0-9A-Za-z])")


def rename_text(text: str, pattern: re.Pattern[str], mapping: dict[str, str]) -> str:
    """Remplace tous les identifiants source trouvés dans un texte."""
    return pattern.sub(lambda match: mapping[match.group(0)], text)


def rename_tree(
    root: Path,
    pattern: re.Pattern[str],
    mapping: dict[str, str],
    dry_run: bool,
) -> None:
    """Renomme tous les fichiers et dossiers, du plus profond vers la racine."""
    paths = sorted(root.rglob("*"), key=lambda path: len(path.parts), reverse=True)

    renamed = 0
    skipped = 0

    for path in paths:
        new_name = rename_text(path.name, pattern, mapping)

        if new_name == path.name:
            continue

        destination = path.with_name(new_name)

        if destination.exists():
            print(f"[conflit] ignoré : {path} -> {destination}", file=sys.stderr)
            skipped += 1
            continue

        print(f"{path} -> {destination}")

        if not dry_run:
            path.rename(destination)

        renamed += 1

    prefix = "[dry-run] " if dry_run else ""
    print(f"\n{prefix}{renamed} élément(s) renommé(s).")

    if skipped:
        print(f"{skipped} conflit(s) ignoré(s).", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copie un dossier et convertit les identifiants dans les noms de fichiers et dossiers."
    )

    parser.add_argument(
        "src",
        type=Path,
        help="Dossier source à copier.",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        required=True,
        help="Dossier de destination. Il ne doit pas déjà exister.",
    )
    parser.add_argument(
        "--from",
        dest="source_convention",
        required=True,
        help="Nom de la colonne Excel contenant les identifiants source.",
    )
    parser.add_argument(
        "--to",
        dest="target_convention",
        required=True,
        help="Nom de la colonne Excel contenant les identifiants cible.",
    )
    parser.add_argument(
        "--xlsx",
        type=Path,
        default=Path(DEFAULT_XLSX),
        help=f"Fichier Excel de correspondance. Défaut : {DEFAULT_XLSX}",
    )
    parser.add_argument(
        "--sheet",
        default=DEFAULT_SHEET,
        help=f"Nom de la feuille Excel. Défaut : {DEFAULT_SHEET}",
    )
    parser.add_argument(
        "--on-ambiguous",
        choices=("interactive", "error", "first", "last"),
        default="interactive",
        help="Gestion des correspondances ambiguës. Défaut : interactive.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche les renommages prévus sans copier ni modifier de fichiers.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.src.is_dir():
        raise SystemExit(f"Dossier source introuvable : {args.src}")

    if not args.xlsx.is_file():
        raise SystemExit(f"Fichier Excel introuvable : {args.xlsx}")

    if args.dest.exists():
        raise SystemExit(f"Le dossier destination existe déjà : {args.dest}")

    mapping = load_mapping(
        args.xlsx,
        args.sheet,
        args.source_convention,
        args.target_convention,
        args.on_ambiguous,
    )
    pattern = build_pattern(mapping)

    print(
        f"{len(mapping)} correspondance(s) chargée(s) : "
        f"{args.source_convention} -> {args.target_convention}"
    )

    if args.dry_run:
        print("\n[dry-run] Copie non créée. Renommages prévisualisés sur la source.\n")
        rename_tree(args.src, pattern, mapping, dry_run=True)
        return

    print(f"\nCopie : {args.src} -> {args.dest}\n")
    shutil.copytree(args.src, args.dest)

    print("Renommage des fichiers et dossiers :\n")
    rename_tree(args.dest, pattern, mapping, dry_run=False)


if __name__ == "__main__":
    main()