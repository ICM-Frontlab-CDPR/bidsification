#!/usr/bin/env python3
"""
Validation BIDS détaillée avec rapport des erreurs
"""
from pathlib import Path
import json

BIDS_ROOT = Path("/Users/hippolyte.dreyfus/Desktop/hemiatotACS/BIDS")

def check_bids_structure():
    """Vérifie la structure BIDS et génère un rapport détaillé"""
    
    print("=" * 80)
    print("RAPPORT DE VALIDATION BIDS - HEMIANOTACS")
    print("=" * 80)
    print()
    
    errors = []
    warnings = []
    
    # 1. Vérifier dataset_description.json
    print("1. FICHIERS REQUIS")
    print("-" * 80)
    
    dataset_desc = BIDS_ROOT / "dataset_description.json"
    if dataset_desc.exists():
        with open(dataset_desc) as f:
            desc_data = json.load(f)
        print(f"✓ dataset_description.json présent")
        print(f"  - Name: {desc_data.get('Name')}")
        print(f"  - BIDSVersion: {desc_data.get('BIDSVersion')}")
        
        # Vérifier les champs requis
        required_fields = ['Name', 'BIDSVersion']
        for field in required_fields:
            if field not in desc_data:
                errors.append(f"dataset_description.json manque le champ requis: {field}")
    else:
        errors.append("dataset_description.json manquant")
        print("✗ dataset_description.json manquant")
    
    # Vérifier participants.tsv
    participants_file = BIDS_ROOT / "participants.tsv"
    if participants_file.exists():
        print(f"✓ participants.tsv présent")
        with open(participants_file) as f:
            lines = f.readlines()
            print(f"  - {len(lines)-1} participants listés")
    else:
        errors.append("participants.tsv manquant")
        print("✗ participants.tsv manquant")
    
    # 2. Vérifier la structure des sujets
    print()
    print("2. STRUCTURE DES SUJETS")
    print("-" * 80)
    
    subjects = sorted([d for d in BIDS_ROOT.iterdir() if d.is_dir() and d.name.startswith('sub-')])
    print(f"Nombre de sujets: {len(subjects)}")
    
    # Vérifier quelques sujets
    for subj in subjects[:3]:
        print(f"\n  {subj.name}:")
        sessions = sorted([d for d in subj.iterdir() if d.is_dir() and d.name.startswith('ses-')])
        for ses in sessions:
            eeg_dir = ses / "eeg"
            if eeg_dir.exists():
                eeg_files = list(eeg_dir.glob("*.edf"))
                json_files = list(eeg_dir.glob("*.json"))
                tsv_files = list(eeg_dir.glob("*_channels.tsv"))
                
                print(f"    {ses.name}/eeg: {len(eeg_files)} .edf, {len(json_files)} .json, {len(tsv_files)} _channels.tsv")
                
                # Vérifier que chaque .edf a son .json
                for edf in eeg_files:
                    json_counterpart = edf.with_suffix('.json')
                    if not json_counterpart.exists():
                        warnings.append(f"{edf.relative_to(BIDS_ROOT)} manque son fichier .json sidecar")
    
    # 3. Vérifier les noms de fichiers BIDS
    print()
    print("3. NOMENCLATURE DES FICHIERS")
    print("-" * 80)
    
    # Compter les fichiers par task
    tasks = {}
    for subj in subjects:
        for edf_file in subj.rglob("*.edf"):
            # Extraire le task du nom de fichier
            parts = edf_file.stem.split('_')
            for part in parts:
                if part.startswith('task-'):
                    task = part.replace('task-', '')
                    if task not in tasks:
                        tasks[task] = 0
                    tasks[task] += 1
    
    print(f"Tasks trouvées:")
    for task, count in sorted(tasks.items()):
        print(f"  - task-{task}: {count} fichiers")
    
    # 4. Vérifier les métadonnées
    print()
    print("4. MÉTADONNÉES JSON")
    print("-" * 80)
    
    json_files = list(BIDS_ROOT.rglob("*_eeg.json"))
    print(f"Nombre de fichiers JSON sidecar: {len(json_files)}")
    
    if json_files:
        # Vérifier un exemple
        example_json = json_files[0]
        with open(example_json) as f:
            metadata = json.load(f)
        print(f"\nExemple: {example_json.name}")
        print(f"  Champs présents: {', '.join(metadata.keys())}")
        
        # Champs recommandés pour EEG
        recommended_fields = ['SamplingFrequency', 'EEGReference', 'PowerLineFrequency']
        missing_recommended = [f for f in recommended_fields if f not in metadata]
        if missing_recommended:
            warnings.append(f"Champs recommandés manquants dans les JSON: {', '.join(missing_recommended)}")
    
    # 5. README
    print()
    print("5. DOCUMENTATION")
    print("-" * 80)
    
    readme = BIDS_ROOT / "README"
    if readme.exists() or (BIDS_ROOT / "README.md").exists() or (BIDS_ROOT / "README.txt").exists():
        print("✓ README présent")
    else:
        warnings.append("README manquant (recommandé)")
        print("⚠ README manquant (recommandé)")
    
    # RAPPORT FINAL
    print()
    print("=" * 80)
    print("RÉSUMÉ")
    print("=" * 80)
    
    if not errors:
        print("✓ Aucune erreur critique détectée")
    else:
        print(f"❌ {len(errors)} ERREUR(S):")
        for i, err in enumerate(errors, 1):
            print(f"  {i}. {err}")
    
    print()
    
    if not warnings:
        print("✓ Aucun avertissement")
    else:
        print(f"⚠️  {len(warnings)} AVERTISSEMENT(S):")
        for i, warn in enumerate(warnings, 1):
            print(f"  {i}. {warn}")
    
    print()
    print("=" * 80)
    print("RECOMMANDATIONS")
    print("=" * 80)
    print("1. Ajouter un fichier README décrivant le dataset")
    print("2. Vérifier que tous les fichiers JSON contiennent les métadonnées requises")
    print("3. Utiliser un validateur BIDS online: https://bids-standard.github.io/bids-validator/")
    print()
    
    return len(errors) == 0

if __name__ == "__main__":
    is_valid = check_bids_structure()
    exit(0 if is_valid else 1)
