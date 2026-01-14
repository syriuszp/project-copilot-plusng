
import streamlit as st
import pandas as pd
from datetime import datetime
from app.ui.state import AppState

def render(app_state: AppState):
    st.title("Open Loops (Insight Engine V2)")
    st.caption("Review and manage insights detected from your artifacts.")
    
    # --- Config & Setup ---
    db_path = app_state.config.get("db_path")
    if not db_path:
        st.warning("Database path not configured.")
        return

    from app.core.insights.repository import InsightRepository
    from app.core.insights.explainability_service import ExplainabilityService
    
    try:
        repo = InsightRepository(db_path)
        explain_service = ExplainabilityService(repo)
    except Exception as e:
        st.error(f"Failed to connect to DB: {e}")
        return

    # --- Sidebar Filters ---
    with st.sidebar:
        st.header("Filters")
        show_archived = st.checkbox("Show Archived", value=False)
        group_mode = st.radio("Group By", ["Artifact", "Section", "None"], index=0)
        
        status_filter = ['open', 'resolved', 'superseded']
        if show_archived:
            status_filter.append('archived')
            
        selected_types = st.multiselect("Types", ['decision', 'dependency', 'unknown'], default=['decision', 'dependency'])

    # --- Data Fetching ---
    try:
        all_rows = repo.list_insights(types=selected_types, require_active_evidence=not show_archived, limit=500)
        filtered_rows = [r for r in all_rows if r['status'] in status_filter]
    except Exception as e:
        st.error(f"Failed to fetch insights: {e}")
        return
        
    # --- Helper: Status Callback ---
    def on_status_change(iid):
        new_stat = st.session_state[f"status_{iid}"]
        # P1: Use latest active run ID or fallback to ensure metrics tracking
        latest_run = repo.get_latest_run_id() or 'manual_update'
        repo.set_status(iid, new_stat, 'manual', 'Changed in UI', latest_run)
        st.toast(f"Updated status for {iid} to {new_stat}")

    # --- UI Rendering ---
    count = len(filtered_rows)
    st.metric("Visible Items", count)
    
    if count == 0:
        st.info("No matching insights found.")
        return
        
    st.divider()

    # Sort
    filtered_rows.sort(key=lambda x: (x['status'] == 'open', x['updated_at']), reverse=True)

    if group_mode == "Artifact":
        files_map = {}
        for r in filtered_rows:
            iid = r['insight_id']
            # MVP: Fetch one evidence to get filename. 
            # Ideally list_insights should return artifact path but schema is complex.
            # We pay the price of N+1 for Artifact Grouping MVP.
            evs = repo.get_evidence(iid, limit=1)
            fname = evs[0]['filename'] if evs else "Unknown Artifact"
            
            if fname not in files_map: files_map[fname] = []
            files_map[fname].append(r)
            
        for fname, items in files_map.items():
            with st.expander(f"📄 {fname} ({len(items)})", expanded=True):
                for r in items:
                    render_insight_card(r, repo, explain_service, on_status_change)
                    
    elif group_mode == "Section":
        sections_map = {}
        for r in filtered_rows:
            section = r.get('section_hint') or "Uncategorized"
            if section not in sections_map: sections_map[section] = []
            sections_map[section].append(r)
            
        for section, items in sections_map.items():
            with st.expander(f"📑 {section} ({len(items)})", expanded=True):
                for r in items:
                    render_insight_card(r, repo, explain_service, on_status_change)
    else:
        for r in filtered_rows:
            render_insight_card(r, repo, explain_service, on_status_change)


def render_insight_card(r, repo, explain_service, callback):
    iid = r['insight_id']
    status = r['status']
    stat_color = "red" if status == 'open' else "green" if status == 'resolved' else "grey"
    
    with st.container():
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"**:{stat_color}[{status.upper()}]** {r['statement']}")
            meta = f"Key: `{r['insight_key'][:8]}...` | Detected: {r['first_detected_at']}"
            if r.get('section_hint'):
                meta += f" | Section: *{r['section_hint']}*"
            st.caption(meta)
            
        with c2:
            st.selectbox(
                "Status", 
                ['open', 'resolved', 'superseded', 'archived'], 
                index=['open', 'resolved', 'superseded', 'archived'].index(status) if status in ['open', 'resolved', 'superseded', 'archived'] else 0,
                key=f"status_{iid}",
                on_change=callback,
                args=(iid,),
                label_visibility="collapsed"
            )

        # Explainability Panel
        with st.expander("Explain Why"):
            # Fetch Explanation on demand (or pre-calc?)
            # Since it's UI, on-render is fast enough for single item usually
            explanation = explain_service.generate_explanation(iid)
            if explanation:
                st.markdown(f"**Rationale:** {explanation.rationale}")
                if explanation.status_logic:
                     st.info(f"ℹ️ {explanation.status_logic}")
                
                # Timeline
                st.caption(f"Timeline: First Detected {explanation.first_detected_at} | Last Confirmed {explanation.last_confirmed_at}")
                if explanation.confidence_justification:
                    st.caption(f"Confidence: {explanation.confidence_justification}")
                
            # Evidence
            evs = repo.get_evidence(iid)
            if evs:
                st.markdown("---")
                st.caption("Supporting Evidence:")
                for e in evs:
                     st.markdown(f"**{e['filename']}** (Pg {e['page']}): `{e['content_text'][:150]}...`")
            
            # JSON Debug
            with st.popover("Raw Data"):
                st.json(r)
        
        st.divider()
