
import streamlit as st
import os
import datetime
from app.ui.state import AppState
from app.services import sources_service
from app.ui.components import list_panel, detail_panel

def render(app_state: AppState):
    st.title("Sources")
    
    # --- Config & Setup ---
    config = app_state.config.get("data", {})
    ingest_dir = None
    
    # Try getting ingest_dir from paths.ingest_dir or fallback
    if "paths" in config and "ingest_dir" in config["paths"]:
        raw_dir = config["paths"]["ingest_dir"]
        # Resolve if relative
        if not os.path.isabs(raw_dir):
            # Try resolving against config dir if we knew it, or project root
            # heuristic: assume project root if relative
            # For strictness we could use app_state logic, but let's assume raw or valid for now.
             pass 
        ingest_dir = raw_dir
    
    # If not in config, maybe env var or default? 
    # For now, if missing, show warning.
    if not ingest_dir:
        st.warning("`paths.ingest_dir` is not configured in YAML.")
        return

    if not os.path.exists(ingest_dir):
        st.error(f"Ingestion directory not found: `{ingest_dir}`")
        return

    # --- Sidebar Filters ---
    with st.sidebar:
        st.subheader("Inbox Filters")
        search_term = st.text_input("Search files", placeholder="filename...")
        
        # Hardcoded common extensions for filter dropdown + 'all'
        ext_options = ["all", ".pdf", ".txt", ".md", ".json", ".png", ".jpg"]
        filter_ext = st.selectbox("Extension", ext_options)
        
        # Future: Sort options if needed (service does mtime desc by default)

    # --- Main Area ---
    st.subheader("Ingestion Inbox")
    
    # --- Wrapper for caching (since service can't import st) ---
    @st.cache_data(ttl=5)
    def cached_list_artifacts(dir_path, f_ext, search):
        return sources_service.list_artifacts(dir_path, f_ext, search)
    
    # 1. Fetch Data
    artifacts = cached_list_artifacts(ingest_dir, filter_ext, search_term)
    
    if not artifacts:
        # P2: Conditional info
        if filter_ext != "all" or search_term:
            st.info("No artifacts found matching criteria.")
        else:
             st.info("No artifacts ingested yet.")
        return

    # 2. Layout: List (Left) | Detail/Preview (Right)
    col_list, col_detail = st.columns([2, 3])
    
    selected_artifact = None
    
    # --- Left: List ---
    with col_list:
        st.caption(f"Found {len(artifacts)} items")
        
        # Simplified custom list rendering (Streamlit native selection is tricky with complex UI)
        # We'll use a radio button or buttons logic. 
        # Ideally, a dataframe with selection is good for "Inbox" style.
        
        # Prepare data for dataframe
        data = []
        for a in artifacts:
            data.append({
                "Name": a.name,
                "Size (KB)": f"{a.size / 1024:.1f}",
                "Modified": datetime.datetime.fromtimestamp(a.mtime).strftime('%Y-%m-%d %H:%M'),
                "Type": a.type,
                "_path": a.path # Hidden col logic if possible, or lookup by name
            })
            
        # Using st.dataframe with selection (available in newer Streamlit) involves session state
        # For simplicity/robustness in standardized shell: 
        # Let's use a selectable list/radio for now, or simple buttons.
        # "Selectbox" for inbox is ugly. 
        # Let's try `st.radio` hidden or formatted? No. 
        # Let's iterate and show simplified items with a "View" button.
        
        # Scrollable container for list
        # P0: Fix st.container(height=...) -> Use simple container + explicit CSS if needed or just container
        # Note: height param in st.container was introduced in recent Streamlit versions. 
        # Requirement says it crashes, so assuming older Streamlit or user has issue with it.
        # We will use standard container without height.
        with st.container():
            import hashlib
            for i, art in enumerate(artifacts):
                # Card-like row
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{art.name}**  \n<span style='color:grey; font-size:0.8em'>{art.type} | {art.size/1024:.1f} KB</span>", unsafe_allow_html=True)
                
                # P1: Stable Key
                # Using index i is stable enough if list is sorted same way. 
                # Or hash of path. 
                safe_key = hashlib.md5(art.path.encode('utf-8')).hexdigest()
                
                if c2.button("View", key=f"btn_{safe_key}"):
                    st.session_state["selected_artifact_path"] = art.path
                
                st.divider()

        # Check selection
        selected_path = st.session_state.get("selected_artifact_path")
        if selected_path:
            # Find the artifact obj
            selected_artifact = next((a for a in artifacts if a.path == selected_path), None)

    # --- Right: Detail & Preview ---
    with col_detail:
        if selected_artifact:
            st.markdown(f"### {selected_artifact.name}")
            
            # Metadata Tab / Preview Tab
            tab_preview, tab_meta = st.tabs(["Preview", "Metadata"])
            
            with tab_meta:
                 # Initial details (without hash)
                 # P1: Lazy hash logic
                 # We don't fetch full details immediately if cache/calc is heavy?
                 # Actually verify if we want to re-fetch or use logic.
                 # Let's check session state for calculated hash or create compute button.
                 
                 # Helper to manage hash state for this artifact
                 hash_key = f"hash_{selected_artifact.path}"
                 current_hash = st.session_state.get(hash_key)
                 
                 details = sources_service.get_artifact_details(
                     selected_artifact.path, 
                     compute_hash=False # Initial fetch: fast, no hash
                 )
                 
                 meta_dict = {
                     "Path": details.path,
                     "Size": f"{details.size} bytes",
                     "Modified": datetime.datetime.fromtimestamp(details.mtime).isoformat(),
                     "Type": details.type,
                 }
                 
                 if current_hash:
                     meta_dict["SHA256"] = current_hash
                 else:
                     meta_dict["SHA256"] = "Not calculated"
                     
                 st.json(meta_dict)
                 
                 if not current_hash:
                     if st.button("Compute Hash"):
                         # Re-fetch with hash
                         d_with_hash = sources_service.get_artifact_details(selected_artifact.path, compute_hash=True)
                         st.session_state[hash_key] = d_with_hash.hash
                         st.rerun()

                 # Windows Open Folder
                 if os.name == 'nt':
                     if st.button("Open Folder"):
                         try:
                             os.startfile(os.path.dirname(details.path))
                         except Exception as e:
                             st.error(f"Cannot open folder: {e}")

            with tab_preview:
                preview = sources_service.preview_artifact(selected_artifact.path)
                
                if preview.type == "text":
                    st.code(preview.content, language=None) # Auto-detect or plain
                elif preview.type == "image":
                    st.image(preview.content)
                elif preview.type == "pdf_placeholder":
                    st.info("PDF preview not yet supported (EPIC 3)")
                elif preview.type == "error":
                    st.error(preview.error_message)
                else:
                    st.warning("No preview available")
        else:
            st.info("Select an artifact to view details.")

