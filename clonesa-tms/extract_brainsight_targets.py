#!/usr/bin/env python3
"""
Script to extract TMS coil position information from Brainsight .bsproj files.
The .bsproj file is a SQLite database with serialized Apple plist binary data.
"""

import sqlite3
import plistlib
import struct
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import sys

try:
    import numpy as np
except ImportError:
    np = None


class BrainsightExtractor:
    """Extract target and coil information from Brainsight .bsproj files."""
    
    def __init__(self, bsproj_path: str):
        """
        Initialize the extractor.
        
        Args:
            bsproj_path: Path to the .bsproj file (SQLite database)
        """
        self.bsproj_path = Path(bsproj_path)
        if not self.bsproj_path.exists():
            raise FileNotFoundError(f"File not found: {bsproj_path}")
        
        self.conn = sqlite3.connect(self.bsproj_path)
        self.cursor = self.conn.cursor()
    
    def _parse_position_data(self, blob_data: bytes) -> Optional[list]:
        """
        Parse binary position data (plist format) to list [x, y, z].
        
        Args:
            blob_data: Binary data from database
            
        Returns:
            Position as [x, y, z] list or None if parsing fails
        """
        try:
            # Try to parse as plist
            if blob_data is None or len(blob_data) == 0:
                return None
                
            plist_data = plistlib.loads(blob_data)
            
            # The plist should contain position information
            # Usually in the format: [x, y, z] or similar structure
            if isinstance(plist_data, dict):
                # Sometimes it's nested in a dict
                for key in ['position', 'POSITION', 'loc', 'LOC', 'Location']:
                    if key in plist_data:
                        position = plist_data[key]
                        if isinstance(position, (list, tuple)) and len(position) >= 3:
                            return [float(position[0]), float(position[1]), float(position[2])]
                
                # Try direct keys for x, y, z
                if all(k in plist_data for k in ['x', 'y', 'z']):
                    return [float(plist_data['x']), float(plist_data['y']), float(plist_data['z'])]
                
                # Try to find any numeric arrays
                for val in plist_data.values():
                    if isinstance(val, (list, tuple)) and len(val) >= 3:
                        try:
                            return [float(val[0]), float(val[1]), float(val[2])]
                        except (ValueError, TypeError):
                            continue
            
            elif isinstance(plist_data, (list, tuple)) and len(plist_data) >= 3:
                return [float(plist_data[0]), float(plist_data[1]), float(plist_data[2])]
            
            return None
        
        except Exception as e:
            print(f"Warning: Could not parse position data: {e}", file=sys.stderr)
            return None
    
    def _parse_transform_data(self, blob_data: bytes) -> Optional[list]:
        """
        Parse binary transform/rotation matrix data (plist format).
        
        Args:
            blob_data: Binary data from database
            
        Returns:
            3x3 rotation matrix as 2D list or None if parsing fails
        """
        try:
            if blob_data is None or len(blob_data) == 0:
                return None
            
            plist_data = plistlib.loads(blob_data)
            
            # Look for matrix-like structures
            if isinstance(plist_data, dict):
                # Check for rotation matrix keys (m0n0, m0n1, etc.)
                matrix_keys = []
                for i in range(3):
                    for j in range(3):
                        key = f'm{i}n{j}'
                        if key in plist_data:
                            matrix_keys.append((i, j, plist_data[key]))
                
                if matrix_keys:
                    if np is not None:
                        matrix = np.zeros((3, 3))
                        for i, j, val in matrix_keys:
                            matrix[i, j] = float(val)
                        return matrix.tolist()
                    else:
                        matrix = [[0.0]*3 for _ in range(3)]
                        for i, j, val in matrix_keys:
                            matrix[i][j] = float(val)
                        return matrix
                
                # Check for 'transform' key
                if 'transform' in plist_data:
                    transform = plist_data['transform']
                    if isinstance(transform, (list, tuple)) and len(transform) == 9:
                        return [list(transform[i*3:(i+1)*3]) for i in range(3)]
            
            elif isinstance(plist_data, (list, tuple)):
                if len(plist_data) == 9:
                    return [list(plist_data[i*3:(i+1)*3]) for i in range(3)]
            
            return None
        
        except Exception as e:
            print(f"Warning: Could not parse transform data: {e}", file=sys.stderr)
            return None
    
    def extract_targets(self) -> List[Dict]:
        """
        Extract all target/coil information from the .bsproj file.
        
        Returns:
            List of target dictionaries with name, position, and transform
        """
        targets = []
        
        try:
            # Query all target nodes with their position and transform data
            query = """
            SELECT 
                ZNAME,
                ZPOSITION,
                ZTRANSFORM,
                Z_PK,
                ZTYPE,
                ZINDEXX,
                ZINDEXY
            FROM ZTARGETNODE
            WHERE ZNAME IS NOT NULL
            ORDER BY ZINDEXX ASC, ZINDEXY ASC
            """
            
            self.cursor.execute(query)
            rows = self.cursor.fetchall()
            
            for row in rows:
                name, position_blob, transform_blob, pk, target_type, index_x, index_y = row
                
                position = self._parse_position_data(position_blob)
                transform = self._parse_transform_data(transform_blob)
                
                target_info = {
                    'name': name,
                    'pk': pk,
                    'type': target_type,
                    'index_x': index_x,
                    'index_y': index_y,
                    'position': position,
                    'transform': transform,
                    'position_raw': position_blob,
                    'transform_raw': transform_blob,
                }
                
                targets.append(target_info)
        
        except sqlite3.Error as e:
            print(f"Database error: {e}", file=sys.stderr)
            return []
        
        return targets
    
    def extract_samples(self) -> List[Dict]:
        """
        Extract all sample/measurement points from the .bsproj file.
        
        Returns:
            List of sample dictionaries with position and metadata
        """
        samples = []
        
        try:
            query = """
            SELECT 
                ZNAME,
                ZPOSITION,
                ZUUID,
                ZINDEX,
                ZCREATIONDATE,
                ZSTIMULATORPOWERA,
                ZSTIMULATORPOWERB
            FROM ZSAMPLE
            WHERE ZPOSITION IS NOT NULL
            ORDER BY ZINDEX ASC
            """
            
            self.cursor.execute(query)
            rows = self.cursor.fetchall()
            
            for row in rows:
                name, position_blob, uuid, index, creation_date, power_a, power_b = row
                
                position = self._parse_position_data(position_blob)
                
                sample_info = {
                    'name': name,
                    'uuid': uuid,
                    'index': index,
                    'position': position,
                    'creation_date': creation_date,
                    'power_a': power_a,
                    'power_b': power_b,
                }
                
                samples.append(sample_info)
        
        except sqlite3.Error as e:
            print(f"Database error: {e}", file=sys.stderr)
            return []
        
        return samples
    
    def export_targets_txt(self, output_path: str) -> None:
        """
        Export targets in the same format as Brainsight's "Exported Targets.txt".
        
        Args:
            output_path: Path to save the exported targets file
        """
        targets = self.extract_targets()
        samples = self.extract_samples()
        
        # Use samples if no targets found
        if not targets and samples:
            targets = samples
        
        if not targets:
            print("Warning: No targets found to export", file=sys.stderr)
            return
        
        with open(output_path, 'w') as f:
            # Write header
            f.write("# Version: 1.0 (Extracted from Brainsight)\n")
            f.write("# Coordinate system: MNI\n")
            f.write("# Units: millimetres, degrees\n")
            f.write("# Encoding: UTF-8\n")
            f.write("# Notes: Extracted from .bsproj file\n")
            f.write("# Target Name\tLoc. X\tLoc. Y\tLoc. Z\t")
            
            # Add matrix headers if transforms are available
            has_transforms = any(t.get('transform') is not None for t in targets)
            if has_transforms:
                for i in range(3):
                    for j in range(3):
                        f.write(f"m{i}n{j}")
                        if not (i == 2 and j == 2):
                            f.write("\t")
            f.write("\n")
            
            # Write targets
            for target in targets:
                if target['position'] is None:
                    continue
                
                f.write(f"{target['name']}\t")
                
                # Write position
                pos = target['position']
                for i, coord in enumerate(pos):
                    f.write(f"{coord:.9f}")
                    if not (i == 2 and not has_transforms):
                        f.write("\t")
                
                # Write transform matrix if available
                if has_transforms:
                    if target['transform'] is not None:
                        matrix = target['transform']
                        for i in range(3):
                            for j in range(3):
                                f.write(f"{matrix[i][j]:.9f}")
                                if not (i == 2 and j == 2):
                                    f.write("\t")
                    else:
                        # Identity matrix if no transform
                        for i in range(3):
                            for j in range(3):
                                val = 1.0 if i == j else 0.0
                                f.write(f"{val:.9f}")
                                if not (i == 2 and j == 2):
                                    f.write("\t")
                
                f.write("\n")
        
        print(f"✓ Exported targets to: {output_path}")
    
    def export_csv(self, output_path: str) -> None:
        """
        Export targets as CSV for easier parsing.
        
        Args:
            output_path: Path to save the CSV file
        """
        import csv
        
        targets = self.extract_targets()
        samples = self.extract_samples()
        
        # Use samples if no targets found
        if not targets and samples:
            targets = samples
        
        with open(output_path, 'w', newline='') as f:
            fieldnames = ['name', 'x', 'y', 'z', 'has_transform']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            writer.writeheader()
            for target in targets:
                if target['position'] is not None:
                    writer.writerow({
                        'name': target['name'],
                        'x': target['position'][0],
                        'y': target['position'][1],
                        'z': target['position'][2],
                        'has_transform': 'yes' if target['transform'] is not None else 'no',
                    })
        
        print(f"✓ Exported targets to CSV: {output_path}")
    
    def print_summary(self) -> None:
        """Print a summary of extracted information."""
        targets = self.extract_targets()
        samples = self.extract_samples()
        
        print(f"\n{'='*60}")
        print(f"Brainsight Project: {self.bsproj_path.name}")
        print(f"{'='*60}")
        
        print(f"\nTargets found: {len(targets)}")
        if targets:
            print("\nTargets:")
            for target in targets:
                status = "✓" if target['position'] is not None else "✗"
                print(f"  {status} {target['name']}")
                if target['position'] is not None:
                    print(f"    Position: ({target['position'][0]:.2f}, {target['position'][1]:.2f}, {target['position'][2]:.2f})")
        
        print(f"\nSamples found: {len(samples)}")
        if samples:
            samples_with_pos = [s for s in samples if s['position'] is not None]
            print(f"  - Samples with position data: {len(samples_with_pos)}")
            if samples_with_pos:
                print(f"\nFirst 5 samples:")
                for sample in samples_with_pos[:5]:
                    print(f"  ✓ {sample['name']}")
                    if sample['position']:
                        print(f"    Position: ({sample['position'][0]:.2f}, {sample['position'][1]:.2f}, {sample['position'][2]:.2f})")
                    if sample.get('power_a') or sample.get('power_b'):
                        print(f"    Power: A={sample.get('power_a', 'N/A')}, B={sample.get('power_b', 'N/A')}")
        
        print(f"{'='*60}\n")
    
    def close(self) -> None:
        """Close database connection."""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Extract TMS coil position information from Brainsight .bsproj files'
    )
    parser.add_argument('bsproj', help='Path to the .bsproj file')
    parser.add_argument(
        '--export-txt',
        help='Export targets in Brainsight format (.txt). If not specified, uses default path.'
    )
    parser.add_argument(
        '--export-csv',
        help='Export targets as CSV. If not specified, uses default path.'
    )
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Print summary of extracted data'
    )
    parser.add_argument(
        '--output-dir',
        default='.',
        help='Output directory for exported files (default: current directory)'
    )
    parser.add_argument(
        '--no-export',
        action='store_true',
        help='Only show summary, do not export anything'
    )
    
    args = parser.parse_args()
    
    try:
        extractor = BrainsightExtractor(args.bsproj)
        
        # Always print summary
        extractor.print_summary()
        
        # Export by default unless --no-export
        if not args.no_export:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            bsproj_name = Path(args.bsproj).stem
            
            # Export to default paths if not specified
            txt_path = args.export_txt or str(output_dir / f"{bsproj_name}_targets.txt")
            csv_path = args.export_csv or str(output_dir / f"{bsproj_name}_targets.csv")
            
            extractor.export_targets_txt(txt_path)
            extractor.export_csv(csv_path)
        
        extractor.close()
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
