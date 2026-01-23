#!/usr/bin/env python3
"""
Script de BIDSification pour le projet hemianotACS
Convertit les fichiers EEG en format BIDS avec une structure modulaire
"""
import mne
from mne_bids import write_raw_bids, BIDSPath
from pathlib import Path
import re
import pandas as pd
import shutil
import json
import sys
from collections import Counter
from typing import Tuple, Optional, List, Dict

# ============================================================================
# CONFIGURATION
# ============================================================================

RAW_ROOT = Path("/Users/hippolyte.dreyfus/Desktop/hemianotACS/Data/raw/HEMIANOTACS_WIP")
BIDS_ROOT = Path("/Users/hippolyte.dreyfus/Desktop/hemianotACS/Data/bidstest")
DERIVATIVES_ROOT = Path("/Users/hippolyte.dreyfus/Desktop/hemianotACS/Data/derivatives")
EEG_PATH = RAW_ROOT / "EEG"

BIDS_ROOT.mkdir(parents=True, exist_ok=True)


# ============================================================================
# FONCTIONS D'EXTRACTION D'INFORMATIONS
# ============================================================================

def extract_subject_info(folder_name: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extrait les informations du dossier participant.
    
    Args:
        folder_name: Nom du dossier (ex: '001-0001-CC_PATIENT')
    
    Returns:
        Tuple (subject_id, group, initials) ou (None, None, None)
    """
    match = re.match(r'(\d+)-(\d+)-([A-Z]+)_(PATIENT|HEALTHY)', folder_name)
    if match:
        subject_id = match.group(2)
        group = match.group(4)
        initials = match.group(3)
        return subject_id, group, initials
    return None, None, None


def extract_session_from_folder(folder_name: str) -> Optional[str]:
    """
    Extrait le numéro de session depuis le nom du dossier.
    
    Args:
        folder_name: Nom du dossier (ex: 'V1_BASELINE_22-12-2020')
    
    Returns:
        Numéro de session formaté ('01', '02', etc.) ou None
    """
    match = re.match(r'V(\d+)', folder_name)
    if match:
        return match.group(1).zfill(2)
    return None


def parse_edf_filename(filename: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parse le nom de fichier .edf pour extraire task, acquisition et run.
    
    Args:
        filename: Nom du fichier .edf
    
    Returns:
        Tuple (task, acquisition, run) ou (None, None, None) si non reconnu
    """
    # Ignorer les fichiers ABORTED ou easy_converted
    if 'ABORTED' in filename or 'easy_converted' in filename:
        return None, None, None
    
    # Extraire le numéro de stimulation (Stim1, Stim2, Stim3)
    stim_match = re.search(r'[Ss]tim(\d+)', filename)
    run = stim_match.group(1) if stim_match else None
    
    # Identifier le type de tâche
    if 'Resting-state' in filename or 'resting' in filename.lower():
        task = 'rest'
        if '_Pre' in filename or 'Pre_' in filename or 'Prestim' in filename:
            acq = 'pre'
        elif '_Post' in filename or 'Post_' in filename or 'Poststim' in filename:
            acq = 'post'
        else:
            acq = None
            
    elif 'Task' in filename or 'task' in filename:
        task = 'flanker'
        if 'PreStim' in filename or 'Prestim' in filename:
            acq = 'pre'
        elif 'PostStim' in filename or 'Poststim' in filename:
            acq = 'post'
        else:
            acq = None
            
    elif 'SHAM' in filename or 'tACS' in filename or 'tRNS' in filename:
        task = 'stim'
        if 'SHAM' in filename:
            acq = 'SHAM'
        elif 'tACS' in filename:
            acq = 'tACS'
        elif 'tRNS' in filename:
            acq = 'tRNS'
        else:
            acq = None
    else:
        return None, None, None
    
    return task, acq, run


# ============================================================================
# FONCTIONS DE COLLECTE DE FICHIERS
# ============================================================================

def collect_subject_directories() -> List[Path]:
    """
    Collecte tous les dossiers de participants valides.
    
    Returns:
        Liste des dossiers de participants triés
    """
    return sorted([d for d in EEG_PATH.iterdir() if d.is_dir()])


def collect_edf_files(subject_dirs: List[Path]) -> List[Path]:
    """
    Collecte tous les fichiers .edf valides.
    
    Args:
        subject_dirs: Liste des dossiers de participants
    
    Returns:
        Liste des fichiers .edf (hors ABORTED et easy_converted)
    """
    edf_files = []
    for subj_dir in subject_dirs:
        subject_id, group, initials = extract_subject_info(subj_dir.name)
        if not subject_id or 'excluded' in subj_dir.name or 'STAND_BY' in subj_dir.name:
            continue
        
        eeg_dir = subj_dir / "2_EEG"
        if eeg_dir.exists():
            edf_files.extend(list(eeg_dir.rglob("*.edf")))
    
    # Filtrer les fichiers ABORTED et easy_converted
    return [f for f in edf_files if 'ABORTED' not in f.name and 'easy_converted' not in f.name]


def analyze_all_files(subject_dirs: List[Path]) -> Dict[str, int]:
    """
    Analyse tous les fichiers dans les dossiers participants.
    
    Args:
        subject_dirs: Liste des dossiers de participants
    
    Returns:
        Dictionnaire {extension: count}
    """
    all_files = []
    for subj_dir in subject_dirs:
        subject_id, group, initials = extract_subject_info(subj_dir.name)
        if not subject_id or 'excluded' in subj_dir.name or 'STAND_BY' in subj_dir.name:
            continue
        
        for file_path in subj_dir.rglob("*"):
            if file_path.is_file():
                all_files.append(file_path)
    
    extensions_counter = Counter([f.suffix.lower() if f.suffix else '[no_extension]' for f in all_files])
    return dict(sorted(extensions_counter.items(), key=lambda x: x[1], reverse=True))


# ============================================================================
# FONCTIONS DE CRÉATION DE BIDS PATH
# ============================================================================

def create_bids_path_from_edf(edf_file: Path) -> Optional[Tuple[BIDSPath, str, str]]:
    """
    Crée un BIDSPath à partir d'un fichier .edf.
    
    Args:
        edf_file: Chemin vers le fichier .edf
    
    Returns:
        Tuple (BIDSPath, subject_id, session) ou None si erreur
    """
    parts = edf_file.parts
    
    # Trouver le dossier participant
    try:
        eeg_idx = parts.index('EEG')
        subj_folder_name = parts[eeg_idx + 1]
        session_folder_name = parts[-2]
    except (ValueError, IndexError):
        return None
    
    # Extraire subject
    subject_id, group, initials = extract_subject_info(subj_folder_name)
    if not subject_id:
        return None
    
    # Extraire session
    session = extract_session_from_folder(session_folder_name)
    if not session:
        return None
    
    # Parser le nom de fichier
    task, acq, run = parse_edf_filename(edf_file.name)
    if task is None:
        return None
    
    # Créer BIDSPath
    bids_path = BIDSPath(
        subject=subject_id,
        session=session,
        task=task,
        acquisition=acq,
        run=run,
        datatype='eeg',
        root=BIDS_ROOT
    )
    
    return bids_path, subject_id, session


def create_bids_filename(subject_id: str, session: str, task: str, 
                        acq: Optional[str], run: Optional[str], 
                        suffix: str, extension: str) -> str:
    """
    Crée un nom de fichier BIDS standard.
    
    Args:
        subject_id: ID du sujet
        session: Numéro de session
        task: Nom de la tâche
        acq: Acquisition (optionnel)
        run: Numéro de run (optionnel)
        suffix: Suffixe (ex: 'eeg')
        extension: Extension (ex: '.edf', '.easy')
    
    Returns:
        Nom de fichier BIDS formaté
    """
    filename = f"sub-{subject_id}_ses-{session}_task-{task}"
    if acq:
        filename += f"_acq-{acq}"
    if run:
        filename += f"_run-{run}"
    filename += f"_{suffix}{extension}"
    return filename


# ============================================================================
# FONCTIONS DE COPIE
# ============================================================================

def copy_edf_with_sidecar_files(edf_file: Path, bids_path: BIDSPath, 
                                subject_id: str, session: str,
                                overwrite: bool = True) -> Tuple[bool, int, int]:
    """
    Copie un fichier .edf et ses fichiers associés (.easy, .info).
    
    Args:
        edf_file: Chemin source du fichier .edf
        bids_path: BIDSPath pour la destination
        subject_id: ID du sujet
        session: Numéro de session
        overwrite: Écraser les fichiers existants
    
    Returns:
        Tuple (success, easy_copied, info_copied)
    """
    try:
        # Lire et écrire le fichier EDF
        raw = mne.io.read_raw_edf(edf_file, preload=False, verbose=False)
        write_raw_bids(raw, bids_path, overwrite=True, verbose=False)
        
        # Dossier de destination
        dest_dir = BIDS_ROOT / f"sub-{subject_id}" / f"ses-{session}" / "eeg"
        
        # Nom de base du fichier source et BIDS
        base_name = edf_file.stem
        task, acq, run = parse_edf_filename(edf_file.name)
        
        bids_basename = create_bids_filename(
            subject_id, session, task, acq, run, 
            suffix='eeg', extension=''
        ).replace('_eeg', '')  # Retirer le suffix pour réutilisation
        
        easy_copied = 0
        info_copied = 0
        
        # Copier le fichier .easy
        easy_file = edf_file.parent / f"{base_name}.easy"
        if easy_file.exists():
            easy_dest = dest_dir / f"{bids_basename}_eeg.easy"
            shutil.copy2(easy_file, easy_dest)
            easy_copied = 1
        
        # Copier le fichier .info
        info_file = edf_file.parent / f"{base_name}.info"
        if info_file.exists():
            info_dest = dest_dir / f"{bids_basename}_eeg.info"
            shutil.copy2(info_file, info_dest)
            info_copied = 1
        
        return True, easy_copied, info_copied
        
    except Exception as e:
        print(f"  ❌ Erreur: {e}")
        return False, 0, 0


def copy_visual_field_data(subject_dirs: List[Path]) -> Tuple[int, int, int, int]:
    """
    Copie les dossiers EEG_VISUAL_FIELD et fichiers PDF associés.
    
    Args:
        subject_dirs: Liste des dossiers de participants
    
    Returns:
        Tuple (vf_copied, vf_failed, pdf_copied, pdf_failed)
    """
    vf_copied = 0
    vf_failed = 0
    pdf_copied = 0
    pdf_failed = 0
    
    for subj_dir in subject_dirs:
        subject_id, group, initials = extract_subject_info(subj_dir.name)
        if not subject_id or 'excluded' in subj_dir.name or 'STAND_BY' in subj_dir.name:
            continue
        
        eeg_dir = subj_dir / "2_EEG"
        if not eeg_dir.exists():
            continue
        
        for session_dir in eeg_dir.iterdir():
            if not session_dir.is_dir():
                continue
            
            session = extract_session_from_folder(session_dir.name)
            if not session:
                continue
            
            ses_dest_dir = BIDS_ROOT / f"sub-{subject_id}" / f"ses-{session}" / "eeg"
            ses_dest_dir.mkdir(parents=True, exist_ok=True)
            
            # Copier dossier EEG_VISUAL_FIELD
            vf_source = session_dir / "EEG_VISUAL_FIELD"
            if vf_source.exists():
                vf_dest = ses_dest_dir / "visual_field"
                try:
                    if vf_dest.exists():
                        shutil.rmtree(vf_dest)
                    shutil.copytree(vf_source, vf_dest)
                    print(f"  ✓ sub-{subject_id}/ses-{session}/eeg/visual_field/")
                    vf_copied += 1
                except Exception as e:
                    print(f"  ❌ Erreur VF sub-{subject_id}/ses-{session}: {e}")
                    vf_failed += 1
            
            # Copier fichiers PDF
            pdf_files = list(session_dir.glob("*.pdf"))
            for pdf_file in pdf_files:
                if any(kw in pdf_file.name.lower() for kw in ['visual', 'field', 'vf', 'champ']):
                    try:
                        pdf_dest = ses_dest_dir / pdf_file.name
                        shutil.copy2(pdf_file, pdf_dest)
                        print(f"  ✓ sub-{subject_id}/ses-{session}/eeg/{pdf_file.name}")
                        pdf_copied += 1
                    except Exception as e:
                        print(f"  ❌ Erreur PDF sub-{subject_id}/ses-{session}/{pdf_file.name}: {e}")
                        pdf_failed += 1
    
    return vf_copied, vf_failed, pdf_copied, pdf_failed


def copy_data_visual_field_to_derivatives() -> bool:
    """
    Copie le dossier data-VisualField vers derivatives/.
    
    Returns:
        True si succès, False sinon
    """
    source_visual_field = RAW_ROOT / "EEG" / "data-VisualField"
    dest_visual_field = DERIVATIVES_ROOT / "data-VisualField"
    
    if not source_visual_field.exists():
        print(f"⚠️  Dossier source non trouvé: {source_visual_field}")
        return False
    
    dest_visual_field.parent.mkdir(parents=True, exist_ok=True)
    
    if dest_visual_field.exists():
        print(f"  ⚠️  Le dossier existe déjà: {dest_visual_field}")
        overwrite_vf = input("  Écraser le dossier existant? (o/n): ")
        if overwrite_vf.lower() not in ['o', 'oui', 'y', 'yes']:
            print(f"⏭️  Copie ignorée")
            return False
        shutil.rmtree(dest_visual_field)
    
    shutil.copytree(source_visual_field, dest_visual_field)
    print(f"✓ data-VisualField copié vers derivatives/")
    return True


# ============================================================================
# FONCTIONS D'INITIALISATION BIDS
# ============================================================================

def create_participants_tsv(subject_dirs: List[Path]) -> int:
    """
    Crée le fichier participants.tsv.
    
    Args:
        subject_dirs: Liste des dossiers de participants
    
    Returns:
        Nombre de participants ajoutés
    """
    participants_data = []
    
    for subj_dir in subject_dirs:
        subject_id, group, initials = extract_subject_info(subj_dir.name)
        if subject_id:
            if 'excluded' in subj_dir.name or 'STAND_BY' in subj_dir.name:
                print(f"  ⏭️  Exclu: {subj_dir.name}")
                continue
            
            participants_data.append({
                'participant_id': f'sub-{subject_id}',
                'group': group.lower(),
                'initials': initials
            })
    
    participants_df = pd.DataFrame(participants_data)
    participants_file = BIDS_ROOT / 'participants.tsv'
    participants_df.to_csv(participants_file, sep='\t', index=False)
    
    return len(participants_data)


def create_dataset_description():
    """Crée le fichier dataset_description.json."""
    dataset_description = {
        "Name": "HemianotACS",
        "BIDSVersion": "1.9.0",
        "Authors": ["Unknown"],
        "Description": "EEG data from hemianopsia tACS study"
    }
    
    with open(BIDS_ROOT / 'dataset_description.json', 'w') as f:
        json.dump(dataset_description, f, indent=4)


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

def main():
    """Fonction principale d'orchestration."""
    
    print("=" * 80)
    print("BIDSIFICATION HEMIANOTACS - Conversion EEG")
    print("=" * 80)
    print()
    
    # Étape 1: Collecter les participants
    print(f"🔍 Collecte des participants...")
    subject_dirs = collect_subject_directories()
    print(f"   {len(subject_dirs)} dossiers trouvés")
    print()
    
    # Étape 2: Créer participants.tsv et dataset_description.json
    print(f"📝 Création des fichiers BIDS de base...")
    n_participants = create_participants_tsv(subject_dirs)
    print(f"✓ participants.tsv créé: {n_participants} participants")
    
    create_dataset_description()
    print("✓ dataset_description.json créé")
    print()
    
    # Étape 3: Copier data-VisualField vers derivatives
    print("📂 Copie du dossier data-VisualField vers derivatives/...")
    copy_data_visual_field_to_derivatives()
    print()
    
    # Étape 4: Copier les dossiers EEG_VISUAL_FIELD et PDF
    print("📂 Copie des dossiers EEG_VISUAL_FIELD et fichiers PDF...")
    vf_copied, vf_failed, pdf_copied, pdf_failed = copy_visual_field_data(subject_dirs)
    print(f"✓ {vf_copied} dossiers EEG_VISUAL_FIELD copiés")
    print(f"✓ {pdf_copied} fichiers PDF copiés")
    if vf_failed > 0 or pdf_failed > 0:
        print(f"⚠️  {vf_failed} dossiers et {pdf_failed} PDF ont échoué")
    print()
    
    # Étape 5: Analyser les types de fichiers
    print("📊 Analyse des fichiers dans le dossier RAW...")
    file_stats = analyze_all_files(subject_dirs)
    print(f"📁 Nombre total de fichiers: {sum(file_stats.values())}")
    print()
    print("📋 Répartition par type de fichier:")
    print("-" * 50)
    for ext, count in list(file_stats.items())[:15]:  # Top 15
        ext_display = ext if ext != '[no_extension]' else '[sans extension]'
        print(f"  {ext_display:20s} : {count:5d} fichiers")
    print("-" * 50)
    print()
    
    # Étape 6: Collecter les fichiers .edf
    print("🔄 Collecte des fichiers .edf...")
    edf_files = collect_edf_files(subject_dirs)
    print(f"📁 {len(edf_files)} fichiers .edf trouvés (hors ABORTED)")
    print()
    
    # Mode test ou confirmation
    if '--test' in sys.argv:
        print("🧪 Mode TEST: conversion des 10 premiers fichiers seulement")
        edf_files = edf_files[:10]
        overwrite = True
    else:
        response = input(f"⚠️  Convertir ces {len(edf_files)} fichiers en BIDS? (o/n): ")
        if response.lower() not in ['o', 'oui', 'y', 'yes']:
            print("❌ Conversion annulée.")
            sys.exit(0)
        
        overwrite_response = input("🔄 Écraser les fichiers BIDS existants? (o/n): ")
        overwrite = overwrite_response.lower() in ['o', 'oui', 'y', 'yes']
    
    print()
    print("🔄 Début de la conversion...")
    print()
    
    # Étape 7: Convertir les fichiers .edf
    files_processed = 0
    files_failed = 0
    files_skipped = 0
    easy_total = 0
    info_total = 0
    
    for edf_file in edf_files:
        # Créer le BIDS path
        result = create_bids_path_from_edf(edf_file)
        if result is None:
            files_failed += 1
            continue
        
        bids_path, subject_id, session = result
        
        # Vérifier si le fichier existe déjà
        bids_file = bids_path.copy().update(suffix='eeg', extension='.edf')
        if bids_file.fpath.exists() and not overwrite:
            files_skipped += 1
            continue
        
        # Copier le fichier et ses sidecars
        success, easy_copied, info_copied = copy_edf_with_sidecar_files(
            edf_file, bids_path, subject_id, session, overwrite
        )
        
        if success:
            task, acq, run = parse_edf_filename(edf_file.name)
            info_str = f"sub-{subject_id}/ses-{session}/task-{task}"
            if acq:
                info_str += f"/acq-{acq}"
            if run:
                info_str += f"/run-{run}"
            print(f"✓ {info_str}")
            files_processed += 1
            easy_total += easy_copied
            info_total += info_copied
        else:
            print(f"❌ {edf_file.name}")
            files_failed += 1
    
    # Rapport final
    print()
    print("=" * 80)
    print("📊 RAPPORT FINAL")
    print("=" * 80)
    print(f"  Fichiers .edf trouvés:   {len(edf_files)}")
    print(f"  Fichiers .edf convertis: {files_processed} ✓")
    print(f"  Fichiers .easy copiés:   {easy_total} ✓")
    print(f"  Fichiers .info copiés:   {info_total} ✓")
    if files_skipped > 0:
        print(f"  Fichiers ignorés:        {files_skipped} ⏭️")
    if files_failed > 0:
        print(f"  Fichiers échoués:        {files_failed} ❌")
    print()
    
    if files_processed > 0:
        print(f"✅ Conversion terminée! Dataset BIDS créé dans: {BIDS_ROOT}")
        print()
        print("📋 Prochaine étape: Valider avec bids-validator")
        print(f"   Commande: bids-validator {BIDS_ROOT}")
    else:
        print("⚠️  Aucun fichier n'a été converti.")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
