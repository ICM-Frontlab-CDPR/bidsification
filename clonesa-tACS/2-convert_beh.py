#!/usr/bin/env python3
"""
Conversion des fichiers de comportement en format BIDS
"""
from pathlib import Path
import yaml

# Charger la configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Chemins
RAW_BHV = Path(config['paths']['raw_root']) / config['paths']['raw_bhv']
BIDS_ROOT = Path(config['paths']['bids_root'])
TASK = config['experiment']['task']
CONDITIONS = config['experiment']['conditions']
SESSIONS = config['experiment']['sessions']

print("=" * 80)
print("🔄 CONVERSION DES FICHIERS DE COMPORTEMENT EN BIDS")
print("=" * 80)
print(f"\n📂 Source: {RAW_BHV}")
print(f"📂 Destination: {BIDS_ROOT}")
print()

# TODO: Implémenter la conversion