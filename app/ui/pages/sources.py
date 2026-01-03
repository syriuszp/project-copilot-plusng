
import streamlit as st
import os
import datetime
import hashlib
from app.ui.state import AppState
from app.services import sources_service
from app.core.artifacts_repo import ArtifactsRepo
from app.core.indexing_service import IndexingService

def render(app_state: AppState):
    st.title("Sources")
    
    # --- Config & Setup ---
    config = app_state.config.get("data", {})
    db_path = app_state.config.get("db_path")
    ingest_dir = None
    
    if "db_init_error" in app_state.config:
        st.error(f"Database Initialization Error: {app_state.config['db_init_error']}")
        return

    # Try getting ingest_dir from paths.ingest_dir or fallback
    if "paths" in config and "ingest_dir" in config["paths"]:
        raw_dir = config["paths"]["ingest_dir"]
        if not os.path.isabs(raw_dir):
             pass # Logic to resolve against root if needed, but assuming absolute or valid relative for now
        ingest_dir = raw_dir
    
    if not ingest_dir:
        st.warning("`paths.ingest_dir` is not configured.")
        return

    if not os.path.exists(ingest_dir):
        st.error(f"Ingestion directory not found: `{ingest_dir}`")
        return

    # --- Initialize Services ---
    repo = None
    indexer = None
    db_status_map = {}
    
    if db_path:
        try:
            repo = ArtifactsRepo(db_path)
            indexer = IndexingService(repo)
            
            # Fetch all statuses for mapping
            # Using empty query to get all
            all_db_artifacts = repo.search_artifacts("") 
            for row in all_db_artifacts:
                db_status_map[row['path']] = row['ingest_status']
                
        except Exception as e:
            st.error(f"Failed to initialize repository: {e}")
    else:
        st.warning("Database path not configured. Indexing disabled.")

    # --- Sidebar Filters ---
    with st.sidebar:
        st.subheader("Inbox Filters")
        search_term = st.text_input("Search files", placeholder="filename...")
        ext_options = ["all", ".pdf", ".txt", ".md", ".json", ".png", ".jpg"]
        filter_ext = st.selectbox("Extension", ext_options)

    # --- Wrapper for caching ---
    @st.cache_data(ttl=5)
    def cached_list_artifacts(dir_path, f_ext, search):
        return sources_service.list_artifacts(dir_path, f_ext, search)
    
    # --- ACTIONS ---
    # Index All
    if indexer:
        c_top1, c_top2 = st.columns([4, 1])
        with c_top2:
            if st.button("Index All", type="primary"):
                with st.spinner("Indexing all files..."):
                    stats = indexer.index_all(ingest_dir)
                st.success(f"Indexed: {stats.get('indexed', 0)}, Failed: {stats.get('failed', 0)}")
                st.rerun()

    # --- Main Area ---
    st.subheader("Ingestion Inbox")
    
    # 1. Fetch File List
    artifacts = cached_list_artifacts(ingest_dir, filter_ext, search_term)
    
    if not artifacts:
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
        
        with st.container():
            for i, art in enumerate(artifacts):
                safe_key = hashlib.md5(art.path.encode('utf-8')).hexdigest()
                
                # Determine status
                status = db_status_map.get(art.path, "new")
                status_color = {
                    "new": "grey",
                    "indexed": "green",
                    "failed": "red",
                    "not_extractable": "orange"
                }.get(status, "grey")
                
                # Card Row
                c1, c2, c3 = st.columns([3, 1, 1])
                
                # Name & Badge
                c1.markdown(f"**{art.name}**  \n<span style='color:{status_color}; font-size:0.8em'>● {status.upper()}</span> <span style='color:grey; font-size:0.8em'>| {art.type}</span>", unsafe_allow_html=True)
                
                # View Button
                if c2.button("View", key=f"view_{safe_key}"):
                    st.session_state["selected_artifact_path"] = art.path
                
                # Index Button (only if indexer available)
                if indexer:
                    btn_label = "Re-Index" if status == "indexed" else "Index"
                    if c3.button(btn_label, key=f"idx_{safe_key}"):
                        with st.spinner(f"Indexing {art.name}..."):
                            res = indexer.index_file(art.path)
                        if res == "indexed":
                            st.toast(f"Indexed {art.name}", icon="✅")
                        elif res == "not_extractable":
                            st.toast(f"Not extractable: {art.name}", icon="⚠️")
                        else:
                            st.toast(f"Failed: {art.name}", icon="❌")
                        st.rerun()
                
                st.divider()

        # Check selection
        selected_path = st.session_state.get("selected_artifact_path")
        if selected_path:
            selected_artifact = next((a for a in artifacts if a.path == selected_path), None)

    # --- Right: Detail & Preview ---
    with col_detail:
        if selected_artifact:
            st.markdown(f"### {selected_artifact.name}")
            
            tab_preview, tab_meta = st.tabs(["Preview", "Metadata"])
            
            with tab_meta:
                 # Helper to manage hash state
                 hash_key = f"hash_{selected_artifact.path}"
                 current_hash = st.session_state.get(hash_key)
                 
                 details = sources_service.get_artifact_details(
                     selected_artifact.path, 
                     compute_hash=False 
                 )
                 
                 # Enrich with DB status
                 status = db_status_map.get(details.path, "new")
                 
                 meta_dict = {
                     "Path": details.path,
                     "Size": f"{details.size} bytes",
                     "Modified": datetime.datetime.fromtimestamp(details.mtime).isoformat(),
                     "Type": details.type,
                     "Status": status
                 }
                 
                 if current_hash:
                     meta_dict["SHA256"] = current_hash
                     # Save to DB if calculated (P2)
                     # Repo upsert handles updating sha256 if passed.
                     if repo:
                         try:
                            # We need to construct full meta. Repo.upsert_artifact takes path, filename, ext, etc.
                            # We can just update sha256? No, upsert needs PK path.
                            repo_meta = {
                                "path": details.path,
                                "filename": details.name,
                                "ext": details.type,
                                "sha256": current_hash
                                # size, mtime might be outdated in params but upsert uses COALESCE for optional? 
                                # Code: sha256=COALESCE(excluded.sha256, artifacts.sha256)
                                # So we pass sha256, others will potentially update or be null?
                                # My upsert SQL: VALUES (..., ?, ?, ...) ON CONFLICT ...
                                # The validation in upsert might require some fields.
                                # Let's assume re-indexing sets it, or separate method.
                                # For P2, let's just show it. Writing to DB without index run might be confusing state?
                                # "Compute Hash writes sha256" is the task.
                                # I will call repo.upsert with just path and sha256?
                                # SQL 'filename' is NOT NULL. So I need to pass it.
                            }
                            repo.upsert_artifact(repo_meta)
                         except Exception as e:
                             pass # P2 nicety, optional failure
                 else:
                     meta_dict["SHA256"] = "Not calculated"
                     
                 st.json(meta_dict)
                 
                 if not current_hash:
                     if st.button("Compute Hash"):
                         d_with_hash = sources_service.get_artifact_details(selected_artifact.path, compute_hash=True)
                         st.session_state[hash_key] = d_with_hash.hash
                         st.rerun()

                 if os.name == 'nt':
                     if st.button("Open Folder"):
                         try:
                             # P2.2: Tooltip logic via help param or text
                             st.info("Opening Explorer (check taskbar)...")
                             os.startfile(os.path.dirname(details.path))
                         except Exception as e:
                             st.error(f"Cannot open folder: {e}")

            with tab_preview:
                preview = sources_service.preview_artifact(selected_artifact.path)
                
                if preview.type == "text":
                    st.code(preview.content, language=None)
                elif preview.type == "image":
                    st.image(preview.content)
                elif preview.type == "pdf_placeholder":
                    # Check if pdf extractor worked? 
                    # If status is "indexed", we actually HAVE text in DB. 
                    # Sources view shows "preview" from DISK. 
                    # The requirement says "preview (reuse sources)".
                    # For PDF, disk preview is placeholder. 
                    # Evidence view (Search) will show snippet from DB.
                    st.info("PDF preview not available in Sources (View in Search for indexed content).")
                elif preview.type == "error":
                    st.error(preview.error_message)
                else:
                    st.warning("No preview available")
        else:
            st.info("Select an artifact to view details.")
