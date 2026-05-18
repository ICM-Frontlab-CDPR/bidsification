"""
Affiche la feuille Patiente/Patient d'un xlsx pour identifier la structure complète.
Usage : python stimSD/_tmp/inspect_patiente.py
        python stimSD/_tmp/inspect_patiente.py /chemin/vers/fichier.xlsx
"""
import re
import sys
from pathlib import Path
import pandas as pd

# Mode "scan" : liste toutes les feuilles de tous les xlsx patients suspects
if len(sys.argv) > 1 and sys.argv[1] == "--scan":
    root = Path("/Volumes/levy/raw/valerocabre/stimSD/Data/sourcedata/1_DATA/1_RAW/1_PATIENTS")
    for xlsx in sorted(root.rglob("*.xlsx")):
        if xlsx.name.startswith("~$") or xlsx.name.startswith("._"):
            continue
        try:
            xl = pd.ExcelFile(xlsx)
            sheets = xl.sheet_names
            pat_sheet = next((s for s in sheets if re.match(r"^patient", s.strip(), re.I)), None)
            if pat_sheet is None:
                print(f"[NO-PAT] {xlsx.parent.name}/{xlsx.name:30s}  {sheets}")
        except Exception as e:
            print(f"[ERR] {xlsx.name}: {e}")
    sys.exit(0)

xl_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "/Users/hippolyte.dreyfus/Desktop/001-001-CM.xlsx"
)
xl = pd.ExcelFile(xl_path)
sheet = next((s for s in xl.sheet_names if re.match(r"patient", s, re.I)), None)
if sheet is None:
    print(f"❌ Aucune feuille 'Patient/Patiente' dans {xl_path.name}")
    print(f"   Feuilles disponibles : {xl.sheet_names}")
    sys.exit(1)

df = pd.read_excel(xl_path, sheet_name=sheet, dtype=str, header=None)
print(f"Fichier : {xl_path.name}  |  Feuille : '{sheet}'  |  shape={df.shape}\n")
print(df.to_string())
print()

# Affichage sous forme clé → valeur pour faciliter la lecture
print("\n─── Paires clé → valeur (col paire: col paire+1) ─────────────────────")
for _, row in df.iterrows():
    for c in range(0, len(row) - 1, 2):
        k = str(row.iloc[c]).strip()
        v = str(row.iloc[c + 1]).strip()
        if k not in ("nan", "", "NaN") and v not in ("nan", "", "NaN"):
            print(f"  {k!r:45s} → {v!r}")
