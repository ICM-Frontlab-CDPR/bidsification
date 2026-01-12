'''
This script checks the if the .fif (present in the events.tsv) and .tsv timing is coherent, remove the events from
if it is not the case. Writing a new 'filtered_events.tsv' which is then used as input to bidsification

- TODO (to finish) OPTIONAL : Try to create the missing events when possible.
'''

import os
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import re
import argparse
import yaml



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



def compare_timing(onset, behtime,filename_prefix, save_dir):
    '''2 colonnes de timings (pandas) à comparer'''
    
    if len(onset) != len(behtime):
        raise ValueError("Les colonnes 'onset' et 'behtime' doivent avoir la même longueur.")
    
    # Création du plot
    plt.figure(figsize=(8, 6))
    plt.scatter(behtime, onset, color='blue', alpha=0.7, label="Timings")
    plt.plot([min(behtime), max(behtime)], [min(behtime), max(behtime)], color='red', linestyle='--', label="y = x (aligné)")
    plt.xlabel('Behavior Time (behtime)', fontsize=12)
    plt.ylabel('Event Onset Time (onset)', fontsize=12)
    plt.title('Comparaison des Timings', fontsize=14)
    plt.legend()
    plt.grid(alpha=0.5)
    
    plot_filename = f"{filename_prefix}.png"
    plot_path = os.path.join(save_dir, plot_filename)
    plt.savefig(plot_path)  # Sauvegarde dans le dossier spécifique au sujet/session/run
    plt.close()
       
def compare_timing2(onset, behtime, filename_prefix, save_dir):
    '''Comparer les deux colonnes de timings (onset et behtime) en calculant la différence.'''
    
    if len(onset) != len(behtime):
        raise ValueError("Les colonnes 'onset' et 'behtime' doivent avoir la même longueur.")
    
    # Calcul des différences
    timing_diff = (onset - behtime )*1000
    
    # Affichage de la différence sous forme de distribution
    plt.figure(figsize=(8, 6))
    plt.hist(timing_diff, bins=range(-30, 32, 1), color='blue', alpha=0.7, edgecolor='black', 
            histtype='stepfilled', range=(-30, 30))
    plt.axvline(0, color='red', linestyle='--', label="Différence = 0")
    plt.xlabel('Différence (onset - behtime)', fontsize=12)
    plt.ylabel('Fréquence', fontsize=12)
    plt.title('Distribution des Différences entre Onset et Behtime', fontsize=14)
    plt.legend()
    plt.grid(alpha=0.5)
    
    plot_filename = f"{filename_prefix}.png"
    plot_path = os.path.join(save_dir, plot_filename)
    plt.savefig(plot_path)  # Sauvegarde dans le dossier spécifique au sujet/session/run
    plt.close()

def save_event_comparisons(tsv_event, events_df, filtered_events, compare_timing):
    # Extraire 'sub', 'ses', et 'run' du nom du fichier
    pattern = r"sub-(\d+)_ses-(\d+)_run-(\d+)"
    match = re.search(pattern, str(tsv_event))
    
    if match:
        sub = match.group(1)
        ses = match.group(2)
        run = match.group(3)
        print(f'sub-{sub} ses-{ses} run-{run}')
        
        # Créer le dossier pour sauvegarder les graphiques (si nécessaire)
        save_dir = os.path.join('saved_plots', f'sub-{sub}', f'ses-{ses}', f'run-{run}')
        
        # Crée les dossiers nécessaires (en s'assurant de ne pas créer un chemin trop long)
        os.makedirs(save_dir, exist_ok=True)
        
        # Comparer les timings pour "resp" et "feedb" et sauvegarder les graphiques
        resp_events = events_df[events_df['event_id'] == 10]
        filtered_resp_events = filtered_events[filtered_events['event_id'] == 10]
        compare_timing(resp_events['onset_diff'], resp_events['behtime_diff'], f'resp_before_{sub}_{ses}_{run}', save_dir)
        
        feedb_events = events_df[events_df['event_id'] == 15]
        filtered_feedb_events = filtered_events[filtered_events['event_id'] == 15]
        compare_timing(feedb_events['onset_diff'], feedb_events['behtime_diff'], f'feedb_before_{sub}_{ses}_{run}', save_dir)
        
        # Comparaison après filtrage
        compare_timing(filtered_resp_events['onset_diff'], filtered_resp_events['behtime_diff'], f'resp_after_{sub}_{ses}_{run}', save_dir)
        compare_timing(filtered_feedb_events['onset_diff'], filtered_feedb_events['behtime_diff'], f'feedb_after_{sub}_{ses}_{run}', save_dir)
        # compare_timing2(resp_onset_diff, resp_behtime_diff,)
        # compare_timing2(feedb_onset_diff, feedb_behtime_diff,)
    else:
        print("Le nom du fichier ne correspond pas au format attendu.")
 



def compute_behtime_diff(events_df):
    events_df.loc[events_df['event_id'] == 5, 'behtime_diff'] = (
        events_df.loc[events_df['event_id'] == 5].groupby('event_id')['cue_time'].diff()
    )
    
    events_df.loc[events_df['event_id'] == 10, 'behtime_diff'] = (
        events_df.loc[events_df['event_id'] == 10].groupby('event_id')['response_time'].diff()
    )
    events_df.loc[events_df['event_id'] == 15, 'behtime_diff'] = (
        events_df.loc[events_df['event_id'] == 15].groupby('event_id')['feedback_time'].diff()
    )
    events_df.loc[events_df['event_id'] == 20, 'behtime_diff'] = (
        events_df.loc[events_df['event_id'] == 20].groupby('event_id')['questions_time'].diff()
    )
    events_df.loc[events_df['event_id'] == 25, 'behtime_diff'] = (
        events_df.loc[events_df['event_id'] == 25].groupby('event_id')['answers_time'].diff()
    )
    
    # TODO handle the 'behtime_diff' == 0 because two times the same timing in the raw 
    
    # handle first event of each type
    events_df.loc[events_df.groupby('event_id').head(1).index, 'behtime_diff'] = 0
    
    if events_df['behtime_diff'].isna().any():
        raise NotImplementedError("Tsv_file contains rows not described in the function")
    return events_df

def compute_onset_diff(events_df):
    events_df['onset_diff'] = events_df.groupby('event_id')['onset'].diff()
    # handle first event of each type
    events_df.loc[events_df.groupby('event_id').head(1).index, 'onset_diff'] = 0
    return events_df

def remove_events(events_df):
    '''  Remove the incoherent events, BE CAREFUL no check for questions and answers type'''
    
    event_condition = events_df['event_id'].isin([5, 10, 15])
    timing_condition = abs(events_df['timing_diff']) <= 0.01
    events_df = events_df[~event_condition | (event_condition & timing_condition)]
    return events_df


if __name__ == '__main__':
    # Recherche récursive des fichiers events.tsv
    all_tsv_events = [file for file in Path(BIDS_DIR).rglob('*_events.tsv') if 'derivatives' not in file.parts]
    sub_list = args.subjects
    all_tsv_events = [file for file in all_tsv_events if any(sub in file.parts for sub in sub_list)]
    
    for tsv_event in all_tsv_events:
        events_df = pd.read_csv(tsv_event, sep='\t')
        print('Reading',tsv_event)
        
        #### inter events #### 
        # create 2 more columns for 'inter events' timings
        events_df = compute_onset_diff(events_df)
        events_df = compute_behtime_diff(events_df)
        # TODO compute cue_time 
        # TODO (+ question/anwer time ?)
        
        # Create 1 more column for 'inter events' comparison .fif et behavior
        events_df['timing_diff'] = events_df.apply(lambda row: row['behtime_diff'] - row['onset_diff'] ,axis=1)
        
        #filtering
        filtered_events = remove_events(events_df) 
       
        ### plot and save final plot events ###
        save_event_comparisons(str(tsv_event), events_df, filtered_events, compare_timing)
        
        
        base_name, ext = os.path.splitext(tsv_event)
        filtered_events.round(3).to_csv(f"{base_name}_filtered{ext}", sep='\t', index=False)
        
        
        




