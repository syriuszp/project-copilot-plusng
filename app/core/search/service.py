from typing import List
from .models import SearchEvidence
from app.core.artifacts_repo import ArtifactsRepo

class SearchService:
    def __init__(self, artifacts_repo: ArtifactsRepo):
        self.repo = artifacts_repo

    def search(self, query: str, limit: int = 20) -> List[SearchEvidence]:
        """
        Searches artifacts and returns structured evidence.
        """
        if not query.strip():
            # P2: Validation in Service/UI. 
            # If repo doesn't handle empty query properly or we want to be strict:
            return []
            
        raw_results = self.repo.search_artifacts(query, limit=limit)
        
        evidence_list = []
        for r in raw_results:
            # Determine search mode from result if possible, or infer from repo state
            # Repo implementation of search_artifacts needs to ideally return this info
            # For now, we know if repo.fts_enabled is true, it used FTS.
            # But specific query might fall back or be mixed? 
            # Repo logic is: if fts_enabled -> matches FTS. else -> matches LIKE.
            # We can pass this info from repo or infer it.
            # Let's infer for now based on repo state, as it's a global switch there.
            mode = "FTS" if self.repo.fts_enabled else "LIKE"
            
            # Map valid fields
            ev = SearchEvidence(
                artifact_id=r['id'],
                artifact_type=r['ext'], # simple mapping for MVP
                source_path=r['path'],
                snippet=r.get('snippet', ''),
                score=None, # FTS rank not always exposed as float yet, keeping None for MVP
                search_mode=mode
            )
            evidence_list.append(ev)
            
        return evidence_list
