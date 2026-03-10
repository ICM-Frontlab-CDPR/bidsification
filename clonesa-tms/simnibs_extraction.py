#!/usr/bin/env python3
"""
Extract TMS coil positions from Brainsight .bsproj files using SimNIBS
"""

import sys
from pathlib import Path
from simnibs import sim_struct, brainsight


# Path to .bsproj file
bsproj_path = '/Volumes/levy/raw/valerocabre/clonesa/Data/ClonesaTMS/brainsight-TMS/CLONESA_002_0001/Clonesa_G2_001.bsproj'

print(f"Reading Brainsight project: {bsproj_path}")
print("="*80)

# Read the Brainsight project using SimNIBS
data = simnibs.brainsight.read(bsproj_path)

# Display the data structure
print(f"\nData type: {type(data)}")
print(f"\nData attributes: {dir(data)}")

# Try to display the data
print("\n=== Data content ===")
print(data)

# Save to file
output_file = Path('brainsight_simnibs_output.txt')
with open(output_file, 'w') as f:
    f.write(f"Brainsight file: {bsproj_path}\n")
    f.write("="*80 + "\n\n")
    f.write(f"Data type: {type(data)}\n\n")
    f.write(f"Data attributes: {dir(data)}\n\n")
    f.write("Data content:\n")
    f.write(str(data))

print(f"\n✓ Output saved to: {output_file}")
