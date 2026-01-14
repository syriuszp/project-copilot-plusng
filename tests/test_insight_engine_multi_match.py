import pytest
import sqlite3
from app.core.insights.engine import InsightEngine
from app.core.insights.repository import InsightRepository

@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "test_insights.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE chunks (chunk_id TEXT, artifact_id TEXT, is_active INTEGER, content_text TEXT, hash TEXT, index_run_id TEXT)")
    conn.execute("CREATE TABLE insights (insight_id TEXT PRIMARY KEY, index_run_id TEXT, type TEXT, statement TEXT, status TEXT, confidence REAL, updated_at TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, insight_fingerprint TEXT)")
    conn.execute("CREATE TABLE insight_evidence (insight_id TEXT, chunk_id TEXT, PRIMARY KEY(insight_id, chunk_id))")
    conn.close()
    return InsightRepository(str(db_path))

def test_engine_extracts_multiple_markers_from_single_chunk(repo):
    """
    Scenario:
    Single chunk has 3 distinct markers.
    Expect 3 insights generated.
    """
    conn = repo._get_conn()
    chunk_text = """
    Here is some intro text.
    TODO: First item to do.
    Some filler text.
    TBD: Second item pending.
    More filler.
    TODO: Third item.
    """
    conn.execute("""
        INSERT INTO chunks (chunk_id, artifact_id, is_active, content_text, index_run_id, hash) 
        VALUES ('c1', 'a1', 1, ?, 'r1', 'h1')
    """, (chunk_text,))
    conn.commit()
    conn.close()
    
    engine = InsightEngine(repo.db_path, repo)
    engine.run('r1')
    
    # Act
    rows = repo.list_insights(types=['unknown'])
    
    # Assert
    assert len(rows) == 3, f"Expected 3 insights, got {len(rows)}"
    statements = sorted([r['statement'] for r in rows])
    assert "TBD: Second item pending." in statements[0] or "TBD: Second item pending." in statements[1] or "TBD: Second item pending." in statements[2]
    # Check simple presence
    all_txt = " ".join(statements)
    assert "First item" in all_txt
    assert "Second item" in all_txt
    assert "Third item" in all_txt
