
import sqlite3
import datetime
import logging
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

class ArtifactsRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._fts_enabled = False
        self._check_and_init_fts()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _check_and_init_fts(self):
        """
        Attempts to create FTS5 table. If fails, fallback to LIKE.
        Also checks for legacy FTS schema (missing ref_id) and rebuilds if needed.
        """
        try:
            with self._get_conn() as conn:
                # 1. Check if legacy FTS exists (missing ref_id)
                needs_rebuild = False
                try:
                    cur = conn.execute("PRAGMA table_info(artifact_fts)")
                    cols = {row[1] for row in cur.fetchall()}
                    if cols and "ref_id" not in cols:
                        logger.warning("Detected legacy artifact_fts schema (missing ref_id). Rebuilding.")
                        needs_rebuild = True
                except:
                    pass
                
                if needs_rebuild:
                    conn.execute("DROP TABLE IF EXISTS artifact_fts")

                # 2. Create FTS
                # Using ref_id to avoid potential naming collision/syntax issues with artifact_id
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS artifact_fts USING fts5(
                        filename, 
                        path, 
                        text, 
                        ref_id
                    );
                """)
                self._fts_enabled = True
        except sqlite3.OperationalError as e:
            logger.warning(f"FTS5 not available, falling back to LIKE: {e}")
            self._fts_enabled = False
        except Exception as e:
            logger.error(f"FTS5 init error: {e}")
            self._fts_enabled = False

    @property
    def fts_enabled(self) -> bool:
        return self._fts_enabled

    def upsert_artifact(self, meta: Dict[str, Any]) -> int:
        """
        Inserts or updates artifact. Returns artifact_id.
        Meta keys: path, filename, ext, size_bytes, modified_at, sha256
        """
        with self._get_conn() as conn:
            cur = conn.cursor()
            # 003 Strict Schema: PK is 'id'. Unique is 'path'.
            cur.execute("""
                INSERT INTO artifacts (path, filename, ext, size_bytes, modified_at, sha256, ingest_status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'new', CURRENT_TIMESTAMP)
                ON CONFLICT(path) DO UPDATE SET
                    size_bytes=excluded.size_bytes,
                    modified_at=excluded.modified_at,
                    sha256=COALESCE(excluded.sha256, artifacts.sha256),
                    updated_at=CURRENT_TIMESTAMP
                RETURNING id;
            """, (
                meta['path'], meta['filename'], meta['ext'], 
                meta.get('size_bytes'), meta.get('modified_at'), meta.get('sha256')
            ))
            row = cur.fetchone()
            return row[0]

    def set_index_status(self, artifact_id: int, status: str, error: Optional[str] = None):
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE artifacts 
                SET ingest_status = ?, error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, error, artifact_id))

    def save_extracted_text(self, artifact_id: int, text: str, extractor: str, chars: int, filename: str, path: str, extracted_at: Optional[str] = None):
        with self._get_conn() as conn:
            # 1. Update artifact_text (Unified)
            conn.execute("""
                INSERT INTO artifact_text (artifact_id, text, extracted_at, extractor, chars)
                VALUES (?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?, ?)
                ON CONFLICT(artifact_id) DO UPDATE SET
                    text=excluded.text,
                    extracted_at=excluded.extracted_at,
                    extractor=excluded.extractor,
                    chars=excluded.chars;
            """, (artifact_id, text, extracted_at, extractor, chars))
            
            # 2. Update status
            conn.execute("UPDATE artifacts SET ingest_status='indexed', updated_at=CURRENT_TIMESTAMP WHERE id=?", (artifact_id,))

            # 3. Update FTS
            if self._fts_enabled:
                conn.execute("DELETE FROM artifact_fts WHERE ref_id = ?", (artifact_id,))
                conn.execute("""
                    INSERT INTO artifact_fts (filename, path, text, ref_id)
                    VALUES (?, ?, ?, ?)
                """, (filename, path, text, artifact_id))

    def search_artifacts(self, query: str, limit: int = 20, offset: int = 0, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        filters = filters or {}
        results = []
        
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            
            # Base query structure for LIKE fallback if FTS not used or initial
            sql_select = """
                SELECT a.id, a.path, a.filename, a.ext, a.ingest_status, a.error, a.modified_at, a.size_bytes, a.sha256, LENGTH(t.text) as text_len, 
                       substr(t.text, 1, 400) as snippet
                FROM artifacts a
                LEFT JOIN artifact_text t ON a.id = t.artifact_id
            """
            
            params = []
            where_clauses = ["1=1"]
            
            # Filters
            if filters.get('ext'):
                where_clauses.append("a.ext = ?")
                params.append(filters['ext'])
            if filters.get('status'):
                where_clauses.append("a.ingest_status = ?")
                params.append(filters['status'])
                
            # Search Logic
            if query and self._fts_enabled:
                # FTS Search
                def quote_fts(q: str) -> str:
                    return '"' + q.replace('"', '""') + '"'
                
                safe_query = quote_fts(query)

                # Join with FTS table
                sql = """
                    SELECT a.id, a.path, a.filename, a.ext, a.ingest_status, a.error, a.modified_at, a.size_bytes, a.sha256, LENGTH(t.text) as text_len,
                           snippet(artifact_fts, 2, '**', '**', '...', 64) as snippet
                    FROM artifacts a
                    JOIN artifact_fts f ON a.id = f.ref_id
                    LEFT JOIN artifact_text t ON a.id = t.artifact_id
                    WHERE artifact_fts MATCH ?
                """
                # Re-add filters to WHERE
                for clause in where_clauses[1:]: # skip 1=1
                    sql += f" AND {clause}"
                
                # Deterministic Sort: FTS Rank then Filename
                sql += " ORDER BY rank, a.filename ASC"
                
                # Params: query + filter params
                params = [safe_query] + params
                
            elif query:
                # LIKE Fallback
                sql = sql_select + " WHERE " + " AND ".join(where_clauses)
                sql += " AND (a.filename LIKE ? OR a.path LIKE ? OR t.text LIKE ?)"
                p = f"%{query}%"
                params.extend([p, p, p])
                
                # Deterministic Sort: Snippet length (as proxy for relevance/conciseness) + ID
                sql += " ORDER BY length(snippet) ASC, a.id ASC"
                
            else:
                # No query, just filters
                sql = sql_select + " WHERE " + " AND ".join(where_clauses)
                sql += " ORDER BY a.id DESC"

            # Apply Limit and Offset
            sql += f" LIMIT {limit} OFFSET {offset}"

            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            
            # Determine mode for metadata
            if query and self._fts_enabled:
                 mode = "FTS"
            elif query:
                 mode = "LIKE"
            else:
                 mode = "SCAN"

            for r in rows:
                d = dict(r)
                d["_search_mode"] = mode
                results.append(d)
                
        return results

    def record_index_run(self, run_meta: Dict[str, Any]):
        """
        Records statistics about an indexing run.
        """
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO index_runs (
                    run_id, started_at, ended_at, env, ingest_dir, 
                    files_seen, files_indexed, files_failed, files_not_extractable, fts_enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_meta['run_id'], run_meta['started_at'], run_meta['ended_at'], 
                run_meta.get('env'), run_meta.get('ingest_dir'),
                run_meta.get('files_seen', 0), run_meta.get('files_indexed', 0), 
                run_meta.get('files_failed', 0), run_meta.get('files_not_extractable', 0),
                1 if self._fts_enabled else 0
            ))

    def get_text_content(self, artifact_id: int) -> Optional[str]:
        """
        Retrieves the full extracted text for an artifact ID.
        """
        with self._get_conn() as conn:
            cur = conn.execute("SELECT text FROM artifact_text WHERE artifact_id = ?", (artifact_id,))
            row = cur.fetchone()
            if row:
                return row[0]
            return None
