
import pytest
import sqlite3
import hashlib
from app.db.database import init_or_upgrade_db
from app.core.insights.engine import InsightEngine
from app.core.insights.repository import InsightRepository

@pytest.fixture
def db_path(tmp_path):
    d = tmp_path / "project.db"
    cfg = {"paths": {"db_path": str(d)}}
    res = init_or_upgrade_db(cfg)
    assert res.status == "OK"
    return str(d)

def test_dedupe_merge_evidence(db_path):
    repo = InsightRepository(db_path)
    engine = InsightEngine(db_path, repo)
    
    run_id = "run_merge"
    artifact_id = 888 # Integer
    
    # 1. Insert 2 chunks with SAME marker => Should produce SAME fingerprint
    c1 = "chunk_1"
    c2 = "chunk_2"
    content = "Please TBD: Implement Login Feature here."
    
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO artifacts (id, path, filename, ext) VALUES (?, '/tmp/art', 'art.txt', '.txt')", (artifact_id,))
        conn.execute("INSERT INTO index_runs (run_id) VALUES (?)", (run_id,))
        for c in [c1, c2]:
            conn.execute("""
                INSERT INTO chunks (chunk_id, artifact_id, index_run_id, content_text, chunk_type, hash, position_index, is_active)
                VALUES (?, ?, ?, ?, 'text', ?, 0, 1)
            """, (c, str(artifact_id), run_id, content, c)) # hash=id for uniqueness
            
    # 2. Run Engine
    engine.run(run_id)
    
    # 3. Verify: 1 Insight, 2 Evidence Rows
    insights = repo.get_insights_for_run(run_id)
    assert len(insights) == 1, "Should be deduplicated to 1 insight"
    
    insight = insights[0]
    # Check Evidence count via Repo
    evidence = repo.get_evidence(insight.insight_id)
    
    assert len(evidence) == 2, "Should have 2 merged evidence chunks"
    chunk_ids = {e['chunk_id'] for e in evidence}
    assert c1 in chunk_ids
    assert c2 in chunk_ids

def test_separate_insights_different_artifacts(db_path):
    """
    P1 Hardening: Ensure TBDs in different artifacts do NOT merge.
    Fingerprint should include artifact_id.
    """
    repo = InsightRepository(db_path)
    engine = InsightEngine(db_path, repo)
    
    run_id = "run_sep"
    art_1 = 101
    art_2 = 102
    
    content = "TODO: Fix migration script"
    
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO index_runs (run_id) VALUES (?)", (run_id,))
        
        # Artifact 1
        conn.execute("INSERT INTO artifacts (id, path, filename, ext) VALUES (?, '/tmp/a1', 'a1.txt', '.txt')", (art_1,))
        conn.execute("""
            INSERT INTO chunks (chunk_id, artifact_id, index_run_id, content_text, chunk_type, hash, position_index, is_active)
            VALUES ('c_a1', ?, ?, ?, 'text', 'h1', 0, 1)
        """, (str(art_1), run_id, content))
        
        # Artifact 2
        conn.execute("INSERT INTO artifacts (id, path, filename, ext) VALUES (?, '/tmp/a2', 'a2.txt', '.txt')", (art_2,))
        conn.execute("""
            INSERT INTO chunks (chunk_id, artifact_id, index_run_id, content_text, chunk_type, hash, position_index, is_active)
            VALUES ('c_a2', ?, ?, ?, 'text', 'h2', 0, 1)
        """, (str(art_2), run_id, content))

    # Run
    engine.run(run_id)
    
    # Verify: 2 Insights
    insights = repo.get_insights_for_run(run_id)
    assert len(insights) == 2, "Should have 2 separate insights for different artifacts"
    
    # Verify fingerprints differ
    f1 = insights[0].insight_fingerprint
    f2 = insights[1].insight_fingerprint
    assert f1 != f2, "Fingerprints must differ across artifacts"
    
    # Verify P1: ID should be the fingerprint
    assert insights[0].insight_id == f1
    assert insights[1].insight_id == f2
