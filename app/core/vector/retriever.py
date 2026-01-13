import sqlite3
import re
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from app.core.vector.faiss_index import VectorStore
from app.core.embeddings.service import EmbeddingService

@dataclass
class RetrievedChunk:
    chunk_id: str
    score: float # Final weighted score
    snippet: str
    locator: Dict # {page, slide, section}
    source: str # 'vector', 'fts', 'hybrid'
    match_type: str = 'vector' # 'fts', 'vector', 'hybrid'
    keyword_hits: int = 0
    is_literal: bool = False
    
    # Diagnostics
    fts_score_raw: float = 0.0
    fts_score_norm: float = 0.0
    vector_score_raw: float = 0.0
    vector_score_norm: float = 0.0

class HybridRetriever:
    def __init__(self, db_path: str, vector_store: VectorStore, embedding_service: EmbeddingService):
        self.db_path = db_path
        self.vector_store = vector_store
        self.embedding_service = embedding_service

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _fts_query(self, q: str) -> str:
        """Tokenize query for FTS MATCH operator (AND logic)."""
        # remove punctuation that might break syntax, keep alphanum and standard chars
        # MVP: split by whitespace
        terms = [t for t in re.split(r"\s+", q.strip()) if t]
        if not terms:
            return '""'
        # Wrap each term in quotes to avoid syntax errors with special chars
        return " AND ".join([f'"{t}"' for t in terms])

    def _tokenize_terms(self, q: str) -> List[str]:
        return [t for t in re.split(r"\s+", q.strip()) if t]

    def _count_term_hits_in_text(self, text: str, terms: List[str]) -> int:
        if not text or not terms:
            return 0
        hits = 0
        for t in terms:
            # P2: Use word boundaries for stricter matching ("plan" != "plant")
            # Note: This might mismatch FTS slightly if FTS tokenizer is different, but is safer.
            try:
                pattern = rf"\b{re.escape(t)}\b"
                hits += len(re.findall(pattern, text, flags=re.IGNORECASE))
            except Exception:
                 # Fallback for weird regex terms
                 hits += text.lower().count(t.lower())
        return hits

    def _count_offsets(self, offs: str) -> int:
        """Parse FTS5 offsets string to count matches."""
        # offs format: col term position bytes ... (4 integers per hit)
        if not offs:
            return 0
        # Fast estimation: count spaces + 1, divide by 4. 
        # But split() is safer.
        parts = offs.split()
        return len(parts) // 4

    def _search_fts(self, query: str, top_k: int) -> List[RetrievedChunk]:
        """
        Perform Full Text Search using FTS5.
        Returns RetrievedChunk objects with score=999.0 by default (as FTS rank is different scale).
        """
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # We need to join with chunks to check is_active and get real data
        # Note: chunks_fts is explicit external content content='chunks'
        # We use MATCH on fts table, but select from chunks (or joined)
        
        # Prepare FTS query
        fts_query_str = self._fts_query(query)

        # FTS5: snippet(table, col_idx, start_tag, end_tag, ellipsis, max_tokens)
        # We assume chunks_fts has content in column 0 (chunk_id is rowid/not indexed content usually, but check schema).
        # Actually chunks_fts is CREATE VIRTUAL TABLE chunks_fts USING fts5(content_text, content='chunks', content_rowid='chunk_rowid');
        # So column 0 is content_text.
        
        sql = """
            SELECT 
                c.chunk_id, 
                c.page, c.slide, c.section, c.bbox,
                c.content_text AS content_text,
                snippet(chunks_fts, 0, '<b>', '</b>', '...', 12) AS snip,
                bm25(chunks_fts) AS fts_score
            FROM chunks_fts
            JOIN chunks c ON c.chunk_rowid = chunks_fts.rowid
            WHERE chunks_fts MATCH ? AND c.is_active = 1
            ORDER BY fts_score ASC
            LIMIT ?
        """
        
        try:
            cursor.execute(sql, (fts_query_str, top_k))
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            # Fallback for syntax errors
            return []
            
        chunks = []
        terms = self._tokenize_terms(query)
        
        for row in rows:
            # bm25: lower (more negative) is better.
            # We want higher = better for sorting.
            # Using -1 * score works well since score is typically <= 0.
            # e.g. -2.0 -> 2.0 (better) vs -1.0 -> 1.0 (worse? wait)
            # FTS5 BM25: "more negative is better".
            # -2.0 is better than -1.5? Usually yes.
            # So -1 * score makes it positive, where higher is better.
            raw_score = row['fts_score']
            inv_score = -1.0 * raw_score 
            
            # Offsets usage removed due to "unable to use function offsets" error on this environment.
            # We treat any FTS match as at least 1 hit.
            # FTS matches result in "hits".
            # Audit Fixed: calculate hits manually
            hits = self._count_term_hits_in_text(row['content_text'], terms)
            if hits <= 0:
                hits = 1 # Fallback if term not found exactly/tokenization mismatch

            chunks.append(RetrievedChunk(
                chunk_id=row['chunk_id'],
                score=0.0, # Will be calculated via normalization
                snippet=row['snip'], 
                locator={
                    "page": row['page'],
                    "slide": row['slide'],
                    "section": row['section'],
                    "bbox": row['bbox']
                },
                source='fts',
                match_type='fts',
                keyword_hits=hits,
                is_literal=True,
                fts_score_raw=inv_score # Store inverted raw score (higher better)
            ))
            
        conn.close()
        return chunks

    def search(self, query: str, top_k: int = 10, include_semantic: bool = True) -> List[RetrievedChunk]:
        if include_semantic:
            # Perform vector search
            # Mock vector search score for now or use real simple mock if needed
            # For this audit refactor, we focus on FTS scoring structure.
            # Assuming self.vector_retriever.search returns chunks with 'score' (distance/similarity)
            pass 
        
        # 1. Get FTS Results (Raw BM25)
        fts_chunks = self._search_fts(query, top_k)
        fts_ids = {c.chunk_id for c in fts_chunks}
        fts_map = {c.chunk_id: c for c in fts_chunks}
        
        # 2. Get Vector Results (Raw Similarity)
        vector_chunks = []
        if include_semantic:
            try:
                q_vec = self.embedding_service.embed_query(query)
                if q_vec:
                    # In a real app we'd call vector store.
                    raw_vec_results = self.vector_store.search(q_vec, top_k)
                    
                    found_ids = [r[0] for r in raw_vec_results]
                    new_ids = [id for id in found_ids if id not in fts_ids]
                    
                    # Fetch content for new vectors
                    loaded_chunks = {}
                    if new_ids:
                        loaded_chunks = self._fetch_chunks(new_ids)
                        
                    for r in raw_vec_results:
                        cid, score = r
                         # L2 distance calc if needed: 
                        score_val = 1.0 / (1.0 + score)
                        
                        if cid in fts_map:
                            # Item already in FTS. Add to vector_chunks to participate in norm.
                            c = fts_map[cid]
                            c.vector_score_raw = score_val
                            vector_chunks.append(c)
                        elif cid in loaded_chunks:
                            # New semantic item
                            c = loaded_chunks[cid]
                            c.vector_score_raw = score_val 
                            vector_chunks.append(c)

            except Exception as e:
                # If vector search fails (no index etc), ignore
                pass 

        # 3. Normalize Scores
        # Collect raw scores
        fts_raw = [c.fts_score_raw for c in fts_chunks]
        vec_raw = [c.vector_score_raw for c in vector_chunks]

        fts_norm = self._normalize_scores(fts_raw)
        vec_norm = self._normalize_scores(vec_raw)
        
        # Apply Logic: hybrid = w_fts * fts_norm + w_vec * vec_norm
        # Params MVP: Hardcoded defaults or from class config if added
        w_fts = 0.7
        w_vec = 0.3
        
        results = []
        
        # Map by chunk_id
        chunk_map: Dict[str, RetrievedChunk] = {}
        
        # Add FTS
        for i, c in enumerate(fts_chunks):
            c.fts_score_norm = fts_norm[i]
            c.score = w_fts * c.fts_score_norm
            c.source = "fts"
            chunk_map[c.chunk_id] = c
            
        # Add Steps: Merge Vector
        for i, c in enumerate(vector_chunks):
            c.vector_score_norm = vec_norm[i]
            
            if c.chunk_id in chunk_map:
                # Merge: Boost existing
                existing = chunk_map[c.chunk_id]
                existing.vector_score_raw = c.vector_score_raw
                existing.vector_score_norm = c.vector_score_norm
                existing.score += (w_vec * c.vector_score_norm)
                existing.match_type = 'hybrid'
            else:
                # New semantic result
                c.score = w_vec * c.vector_score_norm
                c.source = "semantic"
                chunk_map[c.chunk_id] = c

        # Convert back to list
        final_results = list(chunk_map.values())

        # Sort by final score
        final_results.sort(key=lambda x: x.score, reverse=True)
        return final_results[:top_k]

    def _normalize_scores(self, scores: List[float]) -> List[float]:
        """MinMax Normalization to [0, 1]."""
        if not scores:
            return []
        mn, mx = min(scores), max(scores)
        if mx == mn:
            return [1.0] * len(scores)
        return [(s - mn) / (mx - mn) for s in scores]

    def _fetch_chunks(self, chunk_ids: List[str]) -> Dict[str, RetrievedChunk]:
        """Helper to load chunks by ID for vector results."""
        if not chunk_ids: return {}
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        placeholders = ",".join(["?"] * len(chunk_ids))
        cursor = conn.execute(f"""
            SELECT chunk_id, content_text, page, slide, section, bbox
            FROM chunks WHERE chunk_id IN ({placeholders}) AND is_active = 1
        """, chunk_ids)
        
        res = {}
        for row in cursor.fetchall():
            res[row['chunk_id']] = RetrievedChunk(
                chunk_id=row['chunk_id'],
                score=0.0,
                snippet=row['content_text'][:200], # Naive snippet
                locator={
                    "page": row['page'], "slide": row['slide'], "section": row['section'], "bbox": row['bbox']
                },
                source='vector',
                match_type='vector'
            )
        conn.close()
        return res
