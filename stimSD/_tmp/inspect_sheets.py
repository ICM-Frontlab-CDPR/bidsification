"""
Résume toutes les feuilles d'un xlsx :
  - nom exact
  - dimensions
  - 4 premières lignes (pour identifier la structure)

Usage : python stimSD/_tmp/inspect_sheets.py
        python stimSD/_tmp/inspect_sheets.py /chemin/vers/fichier.xlsx
"""
import sys
from pathlib import Path
import pandas as pd

xl_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/Users/hippolyte.dreyfus/Desktop/001-001-CM.xlsx")

print(f"Fichier : {xl_path}\n")
xl = pd.ExcelFile(xl_path)

print(f"{'─'*70}")
print(f"{'#':>3}  {'Nom de la feuille':<30}  {'Shape':>12}")
print(f"{'─'*70}")
for i, sheet in enumerate(xl.sheet_names, 1):
    df = pd.read_excel(xl_path, sheet_name=sheet, dtype=str, header=None, nrows=50)
    print(f"{i:>3}  {sheet!r:<30}  {str(df.shape):>12}")
print(f"{'─'*70}\n")

# Détail par feuille : 6 premières lignes, 12 premières colonnes
for sheet in xl.sheet_names:
    df = pd.read_excel(xl_path, sheet_name=sheet, dtype=str, header=None, nrows=6)
    print(f"\n{'='*70}")
    print(f"  FEUILLE : {sheet!r}")
    print(f"{'='*70}")
    print(df.iloc[:, :12].to_string())
