from __future__ import annotations

from collections.abc import Sequence
from typing import cast
from uuid import UUID

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    ActionProposal,
    ActionProposalVersion,
    ClosedWonHandover,
    ClosedWonHandoverRevision,
    ClosedWonHandoverSource,
    Company,
    Contact,
    CreateBusinessCase,
    CreateBusinessCaseVersion,
    DealRoom,
    DealRoomRevision,
    Interaction,
    Opportunity,
    RevenueBrainSourceSnapshot,
    Task,
)


class HandoverRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, entity: object) -> None:
        self.session.add(entity)

    async def opportunity(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        *,
        for_update: bool = False,
    ) -> Opportunity | None:
        statement = select(Opportunity).where(
            Opportunity.organisation_id == organisation_id,
            Opportunity.id == opportunity_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(Opportunity | None, await self.session.scalar(statement))

    async def company(self, organisation_id: UUID, company_id: UUID | None) -> Company | None:
        if company_id is None:
            return None
        return cast(
            Company | None,
            await self.session.scalar(
                select(Company).where(
                    Company.organisation_id == organisation_id,
                    Company.id == company_id,
                    Company.archived_at.is_(None),
                )
            ),
        )

    async def handover(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        *,
        for_update: bool = False,
    ) -> ClosedWonHandover | None:
        statement = select(ClosedWonHandover).where(
            ClosedWonHandover.organisation_id == organisation_id,
            ClosedWonHandover.opportunity_id == opportunity_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(ClosedWonHandover | None, await self.session.scalar(statement))

    async def revision(
        self,
        organisation_id: UUID,
        handover_id: UUID,
        revision_id: UUID,
        *,
        for_update: bool = False,
    ) -> ClosedWonHandoverRevision | None:
        statement = select(ClosedWonHandoverRevision).where(
            ClosedWonHandoverRevision.organisation_id == organisation_id,
            ClosedWonHandoverRevision.handover_id == handover_id,
            ClosedWonHandoverRevision.id == revision_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(ClosedWonHandoverRevision | None, await self.session.scalar(statement))

    async def editable_revision(
        self,
        organisation_id: UUID,
        handover_id: UUID,
        *,
        for_update: bool = False,
    ) -> ClosedWonHandoverRevision | None:
        statement = select(ClosedWonHandoverRevision).where(
            ClosedWonHandoverRevision.organisation_id == organisation_id,
            ClosedWonHandoverRevision.handover_id == handover_id,
            ClosedWonHandoverRevision.status.in_(("draft", "in_review")),
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(ClosedWonHandoverRevision | None, await self.session.scalar(statement))

    async def current_approved_revision(
        self,
        organisation_id: UUID,
        handover_id: UUID,
        *,
        for_update: bool = False,
    ) -> ClosedWonHandoverRevision | None:
        statement = select(ClosedWonHandoverRevision).where(
            ClosedWonHandoverRevision.organisation_id == organisation_id,
            ClosedWonHandoverRevision.handover_id == handover_id,
            ClosedWonHandoverRevision.status == "approved",
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(ClosedWonHandoverRevision | None, await self.session.scalar(statement))

    async def revisions(
        self,
        organisation_id: UUID,
        handover_id: UUID,
    ) -> list[ClosedWonHandoverRevision]:
        return list(
            (
                await self.session.scalars(
                    select(ClosedWonHandoverRevision)
                    .where(
                        ClosedWonHandoverRevision.organisation_id == organisation_id,
                        ClosedWonHandoverRevision.handover_id == handover_id,
                    )
                    .order_by(ClosedWonHandoverRevision.revision.desc())
                    .limit(50)
                )
            ).all()
        )

    async def sources(
        self,
        organisation_id: UUID,
        revision_id: UUID,
    ) -> list[ClosedWonHandoverSource]:
        return list(
            (
                await self.session.scalars(
                    select(ClosedWonHandoverSource)
                    .where(
                        ClosedWonHandoverSource.organisation_id == organisation_id,
                        ClosedWonHandoverSource.revision_id == revision_id,
                    )
                    .order_by(ClosedWonHandoverSource.source_type, ClosedWonHandoverSource.label)
                )
            ).all()
        )

    async def delete_sources(self, organisation_id: UUID, revision_id: UUID) -> None:
        await self.session.execute(
            delete(ClosedWonHandoverSource).where(
                ClosedWonHandoverSource.organisation_id == organisation_id,
                ClosedWonHandoverSource.revision_id == revision_id,
            )
        )

    async def latest_published_deal_room(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
    ) -> tuple[DealRoom, DealRoomRevision] | None:
        row = (
            await self.session.execute(
                select(DealRoom, DealRoomRevision)
                .join(
                    DealRoomRevision,
                    and_(
                        DealRoomRevision.organisation_id == DealRoom.organisation_id,
                        DealRoomRevision.room_id == DealRoom.id,
                        DealRoomRevision.id == DealRoom.published_revision_id,
                    ),
                )
                .where(
                    DealRoom.organisation_id == organisation_id,
                    DealRoom.opportunity_id == opportunity_id,
                    DealRoom.published_revision_id.is_not(None),
                )
            )
        ).first()
        return cast(tuple[DealRoom, DealRoomRevision] | None, row)

    async def approved_business_cases(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
    ) -> list[tuple[CreateBusinessCase, CreateBusinessCaseVersion]]:
        rows = await self.session.execute(
            select(CreateBusinessCase, CreateBusinessCaseVersion)
            .join(
                CreateBusinessCaseVersion,
                and_(
                    CreateBusinessCaseVersion.organisation_id == CreateBusinessCase.organisation_id,
                    CreateBusinessCaseVersion.case_id == CreateBusinessCase.id,
                ),
            )
            .where(
                CreateBusinessCase.organisation_id == organisation_id,
                CreateBusinessCase.opportunity_id == opportunity_id,
                CreateBusinessCase.archived_at.is_(None),
                CreateBusinessCaseVersion.review_state == "approved",
                CreateBusinessCaseVersion.approved_at.is_not(None),
            )
            .order_by(CreateBusinessCaseVersion.approved_at.desc(), CreateBusinessCaseVersion.version.desc())
            .limit(5)
        )
        return list(rows.tuples().all())

    async def evidence_snapshots(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
    ) -> list[RevenueBrainSourceSnapshot]:
        candidates = list(
            (
                await self.session.scalars(
                    select(RevenueBrainSourceSnapshot)
                    .where(
                        RevenueBrainSourceSnapshot.organisation_id == organisation_id,
                        RevenueBrainSourceSnapshot.opportunity_id == opportunity_id,
                        RevenueBrainSourceSnapshot.schema_version == 1,
                    )
                    .order_by(
                        RevenueBrainSourceSnapshot.source_evidence_id,
                        RevenueBrainSourceSnapshot.version.desc(),
                    )
                )
            ).all()
        )
        latest: dict[UUID, RevenueBrainSourceSnapshot] = {}
        for snapshot in candidates:
            latest.setdefault(snapshot.source_evidence_id, snapshot)
        return list(latest.values())[:20]

    async def contacts(self, organisation_id: UUID, company_id: UUID | None) -> list[Contact]:
        if company_id is None:
            return []
        return list(
            (
                await self.session.scalars(
                    select(Contact)
                    .where(
                        Contact.organisation_id == organisation_id,
                        Contact.company_id == company_id,
                        Contact.archived_at.is_(None),
                    )
                    .order_by(Contact.updated_at.desc(), Contact.id)
                    .limit(20)
                )
            ).all()
        )

    async def interactions(self, organisation_id: UUID, opportunity_id: UUID) -> list[Interaction]:
        return list(
            (
                await self.session.scalars(
                    select(Interaction)
                    .where(
                        Interaction.organisation_id == organisation_id,
                        Interaction.opportunity_id == opportunity_id,
                        Interaction.deleted_at.is_(None),
                    )
                    .order_by(Interaction.updated_at.desc(), Interaction.id)
                    .limit(20)
                )
            ).all()
        )

    async def tasks(self, organisation_id: UUID, opportunity_id: UUID) -> list[Task]:
        return list(
            (
                await self.session.scalars(
                    select(Task)
                    .where(
                        Task.organisation_id == organisation_id,
                        Task.opportunity_id == opportunity_id,
                        Task.status.in_(("open", "in_progress")),
                    )
                    .order_by(Task.due_at.asc().nullslast(), Task.updated_at.desc(), Task.id)
                    .limit(20)
                )
            ).all()
        )

    async def approved_actions(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
    ) -> Sequence[tuple[ActionProposal, ActionProposalVersion]]:
        rows = await self.session.execute(
            select(ActionProposal, ActionProposalVersion)
            .join(
                ActionProposalVersion,
                and_(
                    ActionProposalVersion.organisation_id == ActionProposal.organisation_id,
                    ActionProposalVersion.action_id == ActionProposal.id,
                    ActionProposalVersion.version == ActionProposal.approved_version,
                ),
            )
            .where(
                ActionProposal.organisation_id == organisation_id,
                ActionProposal.opportunity_id == opportunity_id,
                ActionProposal.status == "approved",
                ActionProposal.approved_version.is_not(None),
            )
            .order_by(ActionProposal.approved_at.desc(), ActionProposal.id)
            .limit(20)
        )
        return rows.tuples().all()
