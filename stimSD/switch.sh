python convention_switch.py /network/iss/levy/valerocabre/stimSD/Data/derivatives/mri/freesurfer \
  --dest /network/iss/levy/valerocabre/stimSD/Data/derivatives/mri/freesurfer-eCRF \
  --from CENIR_ID \
  --to eCRF \
  --xlsx /network/iss/levy/valerocabre/stimSD/Data/STIM-SD_unification.xlsx \
  --on-ambiguous interactive 

# python convention_switch.py /network/iss/levy/valerocabre/stimSD/Data/derivatives/mri/2-simnibs-simu-right \
#   --dest /network/iss/levy/valerocabre/stimSD/Data/derivatives/mri/2-simnibs-simu-right-eCRF \
#   --from CENIR_ID \
#   --to eCRF \
#   --xlsx /network/iss/levy/valerocabre/stimSD/Data/STIM-SD_unification.xlsx \
#   --on-ambiguous interactive \


# python convention_switch.py /network/iss/levy/valerocabre/stimSD/Data/derivatives/mri/2-simnibs-simu-left \
#   --dest /network/iss/levy/valerocabre/stimSD/Data/derivatives/mri/2-simnibs-simu-left-eCRF \
#   --from CENIR_ID \
#   --to eCRF \
#   --xlsx /network/iss/levy/valerocabre/stimSD/Data/STIM-SD_unification.xlsx \
#   --on-ambiguous interactive \
#   --dry-run


# python convention_switch.py /chemin/dossier_source \
#   --dest /chemin/dossier_converti \
#   --from Excel \
#   --to sub_eCRF_BIDS \
#   --dry-run


# python convention_switch.py /network/iss/levy/valerocabre/stimSD/Data/derivatives/mri/1-simnibs-preps \
#     --from CENIR_ID \
#     --mode copy \
#     --to eCRF \
#     --dest /network/iss/levy/valerocabre/stimSD/Data/derivatives/mri/1-simnibs-preps-eCRF \
#     --xlsx /network/iss/levy/valerocabre/stimSD/Data/STIM-SD_unification.xlsx \
#     --on-ambiguous interactive

# python convention_switch.py /network/iss/levy/valerocabre/stimSD/Data/derivatives/mri/3-simnibs-analyze-right-atlas \
#     --from CENIR_ID \
#     --mode copy \
#     --to eCRF \
#     --dest /network/iss/levy/valerocabre/stimSD/Data/derivatives/mri/3-simnibs-analyze-right-atlas-eCRF \
#     --xlsx /network/iss/levy/valerocabre/stimSD/Data/STIM-SD_unification.xlsx \
#     --on-ambiguous interactive
#
 # --dry-run \












# python convention_switch.py /data/study --from CENIR --to eCRF --dry-run
# python convention_switch.py /data/study --from CENIR --to eCRF --mode inplace


#eCRF, eCRF_ID, sub_eCRF_BIDS, Excel, Excel_ID, CENIR, CENIR_ID