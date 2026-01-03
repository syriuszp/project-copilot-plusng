
import streamlit as st
import sys
import os

# Ensure app root is in path if run directly - MUST BE BEFORE LOCAL IMPORTS
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
   sys.path.insert(0, parent_dir)

from app.ui.state import init_app_state
from app.ui.components import navigation
from app.ui.pages import home, sources, search, ignorance_map, open_loops

def main():
    st.set_page_config(
        page_title="Project Copilot",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Initialize State
    app_state = init_app_state()

    # Define Navigation Map
    page_map = {
        "Home": home.render,
        "Sources": sources.render,
        "Search": search.render,
        "Ignorance Map": ignorance_map.render,
        "Open Loops": open_loops.render,
    }

    # Render Navigation (Sidebar + Page routing)
    navigation.render_sidebar(app_state, page_map)

if __name__ == "__main__":
    main()
