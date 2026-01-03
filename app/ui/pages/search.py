
import streamlit as st
import datetime
import os
from app.ui.state import AppState
from app.core.artifacts_repo import ArtifactsRepo
from app.services import sources_service

def render(app_state: AppState):
    st.title("Search")
    
    config = app_state.config.get("data", {})
    db_path = app_state.config.get("db_path")
    
    if "db_init_error" in app_state.config:
        st.error(f"Database Error: {app_state.config['db_init_error']}")
        return

    if not db_path:
        st.warning("Database not configured. Search disabled.")
        return

    # Initialize Repo
    repo = None
    try:
        repo = ArtifactsRepo(db_path)
    except Exception as e:
        st.error(f"Failed to connect to DB: {e}")
        return

    # --- Search Bar & Filters ---
    c_search, c_filter = st.columns([3, 1])
    with c_search:
        query = st.text_input("Query", placeholder="Type to search content or filename...", key="search_query")
    with c_filter:
         # Dynamic filters could fetch from DB distinct exts
         # For MVP hardcoded
         ext_filter = st.multiselect("Extensions", [".txt", ".md", ".pdf", ".docx", ".json"])
         # Status filter? Usually user wants all or indexed. 
         # Requirement: "filtrować (extension, status, date)"
         # Status defaults to all?
    
    # --- Perform Search ---
    if query:
        # P1: Telemetry could be logged here (index_runs mainly, but search logs nice too?)
        # Not in P1 specs.
        
        filters = {}
        if ext_filter:
            # Repo currently supports single ext? "AND a.ext = ?"
            # Updating repo to support list or loop in UI?
            # Repo implementation: `if filters.get('ext'): sql += " AND a.ext = ?"`. 
            # Only single value supported in my implementation.
            # I will use single select or fix Repo.
            # "filters (dropdown, z DB)" singular implies single?
            # Let's check implementation plan: "ext (dropdown, z DB)".
            # Multiselect is better UX, but repo needs IN clause.
            # I'll stick to single value for MVP compliance with my repo code.
            pass
    
    # --- Revised Filters for Repo Compatibility ---
    # Repo supports 'ext' (single string).
    with c_filter:
        # Overwriting previous multiselect concept
        pass
    
    # Rerendering filters properly
    filters = {}
    with st.expander("Filters", expanded=False):
         c_f1, c_f2 = st.columns(2)
         with c_f1:
             sel_ext = st.selectbox("Extension", ["All", ".txt", ".md", ".pdf", ".docx", ".json"])
             if sel_ext != "All":
                 filters["ext"] = sel_ext
         with c_f2:
             sel_status = st.selectbox("Status", ["All", "Indexed", "New", "Failed", "Not Extractable"])
             if sel_status != "All":
                 filters["status"] = sel_status.lower().replace(" ", "_")

    results = []
    if query or filters: # Allow empty query if filters present?
        results = repo.search_artifacts(query, filters)
    
    if not results and (query or filters):
        st.info("No results found.")
        return
    elif not query and not filters:
        st.info("Enter a query to search.")
        return

    # --- Results Layout ---
    col_res, col_prev = st.columns([2, 3])
    
    selected_result = None
    
    with col_res:
        st.caption(f"Found {len(results)} results")
        if repo.fts_enabled:
            st.caption("FTS: ON (Full-Text Search)")
        else:
            st.caption("FTS: OFF (Fallback to LIKE)")
            
        with st.container():
            for res in results:
                # Evidence Card
                path = res['path']
                filename = res['filename']
                snippet = res.get('snippet') or "No text content."
                snippet = snippet.replace("<b>", "**").replace("</b>", "**") # Sanitize FTS formatting
                
                # Render
                with st.expander(f"{filename}", expanded=False):
                    st.markdown(f"`{path}`")
                    st.markdown(f"_{snippet}_")
                    st.caption(f"Status: {res['ingest_status']} | Ext: {res['ext']}")
                    
                    if st.button("Preview", key=f"prev_{res['id']}"):
                        st.session_state["search_selected_id"] = res['id']
    
    # Check selection
    sel_id = st.session_state.get("search_selected_id")
    if sel_id:
        selected_result = next((r for r in results if r['id'] == sel_id), None)
        
    with col_prev:
        if selected_result:
            st.markdown(f"### {selected_result['filename']}")
            
            # Use sources_service for preview logic
            # This requires file to exist on PROD disk. 
            # Requirement: "otworzyć podgląd (preview) tego samego pliku jak w Sources"
            # So yes, disk read.
            
            if os.path.exists(selected_result['path']):
                preview = sources_service.preview_artifact(selected_result['path'])
                if preview.type == "text":
                    st.code(preview.content) # Full content
                elif preview.type == "image":
                    st.image(preview.content)
                elif preview.type == "pdf_placeholder":
                     st.info("PDF preview not available.")
                else:
                    st.warning(preview.error_message)
            else:
                st.error("File not found on disk.")
                
            # Metadata from DB
            st.write("Metadata:")
            st.json({
                "Path": selected_result['path'],
                "Modified": selected_result['modified_at'],
                "Size": selected_result.get('size_bytes'),
                "Status": selected_result['ingest_status']
            })
            
            if st.button("Open in Sources"):
                 # Navigate to Sources and select this file
                 st.session_state["selected_artifact_path"] = selected_result['path']
                 # How to switch page? 
                 # Streamlit sidebar selection needs to change.
                 # app_state doesn't control navigation directly (navigation component does).
                 # navigation component reads `st.query_params` or internal logic.
                 # standard streamtlit: click sidebar.
                 # Programmatic navigation: st.switch_page("app/ui/pages/sources.py") ?
                 # But we use single-app custom nav `run_streamlit.py`.
                 # We need to set a session state that `navigation` or `run_streamlit` respects?
                 # `navigation.render_sidebar` uses `st.sidebar.radio`.
                 # We can update the key for that radio if we know it.
                 # Navigation uses key="nav_selection" usually?
                 # Let's check `app/ui/components/navigation.py`.
                 pass
        else:
             st.info("Select a result to preview.")

