import csv

CSV_PATH = "/Users/hippolyte.dreyfus/Documents/simnibs-modular/config-files/hemianotacs/participants-info.csv"
BASE = "/network/iss/levy/raw/valerocabre/hemianotACS/Data/derivatives/mri/lesion-synthstroke-masks-SS"

rows = []
with open(CSV_PATH, newline="") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        if row["group"] == "patient":
            sub_id = row["participant_id"]
            row["lesion_mask_path"] = f"{BASE}/{sub_id}/T1_brain_lesion.nii.gz"
        rows.append(row)

with open(CSV_PATH, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print("Done. Updated lesion_mask_path for:")
for row in rows:
    if row["group"] == "patient":
        print(f"  {row['participant_id']} -> {row['lesion_mask_path']}")
