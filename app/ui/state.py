
import streamlit as st
from typing import Dict, Any
from app.ui.config_loader import load_config
from app.db.database import init_or_upgrade_db
from pathlib import Path

class AppState:
    def __init__(self):
        # Load config only once if possible, or reload on refresh
        if "app_config" not in st.session_state:
            st.session_state.app_config = load_config()
        
        self.config = st.session_state.app_config
        
        # Initialize DB if configured and not yet initialized in this session
        if "db_inited" not in st.session_state and self.config.get("config_path"):
            try:
                # Ensure DB exists and migrations are applied
                init_or_upgrade_db(Path(self.config["config_path"]))
                st.session_state.db_inited = True
            except Exception as e:
                # Log error but don't crash app start?
                print(f"DB Init Error: {e}")
                self.config["db_init_error"] = str(e)

    @property
    def env(self) -> str:
        return self.config.get("env", "UNKNOWN")

    @property
    def db_status(self) -> str:
        if self.config.get("status") == "ERROR":
            return "CONFIG_ERROR"
        if not self.config.get("db_path"):
            return "NOT_CONFIGURED"
        # In a real app, we might check connection here or cache the result
        return "OK" # Placeholder, actual check done in Home page logic or here

def init_app_state() -> AppState:
    return AppState()
