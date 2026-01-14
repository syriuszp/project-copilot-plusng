import pytest
import sqlite3
from app.core.insights.repository import InsightRepository

@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "test_status.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE chunks (chunk_id TEXT, artifact_id TEXT, is_active INTEGER, content_text TEXT)")
    conn.execute("CREATE TABLE insights (insight_id TEXT PRIMARY KEY, index_run_id TEXT, type TEXT, statement TEXT, status TEXT, confidence REAL, updated_at TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, insight_fingerprint TEXT)")
    conn.execute("CREATE TABLE insight_evidence (insight_id TEXT, chunk_id TEXT, PRIMARY KEY(insight_id, chunk_id))")
    conn.close()
    return InsightRepository(str(db_path))

def test_list_insights_filters_by_status(repo):
    """
    Scenario:
    2 insights: one open, one closed.
    Repo filter should return only one.
    """
    conn = repo._get_conn()
    conn.execute("INSERT INTO chunks VALUES ('c1', 'a1', 1, 'txt')")
    
    conn.execute("INSERT INTO insights (insight_id, status, type, statement) VALUES ('i1', 'open', 'decision', 'Open One')")
    conn.execute("INSERT INTO insight_evidence VALUES ('i1', 'c1')")
    
    conn.execute("INSERT INTO insights (insight_id, status, type, statement) VALUES ('i2', 'closed', 'decision', 'Closed One')")
    conn.execute("INSERT INTO insight_evidence VALUES ('i2', 'c1')")
    
    conn.commit()
    conn.close()
    
    # Act: Filter 'open'
    rows_open = repo.list_insights(status='open')
    assert len(rows_open) == 1
    assert rows_open[0]['statement'] == 'Open One'
    
    # Act: Filter 'closed'
    rows_closed = repo.list_insights(status='closed')
    assert len(rows_closed) == 1
    assert rows_closed[0]['statement'] == 'Closed One'
    
    # Act: No filter
    rows_all = repo.list_insights()
    assert len(rows_all) == 2
