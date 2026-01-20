
import pytest
from app.core.insights.service import InsightService
from app.core.insights.explainability_service import ExplainabilityService
from app.core.insights.models import Insight
from app.test_support.db_factory import create_test_db
from app.core.insights.repository import InsightRepository

@pytest.fixture
def db_path(tmp_path):
    return create_test_db(tmp_path)

def test_manual_update_without_run_id_fallback(db_path):
    repo = InsightRepository(db_path)
    
    # Create an insight without a run (simulate fresh DB manually seeded or minimal state)
    iid = "test_manual_1"
    insight = Insight(
        insight_id=iid,
        index_run_id="run_1", 
        type="decision",
        statement="Test manual update",
        status="open",
        confidence=0.9,
        evidence_chunk_ids=[],
        insight_key="key_1"
    )
    repo.upsert_insight(insight)
    
    # Simulate UI behavior: get_latest_run_id might be None if stats missing
    # ensuring fallback works
    latest_run = repo.get_latest_run_id() or 'manual_update'
    
    repo.set_status(
        insight_id=iid,
        status="resolved",
        origin="manual",
        comment="Manually fixing",
        run_id=latest_run
    )
    
    # Verify history
    history = repo.get_status_history(iid)
    assert len(history) >= 1
    last = history[0]
    assert last['to_status'] == 'resolved'
    assert last['origin'] == 'manual'
    assert last['comment'] == 'Manually fixing'
    # Run ID should be preserved as passed (fallback or actual)
    assert last['run_id'] == latest_run 
    if not repo.get_latest_run_id():
        assert last['run_id'] == 'manual_update'

def test_explainability_logic_determinism(db_path):
    repo = InsightRepository(db_path)
    svc = ExplainabilityService(repo)
    
    iid = "test_expl_1"
    # Seed history: Open -> Resolved
    repo.log_status_change(iid, "open", "resolved", "manual", "Fixed it", "run_x")
    
    # Mock finding insight
    insight = Insight(
        insight_id=iid,
        index_run_id="run_x",
        type="decision",
        statement="Expl test",
        status="resolved",
        status_origin="manual",
        confidence=1.0, 
        insight_key="key_expl",
        updated_at="2025-01-01 12:00:00"
    )
    repo.upsert_insight(insight)
    
    # Generate explanation
    expl = svc.generate_explanation(iid)
    assert "Resolved manually" in expl.status_logic
    assert "Fixed it" in expl.status_logic
