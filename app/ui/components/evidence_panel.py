
import streamlit as st
from typing import List, Dict, Any

def render(evidence_list: List[Dict[str, Any]], title: str = "Evidence"):
    """
    Renders a list of evidence items.
    Pure render component, no DB access.
    """
    st.markdown(f"### {title}")
    if not evidence_list:
        st.info("No evidence provided.")
        return

    for ev in evidence_list:
        with st.expander(f"{ev.get('source', 'Unknown Source')} - {ev.get('timestamp', '')}"):
            st.markdown(ev.get('content', 'No content'))
            st.caption(f"Confidence: {ev.get('confidence', 'N/A')}")
