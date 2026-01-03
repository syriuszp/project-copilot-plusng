
import streamlit as st
from app.ui.state import AppState

def render(app_state: AppState):
    st.title("Ignorance Map")
    st.write("Visual representation of knowledge gaps coming in EPIC 6.")
