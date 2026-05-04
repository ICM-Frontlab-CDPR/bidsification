my_bids_dataset/
│
├── README
├── dataset_description.json
├── participants.tsv
├── participants.json
│
├── sourcedata/                    # 🔒 DONNÉES ORIGINALES (hors BIDS)
│   ├── sub-01/
│   │   └── eeg/
│   │       ├── sub-01_ses-01_raw.easy
│   │       └── sub-01_ses-01_raw.info
│   │
│   └── sub-02/
│       └── eeg/
│           ├── sub-02_ses-01_raw.easy
│           └── sub-02_ses-01_raw.info
│
├── sub-01/                        # ✅ BIDS RAW (standardisé)
│   └── ses-01/
│       └── eeg/
│           ├── sub-01_ses-01_task-rest_eeg.edf
│           ├── sub-01_ses-01_task-rest_eeg.json
│           ├── sub-01_ses-01_task-rest_channels.tsv
│           ├── sub-01_ses-01_task-rest_events.tsv
│           └── sub-01_ses-01_task-rest_electrodes.tsv
│
├── sub-02/
│   └── ses-01/
│       └── eeg/
│           ├── sub-02_ses-01_task-rest_eeg.edf
│           ├── sub-02_ses-01_task-rest_eeg.json
│           ├── sub-02_ses-01_task-rest_channels.tsv
│           ├── sub-02_ses-01_task-rest_events.tsv
│           └── sub-02_ses-01_task-rest_electrodes.tsv
│
├── derivatives/                   # 📊 RÉSULTATS / TRAITEMENTS
│   ├── preprocessing/
│   │   ├── dataset_description.json
│   │   ├── sub-01/
│   │   │   └── ses-01/
│   │   │       └── eeg/
│   │   │           ├── sub-01_ses-01_task-rest_desc-clean_eeg.edf
│   │   │           └── sub-01_ses-01_task-rest_desc-clean_eeg.json
│   │   └── sub-02/
│   │       └── ses-01/
│   │           └── eeg/
│   │               ├── sub-02_ses-01_task-rest_desc-clean_eeg.edf
│   │               └── sub-02_ses-01_task-rest_desc-clean_eeg.json
│   │
│   └── analysis/
│       ├── dataset_description.json
│       └── sub-01/
│           └── eeg/
│               ├── sub-01_task-rest_desc-psd_eeg.tsv
│               └── sub-01_task-rest_desc-psd_eeg.json
│
└── code/                          # 🧠 SCRIPTS (optionnel)
    ├── convert_to_bids.py
    └── preprocessing_pipeline.py
