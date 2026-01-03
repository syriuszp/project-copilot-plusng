
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
    
    # 1. Fetch Data
    artifacts = sources_service.list_artifacts(ingest_dir, filter_ext, search_term)
    
    if not artifacts:
        st.info("No artifacts found matching criteria.")
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
        with st.container(height=600):
            for art in artifacts:
                # Card-like row
                c1, c2 = st.columns([3, 1])
                c1.markdown(f"**{art.name}**  \n<span style='color:grey; font-size:0.8em'>{art.type} | {art.size/1024:.1f} KB</span>", unsafe_allow_html=True)
                if c2.button("View", key=f"btn_{art.path}"):
                    st.session_state["selected_artifact_path"] = art.path

        # Check selection
        selected_path = st.session_state.get("selected_artifact_path")
        if selected_path:
            # Find the artifact obj
            selected_artifact = next((a for a in artifacts if a.path == selected_path), None)

    # --- Right: Detail & Preview ---
    with col_detail:
        if selected_artifact:
            # Fetch Details (Lazy)
            details = sources_service.get_artifact_details(selected_artifact.path)
            
            st.markdown(f"### {details.name}")
            
            # Metadata Tab / Preview Tab
            tab_preview, tab_meta = st.tabs(["Preview", "Metadata"])
            
            with tab_meta:
                 # Reuse DetailPanel logic or custom
                 meta_dict = {
                     "Path": details.path,
                     "Size": f"{details.size} bytes",
                     "Modified": datetime.datetime.fromtimestamp(details.mtime).isoformat(),
                     "Type": details.type,
                     "SHA256": details.hash or "Calculating..." 
                 }
                 st.json(meta_dict)
                 
                 # Windows Open Folder
                 if os.name == 'nt':
                     if st.button("Open Folder"):
                         try:
                             os.startfile(os.path.dirname(details.path))
                         except Exception as e:
                             st.error(f"Cannot open folder: {e}")

            with tab_preview:
                preview = sources_service.preview_artifact(details.path)
                
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

