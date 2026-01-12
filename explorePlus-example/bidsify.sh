#!/bin/bash


#-----THIS COMMAND NEED TO BE RUN BEFORE the bidsify.sh pipeline -----#
# ...from $BIDS_SCRIPT_DIR...
# python 0_from_excel_to_tsv.py
# ...from dir where EXPLORE wille be stored
# mkdir exp_info
# cd exp_info
# cp /neurospin/unicog/protocols/IRMf/ExplorePlus_Meyniel_Paunov_2023/explore_plus/Data/bidsification/participants_to_import.tsv .    #use BIDS_SCRIPT
## cd exp_info
# neurospin_to_bids
#---------------------------------------------------------------------#



#------------- verification de la bonne version pyenv -----------------#
if ! command -v pyenv >/dev/null; then
  echo "pyenv n'est pas activé. Activez-le avant d'exécuter ce script ou ajoutez l'activation ici."
  exit 1
else
  PYENV_VERSION=$(pyenv version-name)  # Récupère le nom de la version active

  if [ "$PYENV_VERSION" != "unicog_hippo" ]; then
    echo "Erreur : La version active de pyenv est '$PYENV_VERSION', mais 'unicog_hippo' est requise."
    exit 1
  fi

  echo "Running with pyenv version: $PYENV_VERSION"
fi
#---------------------------------------------------------------------#


#-----------------------------------------# TODO --> from config.yaml
#DEFINE HERE WHAT SUBJECT TO BIDSIFY
SUBJECTS="sub-04" #sub-20 sub-16 sub-10
# "sub-01 sub-04 sub-05 sub-06 sub-08 sub-09 sub-10 sub-11 sub-13 sub-14 sub-15 sub-16 sub-17 sub-18 sub-19 sub-20" # 


# # Input directories 
# RAW_DIR=/neurospin/unicog/protocols/IRMf/ExplorePlus_Meyniel_Paunov_2023/RAW/ #normally, should be the MEG acquisition server
# SCANDIR=/neurospin/acquisition/database/Investigational_Device_7T

# #output directories TODO --> from config.yaml
# BIDS_DIR=/neurospin/unicog/protocols/IRMf/ExplorePlus_Meyniel_Paunov_2023/EXPLORE_PLUS_BIS/rawdata/

#code directory
BIDS_SCRIPT_DIR=/neurospin/unicog/protocols/IRMf/ExplorePlus_Meyniel_Paunov_2023/explore_plus/Data/bidsification
#---------------------------------------------------------------------#


cd $BIDS_SCRIPT_DIR 

python 1_insert_behavior.py --subjects $SUBJECTS
python 1b_insert_meg_session.py --subjects $SUBJECTS

python 2_add_events_files.py --subjects $SUBJECTS
python 2b_check_events.py --subjects $SUBJECTS

python 3_bidsify_meg.py --subjects $SUBJECTS

python 4_some_adjusts.py --subjects $SUBJECTS

python 5_mri_add_events_files.py --subjects $SUBJECTS

echo "BIDSification pipeline completed (potentially with errors)"
