from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    Company,
    Opportunity,
    ProspectCandidateReason,
    ProspectDiscoveryCandidate,
    ProspectDiscoveryRun,
    ProspectResearchRun,
    ProspectResearchTarget,
    ProspectTargetFeedback,
    ProspectTargetMarket,
    ProspectTargetMarketVersion,
)

ACTIVE_DISCOVERY_STATUSES = ("pending", "running")
USABLE_DISCOVERY_STATUSES = ("completed", "partial")
USABLE_RESEARCH_STATUSES = ("completed", "partial")


class ProspectTargetMarketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def markets(self, organisation_id: UUID) -> list[ProspectTargetMarket]:
        values = await self.session.scalars(
            select(ProspectTargetMarket)
            .where(ProspectTargetMarket.organisation_id == organisation_id)
            .order_by(ProspectTargetMarket.status, ProspectTargetMarket.name, ProspectTargetMarket.id)
        )
        return list(values.all())

    async def market(
        self,
        organisation_id: UUID,
        target_market_id: UUID,
        *,
        for_update: bool = False,
    ) -> ProspectTargetMarket | None:
        statement = select(ProspectTargetMarket).where(
            ProspectTargetMarket.organisation_id == organisation_id,
            ProspectTargetMarket.id == target_market_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(ProspectTargetMarket | None, await self.session.scalar(statement))

    async def market_by_name(self, organisation_id: UUID, name: str) -> ProspectTargetMarket | None:
        return cast(
            ProspectTargetMarket | None,
            await self.session.scalar(
                select(ProspectTargetMarket).where(
                    ProspectTargetMarket.organisation_id == organisation_id,
                    func.lower(ProspectTargetMarket.name) == name.casefold(),
                )
            ),
        )

    async def active_market_count(self, organisation_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(ProspectTargetMarket)
                .where(
                    ProspectTargetMarket.organisation_id == organisation_id,
                    ProspectTargetMarket.status == "active",
                )
            )
            or 0
        )

    async def version(
        self,
        organisation_id: UUID,
        target_market_id: UUID,
        version: int,
    ) -> ProspectTargetMarketVersion | None:
        return cast(
            ProspectTargetMarketVersion | None,
            await self.session.scalar(
                select(ProspectTargetMarketVersion).where(
                    ProspectTargetMarketVersion.organisation_id == organisation_id,
                    ProspectTargetMarketVersion.target_market_id == target_market_id,
                    ProspectTargetMarketVersion.version == version,
                )
            ),
        )

    async def versions(
        self,
        organisation_id: UUID,
        target_market_id: UUID,
    ) -> list[ProspectTargetMarketVersion]:
        values = await self.session.scalars(
            select(ProspectTargetMarketVersion)
            .where(
                ProspectTargetMarketVersion.organisation_id == organisation_id,
                ProspectTargetMarketVersion.target_market_id == target_market_id,
            )
            .order_by(ProspectTargetMarketVersion.version.desc())
        )
        return list(values.all())

    async def version_by_id(
        self,
        organisation_id: UUID,
        version_id: UUID,
    ) -> ProspectTargetMarketVersion | None:
        return cast(
            ProspectTargetMarketVersion | None,
            await self.session.scalar(
                select(ProspectTargetMarketVersion).where(
                    ProspectTargetMarketVersion.organisation_id == organisation_id,
                    ProspectTargetMarketVersion.id == version_id,
                )
            ),
        )

    async def latest_run(
        self,
        organisation_id: UUID,
        target_market_id: UUID,
    ) -> ProspectDiscoveryRun | None:
        return cast(
            ProspectDiscoveryRun | None,
            await self.session.scalar(
                select(ProspectDiscoveryRun)
                .where(
                    ProspectDiscoveryRun.organisation_id == organisation_id,
                    ProspectDiscoveryRun.target_market_id == target_market_id,
                )
                .order_by(ProspectDiscoveryRun.requested_at.desc(), ProspectDiscoveryRun.id.desc())
                .limit(1)
            ),
        )

    async def runs(
        self,
        organisation_id: UUID,
        target_market_id: UUID,
        *,
        limit: int = 20,
    ) -> list[ProspectDiscoveryRun]:
        values = await self.session.scalars(
            select(ProspectDiscoveryRun)
            .where(
                ProspectDiscoveryRun.organisation_id == organisation_id,
                ProspectDiscoveryRun.target_market_id == target_market_id,
            )
            .order_by(ProspectDiscoveryRun.requested_at.desc(), ProspectDiscoveryRun.id.desc())
            .limit(limit)
        )
        return list(values.all())

    async def active_run(
        self,
        organisation_id: UUID,
        target_market_id: UUID,
        target_market_version_id: UUID,
    ) -> ProspectDiscoveryRun | None:
        return cast(
            ProspectDiscoveryRun | None,
            await self.session.scalar(
                select(ProspectDiscoveryRun)
                .where(
                    ProspectDiscoveryRun.organisation_id == organisation_id,
                    ProspectDiscoveryRun.target_market_id == target_market_id,
                    ProspectDiscoveryRun.target_market_version_id == target_market_version_id,
                    ProspectDiscoveryRun.status.in_(ACTIVE_DISCOVERY_STATUSES),
                )
                .order_by(ProspectDiscoveryRun.requested_at.desc(), ProspectDiscoveryRun.id.desc())
                .limit(1)
            ),
        )

    async def fresh_run(
        self,
        organisation_id: UUID,
        target_market_id: UUID,
        target_market_version_id: UUID,
        *,
        fresh_after: datetime,
    ) -> ProspectDiscoveryRun | None:
        return cast(
            ProspectDiscoveryRun | None,
            await self.session.scalar(
                select(ProspectDiscoveryRun)
                .where(
                    ProspectDiscoveryRun.organisation_id == organisation_id,
                    ProspectDiscoveryRun.target_market_id == target_market_id,
                    ProspectDiscoveryRun.target_market_version_id == target_market_version_id,
                    ProspectDiscoveryRun.status.in_(USABLE_DISCOVERY_STATUSES),
                    ProspectDiscoveryRun.completed_at >= fresh_after,
                )
                .order_by(ProspectDiscoveryRun.completed_at.desc())
                .limit(1)
            ),
        )

    async def run(self, organisation_id: UUID, run_id: UUID) -> ProspectDiscoveryRun | None:
        return cast(
            ProspectDiscoveryRun | None,
            await self.session.scalar(
                select(ProspectDiscoveryRun).where(
                    ProspectDiscoveryRun.organisation_id == organisation_id,
                    ProspectDiscoveryRun.id == run_id,
                )
            ),
        )

    async def run_by_idempotency_key(
        self,
        organisation_id: UUID,
        target_market_id: UUID,
        idempotency_key: str,
    ) -> ProspectDiscoveryRun | None:
        return cast(
            ProspectDiscoveryRun | None,
            await self.session.scalar(
                select(ProspectDiscoveryRun).where(
                    ProspectDiscoveryRun.organisation_id == organisation_id,
                    ProspectDiscoveryRun.target_market_id == target_market_id,
                    ProspectDiscoveryRun.idempotency_key == idempotency_key,
                )
            ),
        )

    async def candidates(
        self,
        organisation_id: UUID,
        run_id: UUID,
    ) -> list[ProspectDiscoveryCandidate]:
        values = await self.session.scalars(
            select(ProspectDiscoveryCandidate)
            .where(
                ProspectDiscoveryCandidate.organisation_id == organisation_id,
                ProspectDiscoveryCandidate.run_id == run_id,
            )
            .order_by(
                ProspectDiscoveryCandidate.priority,
                ProspectDiscoveryCandidate.created_at,
                ProspectDiscoveryCandidate.id,
            )
        )
        return list(values.all())

    async def candidate(
        self,
        organisation_id: UUID,
        candidate_id: UUID,
    ) -> ProspectDiscoveryCandidate | None:
        return cast(
            ProspectDiscoveryCandidate | None,
            await self.session.scalar(
                select(ProspectDiscoveryCandidate).where(
                    ProspectDiscoveryCandidate.organisation_id == organisation_id,
                    ProspectDiscoveryCandidate.id == candidate_id,
                )
            ),
        )

    async def reasons(
        self,
        organisation_id: UUID,
        run_id: UUID,
    ) -> list[ProspectCandidateReason]:
        values = await self.session.scalars(
            select(ProspectCandidateReason)
            .where(
                ProspectCandidateReason.organisation_id == organisation_id,
                ProspectCandidateReason.run_id == run_id,
            )
            .order_by(ProspectCandidateReason.display_order, ProspectCandidateReason.id)
        )
        return list(values.all())

    async def targets_by_ids(
        self,
        organisation_id: UUID,
        target_ids: set[UUID],
    ) -> dict[UUID, ProspectResearchTarget]:
        if not target_ids:
            return {}
        values = await self.session.scalars(
            select(ProspectResearchTarget).where(
                ProspectResearchTarget.organisation_id == organisation_id,
                ProspectResearchTarget.id.in_(target_ids),
            )
        )
        return {value.id: value for value in values.all()}

    async def targets_by_domains(
        self,
        organisation_id: UUID,
        domains: set[str],
    ) -> dict[str, ProspectResearchTarget]:
        if not domains:
            return {}
        values = await self.session.scalars(
            select(ProspectResearchTarget).where(
                ProspectResearchTarget.organisation_id == organisation_id,
                ProspectResearchTarget.normalized_domain.in_(domains),
            )
        )
        return {value.normalized_domain: value for value in values.all()}

    async def companies_by_domains(
        self,
        organisation_id: UUID,
        domains: set[str],
    ) -> dict[str, Company]:
        if not domains:
            return {}
        values = await self.session.scalars(
            select(Company)
            .where(
                Company.organisation_id == organisation_id,
                Company.normalized_domain.in_(domains),
            )
            .order_by(Company.created_at, Company.id)
        )
        result: dict[str, Company] = {}
        for company in values.all():
            if company.normalized_domain is not None:
                result.setdefault(company.normalized_domain, company)
        return result

    async def active_opportunities(
        self,
        organisation_id: UUID,
        company_ids: set[UUID],
    ) -> dict[UUID, Opportunity]:
        if not company_ids:
            return {}
        values = await self.session.scalars(
            select(Opportunity)
            .where(
                Opportunity.organisation_id == organisation_id,
                Opportunity.company_id.in_(company_ids),
                Opportunity.status == "open",
            )
            .order_by(Opportunity.created_at, Opportunity.id)
        )
        result: dict[UUID, Opportunity] = {}
        for opportunity in values.all():
            if opportunity.company_id is not None:
                result.setdefault(opportunity.company_id, opportunity)
        return result

    async def feedback_for_targets(
        self,
        organisation_id: UUID,
        user_id: UUID,
        target_ids: set[UUID],
    ) -> dict[UUID, ProspectTargetFeedback]:
        if not target_ids:
            return {}
        values = await self.session.scalars(
            select(ProspectTargetFeedback).where(
                ProspectTargetFeedback.organisation_id == organisation_id,
                ProspectTargetFeedback.user_id == user_id,
                ProspectTargetFeedback.target_id.in_(target_ids),
            )
        )
        return {value.target_id: value for value in values.all()}

    async def feedback(
        self,
        organisation_id: UUID,
        user_id: UUID,
        target_id: UUID,
    ) -> ProspectTargetFeedback | None:
        return cast(
            ProspectTargetFeedback | None,
            await self.session.scalar(
                select(ProspectTargetFeedback).where(
                    ProspectTargetFeedback.organisation_id == organisation_id,
                    ProspectTargetFeedback.user_id == user_id,
                    ProspectTargetFeedback.target_id == target_id,
                )
            ),
        )

    async def research_statuses(
        self,
        organisation_id: UUID,
        target_ids: set[UUID],
    ) -> dict[UUID, str]:
        if not target_ids:
            return {}
        values = await self.session.scalars(
            select(ProspectResearchRun)
            .where(
                ProspectResearchRun.organisation_id == organisation_id,
                ProspectResearchRun.target_id.in_(target_ids),
                ProspectResearchRun.person_id.is_(None),
            )
            .order_by(ProspectResearchRun.created_at.desc(), ProspectResearchRun.id.desc())
        )
        result: dict[UUID, str] = {}
        for run in values.all():
            result.setdefault(run.target_id, run.status)
        return result

    def add(self, entity: object) -> None:
        self.session.add(entity)

    async def delete(self, entity: object) -> None:
        await self.session.delete(entity)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
