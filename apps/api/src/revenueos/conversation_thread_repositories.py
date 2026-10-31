from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Subquery

from revenueos.interaction_intelligence_eligibility import eligible_interaction_snapshot_ids
from revenueos.models import (
    CaptureSession,
    Contact,
    ConversationThread,
    ConversationThreadAssignment,
    Interaction,
    InteractionIntelligenceSnapshot,
    Meeting,
    MeetingParticipant,
    Opportunity,
)


@dataclass(frozen=True)
class ConversationThreadRecord:
    thread: ConversationThread
    interaction_count: int
    last_interaction_at: datetime | None


@dataclass(frozen=True)
class ConversationThreadAssignmentRecord:
    assignment: ConversationThreadAssignment
    thread: ConversationThreadRecord | None


@dataclass(frozen=True)
class InteractionCompanyContext:
    company_id: UUID | None
    source_company_ids: tuple[UUID, ...]

    @property
    def ambiguous(self) -> bool:
        return len(self.source_company_ids) > 1


@dataclass(frozen=True)
class ConversationSnapshotRecord:
    snapshot: InteractionIntelligenceSnapshot
    interaction: Interaction
    occurred_at: datetime


class ConversationThreadRepository:
    """Tenant-scoped initiative grouping and validated-memory reads."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def interaction(
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

    async def thread(
        self,
        organisation_id: UUID,
        thread_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationThreadRecord | None:
        count_subquery, latest_subquery = self._thread_summaries(organisation_id)
        statement = (
            select(
                ConversationThread,
                func.coalesce(count_subquery.c.interaction_count, 0),
                latest_subquery.c.last_interaction_at,
            )
            .outerjoin(
                count_subquery,
                count_subquery.c.thread_id == ConversationThread.id,
            )
            .outerjoin(
                latest_subquery,
                latest_subquery.c.thread_id == ConversationThread.id,
            )
            .where(
                ConversationThread.organisation_id == organisation_id,
                ConversationThread.id == thread_id,
            )
        )
        if for_update:
            statement = statement.with_for_update(of=ConversationThread)
        row = (await self.session.execute(statement)).one_or_none()
        if row is None:
            return None
        return ConversationThreadRecord(
            thread=cast(ConversationThread, row[0]),
            interaction_count=int(row[1]),
            last_interaction_at=cast(datetime | None, row[2]),
        )

    async def list_threads(
        self,
        organisation_id: UUID,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ConversationThreadRecord]:
        count_subquery, latest_subquery = self._thread_summaries(organisation_id)
        conditions = [ConversationThread.organisation_id == organisation_id]
        if status is not None:
            conditions.append(ConversationThread.status == status)
        rows = (
            await self.session.execute(
                select(
                    ConversationThread,
                    func.coalesce(count_subquery.c.interaction_count, 0),
                    latest_subquery.c.last_interaction_at,
                )
                .outerjoin(count_subquery, count_subquery.c.thread_id == ConversationThread.id)
                .outerjoin(latest_subquery, latest_subquery.c.thread_id == ConversationThread.id)
                .where(*conditions)
                .order_by(
                    latest_subquery.c.last_interaction_at.desc().nullslast(),
                    ConversationThread.updated_at.desc(),
                    ConversationThread.id.asc(),
                )
                .limit(limit)
            )
        ).all()
        return [
            ConversationThreadRecord(
                thread=cast(ConversationThread, row[0]),
                interaction_count=int(row[1]),
                last_interaction_at=cast(datetime | None, row[2]),
            )
            for row in rows
        ]

    async def assignment(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        *,
        for_update: bool = False,
    ) -> ConversationThreadAssignment | None:
        statement = select(ConversationThreadAssignment).where(
            ConversationThreadAssignment.organisation_id == organisation_id,
            ConversationThreadAssignment.interaction_id == interaction_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(ConversationThreadAssignment | None, await self.session.scalar(statement))

    async def assignment_record(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
    ) -> ConversationThreadAssignmentRecord | None:
        assignment = await self.assignment(organisation_id, interaction_id)
        if assignment is None:
            return None
        if assignment.thread_id is None:
            return ConversationThreadAssignmentRecord(assignment=assignment, thread=None)
        thread = await self.thread(organisation_id, assignment.thread_id)
        return ConversationThreadAssignmentRecord(assignment=assignment, thread=thread)

    async def interaction_company_context(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
    ) -> InteractionCompanyContext | None:
        """Resolve every authoritative company relationship for an interaction.

        The direct company, linked opportunity and phone-call Person are equal
        authorities. More than one distinct company is ambiguous and callers
        must fail closed for grouping writes rather than choosing precedence.
        """

        row = (
            await self.session.execute(
                select(
                    Interaction.company_id,
                    Opportunity.company_id,
                    Contact.company_id,
                )
                .select_from(Interaction)
                .outerjoin(
                    Opportunity,
                    and_(
                        Opportunity.organisation_id == Interaction.organisation_id,
                        Opportunity.id == Interaction.opportunity_id,
                    ),
                )
                .outerjoin(
                    Contact,
                    and_(
                        Contact.organisation_id == Interaction.organisation_id,
                        Contact.id == Interaction.contact_id,
                    ),
                )
                .where(
                    Interaction.organisation_id == organisation_id,
                    Interaction.id == interaction_id,
                    Interaction.deleted_at.is_(None),
                )
            )
        ).one_or_none()
        if row is None:
            return None
        source_company_ids = tuple(
            sorted(
                {cast(UUID, value) for value in row if value is not None},
                key=str,
            )
        )
        return InteractionCompanyContext(
            company_id=source_company_ids[0] if len(source_company_ids) == 1 else None,
            source_company_ids=source_company_ids,
        )

    async def participant_ids_for_interaction(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
    ) -> set[UUID]:
        direct = await self.session.scalar(
            select(Interaction.contact_id).where(
                Interaction.organisation_id == organisation_id,
                Interaction.id == interaction_id,
                Interaction.deleted_at.is_(None),
            )
        )
        participant_ids = {
            value
            for value in (
                await self.session.scalars(
                    select(MeetingParticipant.contact_id)
                    .join(
                        Meeting,
                        and_(
                            Meeting.organisation_id == MeetingParticipant.organisation_id,
                            Meeting.id == MeetingParticipant.meeting_id,
                        ),
                    )
                    .where(
                        Meeting.organisation_id == organisation_id,
                        Meeting.interaction_id == interaction_id,
                        Meeting.deleted_at.is_(None),
                        MeetingParticipant.deleted_at.is_(None),
                        MeetingParticipant.contact_id.is_not(None),
                    )
                )
            ).all()
            if value is not None
        }
        if direct is not None:
            participant_ids.add(direct)
        return participant_ids

    async def participant_ids_for_thread(
        self,
        organisation_id: UUID,
        thread_id: UUID,
    ) -> set[UUID]:
        direct_ids = {
            value
            for value in (
                await self.session.scalars(
                    select(Interaction.contact_id)
                    .join(
                        ConversationThreadAssignment,
                        and_(
                            ConversationThreadAssignment.organisation_id == Interaction.organisation_id,
                            ConversationThreadAssignment.interaction_id == Interaction.id,
                        ),
                    )
                    .where(
                        ConversationThreadAssignment.organisation_id == organisation_id,
                        ConversationThreadAssignment.thread_id == thread_id,
                        Interaction.deleted_at.is_(None),
                        Interaction.contact_id.is_not(None),
                    )
                )
            ).all()
            if value is not None
        }
        meeting_ids = {
            value
            for value in (
                await self.session.scalars(
                    select(MeetingParticipant.contact_id)
                    .join(
                        Meeting,
                        and_(
                            Meeting.organisation_id == MeetingParticipant.organisation_id,
                            Meeting.id == MeetingParticipant.meeting_id,
                        ),
                    )
                    .join(
                        ConversationThreadAssignment,
                        and_(
                            ConversationThreadAssignment.organisation_id == Meeting.organisation_id,
                            ConversationThreadAssignment.interaction_id == Meeting.interaction_id,
                        ),
                    )
                    .where(
                        ConversationThreadAssignment.organisation_id == organisation_id,
                        ConversationThreadAssignment.thread_id == thread_id,
                        Meeting.deleted_at.is_(None),
                        MeetingParticipant.deleted_at.is_(None),
                        MeetingParticipant.contact_id.is_not(None),
                    )
                )
            ).all()
            if value is not None
        }
        return direct_ids | meeting_ids

    async def current_snapshot_records(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
    ) -> list[ConversationSnapshotRecord]:
        return await self._snapshot_records(
            organisation_id,
            interaction_ids=(interaction_id,),
            completed_only=False,
        )

    async def thread_snapshot_records(
        self,
        organisation_id: UUID,
        thread_id: UUID,
        *,
        before_at: datetime | None,
    ) -> list[ConversationSnapshotRecord]:
        statement = (
            select(Interaction.id)
            .join(
                ConversationThreadAssignment,
                and_(
                    ConversationThreadAssignment.organisation_id == Interaction.organisation_id,
                    ConversationThreadAssignment.interaction_id == Interaction.id,
                ),
            )
            .where(
                ConversationThreadAssignment.organisation_id == organisation_id,
                ConversationThreadAssignment.thread_id == thread_id,
                Interaction.deleted_at.is_(None),
                Interaction.lifecycle_status == "completed",
            )
        )
        if before_at is not None:
            effective_at = func.coalesce(
                Interaction.actual_end_at,
                Interaction.actual_start_at,
                Interaction.scheduled_start_at,
                Interaction.created_at,
            )
            statement = statement.where(effective_at <= before_at)
        ids = tuple((await self.session.scalars(statement)).all())
        if not ids:
            return []
        return await self._snapshot_records(
            organisation_id,
            interaction_ids=ids,
            completed_only=True,
        )

    async def _snapshot_records(
        self,
        organisation_id: UUID,
        *,
        interaction_ids: tuple[UUID, ...],
        completed_only: bool,
    ) -> list[ConversationSnapshotRecord]:
        conditions = [
            InteractionIntelligenceSnapshot.organisation_id == organisation_id,
            InteractionIntelligenceSnapshot.interaction_id.in_(interaction_ids),
            InteractionIntelligenceSnapshot.validation_state == "validated",
            Interaction.organisation_id == organisation_id,
            Interaction.deleted_at.is_(None),
            CaptureSession.organisation_id == organisation_id,
            CaptureSession.status == "completed",
            CaptureSession.deleted_at.is_(None),
        ]
        if completed_only:
            conditions.append(Interaction.lifecycle_status == "completed")
        rows = (
            await self.session.execute(
                select(InteractionIntelligenceSnapshot, Interaction)
                .join(
                    Interaction,
                    and_(
                        Interaction.organisation_id == InteractionIntelligenceSnapshot.organisation_id,
                        Interaction.id == InteractionIntelligenceSnapshot.interaction_id,
                    ),
                )
                .join(
                    CaptureSession,
                    and_(
                        CaptureSession.organisation_id == InteractionIntelligenceSnapshot.organisation_id,
                        CaptureSession.id == InteractionIntelligenceSnapshot.session_id,
                        CaptureSession.interaction_id == InteractionIntelligenceSnapshot.interaction_id,
                    ),
                )
                .where(*conditions)
                .order_by(
                    InteractionIntelligenceSnapshot.interaction_id.asc(),
                    InteractionIntelligenceSnapshot.version.desc(),
                    InteractionIntelligenceSnapshot.created_at.desc(),
                    InteractionIntelligenceSnapshot.id.desc(),
                )
            )
        ).all()
        snapshots = [cast(InteractionIntelligenceSnapshot, row[0]) for row in rows]
        eligible_ids = await eligible_interaction_snapshot_ids(self.session, organisation_id, snapshots)
        selected: dict[UUID, ConversationSnapshotRecord] = {}
        for snapshot, interaction in rows:
            if snapshot.id not in eligible_ids or interaction.id in selected:
                continue
            occurred_at = (
                interaction.actual_end_at
                or interaction.actual_start_at
                or interaction.scheduled_start_at
                or snapshot.created_at
            )
            selected[interaction.id] = ConversationSnapshotRecord(
                snapshot=cast(InteractionIntelligenceSnapshot, snapshot),
                interaction=cast(Interaction, interaction),
                occurred_at=cast(datetime, occurred_at),
            )
        return sorted(selected.values(), key=lambda item: (item.occurred_at, item.interaction.id))

    def add(self, value: object) -> None:
        self.session.add(value)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    @staticmethod
    def _thread_summaries(organisation_id: UUID) -> tuple[Subquery, Subquery]:
        effective_at = func.coalesce(
            Interaction.actual_end_at,
            Interaction.actual_start_at,
            Interaction.scheduled_start_at,
            Interaction.created_at,
        )
        base = (
            select(
                ConversationThreadAssignment.thread_id.label("thread_id"),
                Interaction.id.label("interaction_id"),
                effective_at.label("effective_at"),
            )
            .join(
                Interaction,
                and_(
                    Interaction.organisation_id == ConversationThreadAssignment.organisation_id,
                    Interaction.id == ConversationThreadAssignment.interaction_id,
                ),
            )
            .where(
                ConversationThreadAssignment.organisation_id == organisation_id,
                Interaction.deleted_at.is_(None),
            )
            .subquery()
        )
        counts = (
            select(base.c.thread_id, func.count(base.c.interaction_id).label("interaction_count"))
            .group_by(base.c.thread_id)
            .subquery()
        )
        latest = (
            select(base.c.thread_id, func.max(base.c.effective_at).label("last_interaction_at"))
            .group_by(base.c.thread_id)
            .subquery()
        )
        return counts, latest
