
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
        
@st.cache_resource
def ensure_db_initialized(db_path_str: str):
    """
    Run DB migrations once per process.
    """
    try:
        project_root = Path(__file__).parent.parent.parent
        migrations_dir = project_root / "db" / "migrations"
        init_or_upgrade_db(Path(db_path_str), migrations_dir)
        return {"status": "OK"}
    except Exception as e:
        print(f"DB Init Fatal Error: {e}")
        return {"status": "ERROR", "error": str(e)}

class AppState:
    def __init__(self):
        # Load config only once if possible, or reload on refresh
        if "app_config" not in st.session_state:
            st.session_state.app_config = load_config()
        
        self.config = st.session_state.app_config
        
        # Initialize DB (Singleton)
        if self.config.get("db_path"):
             db_init_res = ensure_db_initialized(self.config["db_path"])
             if db_init_res["status"] == "ERROR":
                 self.config["db_init_error"] = db_init_res["error"]

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
