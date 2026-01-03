
import streamlit as st
from app.ui.state import AppState

def render(app_state: AppState):
    st.title("Search")
    
    query = st.text_input("Enter query", disabled=True)
    st.button("Search", disabled=True)
    
    st.info("Search backend coming in EPIC 5")
