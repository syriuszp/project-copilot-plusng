
import streamlit as st

# Ensure app root is in path if run directly - MUST BE BEFORE LOCAL IMPORTS


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
