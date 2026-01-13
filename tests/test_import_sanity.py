
import pytest
import sys
import os

def test_critical_modules_import():
    """Ensure core modules are importable."""
    import app.core.insights.engine
    import app.core.insights.repository
    import app.core.vector.retriever
    import app.core.indexing_service
    assert True

def test_ui_no_legacy_search_imports():
    """
    Scan UI files to ensuring they don't import 'app.core.legacy_search' or similar if it existed.
    For this audit, we verify that `app.ui.pages.search.py` imports `SearchService` from `app.core.search.service`
    and NOT from some old location.
    """
    base_path = os.path.join(os.path.dirname(__file__), "../app/ui/pages")
    search_ui = os.path.join(base_path, "search.py")
    
    if os.path.exists(search_ui):
        with open(search_ui, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Check intended imports
        assert "from app.core.search.service import SearchService" in content, "Search page must use SearchService"
        
        # Check forbidden imports (example)
        assert "import app.core.legacy" not in content
        assert "from app.core.legacy" not in content

def test_no_dead_code_references_in_init():
    """Ensure __init__.py files are not exposing broken exports."""
    # We can try to import the package root 'app'
    import app
    assert app
