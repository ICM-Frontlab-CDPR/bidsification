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

RAW_ROOT = Path("/Users/hippolyte.dreyfus/Desktop/hemianotACS/Data/sourcedata/HEMIANOTACS_WIP")
BIDS_ROOT = Path("/Users/hippolyte.dreyfus/Desktop/hemianotACS/Data/bids")
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
    Parse le nom de fichier .edf/.vhdr pour extraire task, acquisition et run.
    
    Args:
        filename: Nom du fichier .edf ou .vhdr
    
    Returns:
        Tuple (task, acquisition, run) ou (None, None, None) si non reconnu
    """
    # Ignorer les fichiers ABORTED ou easy_converted
    if 'ABORTED' in filename or 'easy_converted' in filename:
        return None, None, None
    
    # ========== BASELINE BRAINVISION (V1) ==========
    # Resting state Eyes Closed / Eyes Open
    if 'restingstate_EC' in filename or 'restingstate_EO' in filename:
        task = 'rest'
        if 'EC' in filename:
            acq = 'EC'
        else:
            acq = 'EO'
        return task, acq, None
    
    # Detection task
    if 'Detection' in filename:
        return 'detection', None, None
    
    # VEP fullfield
    if 'VEP_fullfield' in filename:
        return 'vep', 'fullfield', None
    
    # VEP cinétique (run 1 ou 2)
    cinetique_match = re.search(r'cinetique(\d+)', filename, re.IGNORECASE)
    if cinetique_match:
        run = cinetique_match.group(1)
        return 'vep', 'cinetique', run
    
    # VEP statique OD/OG (plusieurs runs possibles)
    if 'statique' in filename:
        # Déterminer si c'est OD ou OG
        eye = 'OD' if 'OD' in filename else 'OG' if 'OG' in filename else None
        if eye:
            # Chercher un numéro de run (OD2, OG2, etc.)
            run_match = re.search(rf'{eye}(\d+)', filename)
            if run_match:
                run_num = run_match.group(1)
                run = f"{eye}{run_num}"
            else:
                run = f"{eye}1"
            return 'vep', 'statique', run
    
    # ========== NEUROELECTRICS (V2-V4) ==========
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
    """Collecte tous les dossiers de participants valides."""
    return sorted([d for d in EEG_PATH.iterdir() if d.is_dir()])


def collect_neuroelectrics_files(subject_dirs: List[Path]) -> List[Path]:
    """Collecte tous les fichiers .easy et .info."""
    files = []
    for subj_dir in subject_dirs:
        subject_id, group, initials = extract_subject_info(subj_dir.name)
        if not subject_id or 'excluded' in subj_dir.name or 'STAND_BY' in subj_dir.name:
            continue
        
        eeg_dir = subj_dir / "2_EEG"
        if eeg_dir.exists():
            files.extend(list(eeg_dir.rglob("*.easy")))
            files.extend(list(eeg_dir.rglob("*.info")))
    
    return [f for f in files if 'ABORTED' not in f.name]


def collect_brainvision_files(subject_dirs: List[Path]) -> List[Path]:
    """Collecte tous les fichiers .vhdr (les .eeg et .vmrk seront associés)."""
    files = []
    for subj_dir in subject_dirs:
        subject_id, group, initials = extract_subject_info(subj_dir.name)
        if not subject_id or 'excluded' in subj_dir.name or 'STAND_BY' in subj_dir.name:
            continue
        
        eeg_dir = subj_dir / "2_EEG"
        if eeg_dir.exists():
            files.extend(list(eeg_dir.rglob("*.vhdr")))
    
    return [f for f in files if 'ABORTED' not in f.name]


def analyze_all_files(subject_dirs: List[Path]) -> Dict[str, int]:
    """Analyse tous les fichiers dans les dossiers participants."""
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

def copy_neuroelectrics_files(edf_file: Path, subject_id: str, session: str) -> Tuple[bool, int, int]:
    """
    Copie uniquement les fichiers .easy et .info associés à un fichier .edf.
    
    Args:
        edf_file: Chemin source du fichier .edf (utilisé pour trouver les .easy/.info)
        subject_id: ID du sujet
        session: Numéro de session
    
    Returns:
        Tuple (success, easy_copied, info_copied)
    """
    try:
        # Dossier de destination
        dest_dir = BIDS_ROOT / f"sub-{subject_id}" / f"ses-{session}" / "eeg"
        dest_dir.mkdir(parents=True, exist_ok=True)
        
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
# ============================================================================
# FONCTIONS DE COPIE
# ============================================================================

def copy_neuroelectrics_files(ne_files: List[Path]) -> Tuple[int, int]:
    """Copie les fichiers Neuroelectrics (.easy/.info) vers BIDS."""
    easy_copied = 0
    info_copied = 0
    
    for ne_file in ne_files:
        parts = ne_file.parts
        try:
            eeg_idx = parts.index('EEG')
            subj_folder = parts[eeg_idx + 1]
            session_folder = parts[-2]
            
            subject_id, _, _ = extract_subject_info(subj_folder)
            session = extract_session_from_folder(session_folder)
            
            if not subject_id or not session:
                continue
            
            task, acq, run = parse_edf_filename(ne_file.stem)
            if task is None:
                continue
            
            dest_dir = BIDS_ROOT / f"sub-{subject_id}" / f"ses-{session}" / "eeg"
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            bids_name = create_bids_filename(subject_id, session, task, acq, run, 
                                            'eeg', ne_file.suffix)
            dest_file = dest_dir / bids_name
            shutil.copy2(ne_file, dest_file)
            
            if ne_file.suffix == '.easy':
                easy_copied += 1
            else:
                info_copied += 1
                
        except (ValueError, IndexError):
            continue
    
    return easy_copied, info_copied


def copy_brainvision_files(vhdr_files: List[Path]) -> Tuple[int, int]:
    """Copie les triplets BrainVision (.vhdr/.vmrk/.eeg) vers BIDS."""
    triplets_copied = 0
    triplets_failed = 0
    
    for vhdr_file in vhdr_files:
        parts = vhdr_file.parts
        try:
            eeg_idx = parts.index('EEG')
            subj_folder = parts[eeg_idx + 1]
            session_folder = parts[-2]
            
            subject_id, _, _ = extract_subject_info(subj_folder)
            session = extract_session_from_folder(session_folder)
            
            if not subject_id or not session:
                continue
            
            task, acq, run = parse_edf_filename(vhdr_file.stem)
            if task is None:
                continue
            
            dest_dir = BIDS_ROOT / f"sub-{subject_id}" / f"ses-{session}" / "eeg"
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            base_name = vhdr_file.stem
            extensions = ['.vhdr', '.vmrk', '.eeg']
            all_exist = all((vhdr_file.parent / f"{base_name}{ext}").exists() for ext in extensions)
            
            if all_exist:
                for ext in extensions:
                    src = vhdr_file.parent / f"{base_name}{ext}"
                    bids_name = create_bids_filename(subject_id, session, task, acq, run, 'eeg', ext)
                    dest = dest_dir / bids_name
                    shutil.copy2(src, dest)
                triplets_copied += 1
            else:
                triplets_failed += 1
                
        except (ValueError, IndexError):
            triplets_failed += 1
    
    return triplets_copied, triplets_failed


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
    """Fonction principale."""
    print("=" * 80)
    print("BIDSIFICATION HEMIANOTACS - Copie fichiers EEG")
    print("=" * 80)
    print()
    
    # Étape 1: Collecter les participants
    subject_dirs = collect_subject_directories()
    print(f"🔍 {len(subject_dirs)} participants trouvés")
    print()
    
    # Étape 2: Créer fichiers BIDS de base
    n_participants = create_participants_tsv(subject_dirs)
    create_dataset_description()
    print(f"✓ participants.tsv: {n_participants} participants")
    print(f"✓ dataset_description.json")
    print()
    
    # Étape 3: Copier data-VisualField
    print("📂 Copie data-VisualField vers derivatives/...")
    copy_data_visual_field_to_derivatives()
    print()
    
    # Étape 4: Copier EEG_VISUAL_FIELD et PDF
    print("📂 Copie EEG_VISUAL_FIELD et PDF...")
    vf_copied, vf_failed, pdf_copied, pdf_failed = copy_visual_field_data(subject_dirs)
    print(f"✓ {vf_copied} dossiers, {pdf_copied} PDF")
    if vf_failed > 0 or pdf_failed > 0:
        print(f"⚠️  {vf_failed} dossiers, {pdf_failed} PDF échoués")
    print()
    
    # Étape 5: Analyser fichiers
    print("📊 Analyse fichiers RAW...")
    file_stats = analyze_all_files(subject_dirs)
    print(f"Total: {sum(file_stats.values())} fichiers")
    for ext, count in list(file_stats.items())[:10]:
        ext_display = ext if ext != '[no_extension]' else '[sans ext]'
        print(f"  {ext_display:15s}: {count:5d}")
    print()
    
    # Étape 6: Collecter et copier Neuroelectrics
    print("🔄 Collecte fichiers Neuroelectrics (.easy/.info)...")
    ne_files = collect_neuroelectrics_files(subject_dirs)
    print(f"📁 {len(ne_files)} fichiers trouvés")
    
    response = input(f"Copier? (o/n): ")
    if response.lower() not in ['o', 'oui', 'y', 'yes']:
        print("❌ Annulé")
        sys.exit(0)
    
    print("📂 Copie Neuroelectrics...")
    easy_copied, info_copied = copy_neuroelectrics_files(ne_files)
    print(f"✓ {easy_copied} .easy, {info_copied} .info copiés")
    print()
    
    # Étape 7: Collecter et copier BrainVision
    print("🔄 Collecte fichiers BrainVision (.vhdr)...")
    vhdr_files = collect_brainvision_files(subject_dirs)
    print(f"📁 {len(vhdr_files)} fichiers .vhdr trouvés")
    
    response = input(f"Copier triplets? (o/n): ")
    if response.lower() not in ['o', 'oui', 'y', 'yes']:
        print("❌ Annulé")
        sys.exit(0)
    
    print("📂 Copie BrainVision...")
    triplets_ok, triplets_fail = copy_brainvision_files(vhdr_files)
    print(f"✓ {triplets_ok} triplets copiés")
    if triplets_fail > 0:
        print(f"⚠️  {triplets_fail} triplets échoués")
    print()
    
    # Rapport final
    print("=" * 80)
    print("✅ Copie terminée!")
    print(f"Destination: {BIDS_ROOT}")
    print("=" * 80)
        edf_files = edf_files[:10]
    else:
        response = input(f"⚠️  Copier les fichiers .easy/.info associés à ces {len(edf_files)} fichiers? (o/n): ")
        if response.lower() not in ['o', 'oui', 'y', 'yes']:
            print("❌ Copie annulée.")
            sys.exit(0)
    
    print()
    print("� Début de la copie des fichiers .easy et .info...")
    print()
    
    # Étape 7: Copier les fichiers .easy et .info
    files_processed = 0
    files_failed = 0
    files_skipped = 0
    easy_total = 0
    info_total = 0
    
    for edf_file in edf_files:
        # Extraire les informations du fichier
        result = create_bids_path_from_edf(edf_file)
        if result is None:
            files_failed += 1
            continue
        
        bids_path, subject_id, session = result
        
        # Copier uniquement les fichiers .easy et .info
        success, easy_copied, info_copied = copy_easy_info_files(
            edf_file, subject_id, session
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
    print(f"  Fichiers .edf analysés:  {len(edf_files)}")
    print(f"  Fichiers traités:        {files_processed} ✓")
    print(f"  Fichiers .easy copiés:   {easy_total} ✓")
    print(f"  Fichiers .info copiés:   {info_total} ✓")
    if files_skipped > 0:
        print(f"  Fichiers ignorés:        {files_skipped} ⏭️")
    if files_failed > 0:
        print(f"  Fichiers échoués:        {files_failed} ❌")
    print()
    
    if files_processed > 0:
        print(f"✅ Copie terminée! Fichiers .easy/.info copiés dans: {BIDS_ROOT}")
    else:
        print("⚠️  Aucun fichier n'a été copié.")
    
    print("=" * 80)


if __name__ == "__main__":
    main()
