
import streamlit as st
from app.ui.state import AppState

def render(app_state: AppState):
    st.title("Sources")
    st.info("No artifacts ingested yet.")
    st.write("This view will list Artifacts and allow drill-down to Chunks.")
