#!/usr/bin/env python3
import mne
from mne_bids import write_raw_bids, BIDSPath
from pathlib import Path
import yaml
import re

# Charger la configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Chemins
RAW = Path(config['paths']['raw_root']) / config['paths']['raw_eeg']
BIDS_ROOT = Path(config['paths']['bids_root'])
TASK = config['experiment']['task']
DATATYPE = config['bids']['datatype_eeg']


def parse_fif_filename(filename):
    """
    Parse le nom de fichier .fif pour extraire les informations.
    Formats attendus:
    - su01_1_RS_C_0_eeg.fif -> RSC, run 0
    - su01_1_SHAM_1_baseline_pre_eeg.fif -> SHAM, run 1, baselinepre
    - su01_1_TACS_2_STIM_eeg.fif -> TACS, run 2, stim
    
    Note: Les underscores ne sont pas autorisés dans les valeurs BIDS,
    donc RS_C devient RSC, baseline_pre devient baselinepre, etc.
    """
    # Enlever le * final et l'extension
    filename = filename.rstrip('*').replace('_eeg.fif', '')
    
    # Pattern pour RS_C ou RS_O
    match_rs = re.match(r'su\d+_\d+_RS_([CO])_(\d+)', filename)
    if match_rs:
        eyes = match_rs.group(1)  # C ou O
        condition = f'RS{eyes}'  # RSC ou RSO (sans underscore pour BIDS)
        run = match_rs.group(2)
        acquisition = None
        return condition, run, acquisition
    
    # Pattern pour SHAM, TACS, TRNS
    match_stim = re.match(r'su\d+_\d+_(SHAM|TACS|TRNS)_(\d+)_(.+)', filename)
    if match_stim:
        condition = match_stim.group(1)  # SHAM, TACS, TRNS
        run = match_stim.group(2)
        acquisition = match_stim.group(3)  # baseline_pre, baseline_post, STIM
        # Remplacer les underscores par rien pour respecter BIDS
        acquisition = acquisition.replace('_', '')  # baseline_pre -> baselinepre
        return condition, run, acquisition
    
    return None, None, None

# Trouver tous les fichiers .fif
fif_files = list(RAW.rglob('*.fif'))
print(f"🔍 {len(fif_files)} fichiers .fif trouvés:")
for f in fif_files:
    print(f"  - {f}")
print()

# Demander confirmation à l'utilisateur
response = input(f"⚠️  Voulez-vous continuer et convertir ces {len(fif_files)} fichiers en BIDS? (o/n): ")
if response.lower() not in ['o', 'oui', 'y', 'yes']:
    print("❌ Conversion annulée par l'utilisateur.")
    exit(0)

# Demander si on écrase les fichiers existants
overwrite = False
overwrite_response = input("🔄 Écraser les fichiers BIDS déjà existants? (o/n): ")
if overwrite_response.lower() in ['o', 'oui', 'y', 'yes']:
    overwrite = True

print("\n🔄 Début de la conversion...")
print()

# Compteur de fichiers traités
files_processed = 0
files_failed = 0
files_skipped = 0

# Parcourir les fichiers .fif
for fif_file in fif_files:
    try:
        # Extraire sub et ses depuis le chemin
        parts = fif_file.parts
        subject = parts[-3].replace('sub_', '')
        session = parts[-2].replace('ses_', '')
        
        # Parser le nom de fichier pour extraire condition, run et acquisition
        condition, run, acquisition = parse_fif_filename(fif_file.name)
        
        if condition is None:
            print(f"⚠️  {fif_file.name}: Format de nom non reconnu, ignoré")
            files_failed += 1
            continue
        
        # Créer BIDSPath avec les informations extraites
        bids_path = BIDSPath(
            subject=subject,
            session=session,
            task=condition,  # Utiliser la condition comme task (RS_C, SHAM, etc.)
            run=run,
            acquisition=acquisition,  # baseline_pre, baseline_post, STIM, ou None
            datatype=DATATYPE,
            root=BIDS_ROOT
        )
        
        # Vérifier si le fichier existe déjà
        bids_file = bids_path.copy().update(suffix=DATATYPE, extension='.fif')
        bids_file_path = bids_file.fpath
        
        if bids_file_path.exists() and not overwrite:
            print(f"⏭️  {fif_file.name} (déjà existant)")
            files_skipped += 1
            continue
        
        # Lire raw
        raw = mne.io.read_raw_fif(fif_file, preload=False)
        
        # Écrire en BIDS
        write_raw_bids(raw, bids_path, overwrite=overwrite)
        
        # Afficher avec les détails
        info_str = f"task={condition}, run={run}"
        if acquisition:
            info_str += f", acq={acquisition}"
        print(f"✓ {fif_file.name} → {info_str}")
        files_processed += 1
        
    except Exception as e:
        print(f"❌ Erreur avec {fif_file.name}: {e}")
        files_failed += 1

# Rapport final
print()
print("=" * 80)
print("📊 RAPPORT FINAL")
print("=" * 80)
print(f"  Fichiers trouvés:   {len(fif_files)}")
print(f"  Fichiers convertis: {files_processed} ✓")
if files_skipped > 0:
    print(f"  Fichiers ignorés:   {files_skipped} ⏭️")
if files_failed > 0:
    print(f"  Fichiers échoués:   {files_failed} ❌")
print()

if files_processed == len(fif_files):
    print("✅ Tous les fichiers ont été convertis avec succès!")
elif files_processed > 0:
    print(f"⚠️  Conversion partielle: {files_processed}/{len(fif_files)} fichiers convertis.")
else:
    if files_skipped > 0:
        print("ℹ️  Aucun nouveau fichier à convertir (tous déjà existants).")
    else:
        print("❌ Aucun fichier n'a été converti.")