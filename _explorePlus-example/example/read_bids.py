from mne_bids import BIDSPath, write_raw_bids, read_raw_bids
import mne
import pandas as pd

bids_path = BIDSPath(subject='05', session='01', task='testing',
                     acquisition=None, run='01', datatype='meg',
                     root='/home/hippolytedreyfus/Documents/BIDS/')

raw = read_raw_bids(bids_path)

print(raw.annotations)

events, event_id = mne.events_from_annotations(raw)
print(events)  # Affiche le tableau des événements (sample, 0, event_id)
print(event_id)  # Affiche les noms et identifiants des événements













