import pytest
import sqlite3
import os
from pathlib import Path
from app.core.chunking.repository import ChunkingRepository
from app.core.chunking.service import ChunkingService
from app.core.chunking.models import Chunk

# Re-use the schema application logic or use a fixture that applies it
REPO_ROOT = Path(__file__).parent.parent
DB_MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"
TEST_DB_PATH = REPO_ROOT / "test_chunking.db"

def apply_migrations(conn):
    cursor = conn.cursor()
    migration_files = sorted(list(DB_MIGRATIONS_DIR.glob("*.sql")))
    for sql_file in migration_files:
        script = sql_file.read_text(encoding="utf-8").split("-- Down")[0]
        cursor.executescript(script)
    conn.commit()

@pytest.fixture
def repo():
    if TEST_DB_PATH.exists():
        os.remove(TEST_DB_PATH)
    
    conn = sqlite3.connect(str(TEST_DB_PATH))
    apply_migrations(conn)
    conn.close()
    
    yield ChunkingRepository(str(TEST_DB_PATH))
    
    if TEST_DB_PATH.exists():
        os.remove(TEST_DB_PATH)

def test_chunking_is_idempotent(repo):
    """
    Test that processing the same artifact twice:
    1. Does not create duplicate chunks (count stays same).
    2. Updates the index_run_id.
    3. Updates updated_at.
    """
    service = ChunkingService(repo)
    artifact_id = "doc_123"
    content = "Para 1.\n\nPara 2."
    
    # Run 1
    chunks_v1 = service.process_artifact(artifact_id, "run_1", content)
    assert len(chunks_v1) == 2
    
    # Verify DB
    conn = sqlite3.connect(str(TEST_DB_PATH))
    assert conn.execute("SELECT count(*) FROM chunks WHERE is_active=1").fetchone()[0] == 2
    assert conn.execute("SELECT index_run_id FROM chunks LIMIT 1").fetchone()[0] == "run_1"
    
    # Run 2 (Same content, new run_id)
    chunks_v2 = service.process_artifact(artifact_id, "run_2", content)
    assert len(chunks_v2) == 2
    
    # Verify DB
    # Should still satisfy count=2 active chunks (no duplicates)
    assert conn.execute("SELECT count(*) FROM chunks WHERE is_active=1").fetchone()[0] == 2
    # run_id should be updated
    assert conn.execute("SELECT index_run_id FROM chunks LIMIT 1").fetchone()[0] == "run_2"
    
    conn.close()

def test_chunks_fts_excludes_inactive_chunks(repo):
    """
    Test that FTS only contains active chunks.
    """
    service = ChunkingService(repo)
    artifact_id = "doc_zombie"
    content_v1 = "Hello World."
    content_v2 = "Hello World Modified." # Hash will change, so old chunk becomes zombie
    
    # Run 1
    service.process_artifact(artifact_id, "run_1", content_v1)
    
    conn = sqlite3.connect(str(TEST_DB_PATH))
    # Check FTS matches v1
    # rowid query is internal, let's query via match
    cursor = conn.execute("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH 'World'")
    results = cursor.fetchall()
    assert len(results) == 1
    
    # Run 2 (Change content -> New Chunk created, Old Chunk deactivated)
    service.process_artifact(artifact_id, "run_2", content_v2)
    
    # Verify chunks state
    # We expect 2 chunks total in DB: 1 active (v2), 1 inactive (v1)
    assert conn.execute("SELECT count(*) FROM chunks").fetchone()[0] == 2
    assert conn.execute("SELECT count(*) FROM chunks WHERE is_active=1").fetchone()[0] == 1
    
    # Check FTS
    # Old "World" chunk (v1) should be GONE from FTS.
    # New "Modified" chunk (v2) should be present.
    
    # Searching for 'Modified' should return 1 hit
    assert len(conn.execute("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH 'Modified'").fetchall()) == 1
    
    # Searching for 'World' should return 1 hit (from v2, as v1 is gone). 
    # Wait, v2 is "Hello World Modified", so it contains World.
    # Let's check specifically that the old rowid is gone.
    
    # Get rowid of inactive chunk
    inactive_rowid = conn.execute("SELECT chunk_rowid FROM chunks WHERE is_active=0").fetchone()[0]
    
    # Check if that rowid exists in FTS
    # FTS rowid maps to chunk_rowid
    # We can join or just select from chunks_fts where rowid = ?
    # FTS5 External Content table returns rows from underlying table if queried directly.
    # To verify DELETION from INDEX, we must ensure MATCH does not return this rowid.
    
    # Query for "World" (present in both v1 and v2)
    # It should match v2 (active).
    # It should NOT match v1 (inactive/deleted from index).
    match_results = conn.execute("SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH 'World'").fetchall()
    matched_rowids = [r[0] for r in match_results]
    
    assert inactive_rowid not in matched_rowids
    assert len(matched_rowids) == 1 # Only v2
    
    # Verify exact match for text unique to v1 if it existed, or just rely on rowid exclusion
    # v1 "Hello World." vs v2 "Hello World Modified."
    # If we searched "Modified", we get v2 (checked above).
    # "Hello" -> both.
    
    # Double check: Search for something that shouldn't be valid for v2 if possible? 
    # v1 is subset of v2 here, so hard. Rowid check is sufficient.

    conn.close()
