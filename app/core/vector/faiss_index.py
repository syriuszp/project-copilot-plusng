try:
    import faiss
except ImportError:
    faiss = None
    import logging
    logging.getLogger(__name__).warning("FAISS not available. Vector search will fail if attempted.")

import json
import os
import numpy as np
import struct
import sqlite3
from typing import List, Tuple, Dict
from pathlib import Path

class VectorStore:
    def __init__(self, index_dir: str):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index = None
        self.mapping = [] # List of chunk_ids corresponding to FAISS IDs
        self.current_model_id = None

    def _get_paths(self, model_id: str) -> Tuple[Path, Path]:
        # sanitized model_id for filename
        safe_id = model_id.replace("/", "_").replace("\\", "_")
        index_path = self.index_dir / f"faiss_{safe_id}.index"
        mapping_path = self.index_dir / f"faiss_{safe_id}.mapping.json"
        return index_path, mapping_path

    def load_index(self, model_id: str):
        if self.current_model_id == model_id and self.index is not None:
            return

        index_path, mapping_path = self._get_paths(model_id)
        
        if index_path.exists() and mapping_path.exists():
            self.index = faiss.read_index(str(index_path))
            with open(mapping_path, 'r', encoding='utf-8') as f:
                self.mapping = json.load(f)
            self.current_model_id = model_id
        else:
            self.index = None
            self.mapping = []
            self.current_model_id = None

    def rebuild_from_db(self, db_path: str, model_id: str):
        """
        Wipes existing index/mapping and rebuilds from DB embeddings.
        ONLY includes is_active=1 chunks.
        """
        from contextlib import closing
        with closing(sqlite3.connect(db_path)) as conn:
            cursor = conn.cursor()
            
            # Join with chunks to filter active
            cursor.execute("""
                SELECT e.chunk_id, e.vector, e.dim 
                FROM chunk_embeddings e
                JOIN chunks c ON e.chunk_id = c.chunk_id
                WHERE e.model_id = ? AND c.is_active = 1
                ORDER BY c.created_at ASC
            """, (model_id,))
            
            rows = cursor.fetchall()
        
        if not rows:
            # Empty index
            self.index = None
            self.mapping = []
            self._save_index(model_id)
            return

        # Prepare data
        dim = rows[0][2]
        chunk_ids = []
        vectors = []
        
        for row in rows:
            chunk_id, blob, _ = row
            vector = struct.unpack(f'{dim}f', blob)
            chunk_ids.append(chunk_id)
            vectors.append(vector)
            
        # Build Index
        matrix = np.array(vectors).astype('float32')
        # L2 norm for cosine similarity? Usually default is L2 distance.
        # For Cosine, vectors should be normalized.
        # Assuming embedding provider returns normalized vectors or we do it here.
        # Let's use IndexFlatL2 for simplicity MVP.
        
        index = faiss.IndexFlatL2(dim)
        index.add(matrix)
        
        self.index = index
        self.mapping = chunk_ids
        self.current_model_id = model_id
        
        self._save_index(model_id)

    def upsert_or_rebuild(self, db_path: str, model_id: str, current_fingerprint: str):
        """
        Rebuilds index only if fingerprint changed or index missing.
        """
        _, _, fingerprint_path = self._get_paths_extended(model_id)
        
        # Check cache
        if self.index and self.current_model_id == model_id and fingerprint_path.exists():
            try:
                with open(fingerprint_path, 'r') as f:
                    saved = json.load(f)
                    if saved.get("fingerprint") == current_fingerprint:
                         print(f"VectorStore: Index up-to-date (fingerprint match). Skipping rebuild.")
                         return
            except Exception:
                pass # corruption or error, ignore and rebuild

        # Rebuild
        print(f"VectorStore: Rebuilding index (fingerprint change or missing).")
        self.rebuild_from_db(db_path, model_id)
        
        # Save new fingerprint
        with open(fingerprint_path, 'w') as f:
            json.dump({
                "model_id": model_id,
                "fingerprint": current_fingerprint,
                "updated_at": "now" # MVP
            }, f)

    def _get_paths_extended(self, model_id: str) -> Tuple[Path, Path, Path]:
         index_path, mapping_path = self._get_paths(model_id)
         safe_id = model_id.replace("/", "_").replace("\\", "_")
         fingerprint_path = self.index_dir / f"faiss_{safe_id}.fingerprint.json"
         return index_path, mapping_path, fingerprint_path

    def _save_index(self, model_id: str):
        index_path, mapping_path = self._get_paths(model_id)
        if self.index:
            faiss.write_index(self.index, str(index_path))
            with open(mapping_path, 'w', encoding='utf-8') as f:
                json.dump(self.mapping, f)
        else:
            # If empty, maybe delete files? Or save empty json?
            # Faiss doesn't save None.
            pass

    def search(self, query_vector: List[float], top_k: int = 10) -> List[Tuple[str, float]]:
        if not self.index:
            return []
            
        vec = np.array([query_vector]).astype('float32')
        distances, ids = self.index.search(vec, top_k)
        
        results = []
        for dist, idx in zip(distances[0], ids[0]):
            if idx != -1 and idx < len(self.mapping):
                chunk_id = self.mapping[idx]
                results.append((chunk_id, float(dist)))
                
        return results
