from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    CandidateEvidence,
    CaptureSession,
    DebriefSession,
    DebriefTurn,
    EvidenceFragment,
    Interaction,
    InteractionIntelligenceSnapshot,
    InteractionMarker,
    Opportunity,
    PreInteractionBrief,
    RevenueBrainInsight,
    RevenueBrainInteractionSnapshot,
    RevenueBrainSnapshot,
    TranscriptVersion,
)


@dataclass(frozen=True)
class DebriefSessionRecord:
    capture_session: CaptureSession
    debrief_session: DebriefSession


class DebriefRepository:
    """Every debrief read is explicitly scoped to the trusted organisation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_interaction(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        *,
        for_update: bool = False,
    ) -> Interaction | None:
        statement = select(Interaction).where(
            Interaction.organisation_id == organisation_id,
            Interaction.id == interaction_id,
            Interaction.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(Interaction | None, await self.session.scalar(statement))

    async def find_idempotent_session(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        user_id: UUID,
        idempotency_key: str,
    ) -> DebriefSessionRecord | None:
        row = (
            await self.session.execute(
                select(CaptureSession, DebriefSession)
                .join(
                    DebriefSession,
                    and_(
                        DebriefSession.organisation_id == CaptureSession.organisation_id,
                        DebriefSession.id == CaptureSession.id,
                    ),
                )
                .where(
                    DebriefSession.organisation_id == organisation_id,
                    DebriefSession.interaction_id == interaction_id,
                    DebriefSession.started_by_user_id == user_id,
                    DebriefSession.idempotency_key == idempotency_key,
                )
            )
        ).one_or_none()
        return DebriefSessionRecord(row[0], row[1]) if row is not None else None

    async def get_session(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        session_id: UUID,
        *,
        for_update: bool = False,
    ) -> DebriefSessionRecord | None:
        statement = (
            select(CaptureSession, DebriefSession)
            .join(
                DebriefSession,
                and_(
                    DebriefSession.organisation_id == CaptureSession.organisation_id,
                    DebriefSession.id == CaptureSession.id,
                ),
            )
            .where(
                DebriefSession.organisation_id == organisation_id,
                DebriefSession.interaction_id == interaction_id,
                DebriefSession.id == session_id,
                CaptureSession.deleted_at.is_(None),
            )
        )
        if for_update:
            statement = statement.with_for_update(of=DebriefSession)
        row = (await self.session.execute(statement)).one_or_none()
        return DebriefSessionRecord(row[0], row[1]) if row is not None else None

    async def count_sessions_since(self, organisation_id: UUID, since: datetime) -> int:
        count = await self.session.scalar(
            select(func.count())
            .select_from(DebriefSession)
            .where(
                DebriefSession.organisation_id == organisation_id,
                DebriefSession.created_at >= since,
            )
        )
        return int(count or 0)

    async def find_turn_by_idempotency(
        self,
        organisation_id: UUID,
        session_id: UUID,
        idempotency_key: str,
    ) -> DebriefTurn | None:
        return cast(
            DebriefTurn | None,
            await self.session.scalar(
                select(DebriefTurn).where(
                    DebriefTurn.organisation_id == organisation_id,
                    DebriefTurn.session_id == session_id,
                    DebriefTurn.idempotency_key == idempotency_key,
                )
            ),
        )

    async def list_turns(self, organisation_id: UUID, session_id: UUID) -> list[DebriefTurn]:
        values = await self.session.scalars(
            select(DebriefTurn)
            .where(
                DebriefTurn.organisation_id == organisation_id,
                DebriefTurn.session_id == session_id,
            )
            .order_by(DebriefTurn.turn_number, DebriefTurn.id)
        )
        return list(values.all())

    async def list_fragments(
        self,
        organisation_id: UUID,
        session_id: UUID,
    ) -> list[EvidenceFragment]:
        values = await self.session.scalars(
            select(EvidenceFragment)
            .where(
                EvidenceFragment.organisation_id == organisation_id,
                EvidenceFragment.session_id == session_id,
                EvidenceFragment.deleted_at.is_(None),
            )
            .order_by(EvidenceFragment.created_at, EvidenceFragment.id)
        )
        return list(values.all())

    async def list_candidates(
        self,
        organisation_id: UUID,
        session_id: UUID,
        *,
        for_update: bool = False,
    ) -> list[CandidateEvidence]:
        statement = (
            select(CandidateEvidence)
            .where(
                CandidateEvidence.organisation_id == organisation_id,
                CandidateEvidence.session_id == session_id,
            )
            .order_by(CandidateEvidence.created_at, CandidateEvidence.id)
        )
        if for_update:
            statement = statement.with_for_update()
        values = await self.session.scalars(statement)
        return list(values.all())

    async def latest_brief_questions(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
    ) -> tuple[str, ...]:
        record = await self.session.scalar(
            select(PreInteractionBrief)
            .where(
                PreInteractionBrief.organisation_id == organisation_id,
                PreInteractionBrief.interaction_id == interaction_id,
                PreInteractionBrief.status == "completed",
            )
            .order_by(PreInteractionBrief.brief_version.desc())
            .limit(1)
        )
        if record is None:
            return ()
        raw = record.content_json.get("questions_to_ask", record.content_json.get("questionsToAsk", []))
        if not isinstance(raw, list):
            return ()
        questions: list[str] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            value = item.get("question")
            if isinstance(value, str) and value.strip():
                questions.append(value.strip()[:300])
        return tuple(questions[:8])

    async def normalised_start_context(
        self,
        organisation_id: UUID,
        interaction: Interaction,
        *,
        include_reconciliation_text: bool = False,
    ) -> dict[str, object]:
        """Return bounded context, with transcript text only for trusted reconciliation."""

        brief = await self.session.scalar(
            select(PreInteractionBrief)
            .where(
                PreInteractionBrief.organisation_id == organisation_id,
                PreInteractionBrief.interaction_id == interaction.id,
                PreInteractionBrief.status == "completed",
            )
            .order_by(PreInteractionBrief.brief_version.desc())
            .limit(1)
        )
        opportunity = (
            await self.session.scalar(
                select(Opportunity).where(
                    Opportunity.organisation_id == organisation_id,
                    Opportunity.id == interaction.opportunity_id,
                )
            )
            if interaction.opportunity_id is not None
            else None
        )
        brain_snapshot = (
            await self.session.scalar(
                select(RevenueBrainSnapshot)
                .where(
                    RevenueBrainSnapshot.organisation_id == organisation_id,
                    RevenueBrainSnapshot.opportunity_id == interaction.opportunity_id,
                )
                .order_by(RevenueBrainSnapshot.created_at.desc(), RevenueBrainSnapshot.id.desc())
                .limit(1)
            )
            if interaction.opportunity_id is not None
            else None
        )
        brain_insight = (
            await self.session.scalar(
                select(RevenueBrainInsight)
                .where(
                    RevenueBrainInsight.organisation_id == organisation_id,
                    RevenueBrainInsight.opportunity_id == interaction.opportunity_id,
                    RevenueBrainInsight.scope == "opportunity",
                    RevenueBrainInsight.status == "completed",
                )
                .order_by(RevenueBrainInsight.created_at.desc(), RevenueBrainInsight.id.desc())
                .limit(1)
            )
            if interaction.opportunity_id is not None
            else None
        )
        reported = (
            await self.latest_reported_intelligence(organisation_id, interaction.opportunity_id)
            if interaction.opportunity_id is not None
            else None
        )
        recording_context = await self._recording_context(organisation_id, interaction.id)
        context: dict[str, object] = {
            "interaction": {
                "id": str(interaction.id),
                "type": interaction.interaction_type,
                "title": interaction.title,
                "scheduledStartAt": (
                    interaction.scheduled_start_at.isoformat() if interaction.scheduled_start_at is not None else None
                ),
                "actualEndAt": interaction.actual_end_at.isoformat() if interaction.actual_end_at is not None else None,
            },
            "opportunity": (
                {
                    "id": str(opportunity.id),
                    "name": opportunity.name,
                    "stage": opportunity.stage,
                    "estimatedValue": (
                        str(opportunity.estimated_value) if opportunity.estimated_value is not None else None
                    ),
                    "currency": opportunity.currency,
                    "expectedCloseDate": (
                        opportunity.expected_close_date.isoformat()
                        if opportunity.expected_close_date is not None
                        else None
                    ),
                }
                if opportunity is not None
                else None
            ),
            "preInteractionBrief": brief.content_json if brief is not None else None,
            "revenueBrainLatestState": (
                {"snapshotId": str(brain_snapshot.id), "version": brain_snapshot.version}
                if brain_snapshot is not None
                else None
            ),
            "revenueBrainLatestLongitudinalInsight": (
                brain_insight.content_json if brain_insight is not None else None
            ),
            "previousValidatedReportedIntelligence": reported.content_json if reported is not None else None,
            "directRecordingAvailable": recording_context[0],
            "directRecordingCoverage": list(recording_context[1]),
            "markerTargets": list(recording_context[2]),
        }
        if include_reconciliation_text and recording_context[3] is not None:
            context["_recordingReconciliationText"] = recording_context[3]
        return context

    async def _recording_context(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
    ) -> tuple[bool, tuple[str, ...], tuple[str, ...], str | None]:
        transcript = await self.session.scalar(
            select(TranscriptVersion.raw_text)
            .where(
                TranscriptVersion.organisation_id == organisation_id,
                TranscriptVersion.interaction_id == interaction_id,
                TranscriptVersion.recording_session_id.is_not(None),
                TranscriptVersion.status == "final",
                TranscriptVersion.deleted_at.is_(None),
            )
            .order_by(TranscriptVersion.created_at.desc(), TranscriptVersion.id.desc())
            .limit(1)
        )
        marker_values = list(
            (
                await self.session.scalars(
                    select(InteractionMarker.marker_type)
                    .where(
                        InteractionMarker.organisation_id == organisation_id,
                        InteractionMarker.interaction_id == interaction_id,
                        InteractionMarker.deleted_at.is_(None),
                    )
                    .distinct()
                )
            ).all()
        )
        marker_map = {
            "buying_signal": "commercial_intent",
            "customer_question": "open_question",
            "follow_up": "next_step",
            "requested_material": "action_item",
        }
        marker_targets = tuple(sorted({marker_map.get(value, value) for value in marker_values}))
        if not isinstance(transcript, str) or not transcript.strip():
            return False, (), marker_targets, None
        normalised = transcript.casefold()
        target_terms = {
            "action_item": ("send", "follow up", "action", "owner"),
            "budget": ("budget", "funding", "price"),
            "commercial_intent": ("purchase", "buy", "proposal", "move forward"),
            "decision": ("decided", "decision", "approved", "agreed"),
            "next_step": ("next step", "follow up", "will send", "schedule"),
            "objection": ("objection", "concern", "blocker", "hesitant"),
            "open_question": ("question", "unanswered", "unclear"),
            "procurement": ("procurement", "purchasing"),
            "security_legal": ("security", "legal", "privacy", "contract"),
            "stakeholder": ("stakeholder", "decision maker", "champion", "procurement"),
            "timeline": ("timeline", "deadline", "date", "quarter"),
        }
        supported = tuple(target for target, terms in target_terms.items() if any(term in normalised for term in terms))
        return True, supported, marker_targets, transcript

    async def intelligence_for_session(
        self,
        organisation_id: UUID,
        session_id: UUID,
    ) -> InteractionIntelligenceSnapshot | None:
        return cast(
            InteractionIntelligenceSnapshot | None,
            await self.session.scalar(
                select(InteractionIntelligenceSnapshot).where(
                    InteractionIntelligenceSnapshot.organisation_id == organisation_id,
                    InteractionIntelligenceSnapshot.session_id == session_id,
                )
            ),
        )

    async def brain_for_intelligence(
        self,
        organisation_id: UUID,
        intelligence_id: UUID,
    ) -> RevenueBrainInteractionSnapshot | None:
        return cast(
            RevenueBrainInteractionSnapshot | None,
            await self.session.scalar(
                select(RevenueBrainInteractionSnapshot).where(
                    RevenueBrainInteractionSnapshot.organisation_id == organisation_id,
                    RevenueBrainInteractionSnapshot.interaction_intelligence_id == intelligence_id,
                )
            ),
        )

    async def next_intelligence_version(self, organisation_id: UUID, interaction_id: UUID) -> int:
        current = await self.session.scalar(
            select(func.max(InteractionIntelligenceSnapshot.version)).where(
                InteractionIntelligenceSnapshot.organisation_id == organisation_id,
                InteractionIntelligenceSnapshot.interaction_id == interaction_id,
            )
        )
        return int(current or 0) + 1

    async def next_brain_version(
        self,
        organisation_id: UUID,
        company_id: UUID,
        opportunity_id: UUID | None,
    ) -> int:
        conditions = [
            RevenueBrainInteractionSnapshot.organisation_id == organisation_id,
            RevenueBrainInteractionSnapshot.company_id == company_id,
        ]
        if opportunity_id is None:
            conditions.append(RevenueBrainInteractionSnapshot.opportunity_id.is_(None))
        else:
            conditions.append(RevenueBrainInteractionSnapshot.opportunity_id == opportunity_id)
        current = await self.session.scalar(
            select(func.max(RevenueBrainInteractionSnapshot.version)).where(*conditions)
        )
        return int(current or 0) + 1

    async def latest_reported_intelligence(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
    ) -> InteractionIntelligenceSnapshot | None:
        return cast(
            InteractionIntelligenceSnapshot | None,
            await self.session.scalar(
                select(InteractionIntelligenceSnapshot)
                .where(
                    InteractionIntelligenceSnapshot.organisation_id == organisation_id,
                    InteractionIntelligenceSnapshot.opportunity_id == opportunity_id,
                    InteractionIntelligenceSnapshot.validation_state == "validated",
                )
                .order_by(
                    InteractionIntelligenceSnapshot.created_at.desc(),
                    InteractionIntelligenceSnapshot.id.desc(),
                )
                .limit(1)
            ),
        )
