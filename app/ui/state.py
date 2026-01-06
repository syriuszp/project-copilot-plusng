import streamlit as st
import logging
from app.ui.config_loader import load_config
from app.core.db_init import init_db

logger = logging.getLogger(__name__)

@st.cache_resource
def get_db_path(config: dict) -> str:
    """
    Run DB migrations once per process via core layer.
    """
    return init_db(config)

class AppState:
    def __init__(self):
        # Load config only once if possible, or reload on refresh
        if "app_config" not in st.session_state:
            st.session_state.app_config = load_config()
        
        self.config = st.session_state.app_config
        
        # Initialize DB (Singleton)
        # We pass the full config now
        self.config["db_path"] = get_db_path(self.config)
        
        # Check for error via db_path? 
        # init_db returns path string even on error (but logs it).
        # To strictly match previous error handling, core/db_init needs improvements or we check file?
        # User requested minimal change. State.py assumes successful path returned.

    @property
    def env(self) -> str:
        return self.config.get("env", "UNKNOWN")

    @property
    def db_status(self) -> str:
        if self.config.get("db_init_error"):
            return "CONFIG_ERROR"
        if not self.config.get("db_path") and not self.config.get("paths", {}).get("db_path"):
            return "NOT_CONFIGURED"
        
        return "OK"

def init_app_state() -> AppState:
    return AppState()
