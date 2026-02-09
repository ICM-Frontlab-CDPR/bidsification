#!/usr/bin/env python3
"""
Script pour ajouter les fichiers IRM dans la structure BIDS
Permet de lister les fichiers source, les vérifier, et les copier dans le BIDS
"""

import os
import sys
import shutil
from pathlib import Path
import yaml
import json
import re
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional


# ============================================================================
# CHARGEMENT DE LA CONFIGURATION
# ============================================================================

def setup_logging(script_name: str = '3-mri-add') -> logging.Logger:
    """Configure le logging pour écrire dans un fichier de log."""
    # Créer le répertoire de logs
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Nom du fichier de log avec timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f"{script_name}_{timestamp}.log"
    
    # Configuration du logger
    logger = logging.getLogger(script_name)
    logger.setLevel(logging.INFO)
    
    # Handler pour le fichier
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # Handler pour la console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Format
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Ajouter les handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logger.info(f"Fichier de log: {log_file}")
    return logger


def load_config(config_path='config.yaml') -> Dict:
    """Charge la configuration depuis le fichier YAML."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config


# ============================================================================
# FONCTIONS D'ANALYSE DES FICHIERS IRM
# ============================================================================

def list_mri_files(source_dir: Path, logger: logging.Logger) -> Dict[str, List[Path]]:
    """
    Liste et catégorise tous les fichiers IRM présents dans le dossier source.
    
    Args:
        source_dir: Chemin vers le dossier source contenant les IRM
        logger: Logger pour les messages
        
    Returns:
        Dictionnaire organisé par type de fichier (T1w, FLAIR, func, dwi, etc.)
    """
    if not source_dir.exists():
        logger.error(f"Le dossier {source_dir} n'existe pas !")
        return {}
    
    # Organisation des fichiers par type
    files_by_type = {
        'T1w': [],
        'FLAIR': [],
        'func': [],
        'dwi': [],
        'localizer': [],
        'unknown': []
    }
    
    # Scanner tous les fichiers
    all_files = list(source_dir.glob('*'))
    
    for file_path in all_files:
        if file_path.is_file():
            filename = file_path.name
            
            # Catégoriser les fichiers
            if '3DT1' in filename:
                files_by_type['T1w'].append(file_path)
            elif '3DFLAIR' in filename or 'FLAIR' in filename:
                files_by_type['FLAIR'].append(file_path)
            elif 'resting' in filename.lower() or 'MB3_3echo' in filename:
                files_by_type['func'].append(file_path)
            elif 'diff' in filename.lower() or 'EP2D_diff' in filename:
                files_by_type['dwi'].append(file_path)
            elif 'LOCAHASTE' in filename or 'LOCA' in filename:
                files_by_type['localizer'].append(file_path)
            else:
                files_by_type['unknown'].append(file_path)
    
    return files_by_type


def get_file_size_mb(file_path: Path) -> float:
    """Retourne la taille du fichier en MB."""
    return file_path.stat().st_size / (1024 * 1024)


def display_files_summary(files_by_type: Dict[str, List[Path]], logger: logging.Logger) -> None:
    """
    Affiche un résumé des fichiers trouvés.
    
    Args:
        files_by_type: Dictionnaire des fichiers organisés par type
        logger: Logger pour les messages
    """
    logger.info("="*80)
    logger.info("RÉSUMÉ DES FICHIERS IRM TROUVÉS")
    logger.info("="*80)
    
    total_files = 0
    total_size = 0
    
    for category, files in files_by_type.items():
        if files:
            logger.info(f"\n{category.upper()} ({len(files)} fichiers)")
            logger.info("-" * 80)
            
            # Organiser les fichiers par paire (nii.gz + json)
            nii_files = sorted([f for f in files if f.suffix == '.gz'])
            
            for nii_file in nii_files:
                json_file = nii_file.parent / (nii_file.stem.replace('.nii', '') + '.json')
                bval_file = nii_file.parent / (nii_file.stem.replace('.nii', '') + '.bval')
                bvec_file = nii_file.parent / (nii_file.stem.replace('.nii', '') + '.bvec')
                
                size = get_file_size_mb(nii_file)
                total_size += size
                total_files += 1
                
                logger.info(f"  {nii_file.name:<50} ({size:>6.1f} MB)")
                
                if json_file.exists():
                    logger.info(f"     └─ {json_file.name}")
                    total_files += 1
                    total_size += get_file_size_mb(json_file)
                
                if bval_file.exists():
                    logger.info(f"     └─ {bval_file.name}")
                    total_files += 1
                    total_size += get_file_size_mb(bval_file)
                
                if bvec_file.exists():
                    logger.info(f"     └─ {bvec_file.name}")
                    total_files += 1
                    total_size += get_file_size_mb(bvec_file)
    
    logger.info("="*80)
    logger.info(f"TOTAL: {total_files} fichiers - {total_size:.1f} MB")
    logger.info("="*80)


# ============================================================================
# FONCTIONS DE MAPPING VERS BIDS
# ============================================================================

def parse_subject_from_path(source_path: Path) -> Tuple[Optional[str], Optional[str]]:
    """
    Extrait l'ID du sujet et le code depuis le chemin source.
    
    Args:
        source_path: Chemin complet du dossier source (ex: .../IRM/001-CC)
        
    Returns:
        Tuple (subject_id, subject_code) ex: ('0001', 'CC')
    """
    folder_name = source_path.name
    
    # Pattern: 001-CC ou 001-0001-CC
    match = re.match(r'(\d+)-(?:(\d+)-)?([A-Z]+)', folder_name)
    if match:
        subject_code = match.group(3)
        # Si on a un ID complet (ex: 001-0001-CC), utiliser le deuxième nombre
        subject_id = match.group(2) if match.group(2) else match.group(1).zfill(4)
        return subject_id, subject_code
    
    return None, None


def determine_bids_path(file_path: Path, subject_id: str, session_id: str, 
                       bids_root: Path) -> Tuple[Path, str]:
    """
    Détermine le chemin BIDS approprié pour un fichier IRM.
    
    Args:
        file_path: Chemin du fichier source
        subject_id: ID du sujet (ex: '0001')
        session_id: ID de la session (ex: '01')
        bids_root: Racine du dossier BIDS
        
    Returns:
        Tuple (bids_dir, bids_filename) - Dossier de destination et nom du fichier
    """
    filename = file_path.name
    suffix = file_path.suffix
    
    # Construire le préfixe commun
    prefix = f"sub-{subject_id}_ses-{session_id}"
    
    # Déterminer le type et le chemin BIDS
    if '3DT1' in filename:
        # Anatomique T1w
        modality_dir = bids_root / f"sub-{subject_id}" / f"ses-{session_id}" / "anat"
        
        # Déterminer le run number à partir du nom original
        run_match = re.search(r'3DT1_(\d+)', filename)
        run_num = run_match.group(1) if run_match else '1'
        
        bids_filename = f"{prefix}_run-{run_num}_T1w{suffix}"
        
    elif '3DFLAIR' in filename or 'FLAIR' in filename:
        # Anatomique FLAIR
        modality_dir = bids_root / f"sub-{subject_id}" / f"ses-{session_id}" / "anat"
        
        run_match = re.search(r'FLAIR_(\d+)', filename)
        run_num = run_match.group(1) if run_match else '1'
        
        bids_filename = f"{prefix}_run-{run_num}_FLAIR{suffix}"
        
    elif 'resting' in filename.lower() and 'MB3_3echo' in filename:
        # Fonctionnel - resting state multi-echo
        modality_dir = bids_root / f"sub-{subject_id}" / f"ses-{session_id}" / "func"
        
        # Extraire le numéro d'écho
        echo_match = re.search(r'_e(\d+)', filename)
        echo_num = echo_match.group(1) if echo_match else '1'
        
        # Extraire le run
        run_match = re.search(r'resting_(\d+)_', filename)
        run_num = run_match.group(1) if run_match else '1'
        
        # Déterminer si c'est refBLIP
        acq = 'refBLIP' if 'refBLIP' in filename else None
        acq_str = f"_acq-{acq}" if acq else ""
        
        bids_filename = f"{prefix}_task-rest{acq_str}_run-{run_num}_echo-{echo_num}_bold{suffix}"
        
    elif 'diff' in filename.lower() or 'EP2D_diff' in filename:
        # Diffusion (DWI)
        modality_dir = bids_root / f"sub-{subject_id}" / f"ses-{session_id}" / "dwi"
        
        # Extraire les informations
        # Patterns: MB3_EP2D_diff_D60_AP_9 ou MB3_EP2D_diff_D60_PA_blip_10
        pattern = re.search(r'diff_D(\d+)_(b\d+)?_(AP|PA)', filename)
        if pattern:
            directions = pattern.group(1)  # 60, 30, 8
            bval = pattern.group(2) if pattern.group(2) else f"b{int(directions)*100}"  # b700, b300
            direction = pattern.group(3)  # AP ou PA
            
            # Run number
            run_match = re.search(r'_(\d+)\.(nii|json|bval|bvec)', filename)
            run_num = run_match.group(1) if run_match else '1'
            
            acq = f"dir{directions}{direction}"
            bids_filename = f"{prefix}_acq-{acq}_run-{run_num}_dwi{suffix}"
        else:
            bids_filename = f"{prefix}_dwi{suffix}"
    
    elif 'LOCAHASTE' in filename or 'LOCA' in filename:
        # Localizer
        modality_dir = bids_root / f"sub-{subject_id}" / f"ses-{session_id}" / "anat"
        
        # Extraire le numéro d'image
        img_match = re.search(r'i(\d+)', filename)
        img_num = img_match.group(1) if img_match else '1'
        
        bids_filename = f"{prefix}_acq-localizer_run-{img_num}_T2w{suffix}"
        
    else:
        # Par défaut, mettre dans anat
        modality_dir = bids_root / f"sub-{subject_id}" / f"ses-{session_id}" / "anat"
        bids_filename = f"{prefix}_{filename}"
    
    return modality_dir, bids_filename


def copy_files_to_bids(files_by_type: Dict[str, List[Path]], 
                      subject_id: str,
                      session_id: str,
                      bids_root: Path,
                      logger: logging.Logger,
                      dry_run: bool = True) -> None:
    """
    Copie les fichiers IRM vers la structure BIDS.
    
    Args:
        files_by_type: Dictionnaire des fichiers organisés par type
        subject_id: ID du sujet
        session_id: ID de la session
        bids_root: Racine du dossier BIDS
        logger: Logger pour les messages
        dry_run: Si True, affiche seulement ce qui serait fait sans copier
    """
    logger.info("="*80)
    if dry_run:
        logger.info("APERÇU DES OPÉRATIONS (DRY RUN)")
    else:
        logger.info("COPIE DES FICHIERS VERS BIDS")
    logger.info("="*80)
    
    operations = []
    
    for category, files in files_by_type.items():
        if category == 'unknown' or not files:
            continue
        
        # Organiser les fichiers par paire (nii.gz + json + bval + bvec)
        nii_files = sorted([f for f in files if f.suffix == '.gz'])
        
        for nii_file in nii_files:
            # Fichiers associés
            json_file = nii_file.parent / (nii_file.stem.replace('.nii', '') + '.json')
            bval_file = nii_file.parent / (nii_file.stem.replace('.nii', '') + '.bval')
            bvec_file = nii_file.parent / (nii_file.stem.replace('.nii', '') + '.bvec')
            
            # Déterminer les chemins BIDS
            for source_file in [nii_file, json_file, bval_file, bvec_file]:
                if source_file.exists():
                    dest_dir, dest_filename = determine_bids_path(
                        source_file, subject_id, session_id, bids_root
                    )
                    dest_path = dest_dir / dest_filename
                    operations.append((source_file, dest_path))
    
    # Afficher les opérations
    for source, dest in operations:
        logger.info(f"  {source.name}")
        logger.info(f"    → {dest.relative_to(bids_root)}")
    
    logger.info(f"\nTOTAL: {len(operations)} fichiers à copier")
    
    if not dry_run:
        # Demander confirmation
        response = input("⚠️  Confirmer la copie des fichiers ? (o/n): ")
        if response.lower() != 'o':
            logger.warning("Opération annulée.")
            return
        
        # Copier les fichiers
        logger.info("Copie en cours...")
        copied_count = 0
        
        for source, dest in operations:
            try:
                # Créer le dossier de destination
                dest.parent.mkdir(parents=True, exist_ok=True)
                
                # Copier le fichier
                shutil.copy2(source, dest)
                logger.info(f"  ✅ {dest.name}")
                copied_count += 1
                
            except Exception as e:
                logger.error(f"  Erreur lors de la copie de {source.name}: {e}")
        
        logger.info(f"Copie terminée ! {copied_count}/{len(operations)} fichiers copiés.")


# ============================================================================
# FONCTION PRINCIPALE
# ============================================================================

def main():
    """Fonction principale du script."""
    # Setup logging
    logger = setup_logging('3-mri-add')
    
    logger.info("="*80)
    logger.info("SCRIPT D'AJOUT DES FICHIERS IRM DANS BIDS")
    logger.info("="*80)
    
    # Charger la configuration
    config = load_config()
    bids_root = Path(config['paths']['bids_root'])
    raw_root = Path(config['paths']['raw_root'])
    mri_path = raw_root / config['paths']['mri_path']
    
    # Lister les participants disponibles
    participant_folders = sorted([d for d in mri_path.iterdir() if d.is_dir()])
    
    logger.info(f"Dossier IRM: {mri_path}")
    logger.info(f"Dossier BIDS: {bids_root}")
    logger.info(f"Participants trouvés: {len(participant_folders)}")
    for folder in participant_folders:
        logger.info(f"  - {folder.name}")
    
    # Demander quel participant traiter
    choice = input("Traiter tous les participants ? (o/n): ").strip().lower()
    if choice == 'o':
        folders_to_process = participant_folders
    else:
        print("\nChoisissez un participant:")
        for i, folder in enumerate(participant_folders, 1):
            print(f"  {i}. {folder.name}")
        num = int(input("\nNuméro: ").strip())
        folders_to_process = [participant_folders[num - 1]]
    
    # Traiter chaque participant
    for source_dir in folders_to_process:
        logger.info("="*80)
        logger.info(f"Traitement de: {source_dir.name}")
        logger.info("="*80)
        
        # Extraire l'ID du sujet depuis le nom du dossier
        subject_id, subject_code = parse_subject_from_path(source_dir)
        if not subject_id:
            logger.error("Impossible d'extraire l'ID du sujet depuis le chemin.")
            continue
        
        session_id = config['paths']['mri_session_id']
        logger.info(f"Sujet détecté: sub-{subject_id} (code: {subject_code})")
        logger.info(f"Session: ses-{session_id}")
        
        # 1. Lister tous les fichiers présents
        logger.info("Étape 1: Analyse du dossier source...")
        files_by_type = list_mri_files(source_dir, logger)
        
        if not any(files_by_type.values()):
            logger.error("Aucun fichier IRM trouvé dans le dossier source.")
            continue
        
        display_files_summary(files_by_type, logger)
        
        # 2. Demander confirmation et copier
        logger.info("Étape 2: Prévisualisation des opérations...")
        copy_files_to_bids(files_by_type, subject_id, session_id, bids_root, logger, dry_run=True)
        
        # Copie réelle
        copy_files_to_bids(files_by_type, subject_id, session_id, bids_root, logger, dry_run=False)


if __name__ == '__main__':
    main()
