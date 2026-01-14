import streamlit as st
from app.ui.state import AppState

def render(app_state: AppState):
    st.title("Open Loops")
    st.caption("Actionable items requiring attention.")
    
    # --- Config & Setup ---
    db_path = app_state.config.get("db_path")
    if not db_path:
        st.warning("Database path not configured.")
        return

    from app.core.insights.repository import InsightRepository
    
    repo = None
    rows = []
    
    # --- Data Fetching ---
    try:
        repo = InsightRepository(db_path)
        # Audit Fix: Use active evidence contract filters AND status filter for accurate count
        rows = repo.list_insights(types=['decision', 'dependency'], require_active_evidence=True, only_latest_run=False, status='open')
    except Exception as e:
        st.error(f"Failed to fetch insights: {e}")
        return
        
    # --- UI Rendering ---
    
    # Counters
    count = len(rows)
    st.metric("Open Items", count)
    
    if count == 0:
        st.info("No open loops found. Good job!")
        return
        
    st.divider()
    
    for r in rows:
        i_type = r["type"].upper()
        status = r["status"]
        conf = r["confidence"]
        insight_id = r["insight_id"]
        
        # Color coding
        msg = f"**[{i_type}]** {r['statement']}"
        icon = "🔗" if i_type == "DEPENDENCY" else "🤔"
        
        with st.expander(f"{icon} {i_type}: {r['statement'][:80]}...", expanded=True):
            st.markdown(r['statement'])
            
            # Metadata
            c1, c2 = st.columns(2)
            c1.caption(f"Confidence: {conf:.2f} | Status: {status}")
            c2.caption(f"Updated: {r['updated_at']}")
            
            # Drilldown Evidence
            evidence = repo.get_evidence(insight_id)
            if evidence:
                st.markdown("---")
                st.markdown("**Evidence:**")
                for ev in evidence:
                    loc = f"Pg {ev['page']}" if ev['page'] else "Text"
                    st.text(f"[{ev['filename']}] ({loc}):")
                    st.caption(f"...{ev['content_text'][:200]}...")
            else:
                st.markdown("---")
                st.caption("No direct chunk evidence linked.")
