'''
mne bidsification of meg data
'''
import os
import argparse
import pdb
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import mne
from mne_bids import BIDSPath, write_raw_bids, write_meg_calibration, write_meg_crosstalk
from pathlib import Path
import yaml




# load config variables 
CONFIG_FILE = "_config.yaml"
try:
    with open(CONFIG_FILE, 'r') as file:
        config = yaml.safe_load(file)
        BIDS_DIR = config.get('bids_dir', '/default/bids/dir/')
        SSS_DIR = config.get('sss_dir', '/default/bids/dir/')
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

def rename_BIO_channels(raw):
    # The current version of the MNE BIDS pipeline doesn't handle BIO channels, so the best is that you rename them
    index_ECG = np.where([raw.info['ch_names'][i] == 'BIO001' for i in range(len(raw.info['ch_names']))])[0][0]
    index_E0G1 = np.where([raw.info['ch_names'][i] == 'BIO002' for i in range(len(raw.info['ch_names']))])[0][0]
    index_E0G2 = np.where([raw.info['ch_names'][i] == 'BIO003' for i in range(len(raw.info['ch_names']))])[0][0]

    raw.info['ch_names'][index_ECG] = 'ECG063'
    raw.info['ch_names'][index_E0G1] = 'E0G061'
    raw.info['ch_names'][index_E0G2] = 'E0G062'



#subjects = os.listdir(BIDS)
subjects = args.subjects
subjects = [x for x in subjects if 'sub-' in x]
subjects_dir = [BIDS_DIR + sub + '/' for sub in subjects]
posix_paths = [Path(sub_dir).rglob('*raw.fif') for sub_dir in subjects_dir]


cal_fname =  SSS_DIR + 'sss_cal_3176_20240123_2.dat' 
ct_fname = SSS_DIR + 'ct_sparse.fif'
event_id = {'cue': 5,'response': 10,'feedback': 15, 'questions':20, 'answers':25}



for posix in posix_paths:
    for file in posix:
        #path preparation
        meg_fname = str(file)
        subject = file.parts[-4].split('-')[1]  # Extrait "04" depuis "sub-04"
        session = file.parts[-3].split('-')[1]  # Extrait "4" depuis "ses-4"
        run = file.stem.split('_')[2].split('-')[1]  # Extrait "8" depuis "run-8"
        bids_path = BIDSPath(root=BIDS_DIR,subject=subject, session=session, run=run, task="EXPLORE", datatype="meg",)
        folder = bids_path.directory
        
        tsv_fname = folder / f"sub-{subject}_ses-{session}_run-{run}_task-beh_events_filtered.tsv"
        original_tsv_fname = folder / f"sub-{subject}_ses-{session}_run-{run}_task-beh_events.tsv"
        if not tsv_fname.exists():
            raise BaseException(f"Found events file: {tsv_fname}")
        
        #read needed files
        raw = mne.io.read_raw_fif(file, allow_maxshield=True)
        events_df = pd.read_csv(tsv_fname, sep='\t')
        
        
        
        ###----------------------- EVENTS from tsv_file ---------------------------###
        # events array to pass to the write_raw_bids
        required_columns = ['onset', 'duration', 'event_id',] # Vérifiez que les colonnes nécessaires existent
        if not all(col in events_df.columns for col in required_columns):
            raise ValueError(f"Le fichier {tsv_fname} ne contient pas les colonnes nécessaires : {required_columns}")
        sfreq = raw.info['sfreq']  # Convertir 'onset' en indices d'échantillons
        events_df['sample_index'] = (events_df['onset'] * sfreq).astype(int)
        events_array = events_df[['sample_index', 'event_id']].copy()
        events_array.insert(1, 'prev_trigger', 0)  # Ajout de la colonne "Previous Trigger"
        events_array.rename(columns={'event_id': 'trigger'}, inplace=True)
        events_array = events_array[['sample_index', 'prev_trigger', 'trigger',]].to_numpy()
        #-----------------------------------------------------------------------------#
        
        
        
        ###----------------------- METADATA of events from tsv_file----------------- ### 
        #TODO fill description
        description = {'arm_choice': 'Arm choice','color_choice': 'Color choice','reward': 'Reward',
                    'RT': 'Reaction time','A': 'A','B': 'B','TrialID': 'Trial ID','forced': 'Forced','outcome_SD': 'Outcome',
                    'forced': 'Forced','A_mean': 'A mean','B_mean': 'B mean','forced': 'Forced', 'onset':'onset'}
        columns_to_keep = list(description.keys())
        event_metadata = events_df.drop(columns=[col for col in events_df.columns if col not in columns_to_keep])
        #-----------------------------------------------------------------------------#
        
        
        
        #---------TEMPORARY SOLUTION TO SAVE METADATA (save in a separate file)-------#
        # TODO HOW TO KEEP THIS METADATA WHILE EPOCHING WITH MNE_BIDS_PIPELINE ? [... mne_file format to upgrade from mne1.7 to mne1.9]
        # Save the DataFrame to a .tsv file
        metadata_path = os.path.join(bids_path.directory, f"metadata_run-{bids_path.run}" + '.tsv')
        event_metadata.to_csv(metadata_path, sep='\t', index=False)
        #-----------------------------------------------------------------------------#
        
        
        
        ###------------------------ RENAME BIO CHANNELS -----------------------------###
        rename_mapping = {"BIO001": "ECG063",
                          "BIO002": "EOG061",
                          "BIO003": "EOG062",}
        mne.rename_channels(raw.info, rename_mapping)
        # raw.info['helium_info']['meas_date'] = datetime.now(timezone.utc)
        # print(type(raw.info['helium_info']['meas_date']))
        ###-----------------------------------------------------------------------------#
        
        
        
        
        ###----------- write BIDS files format and clean folder  ----------------###
        write_meg_calibration(calibration=cal_fname,
                              bids_path=bids_path,
                              )
        write_meg_crosstalk(fname=ct_fname, 
                            bids_path=bids_path, 
                            )
        write_raw_bids(raw, bids_path=bids_path, 
                       events=events_array, 
                       event_id=event_id, 
                    #    event_metadata=event_metadata, #this arg comes in v0.16 of mne_bids, a version which seems to be unsupported by mne_bids_pipeline !
                    #    extra_columns_descriptions= description,
                       overwrite=True) 
        
        ### remove tmp file used to write BIDS ### TODO after !
        # os.unlink(tsv_fname)
        # os.unlink(original_tsv_fname)
        # os.unlink(file)
        ###-----------------------------------------------------------------------------#       



