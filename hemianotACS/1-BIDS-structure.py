#!/usr/bin/env python3
"""
Script de BIDSification pour le projet hemianotACS, a partir du folder HEMIANOTACS_WIP/
Convertit les fichiers EEG .edf en format BIDS
"""
import mne
from mne_bids import write_raw_bids, BIDSPath
from pathlib import Path
import yaml
import re
import pandas as pd

# Charger la configuration
# with open('hemianotACS/config.yaml', 'r') as f:
#     config = yaml.safe_load(f)

# Chemins
RAW_ROOT = Path("/Users/hippolyte.dreyfus/Desktop/hemianotACS/Data/raw/HEMIANOTACS_WIP")
BIDS_ROOT = Path("/Users/hippolyte.dreyfus/Desktop/hemianotACS/Data/bids")
DERIVATIVES_ROOT = Path("/Users/hippolyte.dreyfus/Desktop/hemianotACS/Data/derivatives")
EEG_PATH = RAW_ROOT / "EEG"

# Créer le dossier BIDS s'il n'existe pas
BIDS_ROOT.mkdir(parents=True, exist_ok=True)


def extract_subject_info(folder_name):
    """
    Extrait les informations du dossier participant
    Exemple: 001-0001-CC_PATIENT -> (001, PATIENT, CC)
    """
    match = re.match(r'(\d+)-(\d+)-([A-Z]+)_(PATIENT|HEALTHY)', folder_name)
    if match:
        group_id = match.group(1)
        subject_id = match.group(2)
        initials = match.group(3)
        group = match.group(4)
        return subject_id, group, initials
    return None, None, None


def parse_edf_filename(filename):
    """
    Parse le nom de fichier .edf pour extraire task et run
    Exemples:
    - 20210222152102_Patient1_CC_Stim3_Resting-state_Pre.edf -> task=rest, acq=pre, run=3
    - 20210222155455_Patient1_CC_PostStim3_Task.edf -> task=flanker, acq=post, run=3
    - 20210222152433_Patient1_CC_Stim3_SHAM_Right_Frontal_30_Hz.edf -> task=stim, acq=SHAM, run=3
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
        # Pre ou Post
        if '_Pre' in filename or 'Pre_' in filename or 'Prestim' in filename:
            acq = 'pre'
        elif '_Post' in filename or 'Post_' in filename or 'Poststim' in filename:
            acq = 'post'
        else:
            acq = None
    elif 'Task' in filename or 'task' in filename:
        task = 'flanker'  # Nom de la tâche comportementale
        # Pre ou Post
        if 'PreStim' in filename or 'Prestim' in filename:
            acq = 'pre'
        elif 'PostStim' in filename or 'Poststim' in filename:
            acq = 'post'
        else:
            acq = None
    elif 'SHAM' in filename or 'tACS' in filename or 'tRNS' in filename:
        task = 'stim'
        # Type de stimulation
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


def extract_session_from_folder(folder_name):
    """
    Extrait le numéro de session depuis le nom du dossier
    Exemple: V1_BASELINE_22-12-2020 -> 01
            V2_STIM_28-01-2021 -> 02
    """
    match = re.match(r'V(\d+)', folder_name)
    if match:
        return match.group(1).zfill(2)
    return None


# Étape 1: Scanner les participants et créer participants.tsv
print("=" * 80)
print("BIDSIFICATION HEMIANOTACS - Conversion EEG")
print("=" * 80)
print()

participants_data = []
subject_dirs = sorted([d for d in EEG_PATH.iterdir() if d.is_dir()])

print(f"🔍 Analyse de {len(subject_dirs)} participants...")

for subj_dir in subject_dirs:
    subject_id, group, initials = extract_subject_info(subj_dir.name)
    if subject_id:
        # Exclure les participants STAND_BY et excluded
        if 'excluded' in subj_dir.name or 'STAND_BY' in subj_dir.name:
            print(f"  ⏭️  Exclu: {subj_dir.name}")
            continue
        
        participants_data.append({
            'participant_id': f'sub-{subject_id}',
            'group': group.lower(),
            'initials': initials
        })

# Créer et sauvegarder participants.tsv
participants_df = pd.DataFrame(participants_data)
participants_file = BIDS_ROOT / 'participants.tsv'
participants_df.to_csv(participants_file, sep='\t', index=False)
print(f"✓ participants.tsv créé: {len(participants_data)} participants")
print()

# Créer dataset_description.json
dataset_description = {
    "Name": "HemianotACS",
    "BIDSVersion": "1.9.0",
    "Authors": ["Unknown"],
    "Description": "EEG data from hemianopsia tACS study"
}

import json
with open(BIDS_ROOT / 'dataset_description.json', 'w') as f:
    json.dump(dataset_description, f, indent=4)
print("✓ dataset_description.json créé")
print()

# Étape 2: Copier le dossier data-VisualField vers derivatives
import shutil
print("📂 Copie du dossier data-VisualField vers derivatives/...")
source_visual_field = RAW_ROOT / "EEG" / "data-VisualField"
dest_visual_field = DERIVATIVES_ROOT / "data-VisualField"

if source_visual_field.exists():
    # Créer le dossier derivatives s'il n'existe pas
    dest_visual_field.parent.mkdir(parents=True, exist_ok=True)
    
    # Copier le dossier
    if dest_visual_field.exists():
        print(f"  ⚠️  Le dossier existe déjà: {dest_visual_field}")
        overwrite_vf = input("  Écraser le dossier existant? (o/n): ")
        if overwrite_vf.lower() in ['o', 'oui', 'y', 'yes']:
            shutil.rmtree(dest_visual_field)
            shutil.copytree(source_visual_field, dest_visual_field)
            print(f"✓ data-VisualField copié vers derivatives/")
        else:
            print(f"⏭️  Copie ignorée")
    else:
        shutil.copytree(source_visual_field, dest_visual_field)
        print(f"✓ data-VisualField copié vers derivatives/")
else:
    print(f"⚠️  Dossier source non trouvé: {source_visual_field}")
print()

# Étape 3: Copier les dossiers EEG_VISUAL_FIELD et fichiers PDF de chaque participant
print("📂 Copie des dossiers EEG_VISUAL_FIELD et fichiers PDF des participants...")
vf_copied = 0
vf_failed = 0
pdf_copied = 0
pdf_failed = 0

for subj_dir in subject_dirs:
    subject_id, group, initials = extract_subject_info(subj_dir.name)
    if not subject_id or 'excluded' in subj_dir.name or 'STAND_BY' in subj_dir.name:
        continue
    
    # Chercher les dossiers de session
    eeg_dir = subj_dir / "2_EEG"
    if not eeg_dir.exists():
        continue
    
    # Pour chaque session du participant
    for session_dir in eeg_dir.iterdir():
        if not session_dir.is_dir():
            continue
        
        # Extraire le numéro de session
        session = extract_session_from_folder(session_dir.name)
        if not session:
            continue
        
        # Créer le dossier de destination pour cette session
        ses_dest_dir = BIDS_ROOT / f"sub-{subject_id}" / f"ses-{session}" / "eeg"
        ses_dest_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Copier le dossier EEG_VISUAL_FIELD
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
                print(f"  ❌ Erreur dossier VF pour sub-{subject_id}/ses-{session}: {e}")
                vf_failed += 1
        
        # 2. Copier les fichiers PDF de visual field
        pdf_files = list(session_dir.glob("*.pdf"))
        for pdf_file in pdf_files:
            # Vérifier si c'est un fichier de visual field (peut contenir "visual", "field", "VF", etc.)
            if any(keyword in pdf_file.name.lower() for keyword in ['visual', 'field', 'vf', 'champ']):
                try:
                    pdf_dest = ses_dest_dir / pdf_file.name
                    shutil.copy2(pdf_file, pdf_dest)
                    print(f"  ✓ sub-{subject_id}/ses-{session}/eeg/{pdf_file.name}")
                    pdf_copied += 1
                except Exception as e:
                    print(f"  ❌ Erreur PDF pour sub-{subject_id}/ses-{session}/{pdf_file.name}: {e}")
                    pdf_failed += 1

print(f"✓ {vf_copied} dossiers EEG_VISUAL_FIELD copiés")
print(f"✓ {pdf_copied} fichiers PDF copiés")
if vf_failed > 0 or pdf_failed > 0:
    print(f"⚠️  {vf_failed} dossiers et {pdf_failed} PDF ont échoué")
print()

# Étape 4: Analyser tous les fichiers du dossier RAW
print("📊 Analyse des fichiers dans le dossier RAW...")
print()

# Collecter tous les fichiers
from collections import Counter
all_files = []
for subj_dir in subject_dirs:
    subject_id, group, initials = extract_subject_info(subj_dir.name)
    if not subject_id or 'excluded' in subj_dir.name or 'STAND_BY' in subj_dir.name:
        continue
    
    # Parcourir tous les fichiers du participant
    for file_path in subj_dir.rglob("*"):
        if file_path.is_file():
            all_files.append(file_path)

# Compter par extension
extensions_counter = Counter([f.suffix.lower() if f.suffix else '[no_extension]' for f in all_files])

# Afficher les statistiques
print(f"📁 Nombre total de fichiers: {len(all_files)}")
print()
print("📋 Répartition par type de fichier:")
print("-" * 50)

# Trier par nombre décroissant
for ext, count in sorted(extensions_counter.items(), key=lambda x: x[1], reverse=True):
    ext_display = ext if ext != '[no_extension]' else '[sans extension]'
    print(f"  {ext_display:20s} : {count:5d} fichiers")

print("-" * 50)
print()

# Étape 5: Convertir les fichiers EEG
print("🔄 Début de la conversion des fichiers EEG...")
print()

# Trouver tous les fichiers .edf
edf_files = []
for subj_dir in subject_dirs:
    subject_id, group, initials = extract_subject_info(subj_dir.name)
    if not subject_id or 'excluded' in subj_dir.name or 'STAND_BY' in subj_dir.name:
        continue
    
    eeg_dir = subj_dir / "2_EEG"
    if eeg_dir.exists():
        edf_files.extend(list(eeg_dir.rglob("*.edf")))

# Filtrer les fichiers ABORTED et easy_converted
edf_files = [f for f in edf_files if 'ABORTED' not in f.name and 'easy_converted' not in f.name]

print(f"📁 {len(edf_files)} fichiers .edf trouvés (hors ABORTED)")
print()

# Mode automatique pour les tests - convertir seulement les premiers fichiers
import sys
if '--test' in sys.argv:
    print("🧪 Mode TEST: conversion des 10 premiers fichiers seulement")
    edf_files = edf_files[:10]
    overwrite = True
else:
    # Demander confirmation
    response = input(f"⚠️  Voulez-vous continuer et convertir ces {len(edf_files)} fichiers en BIDS? (o/n): ")
    if response.lower() not in ['o', 'oui', 'y', 'yes']:
        print("❌ Conversion annulée par l'utilisateur.")
        sys.exit(0)

    # Demander si on écrase les fichiers existants
    overwrite = False
    overwrite_response = input("🔄 Écraser les fichiers BIDS déjà existants? (o/n): ")
    if overwrite_response.lower() in ['o', 'oui', 'y', 'yes']:
        overwrite = True

print()
print("🔄 Début de la conversion...")
print()

# Compteurs
files_processed = 0
files_failed = 0
files_skipped = 0
easy_copied = 0
info_copied = 0

# Convertir chaque fichier
for edf_file in edf_files:
    try:
        # Extraire les informations du chemin
        parts = edf_file.parts
        
        # Trouver le dossier participant
        eeg_idx = parts.index('EEG')
        subj_folder_name = parts[eeg_idx + 1]
        session_folder_name = parts[-2]  # Dossier session (V1_BASELINE_..., etc.)
        
        # Extraire subject
        subject_id, group, initials = extract_subject_info(subj_folder_name)
        if not subject_id:
            files_failed += 1
            continue
        
        # Extraire session
        session = extract_session_from_folder(session_folder_name)
        if not session:
            print(f"⚠️  Session non reconnue: {session_folder_name} ({edf_file.name})")
            files_failed += 1
            continue
        
        # Parser le nom de fichier
        task, acq, run = parse_edf_filename(edf_file.name)
        if task is None:
            files_skipped += 1
            continue
        
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
        
        # Vérifier si le fichier existe déjà
        bids_file = bids_path.copy().update(suffix='eeg', extension='.edf')
        if bids_file.fpath.exists() and not overwrite:
            files_skipped += 1
            continue
        
        # Lire le fichier EDF
        raw = mne.io.read_raw_edf(edf_file, preload=False, verbose=False)
        
        # Écrire en BIDS (toujours avec overwrite=True pour mettre à jour participants.tsv)
        write_raw_bids(raw, bids_path, overwrite=True, verbose=False)
        
        # Construire le nom de base du fichier BIDS (sans extension)
        bids_basename = f"sub-{subject_id}_ses-{session}_task-{task}"
        if acq:
            bids_basename += f"_acq-{acq}"
        if run:
            bids_basename += f"_run-{run}"
        
        # Dossier de destination pour les fichiers supplémentaires
        dest_dir = BIDS_ROOT / f"sub-{subject_id}" / f"ses-{session}" / "eeg"
        
        # Copier les fichiers .easy et .info associés
        base_name = edf_file.stem  # Nom sans extension
        
        # Chercher et copier le fichier .easy
        easy_file = edf_file.parent / f"{base_name}.easy"
        if easy_file.exists():
            easy_dest = dest_dir / f"{bids_basename}_eeg.easy"
            shutil.copy2(easy_file, easy_dest)
            easy_copied += 1
        
        # Chercher et copier le fichier .info
        info_file = edf_file.parent / f"{base_name}.info"
        if info_file.exists():
            info_dest = dest_dir / f"{bids_basename}_eeg.info"
            shutil.copy2(info_file, info_dest)
            info_copied += 1
        
        # Afficher
        info_str = f"sub-{subject_id}/ses-{session}/task-{task}"
        if acq:
            info_str += f"/acq-{acq}"
        if run:
            info_str += f"/run-{run}"
        print(f"✓ {info_str}")
        files_processed += 1
        
    except Exception as e:
        print(f"❌ Erreur avec {edf_file.name}: {e}")
        files_failed += 1

# Rapport final
print()
print("=" * 80)
print("📊 RAPPORT FINAL")
print("=" * 80)
print(f"  Fichiers .edf trouvés:   {len(edf_files)}")
print(f"  Fichiers .edf convertis: {files_processed} ✓")
print(f"  Fichiers .easy copiés:   {easy_copied} ✓")
print(f"  Fichiers .info copiés:   {info_copied} ✓")
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
