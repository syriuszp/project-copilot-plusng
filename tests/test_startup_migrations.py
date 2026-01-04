
import pytest
from unittest.mock import MagicMock, patch
from app.ui.state import AppState, init_app_state, ensure_db_initialized

@patch("app.ui.state.init_or_upgrade_db")
@patch("app.ui.state.load_config")
@patch("streamlit.session_state", new_callable=dict) # Mock session state dict
def test_startup_migrations_called(mock_session, mock_load_config, mock_db_init):
    # Setup Config
    mock_load_config.return_value = {
        "db_path": "/abs/path/to/db.sqlite",
        "env": "TEST",
        "status": "OK"
    }
    
    # We need to mock st.cache_resource behavior or bypass it.
    # Since ensure_db_initialized is decorated, we might need to test the logic inside AppState
    # or rely on the fact that calling the decorated function calls the underlying logic (if not cached).
    # However, st.cache_resource might fail in plain pytest without streamlit context.
    # Strategy: Mock internal ensure_db_initialized or ignore the decorator? 
    # Or import the underlying function if available (streamlt 1.x wraps it).
    
    # Let's test AppState.__init__ logic. 
    # It calls ensure_db_initialized.
    # We patch ensure_db_initialized in app.ui.state to verify call.
    
    with patch("app.ui.state.ensure_db_initialized") as mock_ensure:
        mock_ensure.return_value = {"status": "OK"}
        
        # Initialize State
        # We need to mock st.session_state attribute access because AppState uses dot notation?
        # The code uses `st.session_state.app_config = ...`
        # We need a robust mock for st.session_state
        
        with patch("streamlit.session_state", MagicMock()) as mock_st_session:
             # Need to handle 'app_config' not in session state initially
             mock_st_session.__contains__.return_value = False 
             
             state = AppState()
             
             # Assert ensure_db_initialized called with db_path
             mock_ensure.assert_called_once_with("/abs/path/to/db.sqlite")

def test_entrypoint_run_streamlit():
    # Verify main() calls init_app_state
    with patch("app.run_streamlit.init_app_state") as mock_init, \
         patch("app.run_streamlit.navigation") as mock_nav, \
         patch("streamlit.set_page_config"):
         
        from app.run_streamlit import main
        main()
        
        mock_init.assert_called_once()
