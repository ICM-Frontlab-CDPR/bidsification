'''
Be sure to bidsify the beh/ folder properly (name of the files) before to run this script
'''
import pdb
import os
import argparse
import yaml
from glob import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# # load config variables 
# CONFIG_FILE = "_config.yaml" #TODO use pydantic ou hydra
# try:
#     with open(CONFIG_FILE, 'r') as file:
#         config = yaml.safe_load(file)
#         BIDS_DIR = config.get('bids_dir', '/default/bids/dir/')
#         print(f"BIDS_DIR: {BIDS_DIR}")
# except FileNotFoundError:
#     print(f"Le fichier de configuration '{CONFIG_FILE}' est introuvable.")
# except yaml.YAMLError as e:
#     print(f"Erreur lors du chargement du fichier YAML : {e}")
BIDS_DIR = '/home/hdreyfus/nasShare/projects/EXPLORE_PLUS_dev/rawdata'



def get_mri_sessions(bids_root: str, subject: str) -> list[str]:
    """Cherche les sessions où il y a func, fmap ou anat dans le dataset BIDS.

    Args:
        bids_root (str): Chemin vers le répertoire BIDS.
        subject (str): Identifiant du sujet (ex: 'sub-01').

    Returns:
        list[str]: Liste des sessions valides.
    """
    session_paths = glob(os.path.join(bids_root, subject, "ses-*"))
    valid_sessions = []
    for session_path in session_paths:
        if any(os.path.isdir(os.path.join(session_path, folder)) for folder in ['func', 'fmap', 'anat']):
            valid_sessions.append(os.path.basename(session_path))  # Extrait 'ses-X'
    return valid_sessions


def get_mri_beh_files(root, subject) -> list[str]:
    # Récupérer la liste des sessions contenant des données IRM
    valid_sessions = get_mri_sessions(root, subject)
    # Récupérer tous les fichiers comportementaux
    beh_files = glob(os.path.join(root, subject, '*/beh', '*.tsv'))
    # Filtrer les fichiers qui appartiennent aux sessions valides
    beh_files = [f for f in beh_files if any(sess in f for sess in valid_sessions)]
    return beh_files


def extract_events(behavior_data):
    # Définition des types d'événements et des colonnes associées
    event_mapping = {
        "cue": "trial_start",
        "response": "RT",
        "feedback": "outcome_start",
        "questions": "startQuestion",
        "answers": "startQuestion"
    }

    events = []
    for _, row in behavior_data.iterrows():
        for trial_type, col in event_mapping.items():
            if col in row and not pd.isna(row[col]):  # Vérifie si la colonne existe et n'est pas NaN
                if trial_type == "cue":
                    row[col]
                elif trial_type == "response":
                    onset = row["trial_start"] + row[col]
                elif trial_type == "feedback":
                    row[col]
                else:
                    raise BaseException() 
                    #TODO extract questions and answers 
                    # (will need to compute based on what we know from the implementation,
                    # because behavior file do not contains all the information needed)
                events.append({"onset": onset, "duration": 0, "trial_type": trial_type})
                
    return pd.DataFrame(events)


def main():
    parser = argparse.ArgumentParser(description="Script pour traiter un ou des sujet BIDS.")
    parser.add_argument('--subjects', type=str, nargs='+', required=True, help="exemple: sub-08 sub-09")
    args = parser.parse_args()
    print(f"Sujet(s) traité(s) : {args.subjects}")
    
    # récupérer les fichiers behaviors
    beh_files = get_mri_beh_files(BIDS_DIR, args.subjects[0])
    for beh_file in beh_files:
       
        behavior_data = pd.read_csv(beh_file, sep='\t')
        events = extract_events(behavior_data)
        
        # Construction du chemin de sortie dans le répertoire func
        func_dir = beh_file.replace("beh", "func").rsplit("/", 1)[0]

        # Nom du fichier event basé sur le nom du fichier beh
        event_filename = os.path.basename(beh_file).replace("_beh", "_events").replace(".tsv", "_events.tsv")
        event_filepath = os.path.join(func_dir, event_filename)
        
        # Sauvegarde au format TSV
        events.to_csv(event_filepath, sep='\t', index=False)
        print(f"Fichier d'événements enregistré : {event_filepath}")
        

      
if __name__ == '__main__':
    main()