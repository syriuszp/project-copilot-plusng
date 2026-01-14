import streamlit as st
from app.ui.state import AppState
from app.core.insights.repository import InsightRepository

def render(app_state: AppState):
    st.title("Ignorance Map")
    st.caption("Known unknowns grounded in chunk evidence.")

    db_path = app_state.config.get("db_path")
    if not db_path:
        st.error("Database not configured.")
        return

    repo = InsightRepository(db_path)

    # Audit Fix: Use active evidence contract filters
    rows = repo.list_insights(types=["unknown"], limit=200, require_active_evidence=True, only_latest_run=False)
    st.metric("Active Unknowns", len(rows))

    if not rows:
        st.info("No active unknowns detected. Add a document with markers like TBD/TODO/UNKNOWN and re-index.")
        return

    for r in rows:
        insight_id = r["insight_id"]
        title = f"[unknown] {r['statement'][:90]}..."
        with st.expander(title, expanded=False):
            st.write(r["statement"])
            
            # Badge - Current
            st.caption(f"Run: {r.get('index_run_id')} | Confidence: {r.get('confidence')} | :green_heart: Active")

            ev = repo.get_evidence(insight_id, limit=20)
            if not ev:
                # P2: Hide insights without chunk evidence
                st.caption("No direct chunk evidence. Hidden from main view.")
                continue

            st.markdown("**Evidence:**")
            for e in ev:
                loc = []
                if e.get("page"): loc.append(f"page {e['page']}")
                if e.get("slide"): loc.append(f"slide {e['slide']}")
                if e.get("section"): loc.append(f"section {e['section']}")
                loc_s = ", ".join(loc) if loc else "text"

                st.text(f"[{e.get('filename')}] ({loc_s})")
                st.caption(f"...{(e.get('content_text') or '')[:240]}...")
