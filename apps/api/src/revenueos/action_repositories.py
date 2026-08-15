from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.action_contracts import ActionSourceReference
from revenueos.models import (
    ActionAuditEvent,
    ActionProposal,
    ActionProposalVersion,
    AIArtifact,
    AIJob,
    Contact,
    Evidence,
    Interaction,
    InteractionIntelligenceSnapshot,
    Meeting,
    Opportunity,
    RevenueBrainInsight,
    Transcript,
)


@dataclass(frozen=True)
class ActionRecord:
    proposal: ActionProposal
    version: ActionProposalVersion


class ActionRepository:
    """Tenant-scoped persistence and source-validity checks for Action proposals."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def opportunity_for_update(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
    ) -> Opportunity | None:
        return cast(
            Opportunity | None,
            await self.session.scalar(
                select(Opportunity)
                .where(
                    Opportunity.organisation_id == organisation_id,
                    Opportunity.id == opportunity_id,
                )
                .with_for_update()
            ),
        )

    async def list_actions(
        self,
        organisation_id: UUID,
        *,
        opportunity_id: UUID | None = None,
        statuses: set[str] | None = None,
        limit: int = 100,
    ) -> list[ActionRecord]:
        conditions = [ActionProposal.organisation_id == organisation_id]
        if opportunity_id is not None:
            conditions.append(ActionProposal.opportunity_id == opportunity_id)
        if statuses:
            conditions.append(ActionProposal.status.in_(statuses))
        rows = (
            await self.session.execute(
                select(ActionProposal, ActionProposalVersion)
                .join(
                    ActionProposalVersion,
                    and_(
                        ActionProposalVersion.organisation_id == ActionProposal.organisation_id,
                        ActionProposalVersion.action_id == ActionProposal.id,
                        ActionProposalVersion.version == ActionProposal.current_version,
                    ),
                )
                .where(*conditions)
                .order_by(
                    ActionProposal.priority.asc(),
                    ActionProposal.generated_at.desc(),
                    ActionProposal.id.desc(),
                )
                .limit(limit)
            )
        ).all()
        return [ActionRecord(row[0], row[1]) for row in rows]

    async def get_action(
        self,
        organisation_id: UUID,
        action_id: UUID,
        *,
        for_update: bool = False,
    ) -> ActionRecord | None:
        statement = (
            select(ActionProposal, ActionProposalVersion)
            .join(
                ActionProposalVersion,
                and_(
                    ActionProposalVersion.organisation_id == ActionProposal.organisation_id,
                    ActionProposalVersion.action_id == ActionProposal.id,
                    ActionProposalVersion.version == ActionProposal.current_version,
                ),
            )
            .where(
                ActionProposal.organisation_id == organisation_id,
                ActionProposal.id == action_id,
            )
        )
        if for_update:
            statement = statement.with_for_update(of=ActionProposal)
        row = (await self.session.execute(statement)).one_or_none()
        return ActionRecord(row[0], row[1]) if row is not None else None

    async def by_source_fingerprint(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        fingerprint: str,
    ) -> ActionRecord | None:
        row = (
            await self.session.execute(
                select(ActionProposal, ActionProposalVersion)
                .join(
                    ActionProposalVersion,
                    and_(
                        ActionProposalVersion.organisation_id == ActionProposal.organisation_id,
                        ActionProposalVersion.action_id == ActionProposal.id,
                        ActionProposalVersion.version == ActionProposal.current_version,
                    ),
                )
                .where(
                    ActionProposal.organisation_id == organisation_id,
                    ActionProposal.opportunity_id == opportunity_id,
                    ActionProposal.source_fingerprint == fingerprint,
                )
            )
        ).one_or_none()
        return ActionRecord(row[0], row[1]) if row is not None else None

    async def active_by_semantic_key(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        semantic_key: str,
    ) -> list[ActionProposal]:
        values = await self.session.scalars(
            select(ActionProposal)
            .where(
                ActionProposal.organisation_id == organisation_id,
                ActionProposal.opportunity_id == opportunity_id,
                ActionProposal.semantic_key == semantic_key,
                ActionProposal.status.in_(("proposed", "edited", "approved")),
            )
            .with_for_update()
        )
        return list(values.all())

    async def generation_count_since(
        self,
        organisation_id: UUID,
        since: datetime,
    ) -> int:
        value = await self.session.scalar(
            select(func.count())
            .select_from(ActionProposal)
            .where(
                ActionProposal.organisation_id == organisation_id,
                ActionProposal.generated_at >= since,
            )
        )
        return int(value or 0)

    async def active_count(self, organisation_id: UUID, opportunity_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.count())
            .select_from(ActionProposal)
            .where(
                ActionProposal.organisation_id == organisation_id,
                ActionProposal.opportunity_id == opportunity_id,
                ActionProposal.status.in_(("proposed", "edited", "approved")),
            )
        )
        return int(value or 0)

    async def contact(
        self,
        organisation_id: UUID,
        contact_id: UUID,
    ) -> Contact | None:
        return cast(
            Contact | None,
            await self.session.scalar(
                select(Contact).where(
                    Contact.organisation_id == organisation_id,
                    Contact.id == contact_id,
                )
            ),
        )

    async def exact_contact_name(
        self,
        organisation_id: UUID,
        company_id: UUID | None,
        name: str,
    ) -> Contact | None:
        if company_id is None:
            return None
        values = list(
            (
                await self.session.scalars(
                    select(Contact).where(
                        Contact.organisation_id == organisation_id,
                        Contact.company_id == company_id,
                    )
                )
            ).all()
        )
        matches = [item for item in values if f"{item.first_name} {item.last_name}".casefold() == name.casefold()]
        return matches[0] if len(matches) == 1 else None

    async def source_is_current(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        reference: ActionSourceReference,
    ) -> bool:
        if reference.source_type == "accepted_evidence":
            count = await self.session.scalar(
                select(func.count())
                .select_from(Evidence)
                .where(
                    Evidence.organisation_id == organisation_id,
                    Evidence.id == reference.source_id,
                    Evidence.validation_state == "verified",
                    Evidence.lifecycle_status == "available",
                    Evidence.deleted_at.is_(None),
                )
            )
            return int(count or 0) == 1
        if reference.source_type == "ai_artifact":
            count = await self.session.scalar(
                select(func.count())
                .select_from(AIArtifact)
                .join(
                    AIJob,
                    and_(
                        AIJob.organisation_id == AIArtifact.organisation_id,
                        AIJob.id == AIArtifact.job_id,
                        AIJob.meeting_id == AIArtifact.meeting_id,
                        AIJob.transcript_id == AIArtifact.transcript_id,
                        AIJob.transcript_version == AIArtifact.transcript_version,
                    ),
                )
                .join(
                    Transcript,
                    and_(
                        Transcript.organisation_id == AIArtifact.organisation_id,
                        Transcript.id == AIArtifact.transcript_id,
                        Transcript.meeting_id == AIArtifact.meeting_id,
                        Transcript.version == AIArtifact.transcript_version,
                    ),
                )
                .join(
                    Meeting,
                    and_(
                        Meeting.organisation_id == AIArtifact.organisation_id,
                        Meeting.id == AIArtifact.meeting_id,
                    ),
                )
                .where(
                    AIArtifact.organisation_id == organisation_id,
                    AIArtifact.id == reference.source_id,
                    AIArtifact.superseded_at.is_(None),
                    AIJob.status == "completed",
                    Transcript.deleted_at.is_(None),
                    Meeting.opportunity_id == opportunity_id,
                    Meeting.status == "completed",
                    Meeting.deleted_at.is_(None),
                )
            )
            return int(count or 0) == 1
        if reference.source_type == "interaction_intelligence":
            snapshot = await self.session.scalar(
                select(InteractionIntelligenceSnapshot)
                .join(
                    Interaction,
                    and_(
                        Interaction.organisation_id == InteractionIntelligenceSnapshot.organisation_id,
                        Interaction.id == InteractionIntelligenceSnapshot.interaction_id,
                    ),
                )
                .where(
                    InteractionIntelligenceSnapshot.organisation_id == organisation_id,
                    InteractionIntelligenceSnapshot.id == reference.source_id,
                    InteractionIntelligenceSnapshot.opportunity_id == opportunity_id,
                    InteractionIntelligenceSnapshot.validation_state == "validated",
                    Interaction.deleted_at.is_(None),
                    Interaction.lifecycle_status == "completed",
                )
            )
            if snapshot is None:
                return False
            return await self._evidence_ids_are_current(
                organisation_id,
                snapshot.source_evidence_ids,
            )
        if reference.source_type == "revenue_brain_insight":
            count = await self.session.scalar(
                select(func.count())
                .select_from(RevenueBrainInsight)
                .where(
                    RevenueBrainInsight.organisation_id == organisation_id,
                    RevenueBrainInsight.id == reference.source_id,
                    RevenueBrainInsight.opportunity_id == opportunity_id,
                    RevenueBrainInsight.status == "completed",
                )
            )
            return int(count or 0) == 1
        return False

    async def _evidence_ids_are_current(
        self,
        organisation_id: UUID,
        raw_ids: list[str],
    ) -> bool:
        try:
            evidence_ids = [UUID(value) for value in raw_ids]
        except (TypeError, ValueError):
            return False
        if not evidence_ids:
            return False
        count = await self.session.scalar(
            select(func.count())
            .select_from(Evidence)
            .where(
                Evidence.organisation_id == organisation_id,
                Evidence.id.in_(evidence_ids),
                Evidence.validation_state == "verified",
                Evidence.lifecycle_status == "available",
                Evidence.deleted_at.is_(None),
            )
        )
        return int(count or 0) == len(set(evidence_ids))

    def add(self, record: ActionProposal | ActionProposalVersion | ActionAuditEvent) -> None:
        self.session.add(record)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
