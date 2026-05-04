'''' 
Run this file after running the "neurospin_to_bids" command in the terminal of neurospin server.

For all behavior files (.csv) of the RAW folder :
Take the behavior, copy to BIDS folder, bidsifie content and name.
'''

# TODO détecter la modalités associées à la session, pour pouvoir le réinjecter dans le nom du fichier ?

import os 
import numpy as np
import pandas as pd
from glob import glob
import re
import argparse
import yaml


# load config variables 
'/neurospin/unicog/protocols/IRMf/ExplorePlus_Meyniel_Paunov_2023/RAW/'
'/neurospin/unicog/protocols/IRMf/ExplorePlus_Meyniel_Paunov_2023/EXPLORE_PLUS/rawdata/'
CONFIG_FILE = "_config.yaml"
try:
    with open(CONFIG_FILE, 'r') as file:
        config = yaml.safe_load(file)
        RAW_DIR = config.get('raw_dir', '/default/raw/dir/')
        BIDS_DIR = config.get('bids_dir', '/default/bids/dir/')
        print(f"RAW_DIR: {RAW_DIR}")
        print(f"BIDS_DIR: {BIDS_DIR}")
except FileNotFoundError:
    print(f"Le fichier de configuration '{CONFIG_FILE}' est introuvable.")
except yaml.YAMLError as e:
    print(f"Erreur lors du chargement du fichier YAML : {e}")


        
RAW_BEH = 'behavior'
BIDS_BEH = 'beh'



#------- parser
parser = argparse.ArgumentParser(description="Script pour traiter un ou des sujet BIDS.")
parser.add_argument(
    '--subjects', 
    type=str, 
    nargs='+',  # Permet d'accepter plusieurs valeurs
    required=True, 
    help="Liste des identifiants des sujets (par exemple, sub-08 sub-09)"
)
args = parser.parse_args()
print(f"Sujet(s) traité(s) : {args.subjects}")



#recherche des sujet déjà présents dans BIDS_DIR
#BIDSsubjects = os.listdir(BIDS_DIR)
BIDSsubjects = args.subjects
BIDSsubjects = [x for x in BIDSsubjects if 'sub-' in x]
RAWsubjects = [x.replace('sub-', 'sub-1') for x in BIDSsubjects] #ajout d'un 1 après le tiret pour matcher avec la structure de RAW
print('subjects detected', RAWsubjects)


# on rentre dans le dossier de chaque sujet pour renommer les fichiers .fif
i = 0
for subject in RAWsubjects:
    #on récupère les sessions effectuées dans RAW_DIR
    subject_dir = os.path.join(RAW_DIR, subject)
    #on effectue un screening des sessions MEG (sessions qui contienne un dossier 'meg')
    RAWsessions = os.listdir(subject_dir)
    RAWsessions = [x for x in RAWsessions if RAW_BEH in os.listdir(os.path.join(subject_dir, x))]
    print('behavior session detected', RAWsessions)
    # on copie les fichiers .fif dans le dossier BIDS_DIR
    for session in RAWsessions:
        beh_session_dir = os.path.join(subject_dir, session, RAW_BEH)
        files = os.listdir(beh_session_dir)
        files = [x for x in files if ('.csv' in x and 'data' in x)]
        print('behavior files detected ' , files)
        for file in files:
            i+=1
            BIDSsession = session.replace('sess_', 'ses-') # on remplace le _ par un tiret et sess par sess pour matcher avec la structure de RAW
            BIDSsubject = subject.replace('sub-1', 'sub-')
            match = re.search(r'block(\d+)', file)
            BIDSrun = 'run-' + str(match.group(1))
            
            # load behavior data .csv
            sub = int(BIDSsubject.split('-')[1]) +100 
            ses = int(BIDSsession.split('-')[1])
            run = int(BIDSrun.split('-')[1]) 
            filename = f"data_subject_{sub}_session_{ses}_block{run}.000000.csv"
            MEGfilename = f"MEG_data_subject_{sub}_session_{ses}_block{run}.000000.csv"
            beh_file = os.path.join(beh_session_dir, filename)
            MEG_beh_file = os.path.join(beh_session_dir, MEGfilename)
            if os.path.exists(beh_file):
                behavior_data = pd.read_csv(beh_file)
            elif os.path.exists(MEG_beh_file):
                behavior_data = pd.read_csv(MEG_beh_file)
            else :
                raise BaseException('erreur donnée manquante')
            
            # Sauvegarder les données comportementales au format TSV 
            target_beh_file = os.path.join(BIDS_DIR, BIDSsubject, BIDSsession, BIDS_BEH, BIDSsubject + "_" + BIDSsession + "_" + BIDSrun + "_task-beh.tsv")
            os.makedirs(os.path.dirname(target_beh_file), exist_ok=True)
            behavior_data.to_csv(target_beh_file, sep='\t', index=False)
            print(f"Saved behavior data to {target_beh_file}")      
                        
print(f'Total of {i} .tsv files copied to BIDS format')


