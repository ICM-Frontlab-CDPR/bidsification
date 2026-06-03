"""
Explore all tables in a BrainSight .bsproj SQLite database.
Goal: find MRI reference info, stored transforms, and all sample data.
"""

import argparse
import plistlib
import sqlite3
import struct

import numpy as np


def try_decode_blob(blob):
    if blob is None:
        return "(NULL)"
    if len(blob) < 4:
        return f"(bytes len={len(blob)})"
    try:
        plist_data = plistlib.loads(blob)
        objects = plist_data.get("$objects", [])
        summary = []
        for obj in objects:
            if isinstance(obj, bytes) and len(obj) == 128:
                vals = struct.unpack("<16d", obj)
                m = np.array(vals).reshape(4, 4)
                last_col = [vals[3], vals[7], vals[11]]
                summary.append(f"4x4 matrix, last_col={np.round(last_col, 3)}")
            elif isinstance(obj, (str, int, float)) and obj != "$null":
                summary.append(repr(obj))
        return " | ".join(summary[:6]) if summary else f"(plist, {len(objects)} objects)"
    except Exception:
        pass
    try:
        return blob.decode("utf-8", errors="replace")[:120]
    except Exception:
        return f"(bytes len={len(blob)})"


def main():
    parser = argparse.ArgumentParser(description="Explore BrainSight .bsproj database structure")
    parser.add_argument("--bsproj", required=True)
    args = parser.parse_args()

    con = sqlite3.connect(args.bsproj)
    cur = con.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [r[0] for r in cur.fetchall()]
    print(f"Tables: {tables}\n")

    for table in tables:
        cur.execute(f"PRAGMA table_info({table});")
        cols = cur.fetchall()
        col_names = [c[1] for c in cols]
        print(f"{'='*60}")
        print(f"TABLE: {table}  cols={col_names}")

        cur.execute(f"SELECT * FROM {table} LIMIT 5;")
        rows = cur.fetchall()
        print(f"  ({len(rows)} rows shown / max 5)")
        for row in rows:
            print()
            for col, val in zip(col_names, row):
                if isinstance(val, bytes):
                    decoded = try_decode_blob(val)
                    print(f"  {col}: {decoded}")
                else:
                    print(f"  {col}: {val}")
        print()

    # Extra: dump all ZSAMPLE rows with names
    if "ZSAMPLE" in tables:
        print("=" * 60)
        print("ALL ZSAMPLE names:")
        cur.execute("SELECT ZNAME FROM ZSAMPLE;")
        for r in cur.fetchall():
            print(f"  - {r[0]}")

    con.close()


if __name__ == "__main__":
    main()
