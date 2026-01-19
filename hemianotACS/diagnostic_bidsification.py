#!/usr/bin/env python3
"""
Diagnostic simple pour la BIDSification du projet hemianotACS
"""
import os
from pathlib import Path
import yaml

# Configuration
RAW_PATH = Path("/Users/hippolyte.dreyfus/Desktop/hemiatotACS/HEMIANOTACS_WIP")
BIDS_PATH = Path("/Users/hippolyte.dreyfus/Desktop/hemiatotACS/BIDS")

def analyze_raw_structure():
    """Analyse la structure des données brutes"""
    print("=" * 60)
    print("DIAGNOSTIC HEMIANOTACS - BIDSification")
    print("=" * 60)
    
    # 1. Vérifier l'existence des dossiers
    print("\n1. VÉRIFICATION DES DOSSIERS")
    print("-" * 60)
    print(f"   RAW existe: {'✓' if RAW_PATH.exists() else '✗'} ({RAW_PATH})")
    print(f"   BIDS existe: {'✓' if BIDS_PATH.exists() else '✗'} ({BIDS_PATH})")
    
    if not RAW_PATH.exists():
        print("\n❌ ERREUR: Le dossier RAW n'existe pas!")
        return
    
    # 2. Analyser les participants
    print("\n2. PARTICIPANTS")
    print("-" * 60)
    
    eeg_path = RAW_PATH / "EEG"
    if eeg_path.exists():
        participants = sorted([d.name for d in eeg_path.iterdir() if d.is_dir()])
        print(f"   Nombre total de participants: {len(participants)}")
        
        # Distinguer patients et contrôles
        patients = [p for p in participants if "PATIENT" in p]
        healthy = [p for p in participants if "HEALTHY" in p]
        excluded = [p for p in participants if "excluded" in p or "STAND_BY" in p]
        
        print(f"   - Patients: {len(patients)}")
        print(f"   - Contrôles (HEALTHY): {len(healthy)}")
        print(f"   - Exclus/Stand-by: {len(excluded)}")
        
        if excluded:
            print(f"\n   ⚠️  Participants à exclure:")
            for p in excluded:
                print(f"      - {p}")
    
    # 3. Analyser la structure des données
    print("\n3. TYPES DE DONNÉES")
    print("-" * 60)
    
    # Analyser un participant exemple
    if participants:
        example_subj = [p for p in participants if "excluded" not in p and "STAND_BY" not in p][0]
        example_path = eeg_path / example_subj
        print(f"   Exemple: {example_subj}")
        
        if (example_path / "2_EEG").exists():
            eeg_sessions = sorted([d.name for d in (example_path / "2_EEG").iterdir() if d.is_dir()])
            print(f"   Sessions EEG: {len(eeg_sessions)}")
            for ses in eeg_sessions[:5]:  # Montrer les 5 premières
                print(f"      - {ses}")
            
            # Compter les fichiers EDF
            if eeg_sessions:
                first_session = example_path / "2_EEG" / eeg_sessions[0]
                edf_files = list(first_session.glob("*.edf"))
                print(f"\n   Fichiers EEG (.edf) dans {eeg_sessions[0]}: {len(edf_files)}")
                for f in edf_files[:3]:
                    print(f"      - {f.name}")
        
        if (example_path / "1_VISUAL_FIELD").exists():
            print(f"\n   ✓ Données VISUAL_FIELD présentes")
    
    # 4. IRM
    print("\n4. DONNÉES IRM")
    print("-" * 60)
    irm_path = RAW_PATH / "IRM"
    if irm_path.exists():
        irm_subjects = sorted([d.name for d in irm_path.iterdir() if d.is_dir()])
        print(f"   Nombre de sujets avec IRM: {len(irm_subjects)}")
        print(f"   Premiers sujets: {', '.join(irm_subjects[:5])}")
    
    # 5. État BIDS
    print("\n5. ÉTAT DE LA BIDSIFICATION")
    print("-" * 60)
    if BIDS_PATH.exists():
        bids_content = list(BIDS_PATH.iterdir())
        if not bids_content:
            print("   ⚠️  Dossier BIDS vide - Aucune conversion effectuée")
        else:
            print(f"   Contenu BIDS: {len(bids_content)} éléments")
            for item in bids_content[:5]:
                print(f"      - {item.name}")
    
    # 6. Recommandations
    print("\n6. RECOMMANDATIONS")
    print("-" * 60)
    print("   📋 ÉTAPES RECOMMANDÉES:")
    print("   1. Créer un fichier participants.tsv avec les métadonnées")
    print("   2. Définir la nomenclature BIDS (task, sessions)")
    print("   3. Utiliser mne-bids pour convertir les fichiers EEG (.edf)")
    print("   4. Ajouter les fichiers sidecar JSON pour les métadonnées")
    print("   5. Valider avec bids-validator")
    
    print("\n   🔧 OUTILS DISPONIBLES:")
    print("   ✓ mne-bids (déjà installé)")
    print("   ✓ bids-validator (déjà installé)")
    
    print("\n" + "=" * 60)
    print("Diagnostic terminé!")
    print("=" * 60)

if __name__ == "__main__":
    analyze_raw_structure()
