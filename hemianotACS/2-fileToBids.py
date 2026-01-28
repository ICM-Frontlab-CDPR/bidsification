#!/usr/bin/env python3
"""
Bidsifie les fichiers BrainVision (.vhdr) présents dans BIDS_ROOT.
Corrige les références internes et renomme les fichiers au format BIDS.
"""

import mne
from mne_bids import write_raw_bids, BIDSPath, get_entities_from_fname
from pathlib import Path
import yaml
import re
import shutil

# Charger la configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

BIDS_ROOT = Path(config['paths']['bids_root'])

# Listes des sujets et sessions à traiter
subjects = ['0002']
sessions = ['01']


def fix_vhdr_references(vhdr_file):
    """Corrige les références aux fichiers .vmrk et .eeg dans le .vhdr."""
    content = vhdr_file.read_text()
    
    # Construire les noms BIDS attendus
    base_name = vhdr_file.stem.replace('_eeg', '')
    expected_vmrk = f"{base_name}_eeg.vmrk"
    expected_eeg = f"{base_name}_eeg.eeg"
    
    # Remplacer les références
    content = re.sub(r'MarkerFile=.*\.vmrk', f'MarkerFile={expected_vmrk}', content)
    content = re.sub(r'DataFile=.*\.(eeg|dat)', f'DataFile={expected_eeg}', content)
    
    vhdr_file.write_text(content)
    return expected_vmrk, expected_eeg


def rename_associated_files(vhdr_file):
    """Renomme les fichiers .vmrk et .eeg/.dat associés pour correspondre au .vhdr."""
    eeg_dir = vhdr_file.parent
    base_name = vhdr_file.stem.replace('_eeg', '')
    
    # Lire le contenu du .vhdr pour trouver les noms actuels des fichiers associés
    try:
        content = vhdr_file.read_text()
        
        # Trouver le fichier .vmrk référencé
        vmrk_match = re.search(r'MarkerFile=(.+\.vmrk)', content)
        if vmrk_match:
            old_vmrk_name = vmrk_match.group(1).strip()
            old_vmrk = eeg_dir / old_vmrk_name
            new_vmrk = eeg_dir / f"{base_name}_eeg.vmrk"
            if old_vmrk.exists() and old_vmrk != new_vmrk:
                shutil.move(str(old_vmrk), str(new_vmrk))
        
        # Trouver le fichier .eeg/.dat référencé
        data_match = re.search(r'DataFile=(.+\.(eeg|dat))', content)
        if data_match:
            old_data_name = data_match.group(1).strip()
            old_data = eeg_dir / old_data_name
            ext = Path(old_data_name).suffix
            new_data = eeg_dir / f"{base_name}_eeg{ext}"
            if old_data.exists() and old_data != new_data:
                shutil.move(str(old_data), str(new_data))
                
    except Exception as e:
        # Si on ne peut pas lire le fichier, on passe
        pass


def fix_run_in_filename(vhdr_file):
    """Corrige les noms de fichiers avec run non-numérique (OG1, OD2, etc.) et ajoute run-1 si absent."""
    name = vhdr_file.name
    eeg_dir = vhdr_file.parent
    
    # Mapper OG1->1, OD2->2, etc.
    run_mapping = {
        'OG1': '1', 'OG2': '2',
        'OD1': '1', 'OD2': '2',
    }
    
    for old_run, new_run in run_mapping.items():
        if f'run-{old_run}' in name:
            new_name = name.replace(f'run-{old_run}', f'run-{new_run}')
            new_path = vhdr_file.parent / new_name
            if not new_path.exists():
                # Renommer aussi les fichiers associés
                base_old = vhdr_file.stem.replace('_eeg', '')
                base_new = new_path.stem.replace('_eeg', '')
                
                # Renommer .vmrk
                old_vmrk = eeg_dir / f"{base_old}_eeg.vmrk"
                new_vmrk = eeg_dir / f"{base_new}_eeg.vmrk"
                if old_vmrk.exists():
                    shutil.move(str(old_vmrk), str(new_vmrk))
                
                # Renommer .eeg/.dat
                for ext in ['.eeg', '.dat']:
                    old_data = eeg_dir / f"{base_old}_eeg{ext}"
                    new_data = eeg_dir / f"{base_new}_eeg{ext}"
                    if old_data.exists():
                        shutil.move(str(old_data), str(new_data))
                
                # Renommer le .vhdr
                shutil.move(str(vhdr_file), str(new_path))
                return new_path
    
    # Ajouter run-1 si pas de run dans le nom
    if '_run-' not in name:
        # Insérer run-1 avant _eeg
        new_name = name.replace('_eeg.vhdr', '_run-1_eeg.vhdr')
        new_path = vhdr_file.parent / new_name
        if new_path != vhdr_file and not new_path.exists():
            # Renommer aussi les fichiers associés
            base_old = vhdr_file.stem.replace('_eeg', '')
            base_new = new_path.stem.replace('_eeg', '')
            
            # Renommer .vmrk
            old_vmrk = eeg_dir / f"{base_old}_eeg.vmrk"
            new_vmrk = eeg_dir / f"{base_new}_eeg.vmrk"
            if old_vmrk.exists():
                shutil.move(str(old_vmrk), str(new_vmrk))
            
            # Renommer .eeg/.dat
            for ext in ['.eeg', '.dat']:
                old_data = eeg_dir / f"{base_old}_eeg{ext}"
                new_data = eeg_dir / f"{base_new}_eeg{ext}"
                if old_data.exists():
                    shutil.move(str(old_data), str(new_data))
            
            # Renommer le .vhdr
            shutil.move(str(vhdr_file), str(new_path))
            return new_path
    
    return vhdr_file


def bidsify_brainvision(vhdr_file, overwrite=False):
    """Convertit un fichier BrainVision au format BIDS."""
    try:
        # D'abord renommer les fichiers associés basés sur le contenu du .vhdr
        rename_associated_files(vhdr_file)
        
        # Puis corriger le nom du .vhdr (et ses associés) si nécessaire
        vhdr_file = fix_run_in_filename(vhdr_file)
        
        # Corriger les références internes
        fix_vhdr_references(vhdr_file)
        
        # Parser et convertir
        entities = get_entities_from_fname(vhdr_file.name)
        
        bids_path = BIDSPath(
            subject=entities.get('subject'),
            session=entities.get('session'),
            task=entities.get('task'),
            run=entities.get('run') or '1',  # Utiliser run-1 si pas de run
            acquisition=entities.get('acquisition'),
            datatype='eeg',
            root=BIDS_ROOT
        )
        
        raw = mne.io.read_raw_brainvision(vhdr_file, preload=False, verbose=False)
        write_raw_bids(raw, bids_path, format='BrainVision', overwrite=overwrite, verbose=False)
        
        return True, None
    except Exception as e:
        return False, str(e)


def process_session(subject, session, overwrite=False):
    """Traite une session."""
    session_dir = BIDS_ROOT / f"sub-{subject}" / f"ses-{session}"
    eeg_dir = session_dir / "eeg"
    
    if not eeg_dir.exists():
        return 0, 0
    
    vhdr_files = list(eeg_dir.glob("*.vhdr"))
    processed = 0
    failed = 0
    
    for vhdr_file in vhdr_files:
        json_file = vhdr_file.with_suffix('.json')
        if json_file.exists() and not overwrite:
            continue
        
        success, error = bidsify_brainvision(vhdr_file, overwrite)
        if success:
            processed += 1
        else:
            print(f"❌ {vhdr_file.name}: {error}")
            failed += 1
    
    return processed, failed


def main(overwrite=True):
    """Fonction principale."""
    total_processed = 0
    total_failed = 0
    
    for subject in subjects:
        for session in sessions:
            processed, failed = process_session(subject, session, overwrite)
            total_processed += processed
            total_failed += failed
    
    if total_failed > 0:
        print(f"❌ {total_failed} fichiers échoués")
    if total_processed > 0:
        print(f"✓ {total_processed} fichiers convertis")


if __name__ == "__main__":
    main()
