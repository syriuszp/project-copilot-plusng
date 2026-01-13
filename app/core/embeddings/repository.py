import sqlite3
import json
import struct
from typing import List, Optional, Dict
from app.core.chunking.models import Chunk

class EmbeddingRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def get_existing_embeddings(self, chunk_ids: List[str], model_id: str) -> List[str]:
        """Returns list of chunk_ids that already have embeddings for this model."""
        if not chunk_ids:
            return []
            
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            placeholders = ','.join('?' for _ in chunk_ids)
            cursor.execute(f"""
                SELECT chunk_id FROM chunk_embeddings 
                WHERE model_id = ? AND chunk_id IN ({placeholders})
            """, (model_id, *chunk_ids))
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_missing_chunk_ids(self, chunk_ids: List[str], model_id: str) -> set[str]:
        """Returns set of chunk_ids that DO NOT have embeddings for this model."""
        existing = set(self.get_existing_embeddings(chunk_ids, model_id))
        return set(chunk_ids) - existing

    def get_embeddings_fingerprint(self, model_id: str) -> str:
        """Calculates a deterministic fingerprint for the embeddings state."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT COUNT(*), MAX(created_at) 
                FROM chunk_embeddings 
                WHERE model_id = ?
            """, (model_id,))
            row = cursor.fetchone()
            if not row:
                return "0|None"
            
            count = row[0]
            last_update = row[1] or "None"
            raw = f"{count}|{last_update}"
            
            import hashlib
            return hashlib.sha256(raw.encode()).hexdigest()
        finally:
            conn.close()

    def upsert_embeddings(self, embeddings_data: List[Dict]):
        """
        Upserts embeddings.
        embeddings_data: list of dicts {chunk_id, model_id, dim, vector}
        vector is list of floats.
        """
        if not embeddings_data:
            return

        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            for item in embeddings_data:
                # Convert float list to binary blob (little-endian floats)
                vector_blob = struct.pack(f'{len(item["vector"])}f', *item["vector"])
                
                cursor.execute("""
                    INSERT INTO chunk_embeddings (chunk_id, model_id, dim, vector)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(chunk_id, model_id) DO UPDATE SET
                        vector=excluded.vector,
                        dim=excluded.dim,
                        created_at=CURRENT_TIMESTAMP
                """, (item["chunk_id"], item["model_id"], item["dim"], vector_blob))
            conn.commit()
        finally:
            conn.close()
            
    def get_embedding_vector(self, chunk_id: str, model_id: str) -> Optional[List[float]]:
        """Used for verification/debugging."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT vector, dim FROM chunk_embeddings 
                WHERE chunk_id = ? AND model_id = ?
            """, (chunk_id, model_id))
            row = cursor.fetchone()
            if row:
                blob, dim = row
                return list(struct.unpack(f'{dim}f', blob))
            return None
        finally:
            conn.close()
