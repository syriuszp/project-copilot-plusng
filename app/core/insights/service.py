
import logging
import sqlite3
from typing import List, Optional, Dict
from datetime import datetime
import hashlib

from app.core.insights.models import Insight
from app.core.insights.repository import InsightRepository
# from app.core.insights.engine import InsightEngine # Cyclic import? Pass engine logic or results in.

logger = logging.getLogger(__name__)

class InsightService:
    def __init__(self, repository: InsightRepository):
        self.repo = repository

    def _generate_key(self, artifact_id: str, rule_id: str, position_index: Optional[int], statement: str) -> str:
        """
        Deterministic ID generation.
        Priority: Location (Artifact + Rule + Position) > Content (Artifact + Rule + Normalized Statement).
        """
        if position_index is not None:
             # Location-based + Content Disambiguation (for multiple insights per chunk)
             loc_hash = hashlib.sha1(str(position_index).encode('utf-8')).hexdigest()
             # We must include statement (normalized) or offset to distinguish multiple TODOs in same chunk.
             # Using normalized statement provides some resilience to minor formatting while ensuring uniqueness.
             norm_stmt = " ".join(statement.split()).lower()
             raw = f"{artifact_id}|{rule_id}|{loc_hash}|{norm_stmt}"
             return hashlib.sha1(raw.encode('utf-8')).hexdigest()
        else:
             # Content-based Fallback
             norm_stmt = " ".join(statement.split()).lower()
             raw = f"{artifact_id}|{rule_id}|{norm_stmt}"
             return hashlib.sha1(raw.encode('utf-8')).hexdigest()

    def scan_compare_transition(self, artifact_id: str, candidates: List[dict], run_id: str):
        """
        Core Lifecycle logic (Match/New/Lost/Restore).
        Refactored to use a SINGLE transaction per artifact to prevent locking.
        """
        # 1. Open Transaction Scope
        conn = self.repo._get_conn()
        conn.row_factory = sqlite3.Row
        
        try:
            # 2. Get existing active insights for this artifact MANUALLY within transaction
            # to ensure isolation and lock consistency.
            cursor = conn.execute("""
                SELECT i.* 
                FROM insights i
                JOIN insight_evidence ie ON i.insight_id = ie.insight_id
                JOIN chunks c ON ie.chunk_id = c.chunk_id
                WHERE c.artifact_id = ? 
                  AND i.status != 'archived'
            """, (artifact_id,))
            
            # Helper to map rows
            existing_rows = cursor.fetchall()
            existing_insights = {} 
            
            # Load basic map. We skip heavy object mapping for read-only checks where possible
            # but we need object for upsert helpers later.
            for row in existing_rows:
                if row['insight_key']:
                    # Minimal conversion
                    existing_insights[row['insight_key']] = self.repo._row_to_insight(row, [])
            
            matched_keys = set()
            insights_to_persist = [] # List of Insight objects
            evidence_pairs = [] # List of (insight_id, chunk_id)
            history_entries = [] # List of params for history log
            
            timestamp = datetime.utcnow()
            
            for cand in candidates:
                cand_type = cand.get('type', 'unknown')
                cand_stmt = cand.get('statement', '')
                chunk_id = cand.get('chunk_id')
                chunk_idx = cand.get('position_index', 0)
                rule_id = cand.get('detection_rule_id')
                pattern = cand.get('detection_pattern')
                section_hint = cand.get('section_hint')

                key = self._generate_key(artifact_id, rule_id or cand_type, chunk_idx, cand_stmt)
                
                if key in existing_insights:
                    # MATCH
                    matched_keys.add(key)
                    existing = existing_insights[key]
                    
                    existing.last_confirmed_at = timestamp
                    existing.index_run_id = run_id
                    
                    if chunk_id:
                        evidence_pairs.append((existing.insight_id, chunk_id))
                    
                    insights_to_persist.append(existing)
                    
                else:
                    # NEW or RESTORE
                    # Check Archive within transaction
                    archived = conn.execute("SELECT * FROM insights WHERE insight_key = ?", (key,)).fetchone()
                    
                    if archived:
                        # RESTORE
                        row_archived = archived
                        iid = row_archived['insight_id']
                        prev_status = row_archived['previous_status'] or 'open'
                        old_status = row_archived['status']
                        
                        # Apply Restore Logic
                        if old_status == 'archived':
                            new_status = prev_status
                            
                            # Logically, if the chunk has a section, we might want to update it on restore too?
                            # For now, minimal update to valid columns.
                            conn.execute("""
                                UPDATE insights 
                                SET status = ?, status_origin = 'system', last_confirmed_at = ?, index_run_id = ?, status_updated_at = ?
                                WHERE insight_id = ?
                            """, (new_status, timestamp, run_id, timestamp, iid))
                            
                            # Log History
                            history_entries.append((iid, old_status, new_status, 'system', run_id, timestamp, 'Restored by scan'))
                        else:
                            # It exists but wasn't active in our initial fetch? 
                            # Maybe weird state, just update timestamp
                            conn.execute("UPDATE insights SET last_confirmed_at = ?, index_run_id = ? WHERE insight_id = ?", (timestamp, run_id, iid))

                        if chunk_id:
                            evidence_pairs.append((iid, chunk_id))
                            
                    else:
                        # CREATE
                        new_id = key # Use key as ID for valid strict persistence
                        new_insight = Insight(
                            insight_id=new_id,
                            index_run_id=run_id,
                            type=cand_type,
                            statement=cand_stmt,
                            status='open',
                            confidence=0.9,
                            insight_key=key,
                            detection_rule_id=rule_id,
                            detection_pattern=pattern,
                            first_detected_at=timestamp,
                            last_confirmed_at=timestamp,
                            evidence_chunk_ids=[chunk_id] if chunk_id else [],
                            section_hint=section_hint
                        )
                        
                        # Persist Object (New)
                        insights_to_persist.append(new_insight)
                        history_entries.append((new_id, None, 'open', 'system', run_id, timestamp, 'First detected'))

            # 3. Process LOST
            for key, insight in existing_insights.items():
                if key not in matched_keys and insight.status != 'superseded': 
                    # Detect Lost
                    prev_status = insight.status
                    new_status = 'archived'
                    
                    conn.execute("""
                        UPDATE insights 
                        SET status = ?, previous_status = ?, status_origin = 'system', status_updated_at = ?
                        WHERE insight_id = ?
                    """, (new_status, prev_status, timestamp, insight.insight_id))
                    
                    history_entries.append((insight.insight_id, prev_status, new_status, 'system', run_id, timestamp, 'Lost in scan'))

            # 4. Commit Bulk Work
            
            # Upserts (Updates + New)
            for ins in insights_to_persist:
                self.repo.upsert_insight(ins, conn=conn)
                
            # Evidence
            self.repo.bulk_add_evidence(evidence_pairs, conn=conn)
            
            # History Logs
            if history_entries:
                conn.executemany("""
                    INSERT INTO insight_status_history (insight_id, from_status, to_status, origin, run_id, changed_at, comment)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, history_entries)
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Error in lifecycle scan for {artifact_id}: {e}")
            conn.rollback()
            raise e
        finally:
            conn.close()

    def _generate_legacy_fingerprint(self, type_, statement):
         # Just a placeholder if needed, logic above uses key as ID.
         return hashlib.sha256(f"{type_}|{statement}".encode()).hexdigest()
