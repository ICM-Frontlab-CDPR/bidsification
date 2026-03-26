# BIDSification Script Examples

## Goal

This repository contains **example scripts** to convert and organize neuroscience datasets into the **BIDS format**.

It also includes a brief description of an LLM-based approach in [LLM-BIDS](LLM-BIDS).

Reference: https://bids.neuroimaging.io/index.html

The objective is to produce a valid, shareable dataset structure that is easier to analyze, reproduce, and publish.

### Example BIDS dataset structure

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

## Validation

Always validate your output with a BIDS validator.

- Online validator: https://bids-standard.github.io/bids-validator/
- CLI validator: https://www.npmjs.com/package/bids-validator

## Typical workflow (standard scripted process)

1. Reorganize raw data by participant/session.
2. Convert modality-specific files (EEG/MEG/MRI/behavior) to BIDS-compliant names and sidecars.
3. Generate/update metadata files (`participants.tsv`, `dataset_description.json`, JSON sidecars, events/channels files).
4. Run the BIDS validator and fix reported issues.

## Useful tools

- `mne-bids`
- `pybids`
- BIDS Validator (online or CLI)

## Minimal pre-commit setup

This repository includes a minimal hook configuration in [.pre-commit-config.yaml](.pre-commit-config.yaml).

Quick setup:

1. Install pre-commit.
2. Run `pre-commit install` in the repository.
3. (Optional) Run `pre-commit run --all-files` once.

Current hooks:

- trailing whitespace removal
- end-of-file fixer
- YAML validation
- large file check

## License

This repository is released under a **non-commercial** license:
[LICENSE](LICENSE) (CC BY-NC 4.0).

## Notes

- This repository is intended as a **collection of practical examples**, not a single packaged pipeline.
- Scripts may differ between projects (EEG, MEG, MRI, behavior) and should be adapted to your dataset.
- The LLM-based approach is exploratory and should be treated as assistive, not fully autonomous.
