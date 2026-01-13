
import pytest
import sqlite3
import datetime
from app.db.database import init_or_upgrade_db
from app.core.insights.repository import InsightRepository

@pytest.fixture
def db_path(tmp_path):
    d = tmp_path / "project.db"
    cfg = {"paths": {"db_path": str(d)}}
    res = init_or_upgrade_db(cfg)
    assert res.status == "OK"
    return str(d)

def test_ignorance_map_only_latest_run(db_path):
    repo = InsightRepository(db_path)
    
    # 1. Setup Data: Two Runs
    run1 = "run_old_1"
    run2 = "run_new_2"
    
    t1 = (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat()
    t2 = datetime.datetime.now().isoformat()
    
    with sqlite3.connect(db_path) as conn:
        # Create Index Runs
        # Table: index_runs(run_id PK, started_at TEXT, ...) (from 001_initial)
        conn.execute("INSERT INTO index_runs (run_id, started_at) VALUES (?, ?)", (run1, t1))
        conn.execute("INSERT INTO index_runs (run_id, started_at) VALUES (?, ?)", (run2, t2))
        
        # Create Insights
        # Run 1 Insights
        conn.execute("""
            INSERT INTO insights (insight_id, index_run_id, type, statement, status, confidence, insight_fingerprint)
            VALUES ('i1', ?, 'unknown', 'Old Insight', 'open', 1.0, 'fp1')
        """, (run1,))
        
        # Run 2 Insights
        conn.execute("""
            INSERT INTO insights (insight_id, index_run_id, type, statement, status, confidence, insight_fingerprint)
            VALUES ('i2', ?, 'unknown', 'New Insight', 'open', 1.0, 'fp2')
        """, (run2,))
        
    # 2. Test Default Fetch (Latest Only)
    insights = repo.list_insights(types=["unknown"])
    
    assert len(insights) == 1
    assert insights[0]["index_run_id"] == run2
    assert insights[0]["statement"] == "New Insight"
    assert insights[0]["is_latest"] is True

    # 3. Test Explicit All Fetch (if needed by Admin)
    insights_all = repo.list_insights(types=["unknown"], only_latest_run=False)
    assert len(insights_all) == 2
