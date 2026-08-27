from __future__ import annotations

from datetime import date
from typing import cast
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    Company,
    Contact,
    CreateApprovedContentItem,
    CreatePresentation,
    CreatePresentationVersion,
    CreateTemplate,
    CreateTemplateSlide,
    CreateTemplateVersion,
    CreateUsageCounter,
    Evidence,
    Opportunity,
    Organisation,
    OrganisationModuleEntitlement,
    ProspectResearchObservation,
    ProspectResearchObservationSource,
    ProspectResearchRun,
    ProspectResearchSource,
    ProspectResearchTarget,
    RevenueBrainSourceSnapshot,
)


class CreateRepository:
    """Create persistence with explicit organisation predicates on every query."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, value: object) -> None:
        self.session.add(value)

    async def entitlement(self, organisation_id: UUID) -> OrganisationModuleEntitlement | None:
        return cast(
            OrganisationModuleEntitlement | None,
            await self.session.scalar(
                select(OrganisationModuleEntitlement).where(
                    OrganisationModuleEntitlement.organisation_id == organisation_id,
                    OrganisationModuleEntitlement.module_key == "create",
                )
            ),
        )

    async def organisation(self, organisation_id: UUID) -> Organisation | None:
        return cast(
            Organisation | None,
            await self.session.scalar(select(Organisation).where(Organisation.id == organisation_id)),
        )

    async def template(self, organisation_id: UUID, template_id: UUID) -> CreateTemplate | None:
        return cast(
            CreateTemplate | None,
            await self.session.scalar(
                select(CreateTemplate).where(
                    CreateTemplate.organisation_id == organisation_id,
                    CreateTemplate.id == template_id,
                )
            ),
        )

    async def template_by_name(self, organisation_id: UUID, name: str) -> CreateTemplate | None:
        return cast(
            CreateTemplate | None,
            await self.session.scalar(
                select(CreateTemplate).where(
                    CreateTemplate.organisation_id == organisation_id,
                    func.lower(CreateTemplate.name) == name.casefold(),
                )
            ),
        )

    async def active_template_count(self, organisation_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(CreateTemplate)
                .where(
                    CreateTemplate.organisation_id == organisation_id,
                    CreateTemplate.state == "active",
                )
            )
            or 0
        )

    async def template_version_count(self, organisation_id: UUID, template_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(CreateTemplateVersion)
                .where(
                    CreateTemplateVersion.organisation_id == organisation_id,
                    CreateTemplateVersion.template_id == template_id,
                )
            )
            or 0
        )

    async def template_version(
        self,
        organisation_id: UUID,
        version_id: UUID,
    ) -> CreateTemplateVersion | None:
        return cast(
            CreateTemplateVersion | None,
            await self.session.scalar(
                select(CreateTemplateVersion).where(
                    CreateTemplateVersion.organisation_id == organisation_id,
                    CreateTemplateVersion.id == version_id,
                )
            ),
        )

    async def template_version_by_checksum(
        self,
        organisation_id: UUID,
        checksum: str,
    ) -> CreateTemplateVersion | None:
        return cast(
            CreateTemplateVersion | None,
            await self.session.scalar(
                select(CreateTemplateVersion).where(
                    CreateTemplateVersion.organisation_id == organisation_id,
                    CreateTemplateVersion.checksum_sha256 == checksum,
                )
            ),
        )

    async def templates(self, organisation_id: UUID) -> list[CreateTemplate]:
        values = await self.session.scalars(
            select(CreateTemplate)
            .where(CreateTemplate.organisation_id == organisation_id, CreateTemplate.state == "active")
            .order_by(CreateTemplate.updated_at.desc(), CreateTemplate.id)
        )
        return list(values.all())

    async def latest_template_version(
        self,
        organisation_id: UUID,
        template_id: UUID,
    ) -> CreateTemplateVersion | None:
        return cast(
            CreateTemplateVersion | None,
            await self.session.scalar(
                select(CreateTemplateVersion)
                .where(
                    CreateTemplateVersion.organisation_id == organisation_id,
                    CreateTemplateVersion.template_id == template_id,
                )
                .order_by(CreateTemplateVersion.version.desc())
                .limit(1)
            ),
        )

    async def slides(self, organisation_id: UUID, version_id: UUID) -> list[CreateTemplateSlide]:
        values = await self.session.scalars(
            select(CreateTemplateSlide)
            .where(
                CreateTemplateSlide.organisation_id == organisation_id,
                CreateTemplateSlide.template_version_id == version_id,
            )
            .order_by(CreateTemplateSlide.slide_number)
        )
        return list(values.all())

    async def slide(self, organisation_id: UUID, slide_id: UUID) -> CreateTemplateSlide | None:
        return cast(
            CreateTemplateSlide | None,
            await self.session.scalar(
                select(CreateTemplateSlide).where(
                    CreateTemplateSlide.organisation_id == organisation_id,
                    CreateTemplateSlide.id == slide_id,
                )
            ),
        )

    async def content_items(
        self,
        organisation_id: UUID,
        version_id: UUID,
    ) -> list[CreateApprovedContentItem]:
        values = await self.session.scalars(
            select(CreateApprovedContentItem)
            .where(
                CreateApprovedContentItem.organisation_id == organisation_id,
                CreateApprovedContentItem.template_version_id == version_id,
                CreateApprovedContentItem.status == "approved",
            )
            .order_by(CreateApprovedContentItem.created_at, CreateApprovedContentItem.id)
        )
        return list(values.all())

    async def content_item_for_slide(
        self,
        organisation_id: UUID,
        slide_id: UUID,
    ) -> CreateApprovedContentItem | None:
        return cast(
            CreateApprovedContentItem | None,
            await self.session.scalar(
                select(CreateApprovedContentItem).where(
                    CreateApprovedContentItem.organisation_id == organisation_id,
                    CreateApprovedContentItem.slide_id == slide_id,
                )
            ),
        )

    async def company(self, organisation_id: UUID, company_id: UUID) -> Company | None:
        return cast(
            Company | None,
            await self.session.scalar(
                select(Company).where(
                    Company.organisation_id == organisation_id,
                    Company.id == company_id,
                )
            ),
        )

    async def opportunity(self, organisation_id: UUID, opportunity_id: UUID) -> Opportunity | None:
        return cast(
            Opportunity | None,
            await self.session.scalar(
                select(Opportunity).where(
                    Opportunity.organisation_id == organisation_id,
                    Opportunity.id == opportunity_id,
                )
            ),
        )

    async def contacts(self, organisation_id: UUID, contact_ids: list[UUID]) -> list[Contact]:
        if not contact_ids:
            return []
        values = await self.session.scalars(
            select(Contact).where(
                Contact.organisation_id == organisation_id,
                Contact.id.in_(contact_ids),
            )
        )
        return list(values.all())

    async def reserve_generation_counter(
        self,
        organisation_id: UUID,
        usage_date: date,
        scope_key: str,
        limit: int,
    ) -> bool:
        insert = postgresql_insert if self.session.get_bind().dialect.name == "postgresql" else sqlite_insert
        base = insert(CreateUsageCounter).values(
            organisation_id=organisation_id,
            usage_date=usage_date,
            scope_key=scope_key,
            generation_count=1,
        )
        statement = base.on_conflict_do_update(
            index_elements=[
                CreateUsageCounter.organisation_id,
                CreateUsageCounter.usage_date,
                CreateUsageCounter.scope_key,
            ],
            set_={
                "generation_count": CreateUsageCounter.generation_count + 1,
                "updated_at": func.now(),
            },
            where=CreateUsageCounter.generation_count < limit,
        ).returning(CreateUsageCounter.generation_count)
        return (await self.session.execute(statement)).scalar_one_or_none() is not None

    async def presentation_by_key(
        self,
        organisation_id: UUID,
        user_id: UUID,
        key: str,
    ) -> CreatePresentation | None:
        return cast(
            CreatePresentation | None,
            await self.session.scalar(
                select(CreatePresentation).where(
                    CreatePresentation.organisation_id == organisation_id,
                    CreatePresentation.created_by_user_id == user_id,
                    CreatePresentation.idempotency_key == key,
                )
            ),
        )

    async def presentation(self, organisation_id: UUID, presentation_id: UUID) -> CreatePresentation | None:
        return cast(
            CreatePresentation | None,
            await self.session.scalar(
                select(CreatePresentation).where(
                    CreatePresentation.organisation_id == organisation_id,
                    CreatePresentation.id == presentation_id,
                )
            ),
        )

    async def presentations(self, organisation_id: UUID) -> list[CreatePresentation]:
        values = await self.session.scalars(
            select(CreatePresentation)
            .where(
                CreatePresentation.organisation_id == organisation_id,
                CreatePresentation.state != "archived",
            )
            .order_by(CreatePresentation.updated_at.desc(), CreatePresentation.id)
            .limit(100)
        )
        return list(values.all())

    async def latest_presentation_version(
        self,
        organisation_id: UUID,
        presentation_id: UUID,
    ) -> CreatePresentationVersion | None:
        return cast(
            CreatePresentationVersion | None,
            await self.session.scalar(
                select(CreatePresentationVersion)
                .where(
                    CreatePresentationVersion.organisation_id == organisation_id,
                    CreatePresentationVersion.presentation_id == presentation_id,
                )
                .order_by(CreatePresentationVersion.version.desc())
                .limit(1)
            ),
        )

    async def presentation_version(
        self,
        organisation_id: UUID,
        presentation_id: UUID,
        version_id: UUID,
    ) -> CreatePresentationVersion | None:
        return cast(
            CreatePresentationVersion | None,
            await self.session.scalar(
                select(CreatePresentationVersion).where(
                    CreatePresentationVersion.organisation_id == organisation_id,
                    CreatePresentationVersion.presentation_id == presentation_id,
                    CreatePresentationVersion.id == version_id,
                )
            ),
        )

    async def revenue_brain_snapshots(
        self,
        organisation_id: UUID,
        company_id: UUID,
        opportunity_id: UUID | None,
    ) -> list[RevenueBrainSourceSnapshot]:
        opportunity_scope = (
            RevenueBrainSourceSnapshot.opportunity_id.is_(None)
            if opportunity_id is None
            else or_(
                RevenueBrainSourceSnapshot.opportunity_id.is_(None),
                RevenueBrainSourceSnapshot.opportunity_id == opportunity_id,
            )
        )
        values = await self.session.scalars(
            select(RevenueBrainSourceSnapshot)
            .where(
                RevenueBrainSourceSnapshot.organisation_id == organisation_id,
                RevenueBrainSourceSnapshot.company_id == company_id,
                opportunity_scope,
            )
            .order_by(RevenueBrainSourceSnapshot.created_at.desc())
            .limit(20)
        )
        return list(values.all())

    async def public_observations(
        self,
        organisation_id: UUID,
        company_id: UUID,
    ) -> list[tuple[ProspectResearchObservation, ProspectResearchSource | None]]:
        latest_run = (
            select(ProspectResearchRun.id)
            .join(
                ProspectResearchTarget,
                ProspectResearchTarget.id == ProspectResearchRun.target_id,
            )
            .where(
                ProspectResearchRun.organisation_id == organisation_id,
                ProspectResearchTarget.organisation_id == organisation_id,
                ProspectResearchTarget.promoted_company_id == company_id,
                ProspectResearchRun.status.in_(("completed", "partial")),
                ProspectResearchRun.person_id.is_(None),
            )
            .order_by(ProspectResearchRun.created_at.desc())
            .limit(1)
            .scalar_subquery()
        )
        values = await self.session.execute(
            select(ProspectResearchObservation, ProspectResearchSource)
            .outerjoin(
                ProspectResearchObservationSource,
                (ProspectResearchObservationSource.organisation_id == organisation_id)
                & (ProspectResearchObservationSource.observation_id == ProspectResearchObservation.id)
                & (ProspectResearchObservationSource.run_id == ProspectResearchObservation.run_id),
            )
            .outerjoin(
                ProspectResearchSource,
                (ProspectResearchSource.organisation_id == organisation_id)
                & (ProspectResearchSource.id == ProspectResearchObservationSource.source_id)
                & (ProspectResearchSource.run_id == ProspectResearchObservationSource.run_id),
            )
            .where(
                ProspectResearchObservation.organisation_id == organisation_id,
                ProspectResearchObservation.run_id == latest_run,
                ProspectResearchObservation.status == "current",
            )
            .order_by(
                ProspectResearchObservation.relevance.desc(),
                ProspectResearchObservation.generated_at.desc(),
            )
            .limit(12)
        )
        # A source is used for a user-facing label only. Observation-to-source
        # cardinality is intentionally collapsed here and never changes support.
        deduplicated: dict[UUID, tuple[ProspectResearchObservation, ProspectResearchSource | None]] = {}
        for observation, source in values.all():
            deduplicated.setdefault(observation.id, (observation, source))
        return list(deduplicated.values())

    async def existing_source_ids(
        self,
        organisation_id: UUID,
        source_type: str,
        source_ids: set[UUID],
    ) -> set[UUID]:
        if not source_ids:
            return set()
        if source_type == "approved_company_content":
            statement = select(CreateApprovedContentItem.id).where(
                CreateApprovedContentItem.organisation_id == organisation_id,
                CreateApprovedContentItem.id.in_(source_ids),
                CreateApprovedContentItem.status == "approved",
            )
        elif source_type == "customer_evidence":
            statement = select(Evidence.id).where(
                Evidence.organisation_id == organisation_id,
                Evidence.id.in_(source_ids),
                Evidence.lifecycle_status == "available",
            )
        elif source_type == "prospect_public":
            statement = select(ProspectResearchObservation.id).where(
                ProspectResearchObservation.organisation_id == organisation_id,
                ProspectResearchObservation.id.in_(source_ids),
                ProspectResearchObservation.status == "current",
            )
        else:
            return set()
        values = await self.session.scalars(statement)
        return set(values.all())
