"""
Focused exploration of BrainSight .bsproj database.
Targets: ZDATASET, ZFILEREFERENCE, ZWORLDTRANSFORM, ZATLASSPACE, ZPROJECT, ZSESSION, ZLANDMARK, ZSAMPLE
"""

import argparse
import plistlib
import sqlite3
import struct

import numpy as np


def decode_plist_blob(blob, col_name=""):
    """Decode a plist blob. Skips visual/colour fields."""
    if blob is None:
        return None
    # Skip blobs that are almost certainly colour/visual data
    skip_keywords = ("colour", "color", "lut", "texture", "icon")
    if any(k in col_name.lower() for k in skip_keywords):
        return {"(skipped colour/visual blob)": True}
    try:
        plist_data = plistlib.loads(blob)
        objects = plist_data.get("$objects", [])
        results = {}
        for i, obj in enumerate(objects):
            if isinstance(obj, bytes) and len(obj) == 128:
                # Exactly 16 doubles: treat as 4x4 matrix
                vals = struct.unpack("<16d", obj)
                m = np.array(vals).reshape(4, 4)
                results[f"matrix4x4_{i}"] = m
            elif isinstance(obj, bytes) and len(obj) in (24, 32, 40):
                # 3, 4, or 5 doubles: likely coordinates or small vectors
                n = len(obj) // 8
                vals = struct.unpack(f"<{n}d", obj)
                if all(abs(v) < 1e6 for v in vals):  # sanity check
                    results[f"vec{n}d_{i}"] = np.round(vals, 5)
            elif isinstance(obj, (str, int, float, bool)) and obj != "$null":
                results[f"val_{i}"] = obj
            elif isinstance(obj, dict):
                filtered = {k: v for k, v in obj.items()
                            if not str(k).startswith("$") and k not in ("NSColorSpace", "NSID", "NSICC")}
                if filtered:
                    results[f"dict_{i}"] = filtered
        return results
    except Exception:
        try:
            return {"text": blob.decode("utf-8", errors="replace")[:300]}
        except Exception:
            return {"hex": blob.hex()[:80]}


def print_table(con, table, limit=10):
    cur = con.cursor()
    try:
        cur.execute(f"PRAGMA table_info({table});")
    except Exception as e:
        print(f"\n[{table}] not found: {e}")
        return
    cols = [c[1] for c in cur.fetchall()]
    cur.execute(f"SELECT COUNT(*) FROM {table};")
    total = cur.fetchone()[0]
    print(f"\n{'='*60}")
    print(f"TABLE: {table}  (total={total}, showing {min(limit, total)})")
    cur.execute(f"SELECT * FROM {table} LIMIT {limit};")
    rows = cur.fetchall()
    for row in rows:
        print()
        for col, val in zip(cols, row):
            if isinstance(val, bytes):
                decoded = decode_plist_blob(val, col_name=col)
                if not decoded:
                    continue
                print(f"  {col}:")
                for k, v in decoded.items():
                    if isinstance(v, np.ndarray) and v.shape == (4, 4):
                        print(f"    {k}:")
                        for r in v:
                            print(f"      [{r[0]:10.4f} {r[1]:10.4f} {r[2]:10.4f} {r[3]:10.4f}]")
                        last_col = v[:3, 3]
                        print(f"      -> translation: {np.round(last_col, 3)}")
                    elif "(skipped" not in k:
                        print(f"    {k}: {v}")
            else:
                print(f"  {col}: {val}")


def print_sample_blobs(con, sample_name):
    """Specifically decode all blob fields of a ZSAMPLE row."""
    cur = con.cursor()
    cur.execute("PRAGMA table_info(ZSAMPLE);")
    cols = [c[1] for c in cur.fetchall()]
    cur.execute("SELECT * FROM ZSAMPLE WHERE ZNAME = ? LIMIT 1;", (sample_name,))
    row = cur.fetchone()
    if not row:
        print(f"Sample not found: {sample_name}")
        return
    print(f"\n{'='*60}")
    print(f"ZSAMPLE row: {sample_name}")
    for col, val in zip(cols, row):
        if isinstance(val, bytes):
            decoded = decode_plist_blob(val, col_name=col)
            print(f"  {col}:")
            if decoded:
                for k, v in decoded.items():
                    if isinstance(v, np.ndarray) and v.shape == (4, 4):
                        print(f"    {k}:")
                        for r in v:
                            print(f"      [{r[0]:10.4f} {r[1]:10.4f} {r[2]:10.4f} {r[3]:10.4f}]")
                        print(f"      -> translation (col3): {np.round(v[:3, 3], 4)}")
                        print(f"      -> translation (row3): {np.round(v[3, :3], 4)}")
                    else:
                        print(f"    {k}: {v}")
        else:
            print(f"  {col}: {val}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bsproj", required=True)
    parser.add_argument("--sample", default="Sample 5", help="Sample name to inspect in detail")
    args = parser.parse_args()

    con = sqlite3.connect(args.bsproj)

    # Tables most likely to contain coordinate system / file reference info
    for table in ["ZPROJECT", "ZSESSION", "ZFILEREFERENCE", "ZDATASET", "ZWORLDTRANSFORM", "ZATLASSPACE", "ZLANDMARK"]:
        print_table(con, table, limit=10)

    print_sample_blobs(con, args.sample)

    con.close()


if __name__ == "__main__":
    main()
