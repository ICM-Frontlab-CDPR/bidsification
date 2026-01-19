#!/usr/bin/env python3
"""
Script de BIDSification pour le projet hemianotACS
Convertit les fichiers EEG .edf en format BIDS
"""
import mne
from mne_bids import write_raw_bids, BIDSPath
from pathlib import Path
import yaml
import re
import pandas as pd

# Charger la configuration
with open('hemianotACS/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Chemins
RAW_ROOT = Path("/Users/hippolyte.dreyfus/Desktop/hemiatotACS/HEMIANOTACS_WIP")
BIDS_ROOT = Path("/Users/hippolyte.dreyfus/Desktop/hemiatotACS/BIDS")
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

# Étape 2: Convertir les fichiers EEG
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
        exit(0)

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
        
        # Écrire en BIDS
        write_raw_bids(raw, bids_path, overwrite=overwrite, verbose=False)
        
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
print(f"  Fichiers trouvés:   {len(edf_files)}")
print(f"  Fichiers convertis: {files_processed} ✓")
if files_skipped > 0:
    print(f"  Fichiers ignorés:   {files_skipped} ⏭️")
if files_failed > 0:
    print(f"  Fichiers échoués:   {files_failed} ❌")
print()

if files_processed > 0:
    print(f"✅ Conversion terminée! Dataset BIDS créé dans: {BIDS_ROOT}")
    print()
    print("📋 Prochaine étape: Valider avec bids-validator")
    print(f"   Commande: bids-validator {BIDS_ROOT}")
else:
    print("⚠️  Aucun fichier n'a été converti.")

print("=" * 80)
