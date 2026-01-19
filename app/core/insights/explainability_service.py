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
             if insight.superseded_by_insight_id:
                 rationale += f" This insight was superseded by {insight.superseded_by_insight_id}."
             else:
                 rationale += " This insight was superseded (target not specified)."
             
        # Related Sections
        related = []
        if insight.section_hint:
             related.append(insight.section_hint)
             
        # Justification
        justification = f"Confidence {insight.confidence:.2f} based on rule match."
        if insight.status_origin == 'manual':
             justification += " Status manually overridden."

        # Status Logic (Deterministic from History)
        status_logic = f"Status is {insight.status}."
        
        # Check history for precise logic
        last_manual_change = None

        # Check history for precise logic & manual actions
        history = self.repo.get_status_history(insight_id)
        
        # Epic 5: Find last manual change for UI
        for event in history:
            if event['origin'] == 'manual':
                last_manual_change = {
                    'from_status': event['from_status'],
                    'to_status': event['to_status'],
                    'origin': event['origin'],
                    'changed_at': event['changed_at'],
                    'comment': event.get('comment')
                }
                break

        last_event = history[0] if history else None
        
        if insight.status == 'superseded':
             target = insight.superseded_by_insight_id
             # Fallback to manual comment if available
             comment = last_manual_change['comment'] if last_manual_change and last_manual_change['to_status'] == 'superseded' else ""
             
             if target:
                 # Fetch target to get title
                 target_insight = self.repo.get_insight_by_id(target)
                 target_desc = f"{target[:8]}... ({target_insight.statement[:50]}...)" if target_insight else target
                 status_logic = f"Superseded by insight {target_desc}."
             else:
                 status_logic = "Superseded (target not set)."
             
             if comment:
                 status_logic += f" Reason: {comment}"
        
        elif last_event:
             from_s = last_event['from_status']
             to_s = last_event['to_status']
             origin = last_event['origin']
             changed_at = last_event['changed_at']
             comment = last_event.get('comment') or ""
             
             if to_s == 'resolved' and origin == 'manual':
                 status_logic = f"Resolved manually on {changed_at}. Comment: {comment}"
             
             elif to_s == 'archived' and origin == 'system':
                  conf_at = insight.last_confirmed_at or changed_at
                  status_logic = f"Archived because evidence missing since {conf_at}."
             
             elif to_s == 'resolved' and from_s == 'archived':
                  status_logic = f"Restored to previous_status=resolved on {changed_at} (evidence reappeared)."
                  
             elif to_s == 'open' and from_s == 'archived':
                  status_logic = f"Restored to previous_status=open on {changed_at} (evidence reappeared)."
             
             elif to_s == 'open' and origin == 'manual':
                  status_logic = f"Re-opened manually on {changed_at}. Comment: {comment}"
                  
        # Epic 5: P1 Consistency check - if resolved manually, ensure status logic reflects it even if history is weird
        if insight.status == 'resolved' and insight.status_origin == 'manual' and "Resolved manually" not in status_logic:
             # Fallback if history missing but current state is manual resolved
             status_logic = f"Resolved manually. (History unavailable)"

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

            status_logic=status_logic,
            last_manual_change=last_manual_change
        )
