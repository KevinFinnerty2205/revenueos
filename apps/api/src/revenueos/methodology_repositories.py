from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    Base,
    Evidence,
    Interaction,
    InteractionIntelligenceSnapshot,
    MethodologyDefinition,
    MethodologyDefinitionVersion,
    MethodologyProjection,
    MethodologyReview,
    Opportunity,
    OrganisationMethodologySetting,
)


@dataclass(frozen=True)
class CustomDefinitionRecord:
    definition: MethodologyDefinition
    version: MethodologyDefinitionVersion


class MethodologyRepository:
    """Explicitly tenant-scoped persistence for methodology configuration and history."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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

    async def setting(
        self,
        organisation_id: UUID,
        *,
        for_update: bool = False,
    ) -> OrganisationMethodologySetting | None:
        statement = select(OrganisationMethodologySetting).where(
            OrganisationMethodologySetting.organisation_id == organisation_id
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(OrganisationMethodologySetting | None, await self.session.scalar(statement))

    async def custom_definition(
        self,
        organisation_id: UUID,
        definition_id: UUID,
        *,
        version: int | None = None,
        for_update: bool = False,
    ) -> CustomDefinitionRecord | None:
        definition_statement = select(MethodologyDefinition).where(
            MethodologyDefinition.organisation_id == organisation_id,
            MethodologyDefinition.id == definition_id,
        )
        if for_update:
            definition_statement = definition_statement.with_for_update()
        definition = await self.session.scalar(definition_statement)
        if definition is None:
            return None
        selected_version = version or definition.current_version
        version_row = await self.session.scalar(
            select(MethodologyDefinitionVersion).where(
                MethodologyDefinitionVersion.organisation_id == organisation_id,
                MethodologyDefinitionVersion.definition_id == definition_id,
                MethodologyDefinitionVersion.version == selected_version,
            )
        )
        if version_row is None:
            return None
        return CustomDefinitionRecord(definition=definition, version=version_row)

    async def custom_definitions(self, organisation_id: UUID) -> list[CustomDefinitionRecord]:
        rows = (
            await self.session.execute(
                select(MethodologyDefinition, MethodologyDefinitionVersion)
                .join(
                    MethodologyDefinitionVersion,
                    and_(
                        MethodologyDefinitionVersion.organisation_id == MethodologyDefinition.organisation_id,
                        MethodologyDefinitionVersion.definition_id == MethodologyDefinition.id,
                        MethodologyDefinitionVersion.version == MethodologyDefinition.current_version,
                    ),
                )
                .where(MethodologyDefinition.organisation_id == organisation_id)
                .order_by(MethodologyDefinition.created_at, MethodologyDefinition.id)
            )
        ).all()
        return [CustomDefinitionRecord(definition=row[0], version=row[1]) for row in rows]

    async def custom_definition_count(self, organisation_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.count())
            .select_from(MethodologyDefinition)
            .where(MethodologyDefinition.organisation_id == organisation_id)
        )
        return int(value or 0)

    async def projection_by_fingerprint(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        definition_key: str,
        definition_version: int,
        source_fingerprint: str,
    ) -> MethodologyProjection | None:
        return cast(
            MethodologyProjection | None,
            await self.session.scalar(
                select(MethodologyProjection).where(
                    MethodologyProjection.organisation_id == organisation_id,
                    MethodologyProjection.opportunity_id == opportunity_id,
                    MethodologyProjection.definition_key == definition_key,
                    MethodologyProjection.definition_version == definition_version,
                    MethodologyProjection.source_fingerprint == source_fingerprint,
                )
            ),
        )

    async def latest_projection(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        *,
        definition_key: str | None = None,
        definition_version: int | None = None,
    ) -> MethodologyProjection | None:
        conditions = [
            MethodologyProjection.organisation_id == organisation_id,
            MethodologyProjection.opportunity_id == opportunity_id,
        ]
        if definition_key is not None:
            conditions.append(MethodologyProjection.definition_key == definition_key)
        if definition_version is not None:
            conditions.append(MethodologyProjection.definition_version == definition_version)
        return cast(
            MethodologyProjection | None,
            await self.session.scalar(
                select(MethodologyProjection)
                .where(*conditions)
                .order_by(
                    MethodologyProjection.projection_version.desc(),
                    MethodologyProjection.generated_at.desc(),
                    MethodologyProjection.id.desc(),
                )
                .limit(1)
            ),
        )

    async def projection(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        projection_id: UUID,
        *,
        for_update: bool = False,
    ) -> MethodologyProjection | None:
        statement = select(MethodologyProjection).where(
            MethodologyProjection.organisation_id == organisation_id,
            MethodologyProjection.opportunity_id == opportunity_id,
            MethodologyProjection.id == projection_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(MethodologyProjection | None, await self.session.scalar(statement))

    async def projection_history(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        *,
        limit: int = 50,
    ) -> list[MethodologyProjection]:
        values = await self.session.scalars(
            select(MethodologyProjection)
            .where(
                MethodologyProjection.organisation_id == organisation_id,
                MethodologyProjection.opportunity_id == opportunity_id,
            )
            .order_by(
                MethodologyProjection.projection_version.desc(),
                MethodologyProjection.id.desc(),
            )
            .limit(limit)
        )
        return list(values.all())

    async def next_projection_version(self, organisation_id: UUID, opportunity_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.max(MethodologyProjection.projection_version)).where(
                MethodologyProjection.organisation_id == organisation_id,
                MethodologyProjection.opportunity_id == opportunity_id,
            )
        )
        return int(value or 0) + 1

    async def reviews(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        *,
        limit: int = 100,
    ) -> list[MethodologyReview]:
        values = await self.session.scalars(
            select(MethodologyReview)
            .where(
                MethodologyReview.organisation_id == organisation_id,
                MethodologyReview.opportunity_id == opportunity_id,
            )
            .order_by(MethodologyReview.created_at, MethodologyReview.id)
            .limit(limit)
        )
        current: list[MethodologyReview] = []
        for review in values.all():
            if review.clarification_evidence_id is not None and not await self.evidence_ids_are_current(
                organisation_id,
                [str(review.clarification_evidence_id)],
            ):
                continue
            current.append(review)
        return current

    async def review_by_idempotency(
        self,
        organisation_id: UUID,
        user_id: UUID,
        idempotency_key: str,
    ) -> MethodologyReview | None:
        return cast(
            MethodologyReview | None,
            await self.session.scalar(
                select(MethodologyReview).where(
                    MethodologyReview.organisation_id == organisation_id,
                    MethodologyReview.reviewed_by_user_id == user_id,
                    MethodologyReview.idempotency_key == idempotency_key,
                )
            ),
        )

    async def eligible_interaction_snapshots(
        self,
        organisation_id: UUID,
        opportunity_id: UUID,
        *,
        limit: int = 20,
    ) -> list[InteractionIntelligenceSnapshot]:
        values = await self.session.scalars(
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
                InteractionIntelligenceSnapshot.opportunity_id == opportunity_id,
                InteractionIntelligenceSnapshot.validation_state == "validated",
                Interaction.deleted_at.is_(None),
                Interaction.lifecycle_status == "completed",
            )
            .order_by(
                InteractionIntelligenceSnapshot.created_at.desc(),
                InteractionIntelligenceSnapshot.id.desc(),
            )
            .limit(limit)
        )
        snapshots: list[InteractionIntelligenceSnapshot] = []
        for snapshot in values.all():
            if await self.evidence_ids_are_current(organisation_id, snapshot.source_evidence_ids):
                snapshots.append(snapshot)
        return snapshots

    async def evidence_ids_are_current(self, organisation_id: UUID, raw_ids: list[str]) -> bool:
        try:
            identifiers = {UUID(value) for value in raw_ids}
        except (TypeError, ValueError):
            return False
        if not identifiers:
            return False
        value = await self.session.scalar(
            select(func.count())
            .select_from(Evidence)
            .where(
                Evidence.organisation_id == organisation_id,
                Evidence.id.in_(identifiers),
                Evidence.validation_state == "verified",
                Evidence.lifecycle_status == "available",
                Evidence.deleted_at.is_(None),
            )
        )
        return int(value or 0) == len(identifiers)

    def add(self, record: Base) -> None:
        self.session.add(record)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
