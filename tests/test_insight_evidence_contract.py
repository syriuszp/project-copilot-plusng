
import pytest
import sqlite3
import datetime
from app.db.database import init_or_upgrade_db
from app.core.insights.repository import InsightRepository
from app.core.insights.models import Insight

@pytest.fixture
def db_path(tmp_path):
    d = tmp_path / "project.db"
    cfg = {"paths": {"db_path": str(d)}}
    res = init_or_upgrade_db(cfg)
    assert res.status == "OK"
    return str(d)

def test_repo_does_not_delete_evidence_on_empty_update(db_path):
    repo = InsightRepository(db_path)
    
    # 1. Create Insight with Evidence
    chunk1 = "c1"
    insight_id = "i1"
    
    # Pre-populate chunk (FK constraint)
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO artifacts (id, path, filename, ext) VALUES (999, '/tmp/a1', 'a1.txt', '.txt')")
        conn.execute("INSERT INTO index_runs (run_id) VALUES ('r1')")
        conn.execute("INSERT INTO chunks (chunk_id, artifact_id, index_run_id, is_active, hash, chunk_type, position_index) VALUES (?, '999', 'r1', 1, 'h1', 'text', 1)", (chunk1,))
        # Populate insight manually to simulate initial state
        conn.execute("INSERT INTO insights (insight_id, index_run_id, type, statement, status, insight_fingerprint) VALUES (?, 'r1', 'unknown', 'stmt', 'open', 'fp1')", (insight_id,))
        conn.execute("INSERT INTO insight_evidence (insight_id, chunk_id) VALUES (?, ?)", (insight_id, chunk1))

    # Verify setup
    ev = repo.get_evidence(insight_id)
    assert len(ev) == 1
    
    # 2. Upsert Insight with NO Evidence
    insight = Insight(
        insight_id=insight_id,
        index_run_id='r1',
        type='unknown',
        statement='stmt',
        status='open',
        evidence_chunk_ids=[] # Empty!
    )
    repo.upsert_insight(insight)
    
    # 3. Assert Evidence Persists
    ev_after = repo.get_evidence(insight_id)
    assert len(ev_after) == 1, "Evidence should NOT be deleted when updating with empty evidence list"
