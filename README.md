

Obejctif : 

Avoir un dataset au format BIDS tel que decrit par : https://bids.neuroimaging.io/index.html 

Ceci per;mettqnt detre publiees...

Voici un apercu de la structure de donnees

dataset/
├── dataset_description.json
├── participants.tsv
├── participants.json
├── sub-01/
│   └── ses-01/
│       └── eeg/
│           ├── sub-01_ses-01_task-rest_run-01_eeg.vhdr
│           ├── sub-01_ses-01_task-rest_run-01_eeg.json
│           ├── sub-01_ses-01_task-rest_run-01_channels.tsv
│           ├── sub-01_ses-01_task-rest_run-01_events.tsv
│           └── sub-01_ses-01_task-rest_run-01_electrodes.tsv



Checker gr6ace au BIDS validator (plusieurs outils sont utilisables selon votre maniere de trqvailler) :

- online :
- CLI :


**Process general - Main steps**

1/ chqnger lq structure par participant

2/ 

3/

Bids-validator



**Les outils a utiliser:**

- mne-bids !
