#!/bin/bash

src_base="/network/iss/levy/raw/valerocabre/HEMIANOTACS_new/1_DATAS/1_RAW_DATAS/1_UPDATED_DATAS"
dst_base="/network/iss/levy/raw/valerocabre/HEMIANOTACS_WIP/test"

# # Remove destination directory if it exists to start fresh
# if [ -d "$dst_base" ]; then
#     rm -rf "$dst_base"
#     echo "Removed existing destination directory: $dst_base"
# fi

# Copy patient files
find "$src_base" -maxdepth 1 -type d -name "*0013*" | while read -r patient_dir; do
    for subfolder in "1_VISUAL FIELD" "2_EEG"; do
        src="$patient_dir/$subfolder"
        if [ -d "$src" ]; then
            dst="$dst_base/$(basename "$patient_dir")/$subfolder"
            mkdir -pv "$(dirname "$dst")"
            cp -rv "$src" "$dst"
        fi
    done
done

# Copy patient files
find "$src_base" -maxdepth 1 -type d -name "*0022*" | while read -r patient_dir; do
    for subfolder in "1_VISUAL FIELD" "2_EEG"; do
        src="$patient_dir/$subfolder"
        if [ -d "$src" ]; then
            dst="$dst_base/$(basename "$patient_dir")/$subfolder"
            mkdir -pv "$(dirname "$dst")"
            cp -rv "$src" "$dst"
        fi
    done
done

# # Copy control files
# find "$src_base" -maxdepth 1 -type d -name "*HEALTHY*" | while read -r control_dir; do
#     for subfolder in "1_VISUAL FIELD" "2_EEG"; do
#         src="$control_dir/$subfolder"
#         if [ -d "$src" ]; then
#             dst="$dst_base/$(basename "$control_dir")/$subfolder"
#             mkdir -pv "$(dirname "$dst")"
#             cp -rv "$src" "$dst"
#         fi
#     done
# done

# Rename directories in one pass (deepest first to avoid path conflicts)
find "$dst_base" -depth -type d | while read -r dir; do
    dirname=$(basename "$dir")
    parent_dir=$(dirname "$dir")
    
    # Apply all transformations in one step
    newname=$(echo "$dirname" | sed 's/[()]//g' | sed 's/ \+/_/g' | tr '/' '-' | tr '.' '-' | sed 's/[^a-zA-Z0-9_-]/-/g')
    
    # Remove dashes that are adjacent to underscores
    newname=$(echo "$newname" | sed 's/_-/_/g' | sed 's/-_/_/g')

    # Remove redundant consecutive dashes and underscores
    newname=$(echo "$newname" | sed 's/-\+/-/g' | sed 's/_\+/_/g')
    
    # Remove leading and trailing dashes and underscores
    newname=$(echo "$newname" | sed 's/^[-_]\+//' | sed 's/[-_]\+$//')
    
    if [ "$dirname" != "$newname" ]; then
        mv -v "$dir" "$parent_dir/$newname"
        # echo "Renaming '$dir' to '$parent_dir/$newname'"
    fi
done

# Rename files
find "$dst_base" -type f -not -name ".*" | while read -r file; do
    filename=$(basename "$file")
    parent_dir=$(dirname "$file")
    
    # Extract extension and base name
    extension="${filename##*.}"
    basename_only="${filename%.*}"
    
    # If there's no extension (no period in filename), treat whole name as basename
    if [ "$extension" = "$filename" ]; then
        extension=""
        basename_only="$filename"
    fi
    
    # Clean the basename (remove parentheses, convert spaces, replace other special chars including periods)
    clean_basename=$(echo "$basename_only" | sed 's/[()]//g' | sed 's/ \+/_/g' | sed 's/[^a-zA-Z0-9_-]/-/g')
    
    # Remove dashes that are adjacent to underscores
    clean_basename=$(echo "$clean_basename" | sed 's/_-/_/g' | sed 's/-_/_/g')

    # Remove redundant consecutive dashes and underscores
    clean_basename=$(echo "$clean_basename" | sed 's/-\+/-/g' | sed 's/_\+/_/g')
    
    # Remove leading and trailing dashes and underscores from basename
    clean_basename=$(echo "$clean_basename" | sed 's/^[-_]\+//' | sed 's/[-_]\+$//')
    
    # Reconstruct filename
    if [ -n "$extension" ]; then
        newname="${clean_basename}.${extension}"
    else
        newname="$clean_basename"
    fi
    
    if [ "$filename" != "$newname" ]; then
        mv -v "$file" "$parent_dir/$newname"
        # echo "Renaming '$file' to '$parent_dir/$newname'"
    fi
done