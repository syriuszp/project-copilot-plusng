
import pytest
import sqlite3
import hashlib
from app.db.database import init_or_upgrade_db
from app.core.insights.engine import InsightEngine
from app.core.insights.repository import InsightRepository

@pytest.fixture
def db_path(tmp_path):
    d = tmp_path / "project.db"
    # Ensure migrations are applied (including 006)
    # We rely on the real migrations folder in the repo
    cfg = {"paths": {"db_path": str(d)}}
    res = init_or_upgrade_db(cfg)
    assert res.status == "OK"
    return str(d)

def test_reindex_does_not_duplicate_insight(db_path):
    # Setup
    repo = InsightRepository(db_path)
    engine = InsightEngine(db_path, repo)
    
    # 1. Simulate Index Run 1
    run1 = "run_111"
    chunk_hash = "abc123hash"
    artifact_id = "art_1"
    
    with sqlite3.connect(db_path) as conn:
        # Insert Chunk 1
        conn.execute("""
            INSERT INTO chunks (chunk_id, artifact_id, index_run_id, content_text, chunk_type, hash, position_index, is_active)
            VALUES (?, ?, ?, ?, 'text', ?, 0, 1)
        """, ("c1", artifact_id, run1, "This is a TBD item.", chunk_hash))
        
    engine.run(run1)
    
    insights = repo.get_insights_for_run(run1)
    assert len(insights) == 1
    i1 = insights[0]
    assert "TBD" in i1.statement
    assert i1.index_run_id == run1
    
    # Verify DB count
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT count(*) FROM insights").fetchone()[0]
        assert count == 1

    # 2. Simulate Index Run 2 (Re-index)
    # Conceptually, a re-index creates NEW chunks for the new run (or updates existing, but typically distinct rows in V3)
    # The user "chunks" table has index_run_id, implying run-specific chunks.
    run2 = "run_222"
    
    with sqlite3.connect(db_path) as conn:
        # Insert Chunk 2 (Same content/hash/artifact)
        conn.execute("""
            INSERT INTO chunks (chunk_id, artifact_id, index_run_id, content_text, chunk_type, hash, position_index, is_active)
            VALUES (?, ?, ?, ?, 'text', ?, 0, 1)
        """, ("c2", artifact_id, run2, "This is a TBD item.", chunk_hash))
        
    engine.run(run2)
    
    # 3. Assert Deduplication
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT index_run_id, insight_fingerprint FROM insights").fetchall()
        assert len(rows) == 1, f"Expected 1 insight, found {len(rows)}"
        
        row = rows[0]
        assert row[0] == run2, "Insight should be updated to latest run"
    
    # Verify repository fetch
    insights2 = repo.get_insights_for_run(run2)
    assert len(insights2) == 1
    assert insights2[0].insight_id == i1.insight_id, "Insight ID should match (if we kept the old ID logic? Wait)"
    # Update: My logic keeps the OLD insight_id if upsert works on fingerprint.
    # The implementation:
    # INSERT ... ON CONFLICT(fingerprint) DO UPDATE SET index_run_id=...
    # So the original row is kept, so original insight_id is kept.
    # But wait, I am generating a NEW insight_id in python: 
    # insight_id = hashlib.md5(f"{index_run_id}|{chunk_id}|{i_type}".encode()).hexdigest()
    # This passed insight_id is DIFFERENT for run2.
    # Does SQLite UPSERT update the PK (insight_id) if I provide a different one in INSERT VALUES?
    # NO. "DO UPDATE SET index_run_id=excluded.index_run_id..."
    # It does NOT update insight_id. 
    # So insight_id should remain the same (the one from Run1).
    # BUT, the passed insight_id was ignored.
    
    assert insights2[0].insight_id == i1.insight_id
