import os
import numpy as np
import nibabel as nib
from nilearn import plotting #,image
import matplotlib.pyplot as plt

print("Loading T1 image...")
t1_path = "/Users/hippolyte.dreyfus/Desktop/_clonesa/clonesaTMS/bids_mri/sub-0001/anat/sub-0001_T1w.nii.gz"
t1_img = nib.load(t1_path)
print("T1 image loaded.")

output_folder = "/Users/hippolyte.dreyfus/Desktop/_clonesa/clonesaTMS/extracted_targets/sub-0001"

print("Retrieving sphere files...")
sphere_files = sorted([f for f in os.listdir(output_folder) if f.endswith('.nii') or f.endswith('.nii.gz')])
sphere_paths = [os.path.join(output_folder, f) for f in sphere_files]
n_spheres = len(sphere_paths)
print(f"Found {n_spheres} sphere(s).")

cmap = plt.cm.coolwarm
colors = [cmap(i / (n_spheres - 1)) for i in range(n_spheres)]

print("Creating figure...")
fig, axes = plt.subplots(n_spheres, 1, figsize=(10, 4 * n_spheres))
if n_spheres == 1:
    axes = [axes]

for i, (sphere_path, color) in enumerate(zip(sphere_paths, colors)):
    print(f"Plotting sphere {i + 1}/{n_spheres}: {sphere_files[i]}...")
    sphere_img = nib.load(sphere_path)
    display = plotting.plot_roi(
        sphere_img,
        bg_img=t1_img,
        axes=axes[i],
        title=sphere_files[i],
        cmap=plt.cm.colors.ListedColormap([color]),
        alpha=0.7
    )
    print(f"Sphere {i + 1}/{n_spheres} plotted.")

print("Saving figure...")
plt.tight_layout()
plt.savefig(os.path.join(output_folder, "spheres_overlay.png"), dpi=150)
print(f"Figure saved to {os.path.join(output_folder, 'spheres_overlay.png')}.")
plotting.show()
print("Done.")
