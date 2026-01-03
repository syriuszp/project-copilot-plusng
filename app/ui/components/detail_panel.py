
import streamlit as st
from typing import Dict, Any

def render(item: Dict[str, Any], title: str = "Details"):
    """
    Renders details of an item.
    Pure render component, no DB access.
    """
    st.subheader(title)
    if not item:
        st.info("No details available.")
        return

    st.json(item)
