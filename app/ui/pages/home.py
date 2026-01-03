
import streamlit as st
import sqlite3
import os
from app.ui.state import AppState
from app.ui.components import list_panel, detail_panel, evidence_panel

def check_db(db_path: str) -> str:
    """
    Checks if the database is accessible and responds to a simple query.
    Returns "OK", "WARN", or "ERROR".
    """
    if not db_path:
        return "WARN"
    
    if not os.path.exists(db_path):
        return "WARN" # Configured but file missing might be WARN or ERROR. Request says "DB not configured" -> WARN.
                      # If path exists but file missing, it's effectively "not ready". 

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        conn.close()
        return "OK"
    except Exception as e:
        return "ERROR"

def render(app_state: AppState):
    st.title("Project Copilot Starter Kit — Plus NG")
    
    # --- Status Section ---
    st.header("System Status")
    
    col1, col2, col3 = st.columns(3)
    
    # Environment
    with col1:
        st.metric("Environment", app_state.env)

    # Config
    with col2:
        cfg_status = app_state.config.get("status", "UNKNOWN")
        st.metric("Config", cfg_status)
        if cfg_status == "ERROR":
            st.error(f"Config Error: {app_state.config.get('error')}")

    # Database
    with col3:
        db_path = app_state.config.get("db_path")
        db_status = check_db(db_path)
        
        st.metric("Database", db_status)
        
        if db_status == "WARN":
            st.warning("DB not configured or not found.")
        elif db_status == "ERROR":
            st.error(f"Cannot connect to DB at {db_path}")

    st.divider()

    # --- UI Contracts ---
    st.header("UI Contracts")
    st.write("Planned features for upcoming Epics:")
    contracts = [
        {"id": "E1", "title": "Sources", "description": "Artifact ingestion and viewing"},
        {"id": "E2", "title": "Search", "description": "Semantic search capabilities"},
        {"id": "E3", "title": "Ignorance Map", "description": "Visualizing knowledge gaps"},
        {"id": "E4", "title": "Open Loops", "description": "Track unsolved questions"}
    ]
    # Reuse ListPanel
    list_panel.render(contracts, "Planned Features")

    # --- Components Demo ---
    st.subheader("Components Demo")
    
    tab1, tab2 = st.tabs(["Detail Panel", "Evidence Panel"])
    
    with tab1:
        detail_panel.render({
            "key": "value",
            "complex": {"nested": "data"},
            "list": [1, 2, 3]
        }, "Sample Details")
        
    with tab2:
        evidence_panel.render([
            {"source": "doc1.pdf", "content": "This is a sample excerpt.", "confidence": 0.95},
            {"source": "web_page", "content": "Another snippet of text.", "confidence": 0.88}
        ], "Sample Evidence")
