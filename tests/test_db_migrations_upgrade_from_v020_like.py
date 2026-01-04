
import sqlite3
import pytest
from pathlib import Path
from app.db.migrator import init_or_upgrade_db

@pytest.mark.migration
def test_upgrade_from_v020_like(tmp_path):
    """
    Simulates upgrade from a v0.2.0-like database:
    - artifacts table exists but with old schema (source_uri, content_hash).
    - NO unique constraint on path/source_uri.
    - Missing columns (ingest_status, etc).
    """
    db_path = tmp_path / "v020.db"
    migrations_dir = Path("db/migrations") # We use real migrations from repo
    
    # 1. Create "Old" Schema
    with sqlite3.connect(str(db_path)) as conn:
        # P0 Requirement: artifacts PK could be artifact_id OR id. Let's use 'id' as typical legacy.
        # No UNIQUE on source_uri.
        conn.execute("""
            CREATE TABLE artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_uri TEXT,
                content_hash TEXT,
                created_at TEXT
            )
        """)
        # Insert some data, including potential duplicates to test migration robustness
        conn.execute("INSERT INTO artifacts (source_uri, content_hash, created_at) VALUES ('/path/1', 'hash1', '2023-01-01')")
        conn.execute("INSERT INTO artifacts (source_uri, content_hash, created_at) VALUES ('/path/1', 'hash2', '2023-01-02')") # Duplicate path
        conn.execute("INSERT INTO artifacts (source_uri, content_hash, created_at) VALUES ('/path/2', 'hash3', '2023-01-03')")
        
        # Partially created other tables or missing? "Minimal old schema"
        # Let's say artifact_text doesn't exist or is old.
        
    # 2. Run Upgrade
    # This should trigger ensure_schema -> detect legacy -> rebuild
    init_or_upgrade_db(db_path, migrations_dir)
    
    # 3. Verify Final State
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        
        # A. Columns Existence (`artifacts`)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(artifacts)")}
        assert "path" in cols
        assert "filename" in cols
        assert "ingest_status" in cols
        assert "id" in cols # PK
        
        # B. Data Migration & Deduplication
        rows = conn.execute("SELECT path, sha256 FROM artifacts ORDER BY path").fetchall()
        # Should have /path/1 (1 record) and /path/2 (1 record)
        assert len(rows) == 2
        path_map = {r["path"]: r["sha256"] for r in rows}
        
        assert "/path/1" in path_map
        assert path_map["/path/1"] == "hash2" # Should keep latest (hash2)
        assert "/path/2" in path_map
        
        # C. UNIQUE Constraint Verification (Strict Assertion)
        # Search explicitly for an index that covers ONLY 'path' and is UNIQUE
        has_unique_path = False
        indices = conn.execute("PRAGMA index_list(artifacts)").fetchall()
        for idx in indices: # (seq, name, unique, origin, partial)
            is_unique = idx[2] == 1
            if is_unique:
                # Check columns
                idx_name = idx[1]
                idx_cols = [c[2] for c in conn.execute(f"PRAGMA index_info('{idx_name}')")]
                if idx_cols == ["path"]:
                    has_unique_path = True
                    break
        
        assert has_unique_path, "Must have a UNIQUE index specifically on 'path'"
        
        # D. Real UPSERT Verification (The "Acid Test")
        # Try proper ON CONFLICT usage
        try:
            conn.execute("""
                INSERT INTO artifacts (path, filename) VALUES ('/path/1', 'new_name.txt')
                ON CONFLICT(path) DO UPDATE SET filename=excluded.filename
            """)
            # Verify update happened
            row = conn.execute("SELECT filename FROM artifacts WHERE path='/path/1'").fetchone()
            assert row["filename"] == "new_name.txt"
        except Exception as e:
            pytest.fail(f"UPSERT on path failed, implies missing UNIQUE constraint: {e}")

        # E. Artifact Text ID/FK Check (Bonus)
        # Check artifact_text exists
        t_cols = {r[1] for r in conn.execute("PRAGMA table_info(artifact_text)")}
        assert "artifact_id" in t_cols
        
        # Check FK? SQLite pragma foreign_key_list
        fks = conn.execute("PRAGMA foreign_key_list(artifact_text)").fetchall()
        # (id, seq, table, from, to, on_update, on_delete, match)
        # We expect table='artifacts', from='artifact_id', to='id'
        has_fk = any(fk[2] == "artifacts" and fk[3] == "artifact_id" and fk[4] == "id" for fk in fks)
        assert has_fk, "artifact_text missing FK to artifacts(id)"

