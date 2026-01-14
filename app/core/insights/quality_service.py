
import logging
import sqlite3
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class QualityService:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_conn(self):
        return sqlite3.connect(self.db_path, timeout=30.0)

    def get_last_n_runs(self, n: int = 3, conn: Optional[sqlite3.Connection] = None) -> List[str]:
        """
        Get last N runs based on recorded_at in quality_metrics.
        Used for determining the window for flapping detection.
        """
        close_conn = False
        if not conn:
            conn = self._get_conn()
            close_conn = True
            
        try:
            # We sort by recorded_at DESC
            cursor = conn.execute("SELECT run_id FROM quality_metrics ORDER BY recorded_at DESC LIMIT ?", (n,))
            return [row[0] for row in cursor.fetchall()]
        finally:
            if close_conn:
                conn.close()

    def is_flapping(self, insight_id: str, run_window: List[str], conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        Detects if insight is flapping.
        Definition: >= 2 status toggles (archived <-> active) within the run_window.
        """
        if not run_window:
            return False
            
        close_conn = False
        if not conn:
            conn = self._get_conn()
            close_conn = True
            
        try:
            placeholders = ",".join(["?"] * len(run_window))
            query = f"""
                SELECT from_status, to_status 
                FROM insight_status_history
                WHERE insight_id = ? 
                  AND run_id IN ({placeholders})
                  AND (to_status = 'archived' OR from_status = 'archived')
                ORDER BY changed_at ASC
            """
            params = [insight_id] + run_window
            cursor = conn.execute(query, params)
            changes = cursor.fetchall()
            
            # Count toggles
            # A toggle is a change involving archived.
            # If count >= 2, it's flapping (e.g. Open -> Archived -> Open)
            return len(changes) >= 2
        finally:
            if close_conn:
                conn.close()

    def record_run_metrics(self, run_id: str):
        """
        Computes and records metrics for the current run.
        Should be called at the end of the run.
        Uses discrete connections to avoid locking constraints on Windows.
        """
        created = archived = restored = resolved = 0
        changed_insights = []
        
        # Phase 1: Aggregates
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                SELECT 
                    SUM(CASE WHEN to_status = 'open' AND from_status IS NULL THEN 1 ELSE 0 END) as created,
                    SUM(CASE WHEN to_status = 'archived' THEN 1 ELSE 0 END) as archived,
                    SUM(CASE WHEN from_status = 'archived' AND to_status != 'archived' THEN 1 ELSE 0 END) as restored,
                    SUM(CASE WHEN to_status = 'resolved' AND origin = 'manual' THEN 1 ELSE 0 END) as resolved_manual
                FROM insight_status_history
                WHERE run_id = ?
            """, (run_id,))
            
            row = cursor.fetchone()
            if row:
                created = row[0] or 0
                archived = row[1] or 0
                restored = row[2] or 0
                resolved = row[3] or 0
                
            cursor = conn.execute("SELECT DISTINCT insight_id FROM insight_status_history WHERE run_id = ?", (run_id,))
            changed_insights = [r[0] for r in cursor.fetchall()]
        finally:
            conn.close()

        # Phase 2: Flapping Check (Stateless)
        # Note: inefficient but lock-safe
        flapping_count = 0
        try:
            # Get Runs window
            prev_runs = self.get_last_n_runs(2)
            window = prev_runs + [run_id]
            
            for iid in changed_insights:
                # is_flapping manages its own connection
                if self.is_flapping(iid, window):
                    flapping_count += 1
        except Exception as e:
            logger.error(f"Flapping check failed: {e}")

        # Phase 3: Insert
        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO quality_metrics (run_id, recorded_at, created_count, archived_count, restored_count, resolved_manual_count, flapping_count)
                VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)
            """, (run_id, created, archived, restored, resolved, flapping_count))
            conn.commit()
            logger.info(f"Recorded metrics for run {run_id}: Created={created}, Archived={archived}, Flapping={flapping_count}")
        except Exception as e:
            logger.error(f"Failed to record metrics: {e}")
            # Don't raise, telemetry failure shouldn't crash app
        finally:
            conn.close()
