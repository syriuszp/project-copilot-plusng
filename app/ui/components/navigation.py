
import streamlit as st
from typing import Dict, Any, Callable
from app.ui.state import AppState

# Import pages (lazy import inside render to avoid circular deps if any, but top level is fine usually)
# We will inject page modules or import them here
# To avoid ImportErrors before pages exist, we'll import effectively inside render or assume they exist

def render_sidebar(app_state: AppState, page_map: Dict[str, Callable[[AppState], None]]):
    """
    Renders the sidebar navigation and executes the selected page's render function.
    
    Args:
        app_state: The application state object.
        page_map: Dictionary mapping display names to page render functions.
    """
    st.sidebar.title("Project Copilot")
    st.sidebar.caption(f"Env: {app_state.env}")
    
    selection = st.sidebar.radio("Navigation", list(page_map.keys()))
    
    st.sidebar.divider()
    st.sidebar.info("v0.1.0 - Epic 1 shell")
    
    # Execute the selected page
    if selection and selection in page_map:
        page_map[selection](app_state)
