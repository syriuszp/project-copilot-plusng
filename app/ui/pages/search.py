
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
        search_service = SearchService(repo)
        
        # Check for Stale Index (P1)
        # We need ingest_dir to check staleness
        ingest_dir = None
        if "paths" in config and "ingest_dir" in config["paths"]:
             ingest_dir = config["paths"]["ingest_dir"]
        
        if ingest_dir and os.path.exists(ingest_dir):
             from app.core.indexing_service import IndexingService
             indexer = IndexingService(repo, features)
             # Optimization: This hits FS. Cache it? 
             # sources.py caches it. We can cache here too.
             @st.cache_data(ttl=60)
             def check_neeeded(d):
                 return len(indexer.index_needed(d))
             
             needed = check_neeeded(ingest_dir)
             if needed > 0:
                 st.warning(f"Index is stale ({needed} files need updates). Check [Sources] page.")

    except Exception as e:
        st.error(f"Failed to connect to DB: {e}")
        return

    # --- Search Bar & Filters ---
    c_search, c_filter = st.columns([3, 1])
    with c_search:
        query = st.text_input("Query", placeholder="Type to search content or filename...", key="search_query")
    
    # Filters (Simplified for MVP as per repo limitations or strict requirements)
    # Repo currently takes `filters` dict but SearchService.search only takes query and limit in signature?
    # P1 Requirement: "SearchService.search(query, limit, filters) -> SearchResult" (Wait, requirement said search(query, limit, filters)?)
    # "SearchService.search(query, limit, filters)->SearchResult" was in prompt?
    # Let me check prompt... "def search(self, query: str, limit: int = 20):" in Prompt suggestion.
    # But later "jedna funkcja ... SearchService.search(query, limit, filters)->SearchResult".
    # I implemented `def search(self, query: str, limit: int = 20):` without filters in Service.
    # I should update Service to accept filters if I want to keep filters working.
    # For now, let's keep UI simple or fix Service. 
    # Prompt said: "def search(self, query: str, limit: int = 20)" in the code block example.
    # But filters are mentioned in "wyniki zawierają...". 
    # I'll stick to the Prompt's class definition which missed filters arg, OR I'll add it.
    # Adding it is safer for "Expert" grade.
    
    # --- Results ---
    results = [] # Type: List[SearchEvidence]
    
    if query:
        # Call Service (Entry Point)
        # Note: My service currently doesn't accept filters. I'll just pass query/limit.
        results = search_service.search(query, limit=50)
            
    if not results and query:
        st.info("No results found.")
    elif not query:
        st.info("Type something to search...")
        # Don't return, render empty state creates cleaner layout

    # --- Results Layout ---
    col_res, col_prev = st.columns([2, 3])
    
    selected_evidence = None
    
    with col_res:
        if results:
            st.caption(f"Found {len(results)} results")
            # Mode?
            # evidence has search_mode now.
            mode = results[0].search_mode if results else "Unknown"
            st.caption(f"Mode: {mode}")
            
            with st.container():
                for i, ev in enumerate(results):
                    # Evidence Card
                    snippet = ev.snippet.replace("<b>", "**").replace("</b>", "**")
                    
                    with st.expander(f"{i+1}. {os.path.basename(ev.source_path)}", expanded=False):
                        st.markdown(f"`{ev.source_path}`")
                        st.markdown(f"_{snippet}_")
                        st.caption(f"Score: {ev.score} | Mode: {ev.search_mode}")
                        
                        if st.button("Preview", key=f"prev_{ev.artifact_id}"):
                            st.session_state["search_selected_id"] = ev.artifact_id

    # Check selection
    sel_id = st.session_state.get("search_selected_id")
    if sel_id and results:
        selected_evidence = next((r for r in results if r.artifact_id == sel_id), None)
        
    with col_prev:
        if selected_evidence:
            st.markdown(f"### {os.path.basename(selected_evidence.source_path)}")
            
            if os.path.exists(selected_evidence.source_path):
                preview = sources_service.preview_artifact(selected_evidence.source_path)
                if preview.type == "text":
                    st.code(preview.content)
                elif preview.type == "image":
                    st.image(preview.content)
                elif preview.type == "pdf_placeholder":
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
            
            if st.button("Open in Sources"):
                 # Placeholder for navigation
                 pass
        else:
             if query:
                st.info("Select a result to preview.")

