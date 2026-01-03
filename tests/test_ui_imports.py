
import pytest
import sys
import os

# Ensure repo root is in python path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

def test_ui_imports():
    """
    Smoke test to verify that UI modules can be imported without error.
    This ensures no syntax errors or missing dependencies in the new structure.
    """
    try:
        import app.ui.config_loader
        import app.ui.state
        import app.ui.components.list_panel
        import app.ui.components.detail_panel
        import app.ui.components.evidence_panel
        import app.ui.components.navigation
        import app.ui.pages.home
        import app.ui.pages.sources
        import app.ui.pages.search
        import app.ui.pages.ignorance_map
        import app.ui.pages.open_loops
        import app.run_streamlit
    except Exception as e:
        pytest.fail(f"Import failed: {e}")

    assert True
