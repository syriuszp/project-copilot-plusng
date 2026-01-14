import re
import hashlib
import sqlite3
import logging
from typing import List, Dict
from app.core.insights.models import Insight
from app.core.insights.repository import InsightRepository
from app.core.insights.service import InsightService

logger = logging.getLogger(__name__)

class InsightEngine:
    def __init__(self, db_path: str, repository: InsightRepository):
        self.db_path = db_path
        self.repository = repository
        self.service = InsightService(repository)

    def _get_active_chunks(self):
        # Audit Change: Global active evidence contract.
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Need position_index for location key, section per Epic 5
            cursor = conn.execute("""
                SELECT chunk_id, content_text, artifact_id, hash, position_index, section
                FROM chunks 
                WHERE is_active = 1 
                  AND content_text IS NOT NULL 
                  AND length(trim(content_text)) > 0
                ORDER BY artifact_id, position_index
            """)
            rows = cursor.fetchall()
            return rows
        finally:
            conn.close()

    def run(self, index_run_id: str):
        """
        Scans active chunks for this run and generates insights.
        Delegates lifecycle management to InsightService (State Machine).
        """
        rows = self._get_active_chunks()
        
        patterns = {
            "unknown": r"\b(TBD|TODO|FIXME|Unknown|Missing)\b",
            "decision": r"\b(Decision:|Selected_Option:|Resolved:)",
            "dependency": r"\b(Depends on|Blocked by|Requires)\b"
        }
        
        # Group chunks by artifact
        artifacts_map: Dict[str, List[sqlite3.Row]] = {}
        for row in rows:
            aid = row['artifact_id']
            if aid not in artifacts_map:
                artifacts_map[aid] = []
            artifacts_map[aid].append(row)
        
        logger.info(f"InsightEngine: Processing {len(artifacts_map)} artifacts.")

        for artifact_id, chunks in artifacts_map.items():
            candidates = []
            
            for chunk in chunks:
                content = chunk['content_text']
                chunk_id = chunk['chunk_id']
                pos_idx = chunk['position_index']
                section_hint = chunk['section'] if 'section' in chunk.keys() else None
                
                for i_type, pattern_regex in patterns.items():
                    for match in re.finditer(pattern_regex, content, re.IGNORECASE):
                        start = match.start()
                        line_start = content.rfind('\n', 0, start) + 1
                        line_end = content.find('\n', start)
                        if line_end == -1: line_end = len(content)
                        
                        full_line = content[line_start:line_end].strip()
                        if not full_line: continue
                        
                        # Match matched text for pattern hint
                        matched_text = match.group(0)

                        # Create candidate dict
                        candidates.append({
                            "type": i_type,
                            "statement": full_line[:200],
                            "position_index": pos_idx,
                            "chunk_id": chunk_id,
                            "confidence": 1.0,
                            "detection_pattern": matched_text,
                            "section_hint": section_hint,
                            "detection_rule_id": i_type # MVP: Use type as rule ID
                        })
            
            # Delegate to Service
            if candidates:
                 self.service.scan_compare_transition(artifact_id, candidates, index_run_id)
            else:
                 # Even if no candidates, we must call service to detect LOST insights!
                 # If previously active insights exist for this artifact, they are now LOST.
                 self.service.scan_compare_transition(artifact_id, [], index_run_id)
