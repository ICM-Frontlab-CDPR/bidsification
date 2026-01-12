import mne
from mne_bids import BIDSPath, write_raw_bids, write_meg_calibration, write_meg_crosstalk
import numpy as np
import pandas as pd
import re
from pathlib import Path
import argparse
import json

#subj_NIP         = 'ap_120157'
#raw_path         = Path('/Users/anne/Documents/StAnne/protocol/BAYESIAN_BATTERY/data/' + subj_NIP)
#base_path        = '/Users/anne/Documents/StAnne/protocol/BAYESIAN_BATTERY/data'
#log_path         = '/Users/anne/Documents/StAnne/protocol/BAYESIAN_BATTERY/data/log_BayesianBattery.tsv'
#empty_room_path  = '/Users/anne/Documents/StAnne/protocol/BAYESIAN_BATTERY/data/empty_room/'

#calibration_path = '/Users/anne/Documents/StAnne/protocol/BAYESIAN_BATTERY/data/config_files'
#cal_filename     = calibration_path + '/sss_cal_nsp_2017.dat'
#ct_filename      = calibration_path + '/ct_sparse_nsp_2017.fif'



def inspect_raw_to_find_bad_channels_by_eye2(path_raw_file, verbose=False):
    # Open the raw object
    raw        = mne.io.read_raw_fif(path_raw_file, allow_maxshield=True, preload=True, verbose=verbose)
    raw_filter = raw.copy().notch_filter(freqs=[50, 100, 150])

     # 2 - Plot the PSD to note outliers
    raw_filter.compute_psd().plot()

    # 1 - Plot the raw object for the given subjet / run.
    raw_filter.plot(n_channels=30, block = True)

    
    return raw


def extract_additional_info(log_path, subj_NIP, empty_room_path, path_raw_file):
    log_data = pd.read_csv(log_path, sep='\t') 
    ind_sub = log_data.index[log_data['subj NIP'] == subj_NIP].tolist()
    subj_num_pre = log_data['participant_id'][ind_sub]
    subj_num = subj_num_pre.values[0]

    empty_room_filename_pre = log_data['empty_room'][ind_sub]
    empty_room_filename = Path(empty_room_path + str(empty_room_filename_pre.values[0]) + '.fif')
    raw_empty = mne.io.read_raw_fif(empty_room_filename, allow_maxshield=True, preload=True, verbose=False)

    match = re.search(r'run', path_raw_file)
    if match:
        task_name = 'bayesianbattery'
    else:
        task_name = 'localizer'
        run = '01'
        
    if task_name == 'bayesianbattery':
        match = re.search(r'run(\d+)\.fif', path_raw_file)
        if match:
            run_number = match.group(1)
            print(f"Run number: {run_number}")
            run = str('0' + run_number)
        else:
            print("Run number not found.")
    
        list_behav_pre = log_data['list'][ind_sub]
        list_behav = [int(x) for x in list_behav_pre.values[0].strip('[]').split()]
    
    return subj_num, raw_empty, run, task_name


def load_meg_events(subj_NIP, task_name, run):
    
    if task_name == 'bayesianbattery':
        run_events = run[1]       
        events_dic_file = Path('/Users/anne/Documents/StAnne/protocol/BAYESIAN_BATTERY/data/' + subj_NIP + '/events_dictionary_run' + run_events + '.json')
        events_array_file = Path('/Users/anne/Documents/StAnne/protocol/BAYESIAN_BATTERY/data/' + subj_NIP + '/events_of_interest_run' + run_events + '.npy')

    elif task_name == 'localizer':
        events_dic_file = Path('/Users/anne/Documents/StAnne/protocol/BAYESIAN_BATTERY/data/' + subj_NIP + '/events_dictionary_loc.json')
        events_array_file = Path('/Users/anne/Documents/StAnne/protocol/BAYESIAN_BATTERY/data/' + subj_NIP + '/events_of_interest_loc.npy')

    with open(events_dic_file, "r") as json_file:
      event_ids_dict = json.load(json_file)
      
    events_of_interest = np.load(events_array_file)
    
    return events_of_interest, event_ids_dict


def prepare_data_for_mne_bids_pipeline(base_path, subj_num, task_name, run, raw, events_of_interest, event_ids_dict, raw_empty, cal_filename, ct_filename):

    """
    Prepare and convert MEG data to BIDS format for MNE-BIDS pipeline processing.

    Parameters:
    -----------
    subject : str, optional
        Subject identifier (default is '02').

    base_path : str, optional
        Base path where project data is stored (default is "/Users/fosca/Documents/Fosca/INSERM/Projets/ReplaySeq/").

    triux : bool, optional
        Flag to indicate if BIO channels need to be renamed for Triux system (default is True).

    task_name : str, optional
        Task name for the experiment (default is 'reproduction').

    Returns:
    --------
    None
        This function does not return any value. It processes the data and writes it in BIDS format.

    Notes:
    ------
    The function performs the following steps:
    1. Extracts events and event IDs from the raw data.
    2. Creates a BIDS path for each run.
    3. Writes the raw data and event information to the BIDS format.
    4. Writes MEG calibration and crosstalk files.

    Example:
    --------
    prepare_data_for_mne_bids_pipeline(subject='01', base_path="/path/to/project", triux=False, task_name='memory')
    """

    root = base_path + '/BIDS/'

    bids_path = BIDSPath(subject=subj_num[4:6], task=task_name, run=run, datatype='meg', root=root)
    write_raw_bids(raw, bids_path=bids_path, events=events_of_interest , event_id = event_ids_dict, empty_room =raw_empty,allow_preload=True, format='FIF', overwrite=True) 

    write_meg_calibration(calibration=cal_filename, bids_path=bids_path)
    write_meg_crosstalk(fname=ct_filename, bids_path=bids_path)
    
    
def my_function(subj_NIP):
    
    raw_path         = Path('/Users/anne/Documents/StAnne/protocol/BAYESIAN_BATTERY/data/' + subj_NIP)
    base_path        = '/Users/anne/Documents/StAnne/protocol/BAYESIAN_BATTERY/data'
    log_path         = '/Users/anne/Documents/StAnne/protocol/BAYESIAN_BATTERY/data/log_BayesianBattery.tsv'
    empty_room_path  = '/Users/anne/Documents/StAnne/protocol/BAYESIAN_BATTERY/data/empty_room/'
    behav_path       = Path('/Users/anne/Documents/StAnne/protocol/BAYESIAN_BATTERY/data/' + subj_NIP + '/behav/')

    calibration_path = '/Users/anne/Documents/StAnne/protocol/BAYESIAN_BATTERY/data/config_files'
    cal_filename     = calibration_path + '/sss_cal_nsp_2017.dat'
    ct_filename      = calibration_path + '/ct_sparse_nsp_2017.fif'
    
    

    fif_files = list(raw_path.rglob('*.fif'))  # Use .glob('*.fif') to avoid searching subdirectories

    for ifile in range(len(fif_files)):
    
        raw_file = str(fif_files[ifile])

        raw = inspect_raw_to_find_bad_channels_by_eye2(raw_file, verbose=False) 
    
        input("Press Enter to continue once bad channels are marked...")
    
        subj_num, raw_empty, run, task_name = extract_additional_info(log_path, subj_NIP, empty_room_path, raw_file)
        
        
        events_of_interest, event_ids_dict = load_meg_events(subj_NIP, task_name, run)       
        
        prepare_data_for_mne_bids_pipeline(base_path, subj_num, task_name, run, raw, events_of_interest, event_ids_dict, raw_empty, cal_filename, ct_filename)
        
        print('\n\n Run ' + run + ' of the task ' + task_name + ' has been bidsified \n\n')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the script with a number as input.")
    parser.add_argument("text", type=str, help="Subject NIP")
    
    args = parser.parse_args()
    my_function(args.text)

