import re
import hashlib
import sqlite3
from typing import List
from app.core.insights.models import Insight
from app.core.insights.repository import InsightRepository

class InsightEngine:
    def __init__(self, db_path: str, repository: InsightRepository):
        self.db_path = db_path
        self.repository = repository

    def _get_active_chunks(self):
        # Audit Change: Global active evidence contract.
        # Process ALL active chunks, effectively regenerating the insights view 
        # based on current global state, not just this run's delta.
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute("""
                SELECT chunk_id, content_text, artifact_id, hash
                FROM chunks 
                WHERE is_active = 1 
                  AND content_text IS NOT NULL 
                  AND length(trim(content_text)) > 0
            """)
            rows = cursor.fetchall()
            return rows
        finally:
            conn.close()

    def run(self, index_run_id: str):
        """
        Scans active chunks for this run and generates insights.
        """
        rows = self._get_active_chunks()
        
        # Heuristics
        # 1. Unknowns: "TBD", "TODO", "Unknown", "Missing"
        # 2. Decisions: "Decision:", "Selected:"
        # 3. Dependencies: "Depends on", "Blocked by"
        
        patterns = {
            "unknown": r"\b(TBD|TODO|FIXME|Unknown|Missing)\b",
            "decision": r"\b(Decision:|Selected_Option:|Resolved:)",
            "dependency": r"\b(Depends on|Blocked by|Requires)\b"
        }
        
        for row in rows:
            content = row['content_text']
            chunk_id = row['chunk_id']
            artifact_id = row['artifact_id']
            chunk_hash = row['hash']
            
            for i_type, pattern in patterns.items():
                # Change: Use finditer to find ALL occurences in chunk
                for match in re.finditer(pattern, content, re.IGNORECASE):
                    # Fingerprint = hash(type + normalized_statement)
                    # We capture the LINE context to distinguish different TBDs.
                    
                    start = match.start()
                    line_start = content.rfind('\n', 0, start) + 1
                    line_end = content.find('\n', start)
                    if line_end == -1: line_end = len(content)
                    
                    full_line = content[line_start:line_end].strip()
                    # Normalized statement: remove extra spaces, lower case
                    norm_statement = " ".join(full_line.split()).lower()
                    
                    # Fingerprint (P1 Refinement)
                    # Use SHA256 and include artifact_id to separate same text in different files.
                    base = f"{i_type}|{norm_statement}|{artifact_id}"
                    fingerprint = hashlib.sha256(base.encode("utf-8")).hexdigest()
                    
                    # Insight ID: Use fingerprint (P1 Hardening)
                    # This ensures UNIQUE constraint works naturally for dedupe.
                    insight_id = fingerprint

                    # Statement for UI
                    statement = full_line[:200]
                    
                    # Guard P2.1
                    if not chunk_id:
                        continue
                        
                    insight = Insight(
                        insight_id=insight_id,
                        index_run_id=index_run_id,
                        type=i_type,
                        statement=statement,
                        confidence=1.0,
                        evidence_chunk_ids=[chunk_id],
                        insight_fingerprint=fingerprint
                    )
                    self.repository.upsert_insight(insight)
