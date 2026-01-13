import sqlite3
import json
from typing import List, Optional
from app.core.chunking.models import Chunk

class ChunkingRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def upsert_chunk(self, chunk: Chunk) -> int:
        """
        Upserts a chunk.
        Returns the chunk_rowid.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # Upsert logic (SQLite 3.24+ supports DO UPDATE)
            # We assume chunk_id is the unique key
            cursor.execute("""
                INSERT INTO chunks (
                    chunk_id, artifact_id, index_run_id, content_text, chunk_type, 
                    hash, position_index, page, slide, section, bbox, is_active, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chunk_id) DO UPDATE SET
                    index_run_id=excluded.index_run_id,
                    content_text=excluded.content_text,
                    is_active=excluded.is_active,
                    updated_at=CURRENT_TIMESTAMP
            """, (
                chunk.chunk_id, chunk.artifact_id, chunk.index_run_id, chunk.content_text, 
                chunk.chunk_type, chunk.hash, chunk.position_index, 
                chunk.page, chunk.slide, chunk.section, chunk.bbox, chunk.is_active
            ))
            
            # Retrieve the rowid (needed for FTS sync)
            # If inserted, lastrowid works. If updated, we need to fetch it.
            cursor.execute("SELECT chunk_rowid FROM chunks WHERE chunk_id = ?", (chunk.chunk_id,))
            row = cursor.fetchone()
            if row:
                chunk_rowid = row[0]
            else:
                raise ValueError(f"Failed to retrieve chunk_rowid for {chunk.chunk_id}")
            
            conn.commit()
            return chunk_rowid
            
        finally:
            conn.close()

    def sync_fts_for_chunk(self, chunk_rowid: int, content_text: str, is_active: int):
        """
        Manual FTS sync.
        is_active=1 -> INSERT (or REPLACE)
        is_active=0 -> DELETE
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            if is_active:
                # INSERT OR REPLACE into chunks_fts (rowid, content_text)
                cursor.execute("""
                    INSERT OR REPLACE INTO chunks_fts (rowid, content_text) 
                    VALUES (?, ?)
                """, (chunk_rowid, content_text))
            else:
                # DELETE from chunks_fts
                cursor.execute("DELETE FROM chunks_fts WHERE rowid = ?", (chunk_rowid,))
            conn.commit()
        finally:
            conn.close()

    def deactivate_stale_chunks(self, artifact_id: str, current_run_id: str):
        """
        Sets is_active=0 for all chunks of this artifact that do NOT match current_run_id.
        Returns a list of (chunk_rowid, content_text, is_active) for FTS sync.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            # 1. Identify stale chunks
            cursor.execute("""
                SELECT chunk_rowid
                FROM chunks 
                WHERE artifact_id = ? AND index_run_id != ? AND is_active = 1
            """, (artifact_id, current_run_id))
            stale_rows = cursor.fetchall()
            stale_rowids = [r[0] for r in stale_rows]

            if not stale_rowids:
                return []

            # 2. Update them
            # We can't bind a list directly in standard sqlite3 easily without generating placeholders
            placeholders = ','.join('?' for _ in stale_rowids)
            cursor.execute(f"""
                UPDATE chunks 
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP 
                WHERE chunk_rowid IN ({placeholders})
            """, tuple(stale_rowids))
            
            conn.commit()
            return stale_rowids
        finally:
            conn.close()
