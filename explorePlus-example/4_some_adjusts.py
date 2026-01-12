import mne
import pandas as pd
from datetime import datetime
import numpy as np
import pdb
import os
import json
from pathlib import Path
import argparse
import yaml
import re

# load config variables 
CONFIG_FILE = "_config.yaml"
try:
    with open(CONFIG_FILE, 'r') as file:
        config = yaml.safe_load(file)
        BIDS_DIR = config.get('bids_dir', '/default/bids/dir/')
        print(f"BIDS_DIR: {BIDS_DIR}")
except FileNotFoundError:
    print(f"Le fichier de configuration '{CONFIG_FILE}' est introuvable.")
except yaml.YAMLError as e:
    print(f"Erreur lors du chargement du fichier YAML : {e}")




# Fonction pour transformer le nom en format BIDS
def rename_to_bids(file_path):
    parts = file_path.name.split('_')
    subject = parts[0]  # e.g., "sub-01"
    session = parts[1]  # e.g., "ses-1"
    run = next((part for part in parts if part.startswith('run')), None)  # e.g., "run-1"
    new_name = f"{subject}_{session}_task-EXPLORE_{run}.tsv"
    return file_path.parent / new_name

# Ajouter un fichier sidecar .json
def create_sidecar(tsv_file):
    sidecar_path = tsv_file.with_suffix('.json')
    metadata = {
        "TaskName": "EXPLORE",
        "Description": "Behavioral data for the EXPLORE_PLUS study",
        "BIDSVersion": "1.4.0"
    }
    with open(sidecar_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=4)



if __name__ =='__main__':
    parser = argparse.ArgumentParser(description="Script pour traiter un ou des sujet BIDS.")
    parser.add_argument('--subjects', type=str, nargs='+',required=True, 
                    help="Liste des identifiants des sujets (par exemple, sub-08 sub-09)")
    args = parser.parse_args()
    
    # Récupérer tous les fichiers .tsv dans les dossiers 'beh', en excluant 'derivatives'
    beh_tsv_files = [file for file in Path(BIDS_DIR).rglob('*.tsv')
                    if 'beh' in file.parts and 'derivatives' not in file.parts] #TODO ajouter une conditon sur les tsv selectionnées (ex :ils ne respectent pas la normes bids)
    sub_list = args.subjects
    beh_tsv_files = [file for file in beh_tsv_files if any(sub in file.parts for sub in sub_list)]
    


    for tsv_file in beh_tsv_files:
        print(f"Processing: {tsv_file}")
        
        # Vérifier si le fichier est déjà au format correct
        new_name = rename_to_bids(tsv_file)
        if tsv_file.name == new_name.name:
            print(f"File {tsv_file} is already in the correct format. Skipping.")
        else:
            os.rename(tsv_file, new_name)  # Renommer le fichier
            create_sidecar(new_name)      # Créer le fichier sidecar
            print(f"Renamed to: {new_name} and sidecar created.")
            
        
        # if ".tsv.tsv" in str(tsv_file):
        #     new_name = re.sub(r".tsv.tsv", ".tsv", str(tsv_file))
        #     os.rename(tsv_file, new_name)
        #     print(f"Renommé : {tsv_file} -> {new_name}")
        
   
    # # # # # all_files = Path(BIDS_DIR).rglob("*.tsv.json")

    # # # # # for file in all_files:
    # # # # #     if ".tsv.json" in str(file):
    # # # # #         os.remove(file)








# all_fif = [file for file in Path(BIDS_DIR).rglob('*.fif') if 'derivatives' not in file.parts and 'task' in file.name]
# selected_fif = [file for file in all_fif if 'sub-04' in file.parts and 'ses-4' in file.parts]
# print(selected_fif)


# # Parcourir et traiter chaque fichier .fif
# # for fif_file in selected_fif:
# #     print(f"Traitement du fichier: {fif_file}")
    
# #     # Lecture du fichier .fif
# #     raw = mne.io.read_raw_fif(fif_file, allow_maxshield=True, verbose="ERROR")
   
    # temp_fif_file = Path(fif_file).with_suffix('.tmp.fif')
    # # Sauvegarder temporairement
    # raw.save(temp_fif_file, overwrite=True)
    # # Remplacer l'original
    # os.replace(temp_fif_file, fif_file)
    
    
    
    
    
    
    
    
    
