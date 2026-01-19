
import streamlit as st
import pandas as pd
import logging
from datetime import datetime
from app.ui.state import AppState

logger = logging.getLogger(__name__)

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

    # --- Quality Metrics Dashboard (Top Block) ---
    try:
        # P1.5: Fetch latest run metrics
        metrics = repo.get_latest_quality_metrics()
        if metrics:
             m_cols = st.columns(6)
             m_cols[0].metric("Run ID", metrics['run_id'][:8], help=metrics['run_id'])
             m_cols[1].metric("Recorded", metrics['recorded_at'].split(' ')[1] if ' ' in metrics['recorded_at'] else metrics['recorded_at'])
             m_cols[2].metric("Created", metrics['created_count'])
             m_cols[3].metric("Archived", metrics['archived_count'])
             m_cols[4].metric("Restored", metrics['restored_count'])
             m_cols[5].metric("Flapping", metrics['flapping_count'], delta_color="inverse")
             
             # P1: Hint for invisible archived items
             if metrics['archived_count'] > 0 and not show_archived:
                 st.info(f"⚠️ In this run: {metrics['archived_count']} archived. Enable 'Show Archived' to view them.")
             
             st.divider()
    except Exception as e:
        # Don't crash entire page if metrics fail (e.g. table empty)
        logger.warning(f"Failed to load metrics: {e}")

    # --- Data Fetching ---
    try:
        all_rows = repo.list_insights(types=selected_types, require_active_evidence=not show_archived, limit=500)
        filtered_rows = [r for r in all_rows if r['status'] in status_filter]
    except Exception as e:
        st.error(f"Failed to fetch insights: {e}")
        return
        
    # --- Helper: Status Callback ---
    def on_status_change(iid, new_stat, comment, superseded_by_id=None):
        # P1: Use latest active run ID or fallback to ensure metrics tracking
        latest_run = repo.get_latest_run_id() or 'manual_update'
        
        if new_stat == 'superseded':
             if superseded_by_id:
                 repo.mark_superseded(iid, superseded_by_id, comment, latest_run)
                 st.toast(f"Marked {iid} as superseded by {superseded_by_id}")
             else:
                 st.error("Missing target ID for superseded status.")
                 return
        else:
             repo.set_status(iid, new_stat, 'manual', comment or 'Changed in UI', latest_run)
             st.toast(f"Updated status for {iid} to {new_stat}")
        
        st.rerun()

    # --- UI Rendering ---
    count = len(filtered_rows)
    
    # Badge / Header
    filter_label = "Active & Archived" if show_archived else "Active Only"
    st.caption(f"Showing: **{filter_label}** • {count} items")
    
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
            # MVP: Fetch one evidence to get filename (even if archived/lost)
            evs = repo.get_evidence(iid, limit=1, active_only=False)
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
            current_status = status
            
            # Form for Status Update
            new_status = st.selectbox(
                "Status", 
                ['open', 'resolved', 'superseded', 'archived'], 
                index=['open', 'resolved', 'superseded', 'archived'].index(status) if status in ['open', 'resolved', 'superseded', 'archived'] else 0,
                key=f"stat_sel_{iid}",
                label_visibility="collapsed"
            )
            
            comment = ""
            superseded_by = None
            
            # Show Comment Field if status changed
            if new_status != current_status:
                comment = st.text_input("Comment", key=f"comment_{iid}", placeholder="Required for resolved/superseded...")
                
                # Show Superseded Target Selection
                if new_status == 'superseded':
                    # Dynamic fetch of candidates
                    ev = repo.get_evidence(iid, limit=1, active_only=False)
                    candidates = []
                    if ev and 'artifact_id' in ev[0]:
                         aid = ev[0]['artifact_id']
                         # Fetch peers
                         peers = repo.get_active_insights_for_artifact(aid)
                         # Filter self and currently superseded
                         candidates = [p for p in peers if p.insight_id != iid and p.status != 'superseded']
                    
                    if not candidates:
                         st.warning("No active insights found in this artifact to supersede.")
                    else:
                         # Map for selectbox
                         cand_map = {f"{c.insight_key[:8]}... | {c.statement[:50]}...": c.insight_id for c in candidates}
                         selected_cand = st.selectbox("Superseded By", options=list(cand_map.keys()), key=f"sup_sel_{iid}")
                         if selected_cand:
                             superseded_by = cand_map[selected_cand]

                # Validation Logic for Button
                btn_disabled = False
                if new_status == 'resolved' and not comment.strip():
                     btn_disabled = True
                     st.caption("⚠️ Comment required to resolve.")
                elif new_status == 'superseded':
                     if not comment.strip(): 
                         btn_disabled = True
                         st.caption("⚠️ Comment required.")
                     if not superseded_by:
                         btn_disabled = True
                         st.caption("⚠️ Target insight required.")

                if st.button("Apply", key=f"apply_{iid}", disabled=btn_disabled):
                    # Get run_id for manual update tracking
                    latest_run = repo.get_latest_run_id()
                    callback(iid, new_status, comment, superseded_by) # Callback needs to handle this or we invoke repo here?
                    # Wait, the callback is 'on_status_change' defined below. Let's check 'on_status_change' signature.
            else:
                pass

            # Explainability Panel
        with st.expander("Explain Why"):
            # Fetch Explanation on demand (or pre-calc?)
            # Since it's UI, on-render is fast enough for single item usually
            explanation = explain_service.generate_explanation(iid)
            if explanation:
                # Epic 5: Manual Decision Block P0
                if explanation.last_manual_change:
                     mc = explanation.last_manual_change
                     st.info(f"📝 **Manual Decision**\n\n"
                             f"Changed from `{mc['from_status'].upper()}` → `{mc['to_status'].upper()}` on {mc['changed_at']}\n\n"
                             f"**Reason:** {mc['comment']}")
                
                st.markdown(f"**Rationale:** {explanation.rationale}")
                if explanation.status_logic:
                     # If manual decision is already shown above, we might want to de-emphasize this or keep it for completeness
                     # The requirement says "Explainability logic" should still be there.
                     st.caption(f"ℹ️ {explanation.status_logic}")
                
                # Metadata Block
                c_meta1, c_meta2 = st.columns(2)
                with c_meta1:
                     st.text_input("Rule ID", value=r.get('detection_rule_id') or "N/A", disabled=True, key=f"meta_rule_{iid}")
                     st.text_input("Pattern", value=r.get('detection_pattern') or "N/A", disabled=True, key=f"meta_pat_{iid}")
                with c_meta2:
                     st.text_input("Insight Key", value=r.get('insight_key') or "N/A", disabled=True, key=f"meta_key_{iid}")
                     st.caption(f"Confidence: {explanation.confidence_justification}")

                # Timeline
                st.caption(f"Timeline: First Detected {explanation.first_detected_at} | Last Confirmed {explanation.last_confirmed_at}")
                
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
