
import streamlit as st
import datetime
import os
from app.ui.state import AppState
from app.core.artifacts_repo import ArtifactsRepo
from app.core.search.service import SearchService
from app.services import sources_service

def render(app_state: AppState):
    st.title("Search")
    
    config = app_state.config.get("data", {})
    features = config.get("features", {})
    
    # Feature Flag Check
    if not features.get("search_enabled", True): # Default to true if missing? Or strict False?
        # Requirement: "Brak flagi = Search ukryty". So strict False.
        # But wait, I just added it to general.yaml. 
        # If running on old config without it, it might be missing.
        # Let's assume default False for safety as per "Brak flagi = ukryty".
        pass 
        
    if not features.get("search_enabled", False):
        st.warning("Search feature is disabled in configuration.")
        return

    db_path = app_state.config.get("db_path")
    
    if "db_init_error" in app_state.config:
        st.error(f"Database Error: {app_state.config['db_init_error']}")
        return

    if not db_path:
        st.warning("Database not configured. Search disabled.")
        return

    # Initialize Repo & Service
    # Ideally Service is initialized once in AppState, but flexible here for MVP.
    try:
        repo = ArtifactsRepo(db_path)
        search_service = SearchService(repo, app_state.config)
        
        # Check for Stale Index (P1)
        # We need ingest_dir to check staleness
        ingest_dir = None
        if "paths" in config and "ingest_dir" in config["paths"]:
             ingest_dir = config["paths"]["ingest_dir"]
        
        if ingest_dir and os.path.exists(ingest_dir):
             from app.core.indexing_service import IndexingService
             # Pass full config (Fix: v0.3.6)
             indexer = IndexingService(repo, config)
             # Optimization: This hits FS. Cache it? 
             # sources.py caches it. We can cache here too.
             @st.cache_data(ttl=60)
             def check_neeeded(d):
                 return len(indexer.index_needed(d))
             
             needed = check_neeeded(ingest_dir)
             if needed > 0:
                 st.warning(f"Search results may be incomplete – {needed} files pending indexing. Check [Sources] page.")

    except Exception as e:
        st.error(f"Failed to connect to DB: {e}")
        return

    # --- Search Bar & Filters ---
    c_search, c_filter = st.columns([3, 1])
    
    # Persistence Logic
    if "saved_search_query" in st.session_state and "search_query" not in st.session_state:
        st.session_state["search_query"] = st.session_state["saved_search_query"]
        
    def update_query_state():
        st.session_state["saved_search_query"] = st.session_state.search_query

    with c_search:
        query = st.text_input("Query", placeholder="Type to search content or filename...", key="search_query", on_change=update_query_state)
        
    with c_filter:
        st.write("") # Spacer
        include_semantic = st.checkbox("Include semantic results", value=False, help="If unchecked, only text matches will be shown.")

    # --- Results ---
    results = [] # Type: List[SearchEvidence]
    
    if query:
        # Call Service (Entry Point)
        raw_results = search_service.search(query, limit=100, include_semantic=include_semantic)
        
        # --- Grouping Logic (UX Improvement) ---
        grouped_results = {} # path -> {primary: SearchEvidence, literals: List[SearchEvidence], semantic: List[SearchEvidence]}
        seen_contents = set() # For deduplication
        
        for ev in raw_results:
            # Simple content-based deduplication per file
            content_hash = f"{ev.source_path}:{ev.snippet}"
            if content_hash in seen_contents:
                continue
            seen_contents.add(content_hash)
            
            # Check if literal (was flagged in retriever or check again)
            # Use backend truth
            is_lit = ev.is_literal
            # Or match_type checks? 
            # match_type can be 'hybrid', 'fts', 'vector'
            
            if ev.source_path not in grouped_results:
                grouped_results[ev.source_path] = {"primary": ev, "literals": [], "semantic": []}
            
            # Determine which list it goes to based on is_lit
            # Note: A hybrid chunk is both literal and semantic usually, but if it has bold tags it's literal enough.
            if is_lit:
                grouped_results[ev.source_path]["literals"].append(ev)
            else:
                grouped_results[ev.source_path]["semantic"].append(ev)
                
            # Update primary to highest score
            if ev.score > grouped_results[ev.source_path]["primary"].score:
                 grouped_results[ev.source_path]["primary"] = ev
        
        # Sort files by highest primary score
        results = sorted(list(grouped_results.values()), key=lambda x: x["primary"].score, reverse=True)
            
    if not results and query:
        st.info("No results found.")
    elif not query:
        st.info("Type something to search...")

    # --- Results Layout ---
    col_res, col_prev = st.columns([2, 3])
    
    selected_evidence = None
    
    with col_res:
        if results:
            st.caption(f"Found matches across {len(results)} files")
            
            for i, group in enumerate(results):
                primary_ev = group["primary"]
                literals = group["literals"]
                semantics = group["semantic"]
                
                label = f"{i+1}. {os.path.basename(primary_ev.source_path)}"
                counts = []
                
                # Use total count from backend for literal truth
                lit_hits = primary_ev.keyword_hits_in_file 
                lit_chunks = primary_ev.keyword_chunks_in_file
                
                sem_count = len(semantics)
                
                if lit_hits > 0: 
                    counts.append(f"{lit_hits} keyword matches")
                elif lit_chunks > 0:
                    counts.append(f"{lit_chunks} keyword chunks")
                
                if sem_count > 0: counts.append(f"{sem_count} related")
                
                if counts:
                    label += f" ({', '.join(counts)})"
                    
                with st.expander(label, expanded=(i==0)):
                    st.caption(f"Path: `{primary_ev.source_path}`")
                    
                    # Show Literal Matches First (Top 5 to avoid spam)
                    if literals:
                        st.markdown("**Top Keyword Matches:**")
                        # Content preview: Trust the snippet from backend (FTS) or raw text
                        # Auditor P2: Do NOT apply regex highlighting here to avoid misleading "matches" 
                        # that weren't actually found by FTS.
                        display_lits = literals[:5]
                        for j, ev in enumerate(display_lits):
                            # Replace <b> with markdown bold or custom HTML
                            
                            inner_col1, inner_col2 = st.columns([4, 1])
                            with inner_col1:
                                 st.markdown(f"_{ev.snippet}_")
                            with inner_col2:
                                 if st.button("Preview", key=f"prev_lit_{i}_{j}_{ev.artifact_id}"):
                                     st.session_state["search_selected_id"] = ev.artifact_id
                        
                        if len(literals) > 5:
                            st.caption(f"Showing 5 of {len(literals)} chunks. Click Preview to see full document highlights.")
                            
                        if semantics: st.divider()

                    # Show Semantic Matches
                    if semantics:
                        st.markdown("**Semantic Recommendations:**")
                        display_sems = semantics[:3]
                        for j, ev in enumerate(display_sems):
                            snippet = ev.snippet.replace("<b>", "**").replace("</b>", "**")
                            inner_col1, inner_col2 = st.columns([4, 1])
                            with inner_col1:
                                 st.markdown(f"_{snippet}_")
                            with inner_col2:
                                 if st.button("Preview", key=f"prev_sem_{i}_{j}_{ev.artifact_id}"):
                                     st.session_state["search_selected_id"] = ev.artifact_id
                        
                        if len(semantics) > 3:
                             st.caption(f"and {len(semantics)-3} more semantic matches...")
                                     
    # Check selection
    sel_id = st.session_state.get("search_selected_id")
    if sel_id and results:
        # Search in all groups
        all_ev = []
        for g in results:
            all_ev.extend(g["literals"])
            all_ev.extend(g["semantic"])
        selected_evidence = next((ev for ev in all_ev if ev.artifact_id == sel_id), None)
        
    with col_prev:
        if selected_evidence:
            st.markdown(f"### {os.path.basename(selected_evidence.source_path)}")
            
            if os.path.exists(selected_evidence.source_path):
                preview = sources_service.preview_artifact(selected_evidence.source_path)
                
                # Fallback: Get Extracted Text if preview fails
                extracted_text = None
                # We have artifact_id in selected_evidence
                if repo and selected_evidence.artifact_id:
                     extracted_text = repo.get_text_content(selected_evidence.artifact_id)
                
                if preview.type == "text" or extracted_text:
                    # Prefer extracted DB text if available (shows what is actually indexed, including OCR/CSV cleanup)
                    content_to_show = extracted_text if extracted_text else preview.content
                    
                    # Highlighting (Case Insensitive)
                    if query and content_to_show:
                        import re
                        # P2.4: Tokenize query and highlight individual tokens (OR logic)
                        # Split by whitespace, filter empty
                        tokens = [t for t in re.split(r"\s+", query.strip()) if t]
                        
                        if tokens:
                             # Escape each token and join with |
                             pattern_str = "|".join([re.escape(t) for t in tokens])
                             pattern = re.compile(pattern_str, re.IGNORECASE)
                             
                             # Highlight with yellow background using HTML in Markdown
                             # Using Streamlit :background[text] syntax (newer) or HTML
                             highlighted = pattern.sub(lambda m: f"**:{'orange'}[{m.group(0)}]**", content_to_show)
                             
                             st.markdown("### Content Preview (Highlighted)")
                             st.markdown(highlighted)
                        else:
                             st.code(content_to_show)
                    else:
                        st.code(content_to_show)
                        
                elif preview.type == "image":
                    st.image(preview.content)
                elif preview.type == "pdf_placeholder":
                     # This branch might be unreachable due to fallback logic above, but keep for safety
                     st.info("PDF preview not available.")
                else:
                    st.warning(preview.error_message)
            else:
                st.error("File not found on disk.")
                
            st.write("Evidence:")
            st.json({
                "Artifact ID": selected_evidence.artifact_id,
                "Path": selected_evidence.source_path,
                "Type": selected_evidence.artifact_type,
                "Mode": selected_evidence.search_mode
            })
            
            def go_to_sources():
                 st.session_state["selected_artifact_path"] = selected_evidence.source_path
                 st.session_state["navigation_selection"] = "Sources"

            st.button("Open in Sources", on_click=go_to_sources)
        else:
             if query:
                st.info("Select a result to preview.")

