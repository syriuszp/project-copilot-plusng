from typing import List, Optional
from app.core.insights.models import Insight, Explainability
from app.core.insights.repository import InsightRepository

class ExplainabilityService:
    def __init__(self, repo: InsightRepository):
        self.repo = repo

    def generate_explanation(self, insight_id: str) -> Optional[Explainability]:
        insight = self.repo.get_insight_by_id(insight_id)
        if not insight:
            return None
            
        # Get evidence details
        evidence_list = self.repo.get_evidence(insight_id, limit=5)
        snippets = [f"...{e['content_text'][:200]}..." for e in evidence_list]
        
        # Determine Rationale
        rationale = f"Detected via {insight.type}."
        if insight.detection_pattern:
             rationale += f" Pattern matched: '{insight.detection_pattern}'."
             
        if insight.status == 'superseded':
             rationale += f" This insight was superseded by {insight.superseded_by_insight_id}."
             
        # Related Sections
        related = []
        if insight.section_hint:
             related.append(insight.section_hint)
             
        # Justification
        justification = f"Confidence {insight.confidence:.2f} based on rule match."
        if insight.status_origin == 'manual':
             justification += " Status manually overridden."

        # Status Logic
        status_logic = f"Status is {insight.status}."
        if insight.status == 'archived':
             date_str = insight.status_updated_at or insight.last_confirmed_at or "unknown date"
             status_logic = f"Archived because missing evidence in scan(s) since {date_str}."
        elif insight.status_origin == 'manual':
             status_logic = "Status set manually by user."
        elif insight.status == 'superseded':
             status_logic = f"Superseded by {insight.superseded_by_insight_id}."
        elif insight.status == 'open':
             status_logic = f"Active since {insight.first_detected_at}."
             if insight.previous_status:
                  status_logic += f" Restored from {insight.previous_status}."

        return Explainability(
            insight_id=insight.insight_id,
            rationale=rationale,
            related_sections=related,
            key_evidence_snippets=snippets,
            confidence_justification=justification,
            first_detected_at=insight.first_detected_at,
            last_confirmed_at=insight.last_confirmed_at,
            status_updated_at=insight.status_updated_at,
            status=insight.status,
            status_origin=insight.status_origin,
            status_logic=status_logic
        )
