
import streamlit as st
from app.ui.state import AppState

def render(app_state: AppState):
    st.title("Open Loops")
    st.write("Tracking of unsolved questions and follow-ups coming in EPIC 6.")
