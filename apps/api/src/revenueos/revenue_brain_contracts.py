from __future__ import annotations

from datetime import datetime
from uuid import UUID

from revenueos.contracts import APIModel
from revenueos.revenue_brain_repositories import RevenueBrainTimelineItem


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
