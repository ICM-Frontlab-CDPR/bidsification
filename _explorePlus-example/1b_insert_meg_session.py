'''
Run this file after running the "neurospin_to_bids" command in the terminal of neurospin server.

This script will insert the MEG session in the BIDS dataset (from the non-BIDS dataset "RAW" structure)

CAUTION !!!
This is a script that interact with the rawdata,
AND MEG DATA DONT HAVE ANY BACK UP on Neurospin server 
(some of them are present on the server but some of them are only on a hard drive in MEG room.)
So make sure to have a copy of the rawdata before running this script. 
'''

import os
import pandas as pd
import re
import argparse
import warnings
warnings.warn( "BAD CHANNELS TO ADD")
import yaml



# load config variables 
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


#### 1 création des sessions MEG pour les sujets déja présents dans BIDS_DIR et rennomage correct des fichiers .fif

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
    RAWsessions = [x for x in RAWsessions if 'meg' in os.listdir(os.path.join(subject_dir, x))]
    print('meg sessions detected', RAWsessions)
    # on copie les fichiers .fif dans le dossier BIDS_DIR
    for session in RAWsessions:
        meg_session_dir = os.path.join(subject_dir, session, 'meg')
        files = os.listdir(meg_session_dir)
        files = [x for x in files if ('.fif' in x and 'run' in x)]
        print('meg files detected which will be copied in BIDS format' ,files)
        for file in files:
            i+=1
            BIDSsession = session.replace('sess_', 'ses-') # on remplace le _ par un tiret et sess par sess pour matcher avec la structure de RAW
            BIDSsubject = subject.replace('sub-1', 'sub-')
            match = re.search(r'run(\d+)', file)
            BIDSrun = 'run-' + str(match.group(1))
            cmd = 'cp ' + os.path.join(meg_session_dir, file) + ' ' + os.path.join(BIDS_DIR, BIDSsubject,BIDSsession, 'meg', BIDSsubject + '_' + BIDSsession +'_' + BIDSrun + '_task_raw.fif')
            
            #duplication des fichiers .fif dans le dossier BIDS_DIR
            print(cmd)
            destination_dir = os.path.join(BIDS_DIR, BIDSsubject, BIDSsession, 'meg')
            os.makedirs(destination_dir, exist_ok=True)
            os.system(cmd)
            
print(f'Total of {i} .fif files copied to BIDS format')
            


