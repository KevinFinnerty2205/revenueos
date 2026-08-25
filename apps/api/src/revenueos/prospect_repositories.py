from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    Base,
    Company,
    Contact,
    ContactFieldSource,
    Organisation,
    OrganisationMembership,
    OrganisationModuleEntitlement,
    ProspectBuyingRoleHypothesis,
    ProspectBuyingRoleSource,
    ProspectContactPoint,
    ProspectPerson,
    ProspectResearchObservation,
    ProspectResearchObservationSource,
    ProspectResearchRun,
    ProspectResearchSource,
    ProspectResearchTarget,
)

ACTIVE_RUN_STATUSES = ("pending", "fetching", "synthesizing")
USABLE_RUN_STATUSES = ("completed", "partial")


class ProspectRepository:
    """Prospect persistence with explicit organisation predicates on every query."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def entitlement(self, organisation_id: UUID) -> OrganisationModuleEntitlement | None:
        return cast(
            OrganisationModuleEntitlement | None,
            await self.session.scalar(
                select(OrganisationModuleEntitlement).where(
                    OrganisationModuleEntitlement.organisation_id == organisation_id,
                    OrganisationModuleEntitlement.module_key == "prospect",
                )
            ),
        )

    async def lock_organisation(self, organisation_id: UUID) -> None:
        await self.session.scalar(select(Organisation.id).where(Organisation.id == organisation_id).with_for_update())

    async def get_target(
        self,
        organisation_id: UUID,
        target_id: UUID,
        *,
        for_update: bool = False,
    ) -> ProspectResearchTarget | None:
        statement = select(ProspectResearchTarget).where(
            ProspectResearchTarget.organisation_id == organisation_id,
            ProspectResearchTarget.id == target_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(ProspectResearchTarget | None, await self.session.scalar(statement))

    async def target_by_domain(
        self,
        organisation_id: UUID,
        domain: str,
    ) -> ProspectResearchTarget | None:
        return cast(
            ProspectResearchTarget | None,
            await self.session.scalar(
                select(ProspectResearchTarget).where(
                    ProspectResearchTarget.organisation_id == organisation_id,
                    ProspectResearchTarget.normalized_domain == domain,
                )
            ),
        )

    async def target_by_provider_candidate(
        self,
        organisation_id: UUID,
        provider_key: str,
        candidate_id: str,
    ) -> ProspectResearchTarget | None:
        return cast(
            ProspectResearchTarget | None,
            await self.session.scalar(
                select(ProspectResearchTarget).where(
                    ProspectResearchTarget.organisation_id == organisation_id,
                    ProspectResearchTarget.provider_key == provider_key,
                    ProspectResearchTarget.provider_candidate_id == candidate_id,
                )
            ),
        )

    async def recent_targets(self, organisation_id: UUID, *, limit: int) -> list[ProspectResearchTarget]:
        values = await self.session.scalars(
            select(ProspectResearchTarget)
            .where(ProspectResearchTarget.organisation_id == organisation_id)
            .order_by(ProspectResearchTarget.updated_at.desc(), ProspectResearchTarget.id.desc())
            .limit(limit)
        )
        return list(values.all())

    async def company_by_domain(self, organisation_id: UUID, domain: str) -> Company | None:
        return cast(
            Company | None,
            await self.session.scalar(
                select(Company)
                .where(
                    Company.organisation_id == organisation_id,
                    Company.normalized_domain == domain,
                )
                .order_by(Company.created_at, Company.id)
                .limit(1)
            ),
        )

    async def get_company(self, organisation_id: UUID, company_id: UUID) -> Company | None:
        return cast(
            Company | None,
            await self.session.scalar(
                select(Company).where(Company.organisation_id == organisation_id, Company.id == company_id)
            ),
        )

    async def target_for_company(
        self,
        organisation_id: UUID,
        company_id: UUID,
    ) -> ProspectResearchTarget | None:
        return cast(
            ProspectResearchTarget | None,
            await self.session.scalar(
                select(ProspectResearchTarget).where(
                    ProspectResearchTarget.organisation_id == organisation_id,
                    ProspectResearchTarget.promoted_company_id == company_id,
                )
            ),
        )

    async def get_run(self, organisation_id: UUID, run_id: UUID) -> ProspectResearchRun | None:
        return cast(
            ProspectResearchRun | None,
            await self.session.scalar(
                select(ProspectResearchRun).where(
                    ProspectResearchRun.organisation_id == organisation_id,
                    ProspectResearchRun.id == run_id,
                )
            ),
        )

    async def runs_for_target(self, organisation_id: UUID, target_id: UUID) -> list[ProspectResearchRun]:
        values = await self.session.scalars(
            select(ProspectResearchRun)
            .where(
                ProspectResearchRun.organisation_id == organisation_id,
                ProspectResearchRun.target_id == target_id,
                ProspectResearchRun.person_id.is_(None),
            )
            .order_by(ProspectResearchRun.created_at.desc(), ProspectResearchRun.id.desc())
        )
        return list(values.all())

    async def current_run(self, organisation_id: UUID, target_id: UUID) -> ProspectResearchRun | None:
        return cast(
            ProspectResearchRun | None,
            await self.session.scalar(
                select(ProspectResearchRun)
                .where(
                    ProspectResearchRun.organisation_id == organisation_id,
                    ProspectResearchRun.target_id == target_id,
                    ProspectResearchRun.person_id.is_(None),
                    ProspectResearchRun.status.in_(USABLE_RUN_STATUSES),
                )
                .order_by(ProspectResearchRun.completed_at.desc(), ProspectResearchRun.created_at.desc())
                .limit(1)
            ),
        )

    async def active_run(self, organisation_id: UUID, target_id: UUID) -> ProspectResearchRun | None:
        return cast(
            ProspectResearchRun | None,
            await self.session.scalar(
                select(ProspectResearchRun)
                .where(
                    ProspectResearchRun.organisation_id == organisation_id,
                    ProspectResearchRun.target_id == target_id,
                    ProspectResearchRun.person_id.is_(None),
                    ProspectResearchRun.status.in_(ACTIVE_RUN_STATUSES),
                )
                .order_by(ProspectResearchRun.created_at.desc())
                .limit(1)
            ),
        )

    async def fresh_run(
        self,
        organisation_id: UUID,
        target_id: UUID,
        *,
        fresh_after: datetime,
    ) -> ProspectResearchRun | None:
        return cast(
            ProspectResearchRun | None,
            await self.session.scalar(
                select(ProspectResearchRun)
                .where(
                    ProspectResearchRun.organisation_id == organisation_id,
                    ProspectResearchRun.target_id == target_id,
                    ProspectResearchRun.person_id.is_(None),
                    ProspectResearchRun.status.in_(USABLE_RUN_STATUSES),
                    ProspectResearchRun.completed_at >= fresh_after,
                )
                .order_by(ProspectResearchRun.completed_at.desc())
                .limit(1)
            ),
        )

    async def run_sequence(self, organisation_id: UUID, target_id: UUID) -> int:
        count = await self.session.scalar(
            select(func.count())
            .select_from(ProspectResearchRun)
            .where(
                ProspectResearchRun.organisation_id == organisation_id,
                ProspectResearchRun.target_id == target_id,
                ProspectResearchRun.person_id.is_(None),
            )
        )
        return int(count or 0)

    async def sources_for_run(self, organisation_id: UUID, run_id: UUID) -> list[ProspectResearchSource]:
        values = await self.session.scalars(
            select(ProspectResearchSource)
            .where(
                ProspectResearchSource.organisation_id == organisation_id,
                ProspectResearchSource.run_id == run_id,
            )
            .order_by(ProspectResearchSource.published_at.desc(), ProspectResearchSource.id)
        )
        return list(values.all())

    async def observations_for_run(
        self,
        organisation_id: UUID,
        run_id: UUID,
    ) -> list[ProspectResearchObservation]:
        values = await self.session.scalars(
            select(ProspectResearchObservation)
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
        return list(values.all())

    async def observation_source_links(
        self,
        organisation_id: UUID,
        run_id: UUID,
    ) -> list[ProspectResearchObservationSource]:
        values = await self.session.scalars(
            select(ProspectResearchObservationSource).where(
                ProspectResearchObservationSource.organisation_id == organisation_id,
                ProspectResearchObservationSource.run_id == run_id,
            )
        )
        return list(values.all())

    async def active_run_count(self, organisation_id: UUID) -> int:
        count = await self.session.scalar(
            select(func.count())
            .select_from(ProspectResearchRun)
            .where(
                ProspectResearchRun.organisation_id == organisation_id,
                ProspectResearchRun.status.in_(ACTIVE_RUN_STATUSES),
            )
        )
        return int(count or 0)

    async def get_person(
        self,
        organisation_id: UUID,
        person_id: UUID,
        *,
        for_update: bool = False,
    ) -> ProspectPerson | None:
        statement = select(ProspectPerson).where(
            ProspectPerson.organisation_id == organisation_id,
            ProspectPerson.id == person_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(ProspectPerson | None, await self.session.scalar(statement))

    async def person_by_provider_identity(
        self,
        organisation_id: UUID,
        target_id: UUID,
        provider_key: str,
        provider_person_id: str,
    ) -> ProspectPerson | None:
        return cast(
            ProspectPerson | None,
            await self.session.scalar(
                select(ProspectPerson).where(
                    ProspectPerson.organisation_id == organisation_id,
                    ProspectPerson.target_id == target_id,
                    ProspectPerson.provider_key == provider_key,
                    ProspectPerson.provider_person_id == provider_person_id,
                )
            ),
        )

    async def people_for_target(self, organisation_id: UUID, target_id: UUID) -> list[ProspectPerson]:
        values = await self.session.scalars(
            select(ProspectPerson)
            .where(
                ProspectPerson.organisation_id == organisation_id,
                ProspectPerson.target_id == target_id,
            )
            .order_by(ProspectPerson.display_name, ProspectPerson.id)
        )
        return list(values.all())

    async def runs_for_person(self, organisation_id: UUID, person_id: UUID) -> list[ProspectResearchRun]:
        values = await self.session.scalars(
            select(ProspectResearchRun)
            .where(
                ProspectResearchRun.organisation_id == organisation_id,
                ProspectResearchRun.person_id == person_id,
            )
            .order_by(ProspectResearchRun.created_at.desc(), ProspectResearchRun.id.desc())
        )
        return list(values.all())

    async def current_person_run(self, organisation_id: UUID, person_id: UUID) -> ProspectResearchRun | None:
        return cast(
            ProspectResearchRun | None,
            await self.session.scalar(
                select(ProspectResearchRun)
                .where(
                    ProspectResearchRun.organisation_id == organisation_id,
                    ProspectResearchRun.person_id == person_id,
                    ProspectResearchRun.status.in_(USABLE_RUN_STATUSES),
                )
                .order_by(ProspectResearchRun.completed_at.desc(), ProspectResearchRun.created_at.desc())
                .limit(1)
            ),
        )

    async def active_person_run(self, organisation_id: UUID, person_id: UUID) -> ProspectResearchRun | None:
        return cast(
            ProspectResearchRun | None,
            await self.session.scalar(
                select(ProspectResearchRun)
                .where(
                    ProspectResearchRun.organisation_id == organisation_id,
                    ProspectResearchRun.person_id == person_id,
                    ProspectResearchRun.status.in_(ACTIVE_RUN_STATUSES),
                )
                .order_by(ProspectResearchRun.created_at.desc())
                .limit(1)
            ),
        )

    async def fresh_person_run(
        self,
        organisation_id: UUID,
        person_id: UUID,
        *,
        fresh_after: datetime,
    ) -> ProspectResearchRun | None:
        return cast(
            ProspectResearchRun | None,
            await self.session.scalar(
                select(ProspectResearchRun)
                .where(
                    ProspectResearchRun.organisation_id == organisation_id,
                    ProspectResearchRun.person_id == person_id,
                    ProspectResearchRun.status.in_(USABLE_RUN_STATUSES),
                    ProspectResearchRun.completed_at >= fresh_after,
                )
                .order_by(ProspectResearchRun.completed_at.desc())
                .limit(1)
            ),
        )

    async def hypotheses_for_run(
        self,
        organisation_id: UUID,
        run_id: UUID,
    ) -> list[ProspectBuyingRoleHypothesis]:
        values = await self.session.scalars(
            select(ProspectBuyingRoleHypothesis)
            .where(
                ProspectBuyingRoleHypothesis.organisation_id == organisation_id,
                ProspectBuyingRoleHypothesis.run_id == run_id,
            )
            .order_by(ProspectBuyingRoleHypothesis.hypothesized_role, ProspectBuyingRoleHypothesis.id)
        )
        return list(values.all())

    async def hypothesis(
        self,
        organisation_id: UUID,
        person_id: UUID,
        hypothesis_id: UUID,
        *,
        for_update: bool = False,
    ) -> ProspectBuyingRoleHypothesis | None:
        statement = select(ProspectBuyingRoleHypothesis).where(
            ProspectBuyingRoleHypothesis.organisation_id == organisation_id,
            ProspectBuyingRoleHypothesis.person_id == person_id,
            ProspectBuyingRoleHypothesis.id == hypothesis_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(ProspectBuyingRoleHypothesis | None, await self.session.scalar(statement))

    async def buying_role_source_links(
        self,
        organisation_id: UUID,
        run_id: UUID,
    ) -> list[ProspectBuyingRoleSource]:
        values = await self.session.scalars(
            select(ProspectBuyingRoleSource).where(
                ProspectBuyingRoleSource.organisation_id == organisation_id,
                ProspectBuyingRoleSource.run_id == run_id,
            )
        )
        return list(values.all())

    async def contact_points_for_run(
        self,
        organisation_id: UUID,
        run_id: UUID,
        *,
        current_at: datetime,
    ) -> list[ProspectContactPoint]:
        values = await self.session.scalars(
            select(ProspectContactPoint)
            .where(
                ProspectContactPoint.organisation_id == organisation_id,
                ProspectContactPoint.run_id == run_id,
                ProspectContactPoint.active.is_(True),
                or_(ProspectContactPoint.expires_at.is_(None), ProspectContactPoint.expires_at > current_at),
            )
            .order_by(ProspectContactPoint.point_type, ProspectContactPoint.id)
        )
        return list(values.all())

    async def contact_by_email(self, organisation_id: UUID, email: str) -> Contact | None:
        return cast(
            Contact | None,
            await self.session.scalar(
                select(Contact)
                .where(
                    Contact.organisation_id == organisation_id,
                    func.lower(Contact.email) == email.casefold(),
                )
                .order_by(Contact.created_at, Contact.id)
                .limit(1)
            ),
        )

    async def contacts_by_name_and_company(
        self,
        organisation_id: UUID,
        company_id: UUID,
        first_name: str,
        last_name: str,
    ) -> list[Contact]:
        values = await self.session.scalars(
            select(Contact)
            .where(
                Contact.organisation_id == organisation_id,
                Contact.company_id == company_id,
                func.lower(Contact.first_name) == first_name.casefold(),
                func.lower(Contact.last_name) == last_name.casefold(),
            )
            .order_by(Contact.created_at, Contact.id)
        )
        return list(values.all())

    async def get_contact(self, organisation_id: UUID, contact_id: UUID) -> Contact | None:
        return cast(
            Contact | None,
            await self.session.scalar(
                select(Contact).where(Contact.organisation_id == organisation_id, Contact.id == contact_id)
            ),
        )

    async def person_for_contact(self, organisation_id: UUID, contact_id: UUID) -> ProspectPerson | None:
        return cast(
            ProspectPerson | None,
            await self.session.scalar(
                select(ProspectPerson).where(
                    ProspectPerson.organisation_id == organisation_id,
                    ProspectPerson.promoted_contact_id == contact_id,
                )
            ),
        )

    async def field_sources_for_contact(
        self,
        organisation_id: UUID,
        contact_id: UUID,
    ) -> list[ContactFieldSource]:
        values = await self.session.scalars(
            select(ContactFieldSource).where(
                ContactFieldSource.organisation_id == organisation_id,
                ContactFieldSource.contact_id == contact_id,
                ContactFieldSource.active.is_(True),
            )
        )
        return list(values.all())

    def add(self, entity: Base) -> None:
        self.session.add(entity)

    async def delete(self, entity: Base) -> None:
        await self.session.delete(entity)

    async def flush(self) -> None:
        await self.session.flush()

    async def refresh(self, entity: Base) -> None:
        await self.session.refresh(entity)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


class ProspectWorkerRepository:
    """Durable Prospect run queries with one trusted tenant transaction at a time."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def discover_eligible_organisations(self, *, eligible_at: datetime, limit: int) -> list[UUID]:
        if self.session.get_bind().dialect.name == "postgresql":
            result = await self.session.scalars(
                text(
                    """SELECT organisation_id
                    FROM public.revenueos_prospect_worker_eligible_organisations(
                        :eligible_at,
                        :result_limit
                    )"""
                ),
                {"eligible_at": eligible_at, "result_limit": limit},
            )
            return [UUID(str(value)) for value in result.all()]
        result = await self.session.scalars(
            select(Organisation.id)
            .where(
                Organisation.id.in_(
                    select(ProspectResearchRun.organisation_id).where(
                        or_(
                            (
                                (ProspectResearchRun.status == "pending")
                                & (ProspectResearchRun.attempt_count < ProspectResearchRun.max_attempts)
                                & (
                                    ProspectResearchRun.next_attempt_at.is_(None)
                                    | (ProspectResearchRun.next_attempt_at <= eligible_at)
                                )
                            ),
                            (
                                ProspectResearchRun.status.in_(("fetching", "synthesizing"))
                                & ProspectResearchRun.lease_expires_at.is_not(None)
                                & (ProspectResearchRun.lease_expires_at <= eligible_at)
                            ),
                        )
                    )
                )
            )
            .order_by(Organisation.id)
            .limit(limit)
        )
        return list(result.all())

    async def lock_stale(self, organisation_id: UUID, *, stale_at: datetime, limit: int) -> list[ProspectResearchRun]:
        values = await self.session.scalars(
            select(ProspectResearchRun)
            .where(
                ProspectResearchRun.organisation_id == organisation_id,
                ProspectResearchRun.status.in_(("fetching", "synthesizing")),
                ProspectResearchRun.lease_expires_at.is_not(None),
                ProspectResearchRun.lease_expires_at <= stale_at,
            )
            .order_by(ProspectResearchRun.lease_expires_at, ProspectResearchRun.created_at)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        return list(values.all())

    async def claim_next(self, organisation_id: UUID, *, eligible_at: datetime) -> ProspectResearchRun | None:
        return cast(
            ProspectResearchRun | None,
            await self.session.scalar(
                select(ProspectResearchRun)
                .where(
                    ProspectResearchRun.organisation_id == organisation_id,
                    ProspectResearchRun.status == "pending",
                    ProspectResearchRun.attempt_count < ProspectResearchRun.max_attempts,
                    or_(
                        ProspectResearchRun.next_attempt_at.is_(None),
                        ProspectResearchRun.next_attempt_at <= eligible_at,
                    ),
                )
                .order_by(
                    func.coalesce(ProspectResearchRun.next_attempt_at, ProspectResearchRun.created_at),
                    ProspectResearchRun.created_at,
                )
                .with_for_update(skip_locked=True)
                .limit(1)
            ),
        )

    async def lock_owned(
        self,
        organisation_id: UUID,
        run_id: UUID,
        worker_id: str,
        *,
        owned_at: datetime,
    ) -> ProspectResearchRun | None:
        return cast(
            ProspectResearchRun | None,
            await self.session.scalar(
                select(ProspectResearchRun)
                .where(
                    ProspectResearchRun.organisation_id == organisation_id,
                    ProspectResearchRun.id == run_id,
                    ProspectResearchRun.status.in_(("fetching", "synthesizing")),
                    ProspectResearchRun.worker_id == worker_id,
                    ProspectResearchRun.lease_expires_at.is_not(None),
                    ProspectResearchRun.lease_expires_at > owned_at,
                )
                .with_for_update()
            ),
        )

    async def target(self, organisation_id: UUID, target_id: UUID) -> ProspectResearchTarget | None:
        return cast(
            ProspectResearchTarget | None,
            await self.session.scalar(
                select(ProspectResearchTarget).where(
                    ProspectResearchTarget.organisation_id == organisation_id,
                    ProspectResearchTarget.id == target_id,
                )
            ),
        )

    async def person(self, organisation_id: UUID, person_id: UUID) -> ProspectPerson | None:
        return cast(
            ProspectPerson | None,
            await self.session.scalar(
                select(ProspectPerson).where(
                    ProspectPerson.organisation_id == organisation_id,
                    ProspectPerson.id == person_id,
                )
            ),
        )

    async def requester_is_active(self, organisation_id: UUID, user_id: UUID) -> bool:
        value = await self.session.scalar(
            select(OrganisationMembership.user_id).where(
                OrganisationMembership.organisation_id == organisation_id,
                OrganisationMembership.user_id == user_id,
                OrganisationMembership.status == "active",
            )
        )
        return value is not None

    async def prospect_is_entitled(self, organisation_id: UUID) -> bool:
        value = await self.session.scalar(
            select(OrganisationModuleEntitlement.enabled).where(
                OrganisationModuleEntitlement.organisation_id == organisation_id,
                OrganisationModuleEntitlement.module_key == "prospect",
            )
        )
        return value is True
