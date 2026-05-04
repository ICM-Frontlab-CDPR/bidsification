from pathlib import Path
import pandas as pd


from pathlib import Path
import pandas as pd


def patch_bids_channels(bids_root):
    bids_root = Path(bids_root)

    channels_files = list(bids_root.rglob("*_channels.tsv"))
    print(f"🔍 {len(channels_files)} fichiers channels.tsv trouvés")

    files_to_modify = []

    # Création de la liste de fichiers à modifier
    for ch_file in channels_files:
        df = pd.read_csv(ch_file, sep="\t")

        if "name" not in df.columns or "type" not in df.columns:
            continue

        mask = df["name"].isin(["X", "Y", "Z"])

        if mask.any():
            files_to_modify.append(ch_file)

    # ✅ CHECK utilisateur ici (comme tu veux)
    print("\n⚠️ FICHIERS QUI SERONT MODIFIÉS :")
    for f in files_to_modify:
        print(" -", f)

    print(f"\n➡️ Nombre de fichiers à modifier : {len(files_to_modify)}")

    if len(files_to_modify) == 0:
        print("✅ Rien à modifier.")
        return

    answer = input("\nConfirmer la modification ? (y/n) : ").strip().lower()

    if answer != "y":
        print("❌ Annulé par l'utilisateur.")
        return

    # Modification réelle
    for ch_file in files_to_modify:
        df = pd.read_csv(ch_file, sep="\t")
        mask = df["name"].isin(["X", "Y", "Z"])
        df.loc[mask, "type"] = "misc"
        df.to_csv(ch_file, sep="\t", index=False)
        print(f"💾 Modifié : {ch_file}")

    print("\n✅ Terminé.")



bids_path = "/network/iss/levy/raw/valerocabre/clonesatACS/Data/bids"
patch_bids_channels(bids_path)