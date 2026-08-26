from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    ActionExecution,
    ActionProposal,
    Base,
    Company,
    Contact,
    ContactFieldSource,
    ContactSuppression,
    IntegrationConnection,
    Opportunity,
    Organisation,
    OrganisationMembership,
    OrganisationModuleEntitlement,
    OutreachMessage,
    OutreachPersonalizationSource,
    OutreachPolicy,
    OutreachVersion,
    ProspectPerson,
    ProspectResearchObservation,
    ProspectResearchObservationSource,
    ProspectResearchRun,
    ProspectResearchSource,
    User,
)


@dataclass(frozen=True)
class OutreachRecord:
    message: OutreachMessage
    version: OutreachVersion


class OutreachRepository:
    """Every query explicitly carries organisation scope."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def entitlement(self, organisation_id: UUID) -> OrganisationModuleEntitlement | None:
        return cast(
            OrganisationModuleEntitlement | None,
            await self.session.scalar(
                select(OrganisationModuleEntitlement).where(
                    OrganisationModuleEntitlement.organisation_id == organisation_id,
                    OrganisationModuleEntitlement.module_key == "engage",
                )
            ),
        )

    async def policy(self, organisation_id: UUID, *, for_update: bool = False) -> OutreachPolicy | None:
        statement = select(OutreachPolicy).where(OutreachPolicy.organisation_id == organisation_id)
        if for_update:
            statement = statement.with_for_update()
        return cast(OutreachPolicy | None, await self.session.scalar(statement))

    async def contact(self, organisation_id: UUID, contact_id: UUID, *, for_update: bool = False) -> Contact | None:
        statement = select(Contact).where(Contact.organisation_id == organisation_id, Contact.id == contact_id)
        if for_update:
            statement = statement.with_for_update()
        return cast(Contact | None, await self.session.scalar(statement))

    async def company(self, organisation_id: UUID, company_id: UUID) -> Company | None:
        return cast(
            Company | None,
            await self.session.scalar(
                select(Company).where(Company.organisation_id == organisation_id, Company.id == company_id)
            ),
        )

    async def has_active_opportunity(self, organisation_id: UUID, company_id: UUID) -> bool:
        count = await self.session.scalar(
            select(func.count())
            .select_from(Opportunity)
            .where(
                Opportunity.organisation_id == organisation_id,
                Opportunity.company_id == company_id,
                Opportunity.status.in_(("open", "on_hold")),
            )
        )
        return int(count or 0) > 0

    async def organisation(self, organisation_id: UUID) -> Organisation | None:
        return cast(
            Organisation | None,
            await self.session.scalar(select(Organisation).where(Organisation.id == organisation_id)),
        )

    async def user(self, user_id: UUID) -> User | None:
        return cast(User | None, await self.session.scalar(select(User).where(User.id == user_id)))

    async def action(
        self,
        organisation_id: UUID,
        action_id: UUID,
        *,
        for_update: bool = False,
    ) -> ActionProposal | None:
        statement = select(ActionProposal).where(
            ActionProposal.organisation_id == organisation_id,
            ActionProposal.id == action_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(ActionProposal | None, await self.session.scalar(statement))

    async def active_membership(self, organisation_id: UUID, user_id: UUID) -> OrganisationMembership | None:
        return cast(
            OrganisationMembership | None,
            await self.session.scalar(
                select(OrganisationMembership).where(
                    OrganisationMembership.organisation_id == organisation_id,
                    OrganisationMembership.user_id == user_id,
                    OrganisationMembership.status == "active",
                )
            ),
        )

    async def email_source(
        self,
        organisation_id: UUID,
        contact_id: UUID,
        value_fingerprint: str,
    ) -> ContactFieldSource | None:
        return cast(
            ContactFieldSource | None,
            await self.session.scalar(
                select(ContactFieldSource)
                .where(
                    ContactFieldSource.organisation_id == organisation_id,
                    ContactFieldSource.contact_id == contact_id,
                    ContactFieldSource.field_key == "email",
                    ContactFieldSource.value_fingerprint == value_fingerprint,
                    ContactFieldSource.active.is_(True),
                )
                .order_by(ContactFieldSource.observed_at.desc())
                .limit(1)
            ),
        )

    async def suppression(self, organisation_id: UUID, email_fingerprint: str) -> ContactSuppression | None:
        return cast(
            ContactSuppression | None,
            await self.session.scalar(
                select(ContactSuppression).where(
                    ContactSuppression.organisation_id == organisation_id,
                    ContactSuppression.email_fingerprint == email_fingerprint,
                )
            ),
        )

    async def message(
        self,
        organisation_id: UUID,
        outreach_id: UUID,
        *,
        for_update: bool = False,
    ) -> OutreachRecord | None:
        statement = (
            select(OutreachMessage, OutreachVersion)
            .join(
                OutreachVersion,
                and_(
                    OutreachVersion.organisation_id == OutreachMessage.organisation_id,
                    OutreachVersion.outreach_id == OutreachMessage.id,
                    OutreachVersion.version == OutreachMessage.current_version,
                ),
            )
            .where(
                OutreachMessage.organisation_id == organisation_id,
                OutreachMessage.id == outreach_id,
            )
        )
        if for_update:
            statement = statement.with_for_update(of=OutreachMessage)
        row = (await self.session.execute(statement)).one_or_none()
        return OutreachRecord(row[0], row[1]) if row is not None else None

    async def message_by_action(self, organisation_id: UUID, action_id: UUID) -> OutreachRecord | None:
        row = (
            await self.session.execute(
                select(OutreachMessage, OutreachVersion)
                .join(
                    OutreachVersion,
                    and_(
                        OutreachVersion.organisation_id == OutreachMessage.organisation_id,
                        OutreachVersion.outreach_id == OutreachMessage.id,
                        OutreachVersion.version == OutreachMessage.approved_version,
                    ),
                )
                .where(
                    OutreachMessage.organisation_id == organisation_id,
                    OutreachMessage.action_id == action_id,
                )
            )
        ).one_or_none()
        return OutreachRecord(row[0], row[1]) if row is not None else None

    async def version_sources(
        self,
        organisation_id: UUID,
        version_id: UUID,
    ) -> list[OutreachPersonalizationSource]:
        values = await self.session.scalars(
            select(OutreachPersonalizationSource)
            .where(
                OutreachPersonalizationSource.organisation_id == organisation_id,
                OutreachPersonalizationSource.outreach_version_id == version_id,
            )
            .order_by(OutreachPersonalizationSource.created_at, OutreachPersonalizationSource.id)
        )
        return list(values.all())

    async def observation(self, organisation_id: UUID, observation_id: UUID) -> ProspectResearchObservation | None:
        return cast(
            ProspectResearchObservation | None,
            await self.session.scalar(
                select(ProspectResearchObservation).where(
                    ProspectResearchObservation.organisation_id == organisation_id,
                    ProspectResearchObservation.id == observation_id,
                )
            ),
        )

    async def research_source(self, organisation_id: UUID, source_id: UUID) -> ProspectResearchSource | None:
        return cast(
            ProspectResearchSource | None,
            await self.session.scalar(
                select(ProspectResearchSource).where(
                    ProspectResearchSource.organisation_id == organisation_id,
                    ProspectResearchSource.id == source_id,
                )
            ),
        )

    async def prospect_person_for_contact(self, organisation_id: UUID, contact_id: UUID) -> ProspectPerson | None:
        return cast(
            ProspectPerson | None,
            await self.session.scalar(
                select(ProspectPerson).where(
                    ProspectPerson.organisation_id == organisation_id,
                    ProspectPerson.promoted_contact_id == contact_id,
                )
            ),
        )

    async def current_run(
        self,
        organisation_id: UUID,
        target_id: UUID,
        *,
        person_id: UUID | None,
    ) -> ProspectResearchRun | None:
        person_condition = (
            ProspectResearchRun.person_id.is_(None) if person_id is None else ProspectResearchRun.person_id == person_id
        )
        return cast(
            ProspectResearchRun | None,
            await self.session.scalar(
                select(ProspectResearchRun)
                .where(
                    ProspectResearchRun.organisation_id == organisation_id,
                    ProspectResearchRun.target_id == target_id,
                    person_condition,
                    ProspectResearchRun.status.in_(("completed", "partial")),
                )
                .order_by(ProspectResearchRun.completed_at.desc(), ProspectResearchRun.created_at.desc())
                .limit(1)
            ),
        )

    async def observations_with_sources(
        self,
        organisation_id: UUID,
        run_id: UUID,
    ) -> list[tuple[ProspectResearchObservation, ProspectResearchSource]]:
        rows = (
            await self.session.execute(
                select(ProspectResearchObservation, ProspectResearchSource)
                .join(
                    ProspectResearchObservationSource,
                    and_(
                        ProspectResearchObservationSource.organisation_id
                        == ProspectResearchObservation.organisation_id,
                        ProspectResearchObservationSource.observation_id == ProspectResearchObservation.id,
                        ProspectResearchObservationSource.run_id == ProspectResearchObservation.run_id,
                    ),
                )
                .join(
                    ProspectResearchSource,
                    and_(
                        ProspectResearchSource.organisation_id == ProspectResearchObservationSource.organisation_id,
                        ProspectResearchSource.id == ProspectResearchObservationSource.source_id,
                        ProspectResearchSource.run_id == ProspectResearchObservationSource.run_id,
                    ),
                )
                .where(
                    ProspectResearchObservation.organisation_id == organisation_id,
                    ProspectResearchObservation.run_id == run_id,
                )
                .order_by(
                    ProspectResearchObservation.relevance.asc(),
                    ProspectResearchObservation.observed_at.desc(),
                    ProspectResearchObservation.id,
                )
            )
        ).all()
        selected: dict[UUID, tuple[ProspectResearchObservation, ProspectResearchSource]] = {}
        for observation, source in rows:
            selected.setdefault(observation.id, (observation, source))
        return list(selected.values())

    async def latest_execution(self, organisation_id: UUID, action_id: UUID) -> ActionExecution | None:
        return cast(
            ActionExecution | None,
            await self.session.scalar(
                select(ActionExecution)
                .where(ActionExecution.organisation_id == organisation_id, ActionExecution.action_id == action_id)
                .order_by(ActionExecution.created_at.desc())
                .limit(1)
            ),
        )

    async def history(
        self, organisation_id: UUID, contact_id: UUID
    ) -> list[tuple[OutreachMessage, OutreachVersion, ActionExecution | None]]:
        rows = (
            await self.session.execute(
                select(OutreachMessage, OutreachVersion, ActionExecution)
                .join(
                    OutreachVersion,
                    and_(
                        OutreachVersion.organisation_id == OutreachMessage.organisation_id,
                        OutreachVersion.outreach_id == OutreachMessage.id,
                        OutreachVersion.version == OutreachMessage.current_version,
                    ),
                )
                .outerjoin(
                    ActionExecution,
                    and_(
                        ActionExecution.organisation_id == OutreachMessage.organisation_id,
                        ActionExecution.action_id == OutreachMessage.action_id,
                    ),
                )
                .where(
                    OutreachMessage.organisation_id == organisation_id,
                    OutreachMessage.contact_id == contact_id,
                )
                .order_by(OutreachMessage.created_at.desc(), ActionExecution.created_at.desc())
            )
        ).all()
        selected: dict[UUID, tuple[OutreachMessage, OutreachVersion, ActionExecution | None]] = {}
        for message, version, execution in rows:
            selected.setdefault(message.id, (message, version, execution))
        return list(selected.values())

    async def successful_contact_send_since(
        self,
        organisation_id: UUID,
        contact_id: UUID,
        since: datetime,
        *,
        excluding_action_id: UUID,
    ) -> bool:
        count = await self.session.scalar(
            select(func.count())
            .select_from(ActionExecution)
            .join(
                OutreachMessage,
                and_(
                    OutreachMessage.organisation_id == ActionExecution.organisation_id,
                    OutreachMessage.action_id == ActionExecution.action_id,
                ),
            )
            .where(
                ActionExecution.organisation_id == organisation_id,
                OutreachMessage.contact_id == contact_id,
                ActionExecution.action_id != excluding_action_id,
                ActionExecution.execution_status.in_(("simulated_success", "succeeded")),
                ActionExecution.completed_at >= since,
            )
        )
        return int(count or 0) > 0

    async def send_counts_since(
        self,
        organisation_id: UUID,
        user_id: UUID,
        since: datetime,
        *,
        excluding_action_id: UUID,
    ) -> tuple[int, int]:
        base = (
            select(func.count())
            .select_from(ActionExecution)
            .join(
                OutreachMessage,
                and_(
                    OutreachMessage.organisation_id == ActionExecution.organisation_id,
                    OutreachMessage.action_id == ActionExecution.action_id,
                ),
            )
            .where(
                ActionExecution.organisation_id == organisation_id,
                ActionExecution.action_id != excluding_action_id,
                ActionExecution.confirmed_at >= since,
            )
        )
        organisation_count = int(await self.session.scalar(base) or 0)
        user_count = int(await self.session.scalar(base.where(ActionExecution.confirmed_by_user_id == user_id)) or 0)
        return user_count, organisation_count

    async def active_email_connection_for_user(
        self,
        organisation_id: UUID,
        user_id: UUID,
    ) -> IntegrationConnection | None:
        return cast(
            IntegrationConnection | None,
            await self.session.scalar(
                select(IntegrationConnection)
                .where(
                    IntegrationConnection.organisation_id == organisation_id,
                    IntegrationConnection.connector_key == "mock_email",
                    IntegrationConnection.connection_status == "active",
                    IntegrationConnection.created_by_user_id == user_id,
                )
                .limit(1)
            ),
        )

    def add(self, entity: Base) -> None:
        self.session.add(entity)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
