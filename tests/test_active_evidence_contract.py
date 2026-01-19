import pytest
import sqlite3
from app.core.insights.repository import InsightRepository
from app.core.insights.models import Insight

@pytest.fixture
def repo(tmp_path):
    # File DB for correct connection sharing
    db_path = tmp_path / "test_active.db"
    conn = sqlite3.connect(db_path)
    # Minimal Schema for this contract test
    conn.execute("CREATE TABLE chunks (chunk_id TEXT PRIMARY KEY, artifact_id TEXT, is_active INTEGER, content_text TEXT, hash TEXT, index_run_id TEXT, position_index INTEGER, section TEXT)")
    conn.execute("CREATE TABLE insight_evidence (insight_id TEXT, chunk_id TEXT)")
    conn.execute("""
        CREATE TABLE insights (
            insight_id TEXT PRIMARY KEY, index_run_id TEXT, type TEXT, statement TEXT, status TEXT, confidence REAL, updated_at TIMESTAMP, created_at TIMESTAMP,
            insight_key TEXT, status_origin TEXT, detection_rule_id TEXT, first_detected_at TIMESTAMP, last_confirmed_at TIMESTAMP, superseded_by_insight_id TEXT, status_comment TEXT, previous_status TEXT, section_hint TEXT, detection_pattern TEXT,
            insight_fingerprint TEXT, status_updated_at TIMESTAMP
        )
    """)
    conn.commit()
    return InsightRepository(str(db_path))

def test_current_insights_show_multiple_artifacts_even_if_runs_different(repo):
    """
    Scenario A: 
    Run 1 -> Artifact A (Insight A)
    Run 2 -> Artifact B (Insight B)
    Both must be visible in "Current" view.
    """
    conn = repo._get_conn()
    
    # Setup Data
    # Run 1: Chunk A1 (Active), Insight I-A
    conn.execute("INSERT INTO chunks (chunk_id, artifact_id, is_active) VALUES ('c_a1', 'art_A', 1)")
    conn.execute("INSERT INTO insights (insight_id, index_run_id, type, statement, status, confidence, updated_at) VALUES ('i_A', 'run_1', 'unknown', 'Unknown A', 'open', 1.0, 100)")
    conn.execute("INSERT INTO insight_evidence VALUES ('i_A', 'c_a1')")
    
    # Run 2: Chunk B1 (Active), Insight I-B
    conn.execute("INSERT INTO chunks (chunk_id, artifact_id, is_active) VALUES ('c_b1', 'art_B', 1)")
    conn.execute("INSERT INTO insights (insight_id, index_run_id, type, statement, status, confidence, updated_at) VALUES ('i_B', 'run_2', 'unknown', 'Unknown B', 'open', 1.0, 200)")
    conn.execute("INSERT INTO insight_evidence VALUES ('i_B', 'c_b1')")
    conn.commit()
    conn.close()
    
    # Act
    rows = repo.list_insights(types=['unknown'], require_active_evidence=True)
    
    # Assert
    assert len(rows) == 2, "Should return insights from both artifacts regardless of run ID"
    statements = {r['statement'] for r in rows}
    assert "Unknown A" in statements
    assert "Unknown B" in statements


def test_current_view_is_stable_after_single_file_update(repo):
    """
    Scenario B:
    Initial: A and B have insights.
    Update A with NEW RUN.
    Result: A (updated run) and B (old run) both visible.
    """
    conn = repo._get_conn()
    
    # Initial: A (run1), B (run1)
    conn.execute("INSERT INTO chunks (chunk_id, artifact_id, is_active) VALUES ('c_a1_old', 'art_A', 0)") # Set old to inactive later
    conn.execute("INSERT INTO chunks (chunk_id, artifact_id, is_active) VALUES ('c_b1', 'art_B', 1)")
    conn.execute("INSERT INTO insights (insight_id, index_run_id, type, statement, status, confidence, updated_at) VALUES ('i_B', 'run_1', 'unknown', 'Unknown B', 'open', 1.0, 100)")
    conn.execute("INSERT INTO insight_evidence VALUES ('i_B', 'c_b1')")
    conn.commit()
    
    # Update A: Run 2. Old chunk becomes inactive (done by repo logic usually). New chunk active.
    # New Insight for A linked to new chunk.
    conn.execute("INSERT INTO chunks (chunk_id, artifact_id, is_active) VALUES ('c_a2', 'art_A', 1)")
    conn.execute("INSERT INTO insights (insight_id, index_run_id, type, statement, status, confidence, updated_at) VALUES ('i_A_v2', 'run_2', 'unknown', 'Unknown A v2', 'open', 1.0, 200)")
    conn.execute("INSERT INTO insight_evidence VALUES ('i_A_v2', 'c_a2')")
    conn.commit()
    conn.close()

    # Act
    rows = repo.list_insights(types=['unknown'], require_active_evidence=True)
    
    # Assert
    assert len(rows) == 2
    statements = {r['statement'] for r in rows}
    assert "Unknown B" in statements, "B should persist from old run"
    assert "Unknown A v2" in statements, "A should show new version"


def test_stale_chunks_do_not_leak_into_current_insights(repo):
    """
    Scenario C:
    A has insight.
    Reindex A -> No insight markers found.
    Old chunks set to is_active=0.
    Insight should disappear.
    """
    conn = repo._get_conn()
    
    # Initial: Chunk A1 (Active), Insight A
    conn.execute("INSERT INTO chunks (chunk_id, artifact_id, is_active) VALUES ('c_a1', 'art_A', 1)")
    conn.execute("INSERT INTO insights (insight_id, index_run_id, type, statement) VALUES ('i_A', 'run_1', 'unknown', 'Should Vanish')")
    conn.execute("INSERT INTO insight_evidence VALUES ('i_A', 'c_a1')")
    conn.commit()
    
    # Verify initial visibility
    rows_initial = repo.list_insights(require_active_evidence=True)
    assert len(rows_initial) == 1
    
    # Act: Reindex (simulated). 
    # 1. Update old chunk to is_active=0
    conn.execute("UPDATE chunks SET is_active=0 WHERE chunk_id='c_a1'")
    # 2. Insert new chunk A2 (is_active=1) but NO insight linked to it
    conn.execute("INSERT INTO chunks (chunk_id, artifact_id, is_active) VALUES ('c_a2', 'art_A', 1)")
    conn.commit()
    conn.close()
    
    # Verify
    rows_final = repo.list_insights(require_active_evidence= True)
    assert len(rows_final) == 0, "Insight linked only to inactive chunk should be hidden"
