import sqlite3
from typing import List, Optional
from app.core.insights.models import Insight

class InsightRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        # Enable WAL mode for concurrency
        try:
             with sqlite3.connect(db_path) as conn:
                 conn.execute("PRAGMA journal_mode=WAL;")
        except Exception:
             pass

    def _get_conn(self):
        return sqlite3.connect(self.db_path, timeout=30.0)

    def get_insight_by_key(self, insight_key: str) -> Optional[Insight]:
        return self._get_insight_generic("insight_key", insight_key)

    def get_insight_by_id(self, insight_id: str) -> Optional[Insight]:
        return self._get_insight_generic("insight_id", insight_id)

    def _get_insight_generic(self, field: str, value: str) -> Optional[Insight]:
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(f"SELECT * FROM insights WHERE {field} = ?", (value,))
            row = cursor.fetchone()
            if not row:
                return None
            
            # Fetch evidence
            cursor_ev = conn.execute("SELECT chunk_id FROM insight_evidence WHERE insight_id = ?", (row['insight_id'],))
            evidence_ids = [r[0] for r in cursor_ev.fetchall()]
            
            return self._row_to_insight(row, evidence_ids)
        finally:
            conn.close()

    def _validate_status(self, status: str):
        VALID_STATUSES = {'open', 'resolved', 'superseded', 'archived'}
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}. Must be one of {VALID_STATUSES}")

    def upsert_insight(self, insight: Insight, conn: Optional[sqlite3.Connection] = None):
        """
        Persists insight. Supports Epic 5 columns.
        """
        if insight.status:
            self._validate_status(insight.status)
        
        should_close = False
        if not conn:
            conn = self._get_conn()
            should_close = True
        
        try:
            conn.execute("""
                INSERT INTO insights (
                    insight_id, index_run_id, type, statement, status, confidence, updated_at, insight_fingerprint,
                    insight_key, detection_rule_id, detection_pattern, status_origin, status_updated_at,
                    previous_status, superseded_by_insight_id, status_comment, first_detected_at, 
                    last_confirmed_at, section_hint
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(insight_id) DO UPDATE SET
                    index_run_id=excluded.index_run_id,
                    updated_at=CURRENT_TIMESTAMP,
                    confidence=excluded.confidence,
                    last_confirmed_at=excluded.last_confirmed_at,
                    status=excluded.status, -- Engine might update status
                    status_updated_at=excluded.status_updated_at,
                    previous_status=excluded.previous_status,
                    status_origin=excluded.status_origin
            """, (
                insight.insight_id, insight.index_run_id, insight.type, 
                insight.statement, insight.status, insight.confidence, insight.insight_fingerprint,
                insight.insight_key, insight.detection_rule_id, insight.detection_pattern, 
                insight.status_origin, insight.status_updated_at, insight.previous_status,
                insight.superseded_by_insight_id, insight.status_comment, insight.first_detected_at,
                insight.last_confirmed_at, insight.section_hint
            ))
            
            resolved_id = insight.insight_id 

            if insight.evidence_chunk_ids:
                # Optimized bulk insert is better but we use ignore for now
                for chunk_id in insight.evidence_chunk_ids:
                    conn.execute("""
                        INSERT OR IGNORE INTO insight_evidence (insight_id, chunk_id)
                        VALUES (?, ?)
                    """, (resolved_id, chunk_id))
            
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()

    def log_status_change(self, insight_id: str, from_status: Optional[str], to_status: str, 
                         origin: str, comment: Optional[str], run_id: Optional[str]):
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO insight_status_history (
                    insight_id, from_status, to_status, origin, run_id, changed_at, comment
                ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            """, (insight_id, from_status, to_status, origin, run_id, comment))
            conn.commit()
        finally:
            conn.close()

    def set_status(self, insight_id: str, status: str, origin: str, 
                  comment: Optional[str], run_id: Optional[str]):
        """
        Manually or programmatically set status. Logs history.
        """
        # Validation P0
        self._validate_status(status)

        conn = self._get_conn()
        try:
            # Fetch current status for history
            cur = conn.execute("SELECT status FROM insights WHERE insight_id = ?", (insight_id,))
            row = cur.fetchone()
            if not row:
                return # Or raise
            
            old_status = row[0]
            
            if old_status != status:
                conn.execute("""
                    UPDATE insights 
                    SET status = ?, status_origin = ?, status_updated_at = CURRENT_TIMESTAMP, status_comment = ?
                    WHERE insight_id = ?
                """, (status, origin, comment, insight_id))
                
                # Log history
                conn.execute("""
                    INSERT INTO insight_status_history (
                        insight_id, from_status, to_status, origin, run_id, changed_at, comment
                    ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """, (insight_id, old_status, status, origin, run_id, comment))
                
            conn.commit()
        finally:
            conn.close()

    def mark_superseded(self, old_id: str, new_id: str, comment: str, run_id: Optional[str]):
        conn = self._get_conn()
        try:
            with conn: # Transaction
                # Check New ID existence P0
                exists = conn.execute("SELECT 1 FROM insights WHERE insight_id=?", (new_id,)).fetchone()
                if not exists:
                    raise ValueError(f"Target insight {new_id} does not exist.")
                
                # Check Old ID existence
                old_exists = conn.execute("SELECT status FROM insights WHERE insight_id=?", (old_id,)).fetchone()
                if not old_exists:
                    raise ValueError(f"Source insight {old_id} does not exist.")
                    
                from_status = old_exists[0]
            
                conn.execute("""
                    UPDATE insights 
                    SET status = 'superseded', 
                        status_origin = 'manual', 
                        superseded_by_insight_id = ?,
                        status_comment = ?,
                        status_updated_at = CURRENT_TIMESTAMP
                    WHERE insight_id = ?
                """, (new_id, comment, old_id))
                
                conn.execute("""
                    INSERT INTO insight_status_history (
                        insight_id, from_status, to_status, origin, run_id, changed_at, comment
                    ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """, (old_id, from_status, 'superseded', 'manual', run_id, comment))
        finally:
            conn.close()

    def add_evidence(self, insight_id: str, chunk_id: str, conn: Optional[sqlite3.Connection] = None):
        should_close = False
        if not conn:
            conn = self._get_conn()
            should_close = True
        try:
            conn.execute("INSERT OR IGNORE INTO insight_evidence (insight_id, chunk_id) VALUES (?, ?)", (insight_id, chunk_id))
            if should_close: conn.commit()
        finally:
            if should_close: conn.close()

    def bulk_add_evidence(self, pairs: List[tuple], conn: Optional[sqlite3.Connection] = None):
        """
        pairs: List of (insight_id, chunk_id)
        """
        if not pairs: return
        should_close = False
        if not conn:
            conn = self._get_conn()
            should_close = True
        try:
            conn.executemany("INSERT OR IGNORE INTO insight_evidence (insight_id, chunk_id) VALUES (?, ?)", pairs)
            if should_close: conn.commit()
        finally:
            if should_close: conn.close()

    def _row_to_insight(self, row: sqlite3.Row, evidence_ids: List[str]) -> Insight:
         return Insight(
            insight_id=row['insight_id'],
            index_run_id=row['index_run_id'],
            type=row['type'],
            statement=row['statement'],
            status=row['status'],
            confidence=row['confidence'],
            evidence_chunk_ids=evidence_ids,
            insight_fingerprint=row['insight_fingerprint'] if 'insight_fingerprint' in row.keys() else None,
            created_at=row['created_at'] if 'created_at' in row.keys() else None,
            updated_at=row['updated_at'] if 'updated_at' in row.keys() else None,
            insight_key=row['insight_key'] if 'insight_key' in row.keys() else None,
            detection_rule_id=row['detection_rule_id'] if 'detection_rule_id' in row.keys() else None,
            detection_pattern=row['detection_pattern'] if 'detection_pattern' in row.keys() else None,
            status_origin=row['status_origin'] if 'status_origin' in row.keys() else 'system',
            status_updated_at=row['status_updated_at'] if 'status_updated_at' in row.keys() else None,
            previous_status=row['previous_status'] if 'previous_status' in row.keys() else None,
            superseded_by_insight_id=row['superseded_by_insight_id'] if 'superseded_by_insight_id' in row.keys() else None,
            status_comment=row['status_comment'] if 'status_comment' in row.keys() else None,
            first_detected_at=row['first_detected_at'] if 'first_detected_at' in row.keys() else None,
            last_confirmed_at=row['last_confirmed_at'] if 'last_confirmed_at' in row.keys() else None,
            section_hint=row['section_hint'] if 'section_hint' in row.keys() else None
        )

    def get_active_insights_for_artifact(self, artifact_id: str) -> List[Insight]:
        """
        Fetches all non-archived insights linked to the artifact.
        """
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute("""
                SELECT DISTINCT i.* 
                FROM insights i
                JOIN insight_evidence ie ON i.insight_id = ie.insight_id
                JOIN chunks c ON ie.chunk_id = c.chunk_id
                WHERE c.artifact_id = ? 
                  AND i.status != 'archived' 
            """, (artifact_id,))
            
            insights = []
            for row in cursor.fetchall():
                cursor_ev = conn.execute("SELECT chunk_id FROM insight_evidence WHERE insight_id = ?", (row['insight_id'],))
                evidence_ids = [r[0] for r in cursor_ev.fetchall()]
                insights.append(self._row_to_insight(row, evidence_ids))
            return insights
        finally:
            conn.close()

    def get_insights_for_run(self, index_run_id: str) -> List[Insight]:
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT * FROM insights WHERE index_run_id = ?
            """, (index_run_id,))
            
            insights = []
            for row in cursor.fetchall():
                cursor_ev = conn.cursor()
                cursor_ev.execute("SELECT chunk_id FROM insight_evidence WHERE insight_id = ?", (row['insight_id'],))
                evidence_ids = [r[0] for r in cursor_ev.fetchall()]
                
                insights.append(self._row_to_insight(row, evidence_ids))
            return insights
        finally:
            conn.close()

    def get_latest_run_id(self) -> Optional[str]:
        conn = self._get_conn()
        try:
            # P2: Use Update Time or Started At
            # Note: 001_initial.sql defines run_id as PK (text), started_at as text.
            cursor = conn.execute("SELECT run_id FROM index_runs ORDER BY started_at DESC LIMIT 1")
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception:
            return None
        finally:
            conn.close()

    def list_insights(self, types: Optional[List[str]] = None, limit: int = 200, 
                    require_active_evidence: bool = True, only_latest_run: bool = False,
                    status: Optional[str] = None) -> List[dict]:
        """
        List insights.
        Default: Returns only insights linked to at least one ACTIVE chunk.
        Legacy: 'only_latest_run' is deprecated, maintained for strict debug only.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            latest_run_id = None
            if only_latest_run:
                latest_run_id = self.get_latest_run_id()
            
            # Base query Selects distinct insights
            query = """
                SELECT DISTINCT 
                    i.insight_id, i.index_run_id, i.type, i.status, i.statement, i.confidence, i.created_at, i.updated_at,
                    i.insight_key, i.status_origin, i.detection_rule_id, i.first_detected_at, i.last_confirmed_at,
                    i.superseded_by_insight_id, i.status_comment, i.previous_status, i.section_hint, i.detection_pattern
                FROM insights i
            """
            
            params = []
            conditions = ["1=1"]
            
            if require_active_evidence:
                query += """
                    JOIN insight_evidence ie ON ie.insight_id = i.insight_id
                    JOIN chunks c ON c.chunk_id = ie.chunk_id
                """
                conditions.append("c.is_active = 1")
                
            if types:
                placeholders = ",".join(["?"] * len(types))
                conditions.append(f"i.type IN ({placeholders})")
                params.extend(types)

            if status:
                conditions.append("i.status = ?")
                params.append(status)
            
            if only_latest_run and latest_run_id:
                conditions.append("i.index_run_id = ?")
                params.append(latest_run_id)

            query += " WHERE " + " AND ".join(conditions)
            
            # Sort by update time to show freshest information first
            query += " ORDER BY i.updated_at DESC, i.insight_id DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
                
            rows = cursor.fetchall()
            return [
                {
                    "insight_id": r[0], "index_run_id": r[1], "type": r[2], "status": r[3],
                    "statement": r[4], "confidence": r[5], "created_at": r[6], "updated_at": r[7],
                    "insight_key": r[8], "status_origin": r[9], "detection_rule_id": r[10],
                    "first_detected_at": r[11], "last_confirmed_at": r[12],
                    "superseded_by_insight_id": r[13], "status_comment": r[14], "previous_status": r[15],
                    "section_hint": r[16], "detection_pattern": r[17],
                    "is_active": True # Implicit if filtered by active, but useful for UI
                }
                for r in rows
            ]
        finally:
            conn.close()

    def get_evidence(self, insight_id: str, limit: int = 20, active_only: bool = True) -> List[dict]:
        """
        Get detailed evidence (content + location) for an insight.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            query = """
                SELECT
                    c.chunk_id, c.content_text, c.page, c.slide, c.section,
                    a.filename, a.path, c.artifact_id
                FROM insight_evidence ie
                JOIN chunks c ON c.chunk_id = ie.chunk_id
                JOIN artifacts a ON a.id = c.artifact_id
                WHERE ie.insight_id = ?
            """
            params = [insight_id]
            
            if active_only:
                query += " AND c.is_active = 1"
                
            query += " LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [
                {
                    "chunk_id": r[0],
                    "content_text": r[1],
                    "page": r[2],
                    "slide": r[3],
                    "section": r[4],
                    "filename": r[5],
                    "path": r[6],
                    "artifact_id": r[7], 
                }
                for r in rows
            ]
        finally:
            conn.close()

    def get_status_history(self, insight_id: str) -> List[dict]:
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute("""
                SELECT * FROM insight_status_history 
                WHERE insight_id = ? 
                ORDER BY changed_at DESC
            """, (insight_id,))
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def get_latest_quality_metrics(self) -> Optional[dict]:
        """
        Fetches the most recent quality metrics entry.
        """
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            # Check if table exists first (in case of old DBs)
            exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quality_metrics'").fetchone()
            if not exists:
                return None
                
            cur = conn.execute("SELECT * FROM quality_metrics ORDER BY recorded_at DESC LIMIT 1")
            row = cur.fetchone()
            return dict(row) if row else None
        except Exception:
            return None
        finally:
            conn.close()
