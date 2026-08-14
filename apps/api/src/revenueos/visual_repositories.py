from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from revenueos.models import (
    BetaSystemEvent,
    CaptureSession,
    Evidence,
    Interaction,
    InteractionIntelligenceSnapshot,
    Opportunity,
    RevenueBrainInteractionSnapshot,
    VisualAsset,
    VisualCandidateEvidence,
)


@dataclass(frozen=True)
class VisualAssetRecord:
    capture_session: CaptureSession
    source_evidence: Evidence
    visual: VisualAsset


class VisualEvidenceRepository:
    """All visual metadata and lineage reads are explicitly tenant scoped."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_interaction(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
    ) -> Interaction | None:
        return cast(
            Interaction | None,
            await self.session.scalar(
                select(Interaction).where(
                    Interaction.organisation_id == organisation_id,
                    Interaction.id == interaction_id,
                    Interaction.deleted_at.is_(None),
                )
            ),
        )

    async def find_idempotent_upload(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        user_id: UUID,
        idempotency_key: str,
    ) -> VisualAssetRecord | None:
        row = (
            await self.session.execute(
                self._record_statement().where(
                    VisualAsset.organisation_id == organisation_id,
                    VisualAsset.interaction_id == interaction_id,
                    VisualAsset.captured_by_user_id == user_id,
                    VisualAsset.upload_idempotency_key == idempotency_key,
                )
            )
        ).one_or_none()
        return VisualAssetRecord(row[0], row[1], row[2]) if row is not None else None

    async def get_visual(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        visual_id: UUID,
        *,
        for_update: bool = False,
        include_deleted: bool = False,
    ) -> VisualAssetRecord | None:
        statement = self._record_statement().where(
            VisualAsset.organisation_id == organisation_id,
            VisualAsset.interaction_id == interaction_id,
            VisualAsset.id == visual_id,
        )
        if not include_deleted:
            statement = statement.where(VisualAsset.deleted_at.is_(None))
        if for_update:
            statement = statement.with_for_update(of=VisualAsset)
        row = (await self.session.execute(statement)).one_or_none()
        return VisualAssetRecord(row[0], row[1], row[2]) if row is not None else None

    async def list_visuals(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
    ) -> list[VisualAssetRecord]:
        rows = (
            await self.session.execute(
                self._record_statement()
                .where(
                    VisualAsset.organisation_id == organisation_id,
                    VisualAsset.interaction_id == interaction_id,
                    VisualAsset.deleted_at.is_(None),
                )
                .order_by(VisualAsset.created_at.desc(), VisualAsset.id.desc())
            )
        ).all()
        return [VisualAssetRecord(row[0], row[1], row[2]) for row in rows]

    async def visual_usage(self, organisation_id: UUID, interaction_id: UUID) -> tuple[int, int]:
        row = (
            await self.session.execute(
                select(func.count(), func.coalesce(func.sum(VisualAsset.upload_byte_size), 0)).where(
                    VisualAsset.organisation_id == organisation_id,
                    VisualAsset.interaction_id == interaction_id,
                    VisualAsset.deleted_at.is_(None),
                )
            )
        ).one()
        return int(row[0]), int(row[1])

    async def count_processing_since(self, organisation_id: UUID, since: datetime) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(BetaSystemEvent)
                .where(
                    BetaSystemEvent.organisation_id == organisation_id,
                    BetaSystemEvent.event_type == "processing_started",
                    BetaSystemEvent.created_at >= since,
                )
            )
            or 0
        )

    async def list_candidates(
        self,
        organisation_id: UUID,
        visual_id: UUID,
        *,
        for_update: bool = False,
    ) -> list[VisualCandidateEvidence]:
        statement = (
            select(VisualCandidateEvidence)
            .where(
                VisualCandidateEvidence.organisation_id == organisation_id,
                VisualCandidateEvidence.source_visual_id == visual_id,
            )
            .order_by(VisualCandidateEvidence.created_at, VisualCandidateEvidence.id)
        )
        if for_update:
            statement = statement.with_for_update()
        values = await self.session.scalars(statement)
        return list(values.all())

    async def intelligence_for_session(
        self,
        organisation_id: UUID,
        session_id: UUID,
    ) -> InteractionIntelligenceSnapshot | None:
        return cast(
            InteractionIntelligenceSnapshot | None,
            await self.session.scalar(
                select(InteractionIntelligenceSnapshot).where(
                    InteractionIntelligenceSnapshot.organisation_id == organisation_id,
                    InteractionIntelligenceSnapshot.session_id == session_id,
                )
            ),
        )

    async def brain_for_intelligence(
        self,
        organisation_id: UUID,
        intelligence_id: UUID,
    ) -> RevenueBrainInteractionSnapshot | None:
        return cast(
            RevenueBrainInteractionSnapshot | None,
            await self.session.scalar(
                select(RevenueBrainInteractionSnapshot).where(
                    RevenueBrainInteractionSnapshot.organisation_id == organisation_id,
                    RevenueBrainInteractionSnapshot.interaction_intelligence_id == intelligence_id,
                )
            ),
        )

    async def next_intelligence_version(self, organisation_id: UUID, interaction_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.max(InteractionIntelligenceSnapshot.version)).where(
                InteractionIntelligenceSnapshot.organisation_id == organisation_id,
                InteractionIntelligenceSnapshot.interaction_id == interaction_id,
            )
        )
        return int(value or 0) + 1

    async def next_brain_version(
        self,
        organisation_id: UUID,
        company_id: UUID,
        opportunity_id: UUID | None,
    ) -> int:
        conditions = [
            RevenueBrainInteractionSnapshot.organisation_id == organisation_id,
            RevenueBrainInteractionSnapshot.company_id == company_id,
        ]
        if opportunity_id is None:
            conditions.append(RevenueBrainInteractionSnapshot.opportunity_id.is_(None))
        else:
            conditions.append(RevenueBrainInteractionSnapshot.opportunity_id == opportunity_id)
        value = await self.session.scalar(select(func.max(RevenueBrainInteractionSnapshot.version)).where(*conditions))
        return int(value or 0) + 1

    async def company_for_interaction(self, organisation_id: UUID, interaction: Interaction) -> UUID | None:
        if interaction.company_id is not None:
            return interaction.company_id
        if interaction.opportunity_id is None:
            return None
        opportunity = await self.session.scalar(
            select(Opportunity).where(
                Opportunity.organisation_id == organisation_id,
                Opportunity.id == interaction.opportunity_id,
            )
        )
        return opportunity.company_id if opportunity is not None else None

    @staticmethod
    def _record_statement() -> Select[tuple[CaptureSession, Evidence, VisualAsset]]:
        return (
            select(CaptureSession, Evidence, VisualAsset)
            .join(
                VisualAsset,
                and_(
                    VisualAsset.organisation_id == CaptureSession.organisation_id,
                    VisualAsset.capture_session_id == CaptureSession.id,
                ),
            )
            .join(
                Evidence,
                and_(
                    Evidence.organisation_id == VisualAsset.organisation_id,
                    Evidence.id == VisualAsset.source_evidence_id,
                ),
            )
        )
