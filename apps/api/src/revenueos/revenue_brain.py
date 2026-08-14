from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple
from uuid import UUID, uuid5

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.ai_contracts import (
    ACTION_ITEMS_SCHEMA_VERSION,
    BUYING_SIGNALS_SCHEMA_VERSION,
    DECISIONS_SCHEMA_VERSION,
    EXECUTIVE_SUMMARY_SCHEMA_VERSION,
    NEXT_BEST_ACTION_SCHEMA_VERSION,
    OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_VERSION,
    OPEN_QUESTIONS_SCHEMA_VERSION,
    RISKS_BLOCKERS_SCHEMA_VERSION,
    STAKEHOLDER_INTELLIGENCE_SCHEMA_VERSION,
    ActionItemsArtifactContent,
    BuyingSignalsArtifactContent,
    DecisionsArtifactContent,
    ExecutiveSummaryArtifactContent,
    NextBestActionArtifactContent,
    ObjectionsCompetitiveSignalsArtifactContent,
    OpenQuestionsArtifactContent,
    RisksBlockersArtifactContent,
    StakeholderIntelligenceArtifactContent,
)
from revenueos.domain import AIArtifactType, MeetingStatus
from revenueos.errors import PublicAPIError
from revenueos.models import AIArtifact, RevenueBrainSnapshot
from revenueos.revenue_brain_repositories import (
    RevenueBrainInteractionTimelineItem,
    RevenueBrainRepository,
    RevenueBrainTimelineItem,
)
from revenueos.tenant import TenantContext

SNAPSHOT_VERSION = 1


class ArtifactRequirement(NamedTuple):
    artifact_type: str
    schema_version: int
    validation_model: type[BaseModel]


REQUIRED_ARTIFACTS = (
    ArtifactRequirement(
        AIArtifactType.EXECUTIVE_SUMMARY.value,
        EXECUTIVE_SUMMARY_SCHEMA_VERSION,
        ExecutiveSummaryArtifactContent,
    ),
    ArtifactRequirement(
        AIArtifactType.BUYING_SIGNALS.value,
        BUYING_SIGNALS_SCHEMA_VERSION,
        BuyingSignalsArtifactContent,
    ),
    ArtifactRequirement(
        AIArtifactType.OBJECTIONS_COMPETITIVE_SIGNALS.value,
        OBJECTIONS_COMPETITIVE_SIGNALS_SCHEMA_VERSION,
        ObjectionsCompetitiveSignalsArtifactContent,
    ),
    ArtifactRequirement(
        AIArtifactType.STAKEHOLDER_INTELLIGENCE.value,
        STAKEHOLDER_INTELLIGENCE_SCHEMA_VERSION,
        StakeholderIntelligenceArtifactContent,
    ),
    ArtifactRequirement(
        AIArtifactType.DECISIONS.value,
        DECISIONS_SCHEMA_VERSION,
        DecisionsArtifactContent,
    ),
    ArtifactRequirement(
        AIArtifactType.ACTION_ITEMS.value,
        ACTION_ITEMS_SCHEMA_VERSION,
        ActionItemsArtifactContent,
    ),
    ArtifactRequirement(
        AIArtifactType.RISKS_BLOCKERS.value,
        RISKS_BLOCKERS_SCHEMA_VERSION,
        RisksBlockersArtifactContent,
    ),
    ArtifactRequirement(
        AIArtifactType.OPEN_QUESTIONS.value,
        OPEN_QUESTIONS_SCHEMA_VERSION,
        OpenQuestionsArtifactContent,
    ),
    ArtifactRequirement(
        AIArtifactType.NEXT_BEST_ACTION.value,
        NEXT_BEST_ACTION_SCHEMA_VERSION,
        NextBestActionArtifactContent,
    ),
)
REQUIRED_ARTIFACT_TYPES = tuple(requirement.artifact_type for requirement in REQUIRED_ARTIFACTS)


@dataclass(frozen=True)
class SnapshotCreationResult:
    snapshot: RevenueBrainSnapshot | None
    created: bool


def transcript_version_identifier(transcript_id: UUID, transcript_version: int) -> UUID:
    if transcript_version < 1:
        raise ValueError("Transcript version must be positive.")
    return uuid5(transcript_id, f"revenue-brain-transcript-version:{transcript_version}")


class RevenueBrainService:
    """Creates and reads immutable account-level artefact compositions."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        *,
        repository: RevenueBrainRepository | None = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.repository = repository or RevenueBrainRepository(session)

    async def prepare_snapshot_if_ready(
        self,
        meeting_id: UUID,
        transcript_id: UUID,
        transcript_version: int,
    ) -> SnapshotCreationResult:
        meeting = await self.repository.lock_meeting(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None or meeting.status != MeetingStatus.COMPLETED.value or meeting.company_id is None:
            return SnapshotCreationResult(snapshot=None, created=False)

        transcript = await self.repository.get_current_transcript(
            self.tenant.organisation_id,
            meeting_id,
            transcript_id,
            transcript_version,
        )
        if transcript is None:
            return SnapshotCreationResult(snapshot=None, created=False)

        transcript_version_id = transcript_version_identifier(
            transcript_id,
            transcript_version,
        )
        existing = await self.repository.get_snapshot(
            self.tenant.organisation_id,
            meeting_id,
            transcript_version_id,
        )
        if existing is not None:
            return SnapshotCreationResult(snapshot=existing, created=False)

        artifacts = await self.repository.list_completed_artifacts(
            self.tenant.organisation_id,
            meeting_id,
            transcript_id,
            transcript_version,
            REQUIRED_ARTIFACT_TYPES,
        )
        latest_by_type: dict[str, AIArtifact] = {}
        for artifact in artifacts:
            latest_by_type.setdefault(artifact.artifact_type, artifact)

        if set(latest_by_type) != set(REQUIRED_ARTIFACT_TYPES):
            return SnapshotCreationResult(snapshot=None, created=False)

        for requirement in REQUIRED_ARTIFACTS:
            artifact = latest_by_type[requirement.artifact_type]
            if artifact.schema_version != requirement.schema_version:
                return SnapshotCreationResult(snapshot=None, created=False)
            try:
                requirement.validation_model.model_validate(artifact.content_json)
            except ValidationError:
                return SnapshotCreationResult(snapshot=None, created=False)

        snapshot = RevenueBrainSnapshot(
            organisation_id=self.tenant.organisation_id,
            company_id=meeting.company_id,
            opportunity_id=meeting.opportunity_id,
            meeting_id=meeting.id,
            transcript_version_id=transcript_version_id,
            summary_reference=latest_by_type[AIArtifactType.EXECUTIVE_SUMMARY.value].id,
            buying_signals_reference=latest_by_type[AIArtifactType.BUYING_SIGNALS.value].id,
            objections_reference=latest_by_type[AIArtifactType.OBJECTIONS_COMPETITIVE_SIGNALS.value].id,
            stakeholders_reference=latest_by_type[AIArtifactType.STAKEHOLDER_INTELLIGENCE.value].id,
            decisions_reference=latest_by_type[AIArtifactType.DECISIONS.value].id,
            actions_reference=latest_by_type[AIArtifactType.ACTION_ITEMS.value].id,
            risks_reference=latest_by_type[AIArtifactType.RISKS_BLOCKERS.value].id,
            questions_reference=latest_by_type[AIArtifactType.OPEN_QUESTIONS.value].id,
            next_best_action_reference=latest_by_type[AIArtifactType.NEXT_BEST_ACTION.value].id,
            version=SNAPSHOT_VERSION,
        )
        self.repository.create_snapshot(snapshot)
        return SnapshotCreationResult(snapshot=snapshot, created=True)

    async def list_account_snapshots(
        self,
        account_id: UUID,
    ) -> list[RevenueBrainTimelineItem]:
        if not await self.repository.company_exists(
            self.tenant.organisation_id,
            account_id,
        ):
            raise PublicAPIError(
                "not_found",
                "The requested account was not found.",
                404,
            )
        return await self.repository.list_for_company(
            self.tenant.organisation_id,
            account_id,
        )

    async def list_account_visual_snapshots(
        self,
        account_id: UUID,
    ) -> list[RevenueBrainInteractionTimelineItem]:
        if not await self.repository.company_exists(
            self.tenant.organisation_id,
            account_id,
        ):
            raise PublicAPIError(
                "not_found",
                "The requested account was not found.",
                404,
            )
        return await self.repository.list_visual_for_company(
            self.tenant.organisation_id,
            account_id,
        )
