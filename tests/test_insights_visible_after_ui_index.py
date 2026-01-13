
import pytest
import sqlite3
import os
import shutil
from pathlib import Path
from app.core.artifacts_repo import ArtifactsRepo
from app.core.indexing_service import IndexingService
from app.core.insights.repository import InsightRepository

# Re-use schema logic
REPO_ROOT = Path(__file__).parent.parent
DB_MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"
TEST_DB_PATH = REPO_ROOT / "test_insights_vis.db"
TEST_INGEST_DIR = REPO_ROOT / "test_ingest_vis"

def apply_migrations(conn):
    cursor = conn.cursor()
    migration_files = sorted(list(DB_MIGRATIONS_DIR.glob("*.sql")))
    for sql_file in migration_files:
        try:
            script = sql_file.read_text(encoding="utf-8").split("-- Down")[0]
            cursor.executescript(script)
        except Exception as e:
            print(f"Migration failed for {sql_file}: {e}")
            raise
    conn.commit()

@pytest.fixture
def env_setup():
    # Setup DB
    if TEST_DB_PATH.exists():
        os.remove(TEST_DB_PATH)
    
    conn = sqlite3.connect(str(TEST_DB_PATH))
    apply_migrations(conn)
    conn.close()

    # Setup Dir
    if TEST_INGEST_DIR.exists():
        shutil.rmtree(TEST_INGEST_DIR)
    os.makedirs(TEST_INGEST_DIR)
    
    yield
    
    # Cleanup
    if TEST_DB_PATH.exists():
        try:
            os.remove(TEST_DB_PATH)
        except:
            pass
    if TEST_INGEST_DIR.exists():
        shutil.rmtree(TEST_INGEST_DIR)

def test_index_paths_generates_insights(env_setup):
    """
    Simulate UI flow (index_paths) and verify insights visible via Repository.
    """
    repo_artifacts = ArtifactsRepo(str(TEST_DB_PATH))
    config = {
        "paths": {
            "db_path": str(TEST_DB_PATH),
            "index": str(REPO_ROOT / "test_index_vis")
        },
        "indexing": {}
    }
    service = IndexingService(repo_artifacts, config)
    
    # 1. Create a file with TBD marker
    f_path = TEST_INGEST_DIR / "doc_plan.txt"
    f_path.write_text("Deployment Plan\n\nDatabase migration is TBD.\n\nDecision: Use SQLite.", encoding="utf-8")
    
    # 2. Call the PUBLIC Batch API (like UI does)
    res = service.index_paths([str(f_path)])
    assert res["indexed"] == 1
    
    # 3. Use InsightRepository to verify visibility
    repo_insights = InsightRepository(str(TEST_DB_PATH))
    
    # Check List
    insights = repo_insights.list_insights(types=["unknown", "decision"])
    assert len(insights) >= 2
    
    types = [i["type"] for i in insights]
    assert "unknown" in types
    assert "decision" in types
    
    # Explicit check for 'unknown' filtering (Ignorance Map logic)
    unknowns = repo_insights.list_insights(types=["unknown"])
    assert len(unknowns) >= 1
    assert unknowns[0]["type"] == "unknown"
    
    # Check Evidence Drilldown
    # Pick the 'decision' insight
    decision_insight = next(i for i in insights if i["type"] == "decision")
    evidence = repo_insights.get_evidence(decision_insight["insight_id"])
    
    assert len(evidence) > 0
    assert evidence[0]["filename"] == "doc_plan.txt"
    assert "Decision: Use SQLite" in evidence[0]["content_text"]
