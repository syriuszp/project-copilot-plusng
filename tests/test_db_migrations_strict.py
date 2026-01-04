
import sqlite3
import pytest
from pathlib import Path
from app.db.migrator import ensure_schema, init_or_upgrade_db

def test_upgrade_from_legacy_duplicate_paths(tmp_path):
    # This tests the critical logic: Handling duplicates when enforcing UNIQUE(path)
    db_path = tmp_path / "legacy_dupes.db"
    
    # 1. Setup Legacy DB with Duplicates (simulating state before constraint)
    # 001 schema allowed dups if (source_uri, content_hash) differed, or if app logic was loose.
    # Let's create a table that mimics 001 but without unique enforcement or just loose data.
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("CREATE TABLE artifacts (id INTEGER PRIMARY KEY, source_uri TEXT, content_hash TEXT, created_at TEXT)")
        conn.execute("INSERT INTO artifacts (source_uri, content_hash, created_at) VALUES ('/dup', 'hash1', '2023-01-01')")
        conn.execute("INSERT INTO artifacts (source_uri, content_hash, created_at) VALUES ('/dup', 'hash2', '2023-01-02')") # Duplicate path, different hash/time
        conn.execute("INSERT INTO artifacts (source_uri, content_hash, created_at) VALUES ('/unique', 'hash3', '2023-01-03')")
        
    # 2. Upgrade
    # Should collapse /dup to '2023-01-02' (Max created_at/hash?)
    # Logic uses MAX(sha) and MAX(pk) etc.
    with sqlite3.connect(str(db_path)) as conn:
        ensure_schema(conn)
        
    # 3. Verify
    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute("SELECT path, sha256 FROM artifacts ORDER BY path").fetchall()
        print(f"DEBUG Rows: {rows}")
        
        assert len(rows) == 2 # /dup + /unique
        assert rows[0][0] == "/dup"
        assert rows[0][1] == "hash2" # Should keep hash2 (hash2 > hash1 alphabetically, or max logic)
        
        # Verify Constraint
        try:
            conn.execute("INSERT INTO artifacts (path) VALUES ('/unique')")
            assert False, "Should raise IntegrityError due to UNIQUE(path)"
        except sqlite3.IntegrityError:
            pass

def test_fresh_003_install(tmp_path):
    # Verify clean install uses 003 sql effectively
    db_path = tmp_path / "fresh.db"
    migrations_dir = Path("db/migrations") # Real path
    
    init_or_upgrade_db(db_path, migrations_dir)
    
    with sqlite3.connect(str(db_path)) as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(artifacts)")}
        assert "path" in cols
        assert "ingest_status" in cols
        
        # Verify Unique Index exists
        indices = conn.execute("PRAGMA index_list(artifacts)").fetchall()
        print(indices)
        has_unique = any(i[2] == 1 for i in indices)
        assert has_unique, "Fresh install must have UNIQUE index"
        
        # Verify PK is id
        pk_info = [c for c in conn.execute("PRAGMA table_info(artifacts)") if c[5] == 1]
        assert pk_info[0][1] == "id"
