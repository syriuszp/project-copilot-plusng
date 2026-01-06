
import sqlite3
import pytest
from app.db.migrator import ensure_schema
import logging

# Setup logging to capture migrator output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.db.migrator")

def test_ensure_schema_infinite_loop_bug():
    """
    Reproduction test for the infinite DB rebuild loop.
    We create a STRICT schema (valid state), call ensure_schema,
    and assert that it DOES NOT trigger a rebuild.
    Currently, due to the bug, it WILL trigger a rebuild.
    """
    conn = sqlite3.connect(":memory:")
    
    # 1. Create a VALID Strict Schema manually
    conn.execute("""
        CREATE TABLE artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL,
            filename TEXT,
            ext TEXT,
            size_bytes INTEGER,
            modified_at TEXT,
            sha256 TEXT,
            ingest_status TEXT DEFAULT 'new',
            error TEXT,
            updated_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_artifacts_path UNIQUE(path)
        )
    """)
    # Also need artifact_text to avoid non-related rebuilds
    conn.execute("""
        CREATE TABLE artifact_text (
            artifact_id INTEGER PRIMARY KEY,
            text TEXT,
            extracted_at TEXT,
            extractor TEXT,
            chars INTEGER,
            FOREIGN KEY(artifact_id) REFERENCES artifacts(id) ON DELETE CASCADE
        )
    """)
    
    # 2. Add some data
    conn.execute("INSERT INTO artifacts (path, filename) VALUES ('/tmp/test', 'test.txt')")
    
    # 3. Capture logs to see if "Strict Schema Rebuild Triggered" appears
    # Or just check rowid stability? If rebuild happens, rowid might reset if we didn't preserve it?
    # Actually, ensure_schema preserves IDs via user logic, so rowid might stay same.
    # Best way: mocking the logger or checking calls.
    # But since we want to assertion in code, let's verify column introspection logic.
    
    # Logic in code:
    # cur = conn.execute("PRAGMA table_info(artifacts)")
    # cols = set(row[1] for row in cur.fetchall())
    # has_legacy_id = "id" in cols and "artifact_id" not in cols
    # need_rebuild = ... or has_legacy_id ...
    
    cur = conn.execute("PRAGMA table_info(artifacts)")
    cols = {row[1] for row in cur.fetchall()}
    
    # Assertion of the BUG (This determines if the bug exists)
    # The current code says: "id" in cols AND "artifact_id" NOT in cols -> has_legacy_id = True.
    # Which corresponds to our VALID schema above.
    
    is_bug_present = ("id" in cols and "artifact_id" not in cols)
    print(f"Bug Present (Expect True): {is_bug_present}")
    
    # We want to Assert that ensure_schema triggers a rebuild (via log capture? or mocking?)
    # Let's mock the conn.execute to spy on "ALTER TABLE artifacts RENAME..."
    
    class SpyConn(sqlite3.Connection):
        def execute(self, sql, *args):
            if "RENAME TO artifacts_backup_legacy" in sql:
                raise RuntimeError("REBUILD_TRIGGERED")
            return super().execute(sql, *args)
            
    # Re-connect using Spy
    conn.close()
    conn = SpyConn(":memory:")
    conn.execute("""
        CREATE TABLE artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL,
            filename TEXT,
            ext TEXT,
            size_bytes INTEGER,
            modified_at TEXT,
            sha256 TEXT,
            ingest_status TEXT DEFAULT 'new',
            error TEXT,
            updated_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_artifacts_path UNIQUE(path)
        )
    """)
    # (artifact_text not strictly needed for checking artifacts rebuild triggering, but good for completeness)
    
    
    # 4. Assert that ensure_schema SUCCEEDS (does NOT trigger rebuild)
    try:
        ensure_schema(conn)
    except RuntimeError as e:
        if str(e) == "REBUILD_TRIGGERED":
             pytest.fail("ensure_schema incorrectly triggered a rebuild on a valid schema!")
        raise e

if __name__ == "__main__":
    test_ensure_schema_infinite_loop_bug()
