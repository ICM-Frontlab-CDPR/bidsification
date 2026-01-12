'''
This script add a .tsv file of events for each run, this is use just after to select events.
'''

import os 
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import argparse
from glob import glob
import re
import mne
import warnings
warnings.warn("ANNE CHECKS BETWEEN BEHAVIOR AND MEG" )
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
    
    

def find_behavior_files(BIDS_DIR, subjects, BEH="beh", MEG="meg"):
    """
    Recherche et retourne une liste des fichiers de comportement et leurs chemins associés dans une structure BIDS.

    Arguments :
        BIDS_DIR (str) : Répertoire racine BIDS.
        subjects (list) : Liste des sujets à analyser.
        BEH (str) : Nom du sous-dossier comportemental (par défaut 'beh').
        MEG (str) : Nom du sous-dossier MEG (par défaut 'meg').

    Retourne :
        list : Liste de tuples (beh_file_dir, events_file_dir, fif_file).
    """
    results = []

    for subject in subjects:
        subject_dir = os.path.join(BIDS_DIR, subject)
        sessions = os.listdir(subject_dir)
        print('Sessions detected:', sessions)

        for session in sessions:
            beh_session_dir = os.path.join(subject_dir, session, BEH)
            meg_session_dir = os.path.join(subject_dir, session, MEG)

            if not os.path.isdir(beh_session_dir):
                print(f"Behavior session directory not found: {beh_session_dir}")
                continue

            files = os.listdir(beh_session_dir)
            behavior_files = [x for x in files if ('.tsv' in x and 'task' in x and 'events.tsv' not in x)]
            print('Behavior files detected:', behavior_files)

            for beh_file in behavior_files:
                match = re.search(r'run-(\d+)', beh_file)
                if match:
                    run = 'run-' + str(match.group(1))  # Récupère le numéro de run
                else:
                    print(f"Run not found in file name: {beh_file}")
                    continue

                events_file = beh_file.removesuffix(".tsv") + "_events.tsv"
                beh_file_dir = os.path.join(beh_session_dir, beh_file)
                events_file_dir = os.path.join(meg_session_dir, events_file)

                if not os.path.exists(beh_file_dir):
                    raise FileNotFoundError(f"Behavior file missing: {beh_file_dir}")

                if os.path.isdir(meg_session_dir):  # Detect MEG session
                    fif_file = f"{subject}_{session}_{run}_task_raw.fif"
                    meg_file_dir = os.path.join(meg_session_dir, fif_file)
                    results.append((beh_file_dir, events_file_dir, meg_file_dir))

    return results


def filter_answers_near_questions(events_quest, events_answer, max_time_diff=6.0, sfreq=1000, max_events=4, time_window=16.0):
    """
    Filtrer les événements "answer" qui se produisent à moins de `max_time_diff` secondes des événements "quest",
    et limiter à un maximum de `max_events` événements dans une fenêtre temporelle de `time_window` secondes.

    Arguments :
        events_quest : np.ndarray
            Tableau des événements de type "quest", format MNE [n_events, 3].
        events_answer : np.ndarray
            Tableau des événements de type "answer", format MNE [n_events, 3].
        max_time_diff : float
            Différence maximale de temps en secondes entre "quest" et "answer".
        sfreq : int
            Fréquence d'échantillonnage en Hz pour convertir les secondes en points temporels.
        max_events : int
            Nombre maximum d'événements "answer" autorisés dans une fenêtre temporelle donnée.
        time_window : float
            Taille de la fenêtre temporelle en secondes pour limiter le nombre d'événements.

    Retourne :
        np.ndarray : Tableau filtré des événements "answer".
    """
    max_time_diff_samples = int(max_time_diff * sfreq)  # Convertir la différence de temps en points temporels
    time_window_samples = int(time_window * sfreq)  # Convertir la fenêtre temporelle en points temporels
    filtered_answers = []
    answer_times = []  # Liste des temps des événements filtrés

    for answer_event in events_answer:
        answer_time = answer_event[0]  # Temps de l'événement "answer" en points temporels
        
        # Vérifier si un événement "quest" est proche dans le temps
        if np.any(np.abs(answer_time - events_quest[:, 0]) <= max_time_diff_samples):
            # Vérifier la densité temporelle des événements "answer"
            recent_answers = [t for t in answer_times if answer_time - t <= time_window_samples]
            if len(recent_answers) < max_events:
                filtered_answers.append(answer_event)
                answer_times.append(answer_time)  # Ajouter l'événement filtré à la liste

    return np.array(filtered_answers)


def timing_alignment(behavior_data, start_event_value):
    behavior_data['start_event_time'] = start_event_value
    behavior_data['cue_time'] = behavior_data['trial_start'] + start_event_value
    behavior_data['response_time'] = behavior_data['trial_start'] + behavior_data['RT'] + start_event_value 
    behavior_data['feedback_time'] = behavior_data['outcome_start'] + start_event_value 
    behavior_data['questions_time'] = behavior_data['startQuestion'] + start_event_value
    behavior_data['answers_time'] = behavior_data['startQuestion'] + start_event_value 
    return behavior_data


def match_metadata(events, beh_data, col_event, tolerance = 500):
    events_times = events['onset']
    # Boucle sur les événements de type RESPONSE
    metadata = pd.DataFrame()
    for time in events_times:
        # Trouver l'indice du temps le plus proche dans feedb_behavior_time
        closest_row = beh_data.iloc[(time - beh_data[col_event]).abs().idxmin()] # Trouver la ligne avec la plus petite différence temporelle
        closest_row = closest_row.to_frame().T
        # mise à jour du dataframe metadata 
        metadata = pd.concat([metadata, closest_row], ignore_index=True)
    
    # ajout des metadonnées
    events = pd.concat([events, metadata], axis=1)
    return events





def check_events_number(events, event_id_map):
    """
    Vérifie la présence et le nombre d'événements pour chaque type spécifié.
    
    Args:
        events (numpy.ndarray): Tableau contenant les événements (onset, durée, event_id).
        event_id_map (dict): Dictionnaire mappant les noms d'événements aux IDs d'événements.

    Returns:
        dict: Dictionnaire où les clés sont les types d'événements et les valeurs sont des booléens.
    """
    event_presence = {}

    # Vérification des événements par type
    for event_name, event_id in event_id_map.items():
        # Filtrer les événements correspondant à l'event_id
        event_subset = events[events[:, 2] == event_id]
        count = len(event_subset)
        print(f"{event_name}: {count} occurrences trouvées.")
        
        # Déterminer les critères de validation
        if event_name in ['cue', 'response', 'feedback']:
            event_presence[event_name] = (count >= 80)
        elif event_name in ['questions', 'answers']:
            event_presence[event_name] = (count >= 15)
        elif event_name in ['start',]:
            event_presence[event_name] = (count == 1)
        else:
            raise ValueError(f"Type d'événement non pris en charge : {event_name}")
        
        print(f"{event_name}: {'Validé' if event_presence[event_name] else 'Non validé'}")

    return event_presence

#TODO adjust : this function MUST not use the behavior file... because the behavior data will be use to check !
def create_missing_events(event_name,beh_data, event_id_map):
    # récuperer les timings à utiliser depuis le dataframe behavior_data (use timing_from_csv function)
    # alignement dans le même réferentiel (use timing alignment function)
    statistical_delay = 0
    if event_name == 'cue':
        beh_timing = beh_data['cue_time'] + statistical_delay
    elif event_name == 'feedback':
        beh_timing = beh_data['feedback_time'] + statistical_delay
    else:
        raise "event_name probleme"
    # utilisation de beh_timing pour recréer les events 
    idx = event_id_map[event_name]
    events = np.vstack([beh_timing.values, np.zeros_like(beh_timing.values), np.full_like(beh_timing.values, idx)]).T
    return events
    


if '__main__' == __name__ :
    #recherche des sujet déjà présents dans BIDS_DIR
    # subjects = os.listdir(BIDS_DIR)
    subjects = args.subjects
    subjects = [x for x in subjects if 'sub-' in x] 
    results = find_behavior_files(BIDS_DIR,subjects)
    print('subjects detected', subjects)


    for beh_file_dir, events_file_dir, meg_file_dir in results:
        print(f"Reading {meg_file_dir}")
        raw = mne.io.read_raw_fif(meg_file_dir, preload=True, allow_maxshield=True, verbose='ERROR')
        behavior_data = pd.read_csv(beh_file_dir, sep='\t') # warning, there is some comma in the file. sep='\t' is not optional !
        
        
        # EVENTS DETECTION
        print('Finding events...')
        # make a dictionnary with all triggers
        event_id = {'start':1,'cue': 5,'response': 10,'feedback': 15, 'questions':20, 'answers':25}
        # declare channels for TTL detection
        start_chan = 'STI006'
        cue_chan = 'STI001'
        resp_chan = 'STI002'
        feedb_chan = 'STI003'
        iti_chan = 'STI004'
        
        quest_chan = ['STI005']
        answer_chan = ['STI009','STI010','STI012','STI013']
        
        #find events
        events_start = mne.find_events(raw, stim_channel=start_chan, shortest_event=1,verbose='WARNING')
        events_start[:,2]= event_id['start']
        events_start = events_start[:,:] # here we do not remove the first event, which is the only one !
        
        events_cue  = mne.find_events(raw, stim_channel=cue_chan, shortest_event=1,verbose='WARNING')
        events_cue[:,2]= event_id['cue']
        events_cue = events_cue[1:,:]
        events_resp  = mne.find_events(raw, stim_channel=resp_chan, shortest_event=1,verbose='WARNING')
        events_resp[:,2]= event_id['response']
        events_resp = events_resp[1:,:]
        events_feedb = mne.find_events(raw, stim_channel=feedb_chan, shortest_event=1,verbose='WARNING')
        events_feedb[:,2]= event_id['feedback']
        events_feedb = events_feedb[1:,:]
        
        events_quest  = mne.find_events(raw, stim_channel=quest_chan, shortest_event=1, verbose='WARNING')
        events_quest[:,2]= event_id['questions']
        events_quest = events_quest[1:,:]
        events_answ  = mne.find_events(raw, stim_channel=answer_chan, shortest_event=1,verbose='WARNING')
        events_answ[:,2]= event_id['answers']
        events_answ = events_answ[1:,:]
        #filter answers
        # print(events_feedb) # TODO check timing between plot event_detection !
        # print(len(events_feedb))
        events_answ = filter_answers_near_questions(events_quest, events_answ)
        
        # check events detection (events numbers, dependant of event type) 
        tmp_events = np.concatenate((events_start, events_cue, events_resp, events_feedb, events_quest, events_answ,), axis=0)
        is_well_detected = check_events_number(tmp_events,event_id)
        
        # alignement des temps MEG (pc meg) avec les temps behavior (pc behavior)
        behavior_data = timing_alignment(behavior_data, events_start[0, 0]) 
        
        
        ###### HANDLE BAD DETECTION ######
        #plot events if issue detected
        if all(is_well_detected.values()):
            print("Tous les événements ont été bien détectés.")
        else:
            # Filtrer event_id pour inclure uniquement les ids présents
            available_event_ids = set(tmp_events[:, 2])
            filtered_event_id = {key: val for key, val in event_id.items() if val in available_event_ids} 
            fig = mne.viz.plot_events(tmp_events, event_id=filtered_event_id, sfreq=raw.info['sfreq'])
            #user = input("yes to try detecting with behavior file")
            user = 'yes'
        
            # # create events if necessary
            if user == 'yes':
                for event_name, value in is_well_detected.items():
                    if not value:
                        print('\n EVENT',event_name)
                        if event_name == 'cue':
                            events_cue = create_missing_events(event_name, behavior_data,event_id)
                            print('recreate cue')
                        elif event_name == 'feedback':
                            events_feedb = create_missing_events(event_name, behavior_data, event_id)
                            print('recreate feedback')
                        else :
                            raise "not handle"
                    
        
        
        ##### AJOUT DES INFORMATIONS EN PROVENANCE DU TSV ######
        # et reformatage des timing du .csv et du .fif pour comparaison
        
        #conversion events to dataframe
        events_cue = pd.DataFrame(events_cue, columns=["onset", "duration", "event_id"])
        events_resp = pd.DataFrame(events_resp, columns=["onset", "duration", "event_id"])
        events_feedb = pd.DataFrame(events_feedb, columns=["onset", "duration", "event_id"])
        events_quest = pd.DataFrame(events_quest, columns=["onset", "duration", "event_id"])
        events_answ = pd.DataFrame(events_answ, columns=["onset", "duration", "event_id"])
        
        #add the related metadata to each events
        events_cue = match_metadata(events_cue,behavior_data, col_event='cue_time')
        events_resp = match_metadata(events_resp,behavior_data, col_event='response_time')
        events_feedb = match_metadata(events_feedb,behavior_data, col_event='feedback_time')
        events_quest = match_metadata(events_quest,behavior_data, col_event='questions_time')
        events_answ = match_metadata(events_answ,behavior_data, col_event='answers_time')
        
        
        ### Concaténation final           
        events = pd.concat((events_cue,events_resp,events_feedb,events_quest,events_answ),axis=0)
        
        SEC = 1000 # for ms to s conversion
        events['start_event_time'] = events['start_event_time'] / SEC
        events['onset'] = events['onset'] / SEC
        events['cue_time'] = events['cue_time'] / SEC
        events['feedback_time'] = events['feedback_time'] / SEC
        events['response_time'] = events['response_time'] / SEC
        events['questions_time'] = events['questions_time'] / SEC
        events['answers_time'] = events['answers_time'] / SEC

        col_to_save = ["onset",	"duration",	"event_id",	"TrialID",	"arm_choice",	"color_choice",	"reward",	
                    "trial_start",	"RT",	"A",	"B",	"outcome_SD",	"forced",	"A_mean",	"B_mean",]
        col_to_save = col_to_save + ["start_event_time", "cue_time", "response_time","feedback_time", "questions_time", "answers_time"]
        events = events[col_to_save]
        
        
        events.to_csv(events_file_dir, sep='\t', index=False)     
        print(f"Saved events file to {events_file_dir}")
        print('\n\n')

                        
                        


                    