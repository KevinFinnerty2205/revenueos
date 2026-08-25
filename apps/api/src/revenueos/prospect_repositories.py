from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    Base,
    Company,
    Organisation,
    OrganisationMembership,
    OrganisationModuleEntitlement,
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
