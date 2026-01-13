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

    def _get_active_chunks(self, index_run_id: str):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute("""
                SELECT chunk_id, content_text, artifact_id, hash
                FROM chunks 
                WHERE is_active = 1 
                  AND index_run_id = ? 
                  AND content_text IS NOT NULL 
                  AND length(trim(content_text)) > 0
            """, (index_run_id,))
            rows = cursor.fetchall()
            return rows
        finally:
            conn.close()

    def run(self, index_run_id: str):
        """
        Scans active chunks for this run and generates insights.
        """
        rows = self._get_active_chunks(index_run_id)
        
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
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    # Fingerprint = hash(type + normalized_statement)
                    # We want to group same findings across files/chunks.
                    # Statement contains the snippet, which might vary slightly?
                    # Auditor says "Ten sam marker/statement".
                    # If we include snippet in statement, it makes it unique per chunk if snippet differs.
                    # Let's use the Pattern + The Text found (normalized) to group.
                    # e.g. "TODO: Fix this" found in file A and file B.
                    # We need to extract the "value" of the marker if possible, or key off the HIT.
                    
                    # For MVP, let's use the normalized marker + a bit of content?
                    # The instruction says: "fingerprint = hash(type|normalized_statement)"
                    # "Statement" usually means the user description e.g. "TBD: Implement Login".
                    # My current regex only extracts the marker keyword (e.g. "TBD").
                    # If I only fingerprint "TBD", then ALL TBDs merge into ONE insight.
                    # That might be too aggressive if they vary effectively.
                    # But Auditor says: "Ten sam logiczny TBD / DEPENDENCY pojawia się wielokrotnie".
                    # Let's try to capture the LINE or surrounding text to distinguish different TBDs,
                    # but same TBD in re-index (same file, same content) should match.
                    # Wait, if we move the file, the chunk hash changes? No, chunk hash is content based.
                    # P2.2 Requirement: "Fingerprint = hash(type|normalized_statement)".
                    # Let's grab the LINE content as "statement" for better uniqueness than just "TBD".
                    
                    # Improve extraction slightly to get line context
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
                        # Should not happen in this loop, but good practice
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
