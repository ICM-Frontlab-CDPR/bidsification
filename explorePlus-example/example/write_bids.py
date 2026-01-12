from mne_bids import BIDSPath, write_raw_bids
import mne
import pandas as pd


print('hey')
raw = mne.io.read_raw_fif('/home/hippolytedreyfus/Documents/rawdata/sub-01_ses-4_run-1_EXPLORE_task_meg.fif', allow_maxshield=True)
event_id = {'response': 10, 'feedback': 15}
events_tsv = "/home/hippolytedreyfus/Documents/rawdata/sub-01_ses-4_run-1_task-beh_events.tsv"
events_df = pd.read_csv(events_tsv, sep='\t')


### EVENTS from tsv_file ###
required_columns = ['onset', 'duration', 'event_id'] # Vérifiez que les colonnes nécessaires existent
if not all(col in events_df.columns for col in required_columns):
    raise ValueError(f"Le fichier {events_tsv} ne contient pas les colonnes nécessaires : {required_columns}")

sfreq = raw.info['sfreq']  # Convertir 'onset' en indices d'échantillons
events_df['sample_index'] = (events_df['onset'] * sfreq).astype(int)

events_array = events_df[['sample_index', 'event_id']].copy()
events_array.insert(1, 'prev_trigger', 0)  # Ajout de la colonne "Previous Trigger"
events_array.rename(columns={'event_id': 'trigger'}, inplace=True)
events_array = events_array[['sample_index', 'prev_trigger', 'trigger']].to_numpy()
print(events_array)

### METADATA of events from tsv_file ###
event_metadata = events_df.drop(columns=required_columns + ['sample_index'])
#description for this arm_choice	color_choice	reward	trial_start	RT	A	B	outcome_SD	forced	A_mean	B_mean
description = {'arm_choice': 'Arm choice',
                'color_choice': 'Color choice',
                'reward': 'Reward',
                'trial_start': 'Trial start',
                'RT': 'Reaction time',
                'A': 'A',
                'B': 'B',
                'TrialID': 'Trial ID',
                'forced': 'Forced',
                'outcome_SD': 'Outcome',
                'forced': 'Forced',
                'A_mean': 'A mean',
                'B_mean': 'B mean',
                'forced': 'Forced',
                }
                



bids_path = BIDSPath(subject='05', session='01', task='testing',
                     acquisition=None, run='01', datatype='meg',
                     root='/home/hippolytedreyfus/Documents/BIDS/')
write_raw_bids(raw, bids_path, events=events_array, event_id=event_id, event_metadata=event_metadata, extra_columns_descriptions=description, overwrite=True)









