"""
Inspection des fichiers Excel sourcedata pour les cas problématiques.
But : comprendre la structure des colonnes et le décalage signalé.

Les xlsx ont été préalablement copiés localement dans :
  ~/Desktop/_stimSD/tmp/beh/
pour éviter la lenteur du volume réseau.
"""
import pandas as pd
from pathlib import Path

LOCAL_DIR = Path.home() / "Desktop/_stimSD/tmp/beh"

# Cas mentionnés dans la demande (décalage de colonnes + cas limite)
# On lit directement les xlsx copiés localement
CASES = ["001-0001-CMC", "001-0004-MA", "001-0014-BS", "001-0016-BJC"]

# Regroupe tous les xlsx locaux disponibles
all_local = sorted(
    f for f in LOCAL_DIR.glob("*.xlsx")
    if not f.name.startswith("~$") and not f.name.startswith("._")
)
print(f"Fichiers locaux trouvés : {[f.name for f in all_local]}\n")

for xlsx in all_local:
    print(f"\n{'='*70}")
    print(f"Fichier : {xlsx.name}")
    xl = pd.ExcelFile(xlsx)
    print(f"Feuilles : {xl.sheet_names}")

    for sheet in ["AS visuelle", "AS verbale"]:
        if sheet not in xl.sheet_names:
            continue
        df = pd.read_excel(xlsx, sheet_name=sheet, dtype=str, header=0)
        print(f"\n  ---- Feuille : {sheet}  ({df.shape[0]} lignes x {df.shape[1]} cols) ----")
        print(f"  Toutes les colonnes :")
        for i, c in enumerate(df.columns):
            print(f"    [{i:02d}] {repr(c)}")
        print(f"\n  5 premières lignes (toutes colonnes) :")
        print(df.head(5).to_string())


