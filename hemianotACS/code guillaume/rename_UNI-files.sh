#!/bin/bash

# Define the directory containing the images and JSON files
image_dir="/network/iss/levy/collaborative/valerocabre/CLONESA_MRI_preproc/niix2bids_test/sub-CLONESA0010044/ses-1/anat/"

# Loop through the files in the directory
for file in "$image_dir"/*_UNIT1.{nii,json}; do
  # Check if the file exists
  if [ -e "$file" ]; then
    # Construct the new filename
    new_file="${file/_UNIT1/_T1w}"
    # Rename the file
    mv "$file" "$new_file"
  fi
done
echo "Renaming completed."

