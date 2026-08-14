from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from revenueos.contracts import APIModel
from revenueos.revenue_brain_repositories import (
    RevenueBrainInteractionTimelineItem,
    RevenueBrainTimelineItem,
)


class RevenueBrainSnapshotResponse(APIModel):
    id: UUID
    organisation_id: UUID
    company_id: UUID
    opportunity_id: UUID | None
    meeting_id: UUID
    transcript_version_id: UUID
    created_at: datetime
    meeting_date: datetime
    summary_reference: UUID
    buying_signals_reference: UUID
    objections_reference: UUID
    stakeholders_reference: UUID
    decisions_reference: UUID
    actions_reference: UUID
    risks_reference: UUID
    questions_reference: UUID
    next_best_action_reference: UUID
    version: int

    @classmethod
    def from_timeline_item(
        cls,
        item: RevenueBrainTimelineItem,
    ) -> RevenueBrainSnapshotResponse:
        snapshot = item.snapshot
        return cls(
            id=snapshot.id,
            organisation_id=snapshot.organisation_id,
            company_id=snapshot.company_id,
            opportunity_id=snapshot.opportunity_id,
            meeting_id=snapshot.meeting_id,
            transcript_version_id=snapshot.transcript_version_id,
            created_at=snapshot.created_at,
            meeting_date=item.meeting_date,
            summary_reference=snapshot.summary_reference,
            buying_signals_reference=snapshot.buying_signals_reference,
            objections_reference=snapshot.objections_reference,
            stakeholders_reference=snapshot.stakeholders_reference,
            decisions_reference=snapshot.decisions_reference,
            actions_reference=snapshot.actions_reference,
            risks_reference=snapshot.risks_reference,
            questions_reference=snapshot.questions_reference,
            next_best_action_reference=snapshot.next_best_action_reference,
            version=snapshot.version,
        )


class RevenueBrainVisualEvidenceItemResponse(APIModel):
    evidence_id: UUID
    category: str
    statement: str
    origin: Literal["ai_inferred"]
    source_ownership: Literal[
        "customer_created",
        "salesperson_created",
        "jointly_created",
        "unknown_origin",
    ]
    support_classification: Literal["direct", "observed", "context"]
    source_label: str
    validation_state: Literal["verified"]


class RevenueBrainVisualSnapshotResponse(APIModel):
    id: UUID
    interaction_id: UUID
    opportunity_id: UUID | None
    interaction_title: str
    interaction_type: str
    interaction_date: datetime
    created_at: datetime
    source_label: str
    visual_type: str
    items: list[RevenueBrainVisualEvidenceItemResponse]

    @classmethod
    def from_timeline_item(
        cls,
        item: RevenueBrainInteractionTimelineItem,
    ) -> RevenueBrainVisualSnapshotResponse | None:
        content = item.snapshot.content_json
        source_label = content.get("sourceLabel")
        visual_type = content.get("visualType")
        raw_items = content.get("items")
        if not isinstance(source_label, str) or not isinstance(visual_type, str):
            return None
        if not isinstance(raw_items, list):
            return None
        parsed: list[RevenueBrainVisualEvidenceItemResponse] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            try:
                parsed.append(
                    RevenueBrainVisualEvidenceItemResponse.model_validate(
                        {
                            "evidenceId": raw_item.get("evidenceId"),
                            "category": raw_item.get("category"),
                            "statement": raw_item.get("statement"),
                            "origin": raw_item.get("origin"),
                            "sourceOwnership": raw_item.get("sourceOwnership"),
                            "supportClassification": raw_item.get("supportClassification"),
                            "sourceLabel": raw_item.get("sourceLabel"),
                            "validationState": raw_item.get("validationState"),
                        }
                    )
                )
            except (ValueError, TypeError):
                continue
        if not parsed:
            return None
        return cls(
            id=item.snapshot.id,
            interaction_id=item.snapshot.interaction_id,
            opportunity_id=item.snapshot.opportunity_id,
            interaction_title=item.interaction_title,
            interaction_type=item.interaction_type,
            interaction_date=item.interaction_date,
            created_at=item.snapshot.created_at,
            source_label=source_label,
            visual_type=visual_type,
            items=parsed,
        )
