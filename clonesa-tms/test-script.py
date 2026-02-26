import sqlite3
import plistlib
import struct

# Connexion à la base
db = sqlite3.connect('/Volumes/levy/raw/valerocabre/clonesa/Data/ClonesaTMS/brainsight-TMS/CLONESA_002_0001/Clonesa_G2_001.bsproj')
cur = db.cursor()

# Récupérer un sample
cur.execute('SELECT ZNAME, ZPOSITION, ZTARGETPOSITION FROM ZSAMPLE WHERE ZNAME = "Sample 5" LIMIT 1;')
row = cur.fetchone()

if row:
    name, zposition, ztargetposition = row
    print(f"Sample: {name}\n")
    
    # Parser ZPOSITION
    if zposition:
        print("=== ZPOSITION (position du coil) ===")
        plist_data = plistlib.loads(zposition)
        
        # Décoder transformData
        transform_data = plist_data['$objects'][2]
        values = struct.unpack('<16d', transform_data)
        
        print("Matrice 4x4:")
        for i in range(4):
            row_vals = values[i*4:(i+1)*4]
            print(f"  [{row_vals[0]:10.4f} {row_vals[1]:10.4f} {row_vals[2]:10.4f} {row_vals[3]:10.4f}]")
        
        # Position (dernière colonne)
        position = [values[3], values[7], values[11]]
        print(f"\nPosition coil (x, y, z): [{position[0]:.4f}, {position[1]:.4f}, {position[2]:.4f}]")
        
        # Rotation 3x3
        print(f"\nRotation 3x3:")
        for i in range(3):
            row_vals = [values[i*4], values[i*4+1], values[i*4+2]]
            print(f"  [{row_vals[0]:10.6f} {row_vals[1]:10.6f} {row_vals[2]:10.6f}]")

db.close()
