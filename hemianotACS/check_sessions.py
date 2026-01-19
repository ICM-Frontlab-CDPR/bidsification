#!/usr/bin/env python3
"""
Vérifier le nombre de séances pour PATIENTS vs HEALTHY
"""
from pathlib import Path
import re

EEG_PATH = Path("/Users/hippolyte.dreyfus/Desktop/hemiatotACS/HEMIANOTACS_WIP/EEG")

def extract_subject_info(folder_name):
    match = re.match(r'(\d+)-(\d+)-([A-Z]+)_(PATIENT|HEALTHY)', folder_name)
    if match:
        return match.group(2), match.group(4)  # subject_id, group
    return None, None

# Analyser tous les participants
patient_sessions = []
healthy_sessions = []

for subj_dir in sorted(EEG_PATH.iterdir()):
    if not subj_dir.is_dir():
        continue
    
    # Exclure les exclus
    if 'excluded' in subj_dir.name or 'STAND_BY' in subj_dir.name:
        continue
    
    subject_id, group = extract_subject_info(subj_dir.name)
    if not subject_id:
        continue
    
    # Compter les sessions
    eeg_dir = subj_dir / "2_EEG"
    if eeg_dir.exists():
        sessions = [d.name for d in eeg_dir.iterdir() if d.is_dir() and d.name.startswith('V')]
        num_sessions = len(sessions)
        
        if group == "PATIENT":
            patient_sessions.append((subj_dir.name, num_sessions, sessions))
        elif group == "HEALTHY":
            healthy_sessions.append((subj_dir.name, num_sessions, sessions))

# Afficher les résultats
print("=" * 80)
print("ANALYSE DES SÉANCES - PATIENTS vs HEALTHY")
print("=" * 80)
print()

print(f"📊 PATIENTS ({len(patient_sessions)} participants)")
print("-" * 80)
sessions_counts = {}
for name, count, sessions in patient_sessions:
    if count not in sessions_counts:
        sessions_counts[count] = 0
    sessions_counts[count] += 1
    print(f"  {name}: {count} séances - {', '.join(sessions[:4])}")

print()
print("  Résumé PATIENTS:")
for count, num in sorted(sessions_counts.items()):
    print(f"    - {num} patients avec {count} séance(s)")

print()
print(f"📊 HEALTHY ({len(healthy_sessions)} participants)")
print("-" * 80)
sessions_counts_healthy = {}
for name, count, sessions in healthy_sessions:
    if count not in sessions_counts_healthy:
        sessions_counts_healthy[count] = 0
    sessions_counts_healthy[count] += 1
    print(f"  {name}: {count} séances - {', '.join(sessions[:4])}")

print()
print("  Résumé HEALTHY:")
for count, num in sorted(sessions_counts_healthy.items()):
    print(f"    - {num} healthy avec {count} séance(s)")

print()
print("=" * 80)
print("CONCLUSION")
print("=" * 80)

# Calculer la moyenne
if patient_sessions:
    avg_patient = sum(s[1] for s in patient_sessions) / len(patient_sessions)
    print(f"  Moyenne PATIENTS: {avg_patient:.1f} séances/participant")

if healthy_sessions:
    avg_healthy = sum(s[1] for s in healthy_sessions) / len(healthy_sessions)
    print(f"  Moyenne HEALTHY:  {avg_healthy:.1f} séances/participant")

print()
