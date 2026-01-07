
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
            # Pass full config or just features? Registry expects dict. 
            # We already have `config` dict (from app_state.config.get("data")).
            # features is inside it. 
            # Let's pass `features` section specifically or full config?
            # Registry uses it for flags. Better pass `features`.
            # Pass full config (P0 Fix for PROD)
            # IndexingService -> Registry -> ImageExtractor needs 'paths' for tools.
            indexer = IndexingService(repo, config)
            
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
        
        # Status Filter
        status_options = ["All", "Needs Indexing", "Indexed", "Failed", "New", "Dirty"]
        filter_status = st.selectbox("Status", status_options)
        
        ext_options = ["all", ".docx", ".pdf", ".txt", ".md", ".html", ".mht", ".png", ".jpg"]
        filter_ext = st.selectbox("Extension", ext_options)

    # --- Wrapper for caching (P1 Performance) ---
    @st.cache_data(ttl=5)
    def cached_scan(dir_path):
        if indexer:
            return indexer.scan_workspace(dir_path)
        return []

    # 1. Fetch File List & Status
    all_files = cached_scan(ingest_dir)
    
    # Filter Logic
    artifacts = []
    for f in all_files:
        # Status Filter
        s = f["status"]
        if filter_status == "Needs Indexing" and s not in ("NEW", "DIRTY"):
            continue
        if filter_status == "Indexed" and s != "INDEXED":
            continue
        if filter_status == "Failed" and s not in ("FAILED", "NOT_EXTRACTABLE"):
            continue
        if filter_status == "New" and s != "NEW":
            continue
        if filter_status == "Dirty" and s != "DIRTY":
            continue
            
        # Ext filter
        if filter_ext != "all" and f["ext"] != filter_ext:
            continue
        # Search filter
        if search_term and search_term.lower() not in f["filename"].lower():
            continue
        artifacts.append(f)

    # Action Counters
    needed_count = len([f for f in all_files if f["status"] in ("NEW", "DIRTY")])

    # --- ACTIONS ---
    if indexer:
        c_top1, c_top2, c_top3 = st.columns([3, 1, 1])
        with c_top2:
            if needed_count > 0:
                if st.button(f"Index Needed ({needed_count})", type="primary", help="Process NEW and DIRTY files"):
                    with st.spinner("Indexing updates..."):
                        updates = indexer.index_needed(ingest_dir)
                        count = 0
                        progress_bar = st.progress(0)
                        for i, item in enumerate(updates):
                            indexer.index_file(item["path"])
                            count += 1
                            if updates:
                                progress_bar.progress((i + 1) / len(updates))
                        progress_bar.empty()
                        
                    st.success(f"Indexed {count} files.")
                    st.cache_data.clear()
                    st.rerun()
            else:
                 # Disabled state to show "Clean"
                 st.button("Index Needed (0)", disabled=True)
                 
        with c_top3:
             # "Index All" is fallback, not default
             if st.button("Index All"):
                with st.spinner("Indexing all files..."):
                    stats = indexer.index_all(ingest_dir)
                st.success(f"Indexed: {stats.get('indexed', 0)}, Failed: {stats.get('failed', 0)}")
                st.cache_data.clear()
                st.rerun()

    # --- Main Area ---
    st.subheader("Ingestion Inbox")
    
    if not artifacts:
        st.info("No artifacts found matching criteria.")
        return

    # 2. Layout: List (Left) | Detail/Preview (Right)
    col_list, col_detail = st.columns([2, 3])
    
    selected_artifact = None
    
    # --- Left: List ---
    with col_list:
        c_list_head, c_refresh = st.columns([3, 1])
        c_list_head.caption(f"Found {len(artifacts)} items")
        if c_refresh.button("Refresh"):
            st.cache_data.clear()
            st.rerun()
        
        # Pagination (P1 Scalability)
        PAGE_SIZE = 50
        total_pages = max(1, (len(artifacts) + PAGE_SIZE - 1) // PAGE_SIZE)
        
        # State key for page
        if "sources_page" not in st.session_state:
            st.session_state["sources_page"] = 1
            
        page = st.session_state["sources_page"]
        if page > total_pages: page = total_pages
        
        # Paginator UI
        if total_pages > 1:
            c_prev, c_page, c_next = st.columns([1, 2, 1])
            if c_prev.button("Prev", disabled=page==1):
                st.session_state["sources_page"] = page - 1
                st.rerun()
            c_page.markdown(f"<center>Page {page} of {total_pages}</center>", unsafe_allow_html=True)
            if c_next.button("Next", disabled=page==total_pages):
                st.session_state["sources_page"] = page + 1
                st.rerun()
        
        start_idx = (page - 1) * PAGE_SIZE
        end_idx = start_idx + PAGE_SIZE
        current_batch = artifacts[start_idx:end_idx]
        
        with st.container():
            for i, art in enumerate(current_batch):
                safe_key = hashlib.md5(art["path"].encode('utf-8')).hexdigest()
                
                # Determine status
                status = art["status"]
                status_color = {
                    "NEW": "blue",
                    "DIRTY": "orange",
                    "INDEXED": "green",
                    "FAILED": "red",
                    "NOT_EXTRACTABLE": "grey"
                }.get(status, "grey")
                
                # Metadata for Badge
                mod_time = datetime.datetime.fromtimestamp(art['modified_at']).strftime('%Y-%m-%d %H:%M')
                
                # Card Row
                c1, c2, c3 = st.columns([3, 1, 1])
                
                # Name & Badge (Rich HTML)
                # Showing filename, status badge, and modified time line
                c1.markdown(
                    f"**{art['filename']}**<br>"
                    f"<span style='color:{status_color}; font-size:0.8em'>● {status}</span> "
                    f"<span style='color:grey; font-size:0.7em'>| {mod_time} | {art['ext']}</span>", 
                    unsafe_allow_html=True
                )
                
                # View Button
                if c2.button("View", key=f"view_{safe_key}"):
                    st.session_state["selected_artifact_path"] = art["path"]
                
                # Index Button
                if indexer:
                    btn_label = "Update" if status in ("DIRTY", "INDEXED") else "Index"
                    # Help tooltip shows granular details
                    if c3.button(btn_label, key=f"idx_{safe_key}", help=f"Re-index {art['filename']}"):
                        with st.spinner(f"Indexing {art['filename']}..."):
                            res = indexer.index_file(art["path"])
                        if res == "indexed":
                            st.toast(f"Indexed {art['filename']}", icon="✅")
                        elif res == "not_extractable":
                            st.toast(f"Not extractable", icon="⚠️")
                        else:
                            st.toast(f"Failed", icon="❌")
                        st.cache_data.clear()
                        st.rerun()
                
                st.divider()

        # Check selection
        selected_path = st.session_state.get("selected_artifact_path")
        if selected_path:
            selected_artifact = next((a for a in artifacts if a["path"] == selected_path), None)

    # --- Right: Detail & Preview ---
    with col_detail:
        if selected_artifact:
            st.markdown(f"### {selected_artifact['filename']}")
            
            tab_preview, tab_meta = st.tabs(["Preview", "Metadata"])
            
            with tab_meta:
                 # Helper to manage hash state
                 hash_key = f"hash_{selected_artifact['path']}"
                 current_hash = st.session_state.get(hash_key)
                 
                 status = selected_artifact.get("status", "UNKNOWN")
                 
                 meta_dict = {
                     "Path": selected_artifact["path"],
                     "Size": f"{selected_artifact['size_bytes']} bytes",
                     "Modified": datetime.datetime.fromtimestamp(selected_artifact['modified_at']).isoformat(),
                     "Type": selected_artifact["ext"],
                     "Status": status
                 }
                 
                 if current_hash:
                     meta_dict["SHA256"] = current_hash
                     # Save to DB if calculated
                     if repo:
                         try:
                            repo_meta = selected_artifact.copy()
                            repo_meta["sha256"] = current_hash
                            repo.upsert_artifact(repo_meta)
                         except Exception as e:
                             pass 
                 else:
                     meta_dict["SHA256"] = "Not calculated"
                     
                 st.json(meta_dict)
                 
                 if not current_hash:
                     if st.button("Compute Hash"):
                         try:
                             with open(selected_artifact["path"], "rb") as f:
                                 digest = hashlib.sha256(f.read()).hexdigest()
                             st.session_state[hash_key] = digest
                             st.rerun()
                         except Exception as e:
                             st.error(f"Error computing hash: {e}")

                 if os.name == 'nt':
                     if st.button("Open Folder"):
                         try:
                             st.info("Opening Explorer (check taskbar)...")
                             os.startfile(os.path.dirname(selected_artifact["path"]))
                         except Exception as e:
                             st.error(f"Cannot open folder: {e}")

            with tab_preview:
                preview = sources_service.preview_artifact(selected_artifact["path"])
                
                # Check for extracted text fallback (if indexed)
                extracted_text = None
                if selected_artifact.get("id") and repo:
                    extracted_text = repo.get_text_content(selected_artifact["id"])

                # Logic: Show Native Preview OR Extracted Text
                if preview.type == "text":
                    st.code(preview.content, language=None)
                elif preview.type == "image":
                    st.image(preview.content)
                elif preview.type == "pdf_placeholder" or (preview.type == "error" and "not supported" in preview.error_message):
                    # Try to show extracted text
                    if extracted_text:
                        st.info("Previewing Extracted Text (Structure may be lost)")
                        st.text_area("Content", extracted_text, height=600)
                    elif preview.type == "pdf_placeholder":
                        st.info("PDF preview not available. Text content will appear here after indexing.")
                    else:
                        st.warning(f"No preview: {preview.error_message}")
                elif preview.type == "error":
                     st.error(preview.error_message)
                
                # If we have extracted text but the file type was weird, show it anyway
                if extracted_text and preview.type not in ("text", "image", "pdf_placeholder"):
                     with st.expander("View Extracted Text"):
                         st.text_area("ExtractedContent", extracted_text, height=400)
        else:
            st.info("Select an artifact to view details.")
