from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    Company,
    CreateBusinessCase,
    CreateBusinessCaseVersion,
    CreateValueModel,
    CreateValueModelVersion,
    Evidence,
    Opportunity,
    OrganisationModuleEntitlement,
    ProspectResearchObservation,
)


class BusinessCaseRepository:
    """ROI persistence with an explicit organisation predicate on every read."""

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

    async def company(self, organisation_id: UUID, company_id: UUID) -> Company | None:
        return cast(
            Company | None,
            await self.session.scalar(
                select(Company).where(Company.organisation_id == organisation_id, Company.id == company_id)
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

    async def value_model(self, organisation_id: UUID, model_id: UUID) -> CreateValueModel | None:
        return cast(
            CreateValueModel | None,
            await self.session.scalar(
                select(CreateValueModel).where(
                    CreateValueModel.organisation_id == organisation_id,
                    CreateValueModel.id == model_id,
                )
            ),
        )

    async def value_model_by_name(self, organisation_id: UUID, name: str) -> CreateValueModel | None:
        return cast(
            CreateValueModel | None,
            await self.session.scalar(
                select(CreateValueModel).where(
                    CreateValueModel.organisation_id == organisation_id,
                    func.lower(CreateValueModel.name) == name.casefold(),
                )
            ),
        )

    async def value_model_by_key(
        self,
        organisation_id: UUID,
        user_id: UUID,
        idempotency_key: str,
    ) -> CreateValueModel | None:
        return cast(
            CreateValueModel | None,
            await self.session.scalar(
                select(CreateValueModel).where(
                    CreateValueModel.organisation_id == organisation_id,
                    CreateValueModel.created_by_user_id == user_id,
                    CreateValueModel.idempotency_key == idempotency_key,
                )
            ),
        )

    async def active_value_model_count(self, organisation_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(CreateValueModel)
                .where(CreateValueModel.organisation_id == organisation_id, CreateValueModel.state == "active")
            )
            or 0
        )

    async def value_models(self, organisation_id: UUID, include_drafts: bool) -> list[CreateValueModel]:
        statement = select(CreateValueModel).where(
            CreateValueModel.organisation_id == organisation_id,
            CreateValueModel.state == "active",
        )
        if not include_drafts:
            statement = statement.where(
                CreateValueModel.id.in_(
                    select(CreateValueModelVersion.model_id).where(
                        CreateValueModelVersion.organisation_id == organisation_id,
                        CreateValueModelVersion.state == "approved",
                    )
                )
            )
        values = await self.session.scalars(statement.order_by(CreateValueModel.updated_at.desc(), CreateValueModel.id))
        return list(values.all())

    async def value_model_version(
        self,
        organisation_id: UUID,
        version_id: UUID,
    ) -> CreateValueModelVersion | None:
        return cast(
            CreateValueModelVersion | None,
            await self.session.scalar(
                select(CreateValueModelVersion).where(
                    CreateValueModelVersion.organisation_id == organisation_id,
                    CreateValueModelVersion.id == version_id,
                )
            ),
        )

    async def value_model_version_by_key(
        self,
        organisation_id: UUID,
        model_id: UUID,
        idempotency_key: str,
    ) -> CreateValueModelVersion | None:
        return cast(
            CreateValueModelVersion | None,
            await self.session.scalar(
                select(CreateValueModelVersion).where(
                    CreateValueModelVersion.organisation_id == organisation_id,
                    CreateValueModelVersion.model_id == model_id,
                    CreateValueModelVersion.idempotency_key == idempotency_key,
                )
            ),
        )

    async def latest_value_model_version(
        self,
        organisation_id: UUID,
        model_id: UUID,
        approved_only: bool = False,
    ) -> CreateValueModelVersion | None:
        statement = select(CreateValueModelVersion).where(
            CreateValueModelVersion.organisation_id == organisation_id,
            CreateValueModelVersion.model_id == model_id,
        )
        if approved_only:
            statement = statement.where(CreateValueModelVersion.state == "approved")
        return cast(
            CreateValueModelVersion | None,
            await self.session.scalar(statement.order_by(CreateValueModelVersion.version.desc()).limit(1)),
        )

    async def value_model_version_count(self, organisation_id: UUID, model_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(CreateValueModelVersion)
                .where(
                    CreateValueModelVersion.organisation_id == organisation_id,
                    CreateValueModelVersion.model_id == model_id,
                )
            )
            or 0
        )

    async def business_case_by_key(
        self,
        organisation_id: UUID,
        user_id: UUID,
        idempotency_key: str,
    ) -> CreateBusinessCase | None:
        return cast(
            CreateBusinessCase | None,
            await self.session.scalar(
                select(CreateBusinessCase).where(
                    CreateBusinessCase.organisation_id == organisation_id,
                    CreateBusinessCase.created_by_user_id == user_id,
                    CreateBusinessCase.idempotency_key == idempotency_key,
                )
            ),
        )

    async def business_case(self, organisation_id: UUID, case_id: UUID) -> CreateBusinessCase | None:
        return cast(
            CreateBusinessCase | None,
            await self.session.scalar(
                select(CreateBusinessCase).where(
                    CreateBusinessCase.organisation_id == organisation_id,
                    CreateBusinessCase.id == case_id,
                )
            ),
        )

    async def business_cases(
        self,
        organisation_id: UUID,
        account_id: UUID | None = None,
        opportunity_id: UUID | None = None,
        approved_only: bool = False,
    ) -> list[CreateBusinessCase]:
        statement = select(CreateBusinessCase).where(
            CreateBusinessCase.organisation_id == organisation_id,
            CreateBusinessCase.state != "archived",
        )
        if account_id is not None:
            statement = statement.where(CreateBusinessCase.account_id == account_id)
        if opportunity_id is not None:
            statement = statement.where(CreateBusinessCase.opportunity_id == opportunity_id)
        if approved_only:
            statement = statement.where(CreateBusinessCase.state == "approved")
        values = await self.session.scalars(
            statement.order_by(CreateBusinessCase.updated_at.desc(), CreateBusinessCase.id).limit(100)
        )
        return list(values.all())

    async def active_case_count_for_account(self, organisation_id: UUID, account_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(CreateBusinessCase)
                .where(
                    CreateBusinessCase.organisation_id == organisation_id,
                    CreateBusinessCase.account_id == account_id,
                    CreateBusinessCase.state != "archived",
                )
            )
            or 0
        )

    async def business_case_version_by_key(
        self,
        organisation_id: UUID,
        case_id: UUID,
        idempotency_key: str,
    ) -> CreateBusinessCaseVersion | None:
        return cast(
            CreateBusinessCaseVersion | None,
            await self.session.scalar(
                select(CreateBusinessCaseVersion).where(
                    CreateBusinessCaseVersion.organisation_id == organisation_id,
                    CreateBusinessCaseVersion.case_id == case_id,
                    CreateBusinessCaseVersion.idempotency_key == idempotency_key,
                )
            ),
        )

    async def latest_business_case_version(
        self,
        organisation_id: UUID,
        case_id: UUID,
    ) -> CreateBusinessCaseVersion | None:
        return cast(
            CreateBusinessCaseVersion | None,
            await self.session.scalar(
                select(CreateBusinessCaseVersion)
                .where(
                    CreateBusinessCaseVersion.organisation_id == organisation_id,
                    CreateBusinessCaseVersion.case_id == case_id,
                )
                .order_by(CreateBusinessCaseVersion.version.desc())
                .limit(1)
            ),
        )

    async def evidence(self, organisation_id: UUID, evidence_id: UUID) -> Evidence | None:
        return cast(
            Evidence | None,
            await self.session.scalar(
                select(Evidence).where(Evidence.organisation_id == organisation_id, Evidence.id == evidence_id)
            ),
        )

    async def public_observation(
        self,
        organisation_id: UUID,
        observation_id: UUID,
    ) -> ProspectResearchObservation | None:
        return cast(
            ProspectResearchObservation | None,
            await self.session.scalar(
                select(ProspectResearchObservation).where(
                    ProspectResearchObservation.organisation_id == organisation_id,
                    ProspectResearchObservation.id == observation_id,
                )
            ),
        )
