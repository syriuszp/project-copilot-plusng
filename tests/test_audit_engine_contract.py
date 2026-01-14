import pytest
import sqlite3
from app.core.insights.engine import InsightEngine
from app.core.insights.repository import InsightRepository

@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "test_contract.db"
    conn = sqlite3.connect(db_path)
    # Schema matching production usage for this test
    conn.execute("CREATE TABLE chunks (chunk_id TEXT, artifact_id TEXT, is_active INTEGER, content_text TEXT, hash TEXT, index_run_id TEXT)")
    conn.execute("CREATE TABLE insights (insight_id TEXT PRIMARY KEY, index_run_id TEXT, type TEXT, statement TEXT, status TEXT, confidence REAL, updated_at TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, insight_fingerprint TEXT)")
    conn.execute("CREATE TABLE insight_evidence (insight_id TEXT, chunk_id TEXT, PRIMARY KEY(insight_id, chunk_id))")
    conn.close()
    return InsightRepository(str(db_path))

def test_multi_artifact_ignorance_visibility(repo):
    """
    Scenario:
    Two artifacts A and B both have TBD.
    Indexed in different runs (simulated by inserting chunks with different runs).
    Engine run (run 3) should see BOTH and generate insights for BOTH.
    """
    conn = repo._get_conn()
    # A (run 1)
    conn.execute("INSERT INTO chunks (chunk_id, artifact_id, is_active, content_text, index_run_id, hash) VALUES ('c_a', 'art_A', 1, 'TBD: A', 'run_1', 'hA')")
    # B (run 2)
    conn.execute("INSERT INTO chunks (chunk_id, artifact_id, is_active, content_text, index_run_id, hash) VALUES ('c_b', 'art_B', 1, 'TBD: B', 'run_2', 'hB')")
    conn.commit()
    conn.close()
    
    engine = InsightEngine(repo.db_path, repo)
    # Run the engine as part of 'run_3' (global sweep)
    engine.run('run_3')
    
    rows = repo.list_insights(types=['unknown'], require_active_evidence=True)
    assert len(rows) == 2, "Both A and B should be detected"
    stmts = {r['statement'] for r in rows}
    assert "TBD: A" in stmts
    assert "TBD: B" in stmts

def test_stability_contract_update_one_does_not_kill_other(repo):
    """
    Scenario:
    Initial: A and B exist (active).
    Update: A is updated (new chunks, old inactive). B is untouched (remains active).
    Engine Run: Should generate insights for new A and existing B.
    """
    conn = repo._get_conn()
    
    # Initial State: A_v1 and B_v1
    conn.execute("INSERT INTO chunks (chunk_id, artifact_id, is_active, content_text, index_run_id, hash) VALUES ('c_a1', 'art_A', 1, 'TBD: A v1', 'run_1', 'hA1')")
    conn.execute("INSERT INTO chunks (chunk_id, artifact_id, is_active, content_text, index_run_id, hash) VALUES ('c_b1', 'art_B', 1, 'TBD: B v1', 'run_1', 'hB1')")
    conn.commit()
    
    # Run Engine for run 1
    engine = InsightEngine(repo.db_path, repo)
    engine.run('run_1')
    
    # Verify Initial
    rows = repo.list_insights(['unknown'])
    assert len(rows) == 2
    
    # Update State: 
    # A_v1 becomes inactive. A_v2 becomes active.
    # B_v1 remains active.
    conn.execute("UPDATE chunks SET is_active=0 WHERE chunk_id='c_a1'")
    conn.execute("INSERT INTO chunks (chunk_id, artifact_id, is_active, content_text, index_run_id, hash) VALUES ('c_a2', 'art_A', 1, 'TBD: A v2', 'run_2', 'hA2')")
    conn.commit()
    conn.close()
    
    # Run Engine for run 2 (active chunks should include A_v2 and B_v1)
    engine.run('run_2')
    
    # Verify Final
    rows = repo.list_insights(['unknown'], require_active_evidence=True)
    
    # We expect:
    # 1. TBD: A v2 (New)
    # 2. TBD: B v1 (Persisted/Re-detected)
    # 3. TBD: A v1 (Gone/Hidden)
    
    active_stmts = {r['statement'] for r in rows}
    
    assert "TBD: A v2" in active_stmts, "New version of A must be visible"
    assert "TBD: B v1" in active_stmts, "Untouched B must remain visible"
    assert "TBD: A v1" not in active_stmts, "Old version of A must be hidden"
    assert len(active_stmts) == 2
