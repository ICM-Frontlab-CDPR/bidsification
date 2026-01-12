#!/usr/bin/env python3
import mne
from mne_bids import write_raw_bids, BIDSPath
from pathlib import Path

# Chemins
RAW = Path('/Users/hippolyte.dreyfus/Desktop/RAW/eeg/3_fif')
BIDS_ROOT = Path('/Users/hippolyte.dreyfus/Desktop/BIDS')

# Trouver tous les fichiers .fif
fif_files = list(RAW.rglob('*.fif'))
print(f"🔍 {len(fif_files)} fichiers .fif trouvés:")
for f in fif_files:
    print(f"  - {f}")
print()

# Parcourir les fichiers .fif
for fif_file in fif_files:
    # Extraire sub et ses depuis le chemin
    parts = fif_file.parts
    subject = parts[-3].replace('sub_', '')
    session = parts[-2].replace('ses_', '')
    
    # Lire raw
    raw = mne.io.read_raw_fif(fif_file, preload=False)
    
    # Créer BIDSPath
    bids_path = BIDSPath(
        subject=subject,
        session=session,
        task='tacs',
        datatype='eeg',
        root=BIDS_ROOT
    )
    
    # Écrire en BIDS
    write_raw_bids(raw, bids_path, overwrite=True)
    print(f"✓ {fif_file.name}")
