
import sqlite3
import pytest
from pathlib import Path
from app.db.migrator import ensure_schema

def test_clean_rebuild(tmp_path):
    db_path = tmp_path / "clean.db"
    
    # 1. Setup Legacy
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("""
        CREATE TABLE artifacts (
          artifact_id INTEGER PRIMARY KEY,
          source_type TEXT NOT NULL,
          source_uri  TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(source_uri, content_hash)
        );
        """)
        conn.execute("INSERT INTO artifacts (source_type, source_uri, content_hash) VALUES ('file', '/foo', 'abc')")
        
    # 2. Run Migration
    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        
    # 3. Verify
    with sqlite3.connect(str(db_path)) as conn:
        cols = {r[1].lower() for r in conn.execute("PRAGMA table_info(artifacts)")}
        print(f"Final Cols: {cols}")
        
        assert "id" in cols
        assert "path" in cols
        assert "source_uri" not in cols
        assert "source_type" not in cols
        
        # Verify Row
        row = conn.execute("SELECT path, sha256 FROM artifacts").fetchone()
        assert row[0] == "/foo"
        assert row[1] == "abc"
        
        # Verify Unique Index
        try:
            conn.execute("INSERT INTO artifacts (path, filename, ext) VALUES ('/foo', 'f', 'x')")
            assert False, "Duplicate path should fail"
        except sqlite3.IntegrityError:
            pass
            
