
import streamlit as st
from typing import List, Dict, Any

def render(items: List[Dict[str, Any]], title: str = "Items"):
    """
    Renders a list of items using Streamlit components.
    Pure render component, no DB access.
    """
    st.subheader(title)
    if not items:
        st.info("No items to display.")
        return

    for item in items:
        with st.container():
            col1, col2 = st.columns([1, 4])
            with col1:
                st.write(f"**{item.get('id', '-')}**")
            with col2:
                st.write(item.get('title', 'Untitled'))
                if 'description' in item:
                    st.caption(item['description'])
            st.divider()
