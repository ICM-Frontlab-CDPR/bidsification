#!/usr/bin/env python3
"""
Audit des fichiers de comportement dans RAW/bhv
"""
from pathlib import Path
from collections import defaultdict
import pandas as pd
import re
import yaml

# Charger la configuration
config_path = Path(__file__).parent / 'config.yaml'
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

# Chemins
RAW_BHV = Path(config['paths']['raw_root']) / config['paths']['raw_bhv']

# Structure attendue
EXPECTED_CONDITIONS = config['experiment']['conditions']
EXPECTED_SESSIONS = config['experiment']['sessions']
EXPECTED_RUNS_PER_SESSION = config['experiment']['expected_runs_per_session']

print("=" * 80)
print("🔍 AUDIT DES FICHIERS DE COMPORTEMENT")
print("=" * 80)
print()

# Statistiques globales
total_files = 0
subjects_data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
issues = []

# Scanner tous les fichiers
csv_files = list(RAW_BHV.rglob('*.csv'))
total_files = len(csv_files)

print(f"📁 Nombre total de fichiers CSV: {total_files}")
print()

# Analyser chaque fichier
for csv_file in sorted(csv_files):
    parts = csv_file.parts
    
    # Extraire les informations du chemin
    try:
        subject_idx = [i for i, p in enumerate(parts) if p.startswith('sub_')][0]
        subject = parts[subject_idx]
        session = parts[subject_idx + 1]
        filename = csv_file.name
        
        # Parser le nom de fichier
        # Format: sub_XX_CONDITION_RUN_1_probe_min_FT-RSGT_YYYY_MMM_DD_HHMM.csv
        # Enlever le * final qui peut apparaître
        filename_clean = filename.rstrip('*')
        match = re.match(r'sub_(\d+)_(SHAM|tACS|tRNS)\s*_?\s*(\d+)_.*\.csv', filename_clean)
        if match:
            sub_num, condition, run = match.groups()
            
            # Vérifier la cohérence
            if f'sub_{sub_num}' != subject:
                issues.append(f"❌ {csv_file.relative_to(RAW_BHV)}: Incohérence sujet ({subject} vs sub_{sub_num})")
            
            # Stocker l'info
            subjects_data[subject][session][condition].append({
                'run': int(run),
                'file': csv_file,
                'filename': filename
            })
        else:
            issues.append(f"⚠️  {csv_file.relative_to(RAW_BHV)}: Nom de fichier non parsable")
            
    except Exception as e:
        issues.append(f"❌ {csv_file.relative_to(RAW_BHV)}: Erreur de parsing - {e}")

# Rapport par sujet
print("=" * 80)
print("📊 RAPPORT PAR SUJET")
print("=" * 80)
print()

for subject in sorted(subjects_data.keys()):
    print(f"\n{'─' * 80}")
    print(f"👤 {subject.upper()}")
    print(f"{'─' * 80}")
    
    for session in EXPECTED_SESSIONS:
        if session in subjects_data[subject]:
            session_data = subjects_data[subject][session]
            print(f"\n  📅 {session}")
            
            for condition in EXPECTED_CONDITIONS:
                if condition in session_data:
                    runs = sorted(session_data[condition], key=lambda x: x['run'])
                    run_nums = [r['run'] for r in runs]
                    
                    # Vérifier les runs
                    expected_runs = list(range(1, 5))
                    missing_runs = set(expected_runs) - set(run_nums)
                    extra_runs = set(run_nums) - set(expected_runs)
                    
                    status = "✓" if len(runs) == 4 and not missing_runs and not extra_runs else "⚠️ "
                    print(f"    {status} {condition:6s}: {len(runs)} fichiers (runs: {run_nums})")
                    
                    if missing_runs:
                        issues.append(f"⚠️  {subject}/{session}/{condition}: Runs manquants {sorted(missing_runs)}")
                    if extra_runs:
                        issues.append(f"⚠️  {subject}/{session}/{condition}: Runs supplémentaires {sorted(extra_runs)}")
                    
                    # Vérifier les doublons
                    if len(run_nums) != len(set(run_nums)):
                        duplicates = [r for r in run_nums if run_nums.count(r) > 1]
                        issues.append(f"❌ {subject}/{session}/{condition}: Runs dupliqués {set(duplicates)}")
                else:
                    print(f"    ❌ {condition:6s}: MANQUANT")
                    issues.append(f"❌ {subject}/{session}: Condition {condition} complètement manquante")
        else:
            print(f"\n  ❌ {session}: SESSION MANQUANTE")
            issues.append(f"❌ {subject}: Session {session} complètement manquante")

# Résumé des statistiques
print("\n" + "=" * 80)
print("📈 STATISTIQUES GLOBALES")
print("=" * 80)

total_subjects = len(subjects_data)
print(f"\n  Nombre de sujets: {total_subjects}")
print(f"  Nombre de fichiers CSV: {total_files}")

# Compter les fichiers attendus
expected_files = total_subjects * 2 * 3 * 4  # subjects * sessions * conditions * runs
print(f"  Fichiers attendus: {expected_files} ({total_subjects} sujets × 2 sessions × 3 conditions × 4 runs)")
print(f"  Différence: {total_files - expected_files}")

# Vérifier l'intégrité de chaque fichier
print("\n" + "=" * 80)
print("🔬 VÉRIFICATION DE L'INTÉGRITÉ DES FICHIERS")
print("=" * 80)
print()

corrupted_files = []
file_sizes = []

for csv_file in csv_files:
    try:
        # Essayer de lire le fichier
        df = pd.read_csv(csv_file)
        file_size = csv_file.stat().st_size
        file_sizes.append(file_size)
        
        # Vérifications basiques
        if len(df) == 0:
            corrupted_files.append(f"⚠️  {csv_file.name}: Fichier vide")
        elif len(df) < 10:
            corrupted_files.append(f"⚠️  {csv_file.name}: Très peu de lignes ({len(df)})")
            
    except Exception as e:
        corrupted_files.append(f"❌ {csv_file.name}: Erreur de lecture - {str(e)[:50]}")

if corrupted_files:
    print("Fichiers problématiques:")
    for issue in corrupted_files:
        print(f"  {issue}")
else:
    print("✓ Tous les fichiers peuvent être lus correctement")

if file_sizes:
    import numpy as np
    print(f"\nTailles des fichiers:")
    print(f"  Min: {min(file_sizes):,} octets")
    print(f"  Max: {max(file_sizes):,} octets")
    print(f"  Moyenne: {np.mean(file_sizes):,.0f} octets")
    print(f"  Médiane: {np.median(file_sizes):,.0f} octets")

# Rapport des problèmes
print("\n" + "=" * 80)
print("🚨 PROBLÈMES DÉTECTÉS")
print("=" * 80)
print()

if issues:
    print(f"Nombre total de problèmes: {len(issues)}\n")
    for issue in issues:
        print(f"  {issue}")
else:
    print("✓ Aucun problème détecté! 🎉")

print("\n" + "=" * 80)
print("FIN DE L'AUDIT")
print("=" * 80)
