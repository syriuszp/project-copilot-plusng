
import logging
import sys
import sqlite3
import os
import pathlib

# Setup Logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

from app.core.artifacts_repo import ArtifactsRepo

def debug_diagnostics():
    db_path = "dev_data/db/project_copilot.dev.db"
    
    # 0. Manual Drop FTS (to ensure clean slate for test)
    print("--- 0. Dropping FTS Table Manual ---")
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE IF EXISTS artifact_fts")
        
    # 1. Init Repo (Should auto-create FTS)
    print("--- 1. Init Repo ---")
    repo = ArtifactsRepo(db_path)
    print(f"FTS Enabled: {repo.fts_enabled}")
    
    # Verify FTS schema
    with sqlite3.connect(db_path) as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(artifact_fts)")]
        print(f"FTS Columns: {cols}")
        if "ref_id" not in cols:
            print("CRITICAL: ref_id MISSING after Init!")
        else:
            print("OK: ref_id present.")

    # 2. Test Upsert (Size Check)
    filename = "02+PCs+(GJ1).doc.txt"
    filepath = str(pathlib.Path(f"dev_data/ingest/{filename}").resolve())
    
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    stats = os.stat(filepath)
    meta = {
        "path": filepath,
        "filename": filename,
        "ext": ".txt",
        "size_bytes": stats.st_size,
        "modified_at": stats.st_mtime,
        "sha256": "debug_hash"
    }
    
    print(f"--- 2. Upserting {filename} ---")
    print(f"Input Meta: Size={meta['size_bytes']}, Time={meta['modified_at']}")
    
    artifact_id = repo.upsert_artifact(meta)
    print(f"Upserted ID: {artifact_id}")
    
    # 3. Verify Record
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
        print("DB Record:")
        print(f"  ID: {row['id']}")
        print(f"  Size: {row['size_bytes']} (Type: {type(row['size_bytes'])})")
        print(f"  Time: {row['modified_at']}")
        
        if row['size_bytes'] != meta['size_bytes']:
            print(f"CRITICAL FAIL: Size mismatch! DB={row['size_bytes']} vs Input={meta['size_bytes']}")
        else:
            print("OK: Size matches.")

if __name__ == "__main__":
    debug_diagnostics()
