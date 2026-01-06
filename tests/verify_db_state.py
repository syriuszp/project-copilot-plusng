
import sqlite3
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

def verify_state():
    db_path = "dev_data/db/project_copilot.dev.db"
    filename = "02+PCs+(GJ1).doc.txt"
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        
        # 1. Check Artifact Record
        row = conn.execute("SELECT * FROM artifacts WHERE filename=?", (filename,)).fetchone()
        if row:
            print(f"Artifact {filename}:")
            print(f"  ID: {row['id']}")
            print(f"  Size: {row['size_bytes']}")
            print(f"  Time: {row['modified_at']}")
            print(f"  Status: {row['ingest_status']}")
        else:
            print(f"Artifact {filename} NOT FOUND")
            
        # 2. Check FTS Columns
        print("FTS Columns:")
        try:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(artifact_fts)")]
            print(cols)
        except Exception as e:
            print(f"Error checking FTS: {e}")

if __name__ == "__main__":
    verify_state()
