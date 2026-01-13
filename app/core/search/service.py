from typing import List, Dict, Any
from .models import SearchEvidence
from app.core.artifacts_repo import ArtifactsRepo
from app.core.vector.retriever import HybridRetriever
from app.core.vector.faiss_index import VectorStore
from app.core.embeddings.service import EmbeddingService
from app.core.embeddings.repository import EmbeddingRepository
import re

class SearchService:
    def __init__(self, artifacts_repo: ArtifactsRepo, config: Dict[str, Any]):
        self.repo = artifacts_repo
        self.config = config
        
        # Initialize Hybrid Retriever Dependencies
        # (Ideal world: Dependency Injection via State, but MVP here)
        # Try to get db_path from wrapper or nested data
        db_path = config.get("db_path") or config.get("data", {}).get("paths", {}).get("db_path") or "data/project_copilot.db"
        index_dir = config.get("data", {}).get("paths", {}).get("index", "data/index")
        
        # Fallback for debug scripts (top-level paths)
        if not config.get("db_path") and "paths" in config:
             db_path = config.get("paths", {}).get("db_path") or db_path
             index_dir = config.get("paths", {}).get("index") or index_dir
             
        # Prioritize Repo's DB path if available (crucial for tests)
        if hasattr(self.repo, 'db_path') and self.repo.db_path:
            db_path = self.repo.db_path
        
        self.emb_repo = EmbeddingRepository(db_path)
        self.emb_service = EmbeddingService(self.emb_repo, config)
        self.vector_store = VectorStore(index_dir)
        
        self.retriever = HybridRetriever(db_path, self.vector_store, self.emb_service)

    def search(self, query: str, limit: int = 20, include_semantic: bool = None) -> List[SearchEvidence]:
        """
        Searches artifacts using Hybrid Retrieval (Vector + FTS on Chunks).
        """
        if not query.strip():
            return []

        # Determine semantic search usage
        if include_semantic is None:
            config_features = self.config.get("features", {})
            include_semantic = config_features.get("semantic_search", True)
            
        retrieved_chunks = self.retriever.search(query, top_k=limit, include_semantic=include_semantic)
        
        chunk_ids = [rc.chunk_id for rc in retrieved_chunks]
        if not chunk_ids:
            return []
            
        # 2. Extract Artifact Metadata & Total Counts
        import sqlite3
        db_path = self.config.get("db_path") or self.config.get("paths", {}).get("db", "data/project_copilot.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Get unique artifact IDs found
        unique_art_ids = list(set(rc.artifact_id for rc in retrieved_chunks if hasattr(rc, 'artifact_id'))) 
        # Wait, RetrievedChunk has artifact_id? No, it has chunk_id. 
        # I need to get meta_map first.
        
        placeholders = ','.join('?' for _ in chunk_ids)
        cursor = conn.execute(f"""
            SELECT c.chunk_id, c.artifact_id, a.path, a.ext 
            FROM chunks c
            JOIN artifacts a ON c.artifact_id = a.id
            WHERE c.chunk_id IN ({placeholders})
        """, chunk_ids)
        
        meta_map = {row['chunk_id']: row for row in cursor.fetchall()}
        
        # Calculate Total Literal Hits per Artifact (Using FTS)
        art_ids = list(set(m['artifact_id'] for m in meta_map.values()))
        
        file_stats = {} # aid -> {hits: int, chunks: int}
        
        if art_ids:
             # FTS Query again to get reliable counts per artifact
             # "SELECT artifact_id, c.content_text ..."
             # Audit Fixed: Offset unavailable, so we fetch content_text and count in python logic.
             fts_query_str = self.retriever._fts_query(query)
             placeholders_arts = ','.join('?' for _ in art_ids)
             
             # Fetch all matching chunks for these artifacts
             stats_sql = f"""
                SELECT c.artifact_id, c.content_text
                FROM chunks_fts
                JOIN chunks c ON c.chunk_rowid = chunks_fts.rowid
                WHERE chunks_fts MATCH ? 
                  AND c.artifact_id IN ({placeholders_arts})
                  AND c.is_active = 1
             """
             
             try:
                 params = [fts_query_str] + art_ids
                 cursor_stats = conn.execute(stats_sql, params)
                 
                 terms = self.retriever._tokenize_terms(query)
                 
                 for row in cursor_stats.fetchall():
                     aid = row['artifact_id']
                     if aid not in file_stats:
                         file_stats[aid] = {"hits": 0, "chunks": 0}
                     
                     file_stats[aid]["chunks"] += 1
                     h = self.retriever._count_term_hits_in_text(row['content_text'], terms)
                     file_stats[aid]["hits"] += h
                     
             except Exception as e:
                 # print(f"Error stats: {e}")
                 pass

        conn.close()
        
        evidence_list = []
        for rc in retrieved_chunks:
            if rc.chunk_id not in meta_map:
                continue
                
            meta = meta_map[rc.chunk_id]
            aid = meta['artifact_id']
            stats = file_stats.get(aid, {"hits": 0, "chunks": 0})
            
            # Format Snippet with Locator
            loc_str = ""
            if rc.locator:
                parts = []
                if 'page' in rc.locator and rc.locator['page']: parts.append(f"Page {rc.locator['page']}")
                if 'slide' in rc.locator and rc.locator['slide']: parts.append(f"Slide {rc.locator['slide']}")
                if parts: loc_str = f" [{', '.join(parts)}]"
            
            final_snippet = f"{rc.snippet}{loc_str}"
            
            ev = SearchEvidence(
                artifact_id=aid,
                artifact_type=meta['ext'],
                source_path=meta['path'],
                snippet=final_snippet,
                score=rc.score,
                search_mode=f"{rc.match_type}",
                match_type=rc.match_type,
                is_literal=rc.is_literal,
                keyword_hits_in_chunk=getattr(rc, 'keyword_hits', 0),
                keyword_hits_in_file=stats['hits'],
                keyword_chunks_in_file=stats['chunks'],
                total_file_matches=stats['hits'] # Compatibility
            )
            evidence_list.append(ev)
            
        return evidence_list
