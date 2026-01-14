import sqlite3
from typing import List, Optional
from app.core.insights.models import Insight

class InsightRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def upsert_insight(self, insight: Insight):
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            # P1 Hardening: ID is fingerprint. Use direct ON CONFLICT UPSERT.
            
            # Insert or Update (Update run_id and timestamp)
            cursor.execute("""
                INSERT INTO insights (
                    insight_id, index_run_id, type, statement, status, confidence, updated_at, insight_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                ON CONFLICT(insight_id) DO UPDATE SET
                    index_run_id=excluded.index_run_id,
                    updated_at=CURRENT_TIMESTAMP,
                    confidence=excluded.confidence
            """, (
                insight.insight_id, insight.index_run_id, insight.type, 
                insight.statement, insight.status, insight.confidence, insight.insight_fingerprint
            ))
            
            resolved_id = insight.insight_id # ID is stable/fingerprint

            # Guard P2.1: Empty Evidence
            if not insight.evidence_chunk_ids:
                pass
            else:
                # Evidence Linking using RESOLVED ID
                for chunk_id in insight.evidence_chunk_ids:
                    # Use INSERT OR IGNORE to merge
                    cursor.execute("""
                        INSERT OR IGNORE INTO insight_evidence (insight_id, chunk_id)
                        VALUES (?, ?)
                    """, (resolved_id, chunk_id))
            
            conn.commit()
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
                # Get Evidence
                # N+1 query valid for MVP scale
                cursor_ev = conn.cursor()
                cursor_ev.execute("SELECT chunk_id FROM insight_evidence WHERE insight_id = ?", (row['insight_id'],))
                evidence_ids = [r[0] for r in cursor_ev.fetchall()]
                
                insight = Insight(
                    insight_id=row['insight_id'],
                    index_run_id=row['index_run_id'],
                    type=row['type'],
                    statement=row['statement'],
                    status=row['status'],
                    confidence=row['confidence'],
                    evidence_chunk_ids=evidence_ids,
                    insight_fingerprint=row['insight_fingerprint'] if 'insight_fingerprint' in row.keys() else None
                )
                insights.append(insight)
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
                SELECT DISTINCT i.insight_id, i.index_run_id, i.type, i.status, i.statement, i.confidence, i.created_at, i.updated_at
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
                    "is_active": True # Implicit if filtered by active, but useful for UI
                }
                for r in rows
            ]
        finally:
            conn.close()

    def get_evidence(self, insight_id: str, limit: int = 20) -> List[dict]:
        """
        Get detailed evidence (content + location) for an insight.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT
                    c.chunk_id, c.content_text, c.page, c.slide, c.section,
                    a.filename, a.path
                FROM insight_evidence ie
                JOIN chunks c ON c.chunk_id = ie.chunk_id
                JOIN artifacts a ON a.id = c.artifact_id
                WHERE ie.insight_id = ?
                  AND c.is_active = 1
                LIMIT ?
            """, (insight_id, limit))
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
                }
                for r in rows
            ]
        finally:
            conn.close()
