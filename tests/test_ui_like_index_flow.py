
import pytest
import sqlite3
import os
import shutil
from pathlib import Path
from app.core.artifacts_repo import ArtifactsRepo
from app.core.indexing_service import IndexingService

# Re-use schema logic
REPO_ROOT = Path(__file__).parent.parent
DB_MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"
TEST_DB_PATH = REPO_ROOT / "test_ui_flow.db"
TEST_INGEST_DIR = REPO_ROOT / "test_ingest_ui"

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

def test_index_paths_triggers_insights(env_setup):
    """
    Simulate the UI flow: calling index_paths([p]) and verifying insights are generated.
    """
    repo = ArtifactsRepo(str(TEST_DB_PATH))
    config = {
        "paths": {
            "db_path": str(TEST_DB_PATH),
            "index": str(REPO_ROOT / "test_index_ui")
        },
        "indexing": {},
        "embeddings": {"provider": "local"}
    }
    service = IndexingService(repo, config)
    
    # 1. Create a file with TBD marker
    f_path = TEST_INGEST_DIR / "doc_tbd.txt"
    f_path.write_text("Project Plan\n\nFeature X is TBD.\n\nDecision: Use python.", encoding="utf-8")
    
    # 2. Call the PUBLIC Batch API (like UI does)
    res = service.index_paths([str(f_path)])
    
    run_id = res["index_run_id"]
    assert run_id is not None
    assert len(res["results"]) == 1
    assert res["results"][0][1] == "indexed"
    
    # 3. Verify Insights exist for this run
    conn = sqlite3.connect(str(TEST_DB_PATH))
    conn.row_factory = sqlite3.Row
    
    # Check Insights
    rows = conn.execute("SELECT * FROM insights WHERE index_run_id=?", (run_id,)).fetchall()
    assert len(rows) >= 2, f"Expected >1 insights (TBD + Decision), got {len(rows)}"
    
    types = [r["type"] for r in rows]
    assert "unknown" in types # TBD
    assert "decision" in types # Decision: Use python
    
    # Check Evidence (Join)
    # Ensure every insight has evidence
    for r in rows:
        iid = r["insight_id"]
        ev_rows = conn.execute("SELECT * FROM insight_evidence WHERE insight_id=?", (iid,)).fetchall()
        assert len(ev_rows) > 0, f"Insight {iid} missing evidence!"
        
    # Check Chunks status
    # Should be active for this run
    chunk_count = conn.execute("SELECT count(*) FROM chunks WHERE index_run_id=? AND is_active=1", (run_id,)).fetchone()[0]
    assert chunk_count > 0
    
    conn.close()

def test_reindex_flow_refresh_insights(env_setup):
    """
    Verify that re-indexing via index_paths refreshes insights.
    """
    repo = ArtifactsRepo(str(TEST_DB_PATH))
    config = {"paths": {"db_path": str(TEST_DB_PATH)}}
    service = IndexingService(repo, config)
    
    f_path = TEST_INGEST_DIR / "doc_evolve.txt"
    
    # Run 1: TBD
    f_path.write_text("Status: TBD", encoding="utf-8")
    res1 = service.index_paths([str(f_path)])
    run1 = res1["index_run_id"]
    
    conn = sqlite3.connect(str(TEST_DB_PATH))
    cnt1 = conn.execute("SELECT count(*) FROM insights WHERE index_run_id=? AND type='unknown'", (run1,)).fetchone()[0]
    assert cnt1 == 1
    conn.close()
    
    # Run 2: Resolved
    f_path.write_text("Status: Done", encoding="utf-8")
    res2 = service.index_paths([str(f_path)])
    run2 = res2["index_run_id"]
    
    assert run1 != run2
    
    conn = sqlite3.connect(str(TEST_DB_PATH))
    
    # Check Run 2 insights -> TBD should be GONE (count 0)
    cnt2_unknown = conn.execute("SELECT count(*) FROM insights WHERE index_run_id=? AND type='unknown'", (run2,)).fetchone()[0]
    assert cnt2_unknown == 0, "Zombie TBD insight found in new run!"
    
    # Check Zombie Chunks (Run 1 chunks should be inactive)
    active_run1 = conn.execute("SELECT count(*) FROM chunks WHERE index_run_id=? AND is_active=1", (run1,)).fetchone()[0]
    assert active_run1 == 0, "Old chunks still active!"
    
    conn.close()
