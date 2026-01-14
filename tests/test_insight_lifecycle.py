
import pytest
import sqlite3
import hashlib
import time
from datetime import datetime
from app.core.insights.repository import InsightRepository
from app.core.insights.service import InsightService
from app.core.insights.quality_service import QualityService
from app.core.insights.models import Insight
from tests.helpers.db_factory import create_test_db

@pytest.fixture
def db_path(tmp_path):
    return create_test_db(tmp_path)

@pytest.fixture
def services(db_path):
    repo = InsightRepository(db_path)
    service = InsightService(repo)
    quality = QualityService(db_path)
    return repo, service, quality

def test_lifecycle_v2_flow(db_path, services):
    repo, service, quality = services
    
    # Setup
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT OR IGNORE INTO artifacts (id, path, sha256, modified_at) VALUES (1, 'path/to/a1', 'hash', 12345)")
        conn.execute("INSERT INTO chunks (chunk_id, artifact_id, is_active, content_text, position_index, hash, index_run_id, chunk_type) VALUES ('c1', '1', 1, 'TODO: Fix this', 10, 'h1', 'init_run', 'text')")
        conn.commit()
    finally:
        conn.close()
    
    # Run Scan 1
    candidates = [{
        "type": "unknown", "statement": "TODO: Fix this", "position_index": 10, "chunk_id": "c1"
    }]
    service.scan_compare_transition("1", candidates, "run1")
    quality.record_run_metrics("run1")
    
    # Verify Created
    insights = repo.get_active_insights_for_artifact("1")
    assert len(insights) == 1
    i1 = insights[0]
    assert i1.status == 'open'
    
    # Run Scan 2 (Lost)
    service.scan_compare_transition("1", [], "run2")
    quality.record_run_metrics("run2")
    
    # Verify Archived
    i1_updated = repo.get_insight_by_key(i1.insight_key)
    assert i1_updated.status == 'archived'
    
    # Run Scan 3 (Restored)
    service.scan_compare_transition("1", candidates, "run3")
    
    # Verify Restored
    i1_restored = repo.get_insight_by_key(i1.insight_key)
    assert i1_restored.status == 'open'
    
    # Quality (Flapping)
    quality.record_run_metrics("run3")
    with sqlite3.connect(db_path) as verify_conn:
        metrics = verify_conn.execute("SELECT flapping_count FROM quality_metrics WHERE run_id='run3'").fetchone()
        assert metrics[0] == 1 

def test_manual_resolution_v2(db_path, services):
    repo, service, quality = services
    
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT OR IGNORE INTO artifacts (id, path, sha256, modified_at) VALUES (1, 'path/to/a1', 'hash', 12345)")
        conn.execute("INSERT INTO chunks (chunk_id, artifact_id, is_active, content_text, position_index, hash, index_run_id, chunk_type) VALUES ('c1', '1', 1, 'TODO: Fix this', 10, 'h1', 'init_run', 'text')")
        conn.commit()
    finally:
        conn.close()
    
    candidates = [{"type": "unknown", "statement": "TODO: Fix this", "position_index": 10, "chunk_id": "c1"}]
    service.scan_compare_transition("1", candidates, "run1")
    i1 = repo.get_active_insights_for_artifact("1")[0]
    
    repo.set_status(i1.insight_id, 'resolved', 'manual', 'Done', 'man1')
    
    service.scan_compare_transition("1", candidates, "run2")
    
    i1_after = repo.get_insight_by_key(i1.insight_key)
    assert i1_after.status == 'resolved'
