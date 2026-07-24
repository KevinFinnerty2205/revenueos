from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.ai_contracts import BuyingSignalsArtifactContent, NextBestActionArtifactContent
from revenueos.business_repositories import PageResult
from revenueos.domain import (
    MeetingAuditAction,
    MeetingAuditEntityType,
    MeetingStatus,
    OpportunityAuditAction,
    OpportunityStage,
    OpportunityStatus,
)
from revenueos.errors import PublicAPIError
from revenueos.intelligence_workspace import CAPABILITIES, MeetingIntelligenceService
from revenueos.meeting_contracts import MeetingOpportunityUpdate
from revenueos.models import AIArtifact, Meeting, MeetingAuditEvent, OpportunityAuditEvent
from revenueos.opportunity_contracts import (
    IntelligenceReadiness,
    OpportunityListItemResponse,
    OpportunityMeetingSummaryResponse,
    OpportunityWorkspaceOpportunityResponse,
    OpportunityWorkspaceResponse,
)
from revenueos.opportunity_repositories import (
    MeetingSummaryRecord,
    OpportunityDisplayRecord,
    OpportunityWorkspaceRepository,
)
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.opportunity_workspace")


class OpportunityWorkspaceService:
    """Tenant-scoped opportunity read model over stored meeting intelligence."""

    def __init__(self, session: AsyncSession, tenant: TenantContext) -> None:
        self.session = session
        self.tenant = tenant
        self.repository = OpportunityWorkspaceRepository(session)
        self.intelligence = MeetingIntelligenceService(session, tenant)

    async def list_opportunities(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        company_id: UUID | None,
        stage: str | None,
        status: str | None,
        sort_by: str,
        sort_order: str,
    ) -> PageResult[OpportunityListItemResponse]:
        result = await self.repository.list_opportunities(
            self.tenant.organisation_id,
            page=page,
            page_size=page_size,
            search=search,
            company_id=company_id,
            stage=stage,
            status=status,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        latest_by_opportunity = await self.repository.latest_meetings(
            self.tenant.organisation_id,
            [record.opportunity.id for record in result.items],
        )
        latest_records = list(latest_by_opportunity.values())
        preview_artifacts = await self.repository.current_completed_artifacts(
            self.tenant.organisation_id,
            latest_records,
            artifact_types={"buying_signals", "next_best_action"},
        )
        previews = self._previews(preview_artifacts)
        items = []
        for record in result.items:
            latest = latest_by_opportunity.get(record.opportunity.id)
            meeting_previews = previews.get(latest.meeting.id, {}) if latest is not None else {}
            opportunity = record.opportunity
            items.append(
                OpportunityListItemResponse(
                    id=opportunity.id,
                    organisation_id=opportunity.organisation_id,
                    company_id=opportunity.company_id,
                    company_name=record.company_name,
                    name=opportunity.name,
                    stage=OpportunityStage(opportunity.stage),
                    status=OpportunityStatus(opportunity.status),
                    estimated_value=opportunity.estimated_value,
                    currency=opportunity.currency,
                    expected_close_date=opportunity.expected_close_date,
                    owner_user_id=opportunity.owner_user_id,
                    owner_name=record.owner_name,
                    description=opportunity.description,
                    latest_meeting_id=latest.meeting.id if latest is not None else None,
                    latest_meeting_date=(latest.meeting.meeting_date if latest is not None else None),
                    latest_meeting_momentum=meeting_previews.get("momentum"),
                    latest_next_best_action=meeting_previews.get("next_best_action"),
                    created_at=opportunity.created_at,
                    updated_at=opportunity.updated_at,
                )
            )
        return PageResult(items=items, total=result.total)

    async def get_workspace(self, opportunity_id: UUID) -> OpportunityWorkspaceResponse:
        record = await self.repository.get_opportunity(
            self.tenant.organisation_id,
            opportunity_id,
        )
        if record is None:
            raise PublicAPIError(
                "opportunity_not_found",
                "The requested opportunity was not found.",
                404,
            )
        recent = await self.repository.recent_meetings(
            self.tenant.organisation_id,
            opportunity_id,
            limit=20,
        )
        latest = recent[0] if recent else None
        readiness_artifacts = await self.repository.current_completed_artifacts(
            self.tenant.organisation_id,
            recent,
        )
        counts = self._valid_section_counts(readiness_artifacts)
        meeting_summaries = [self._meeting_summary(item, counts.get(item.meeting.id, 0)) for item in recent]
        intelligence = None
        if latest is not None:
            intelligence = await self.intelligence.get_existing_workspace(
                latest.meeting.id,
                latest.transcript_version,
            )
        available_count = intelligence.progress.ready if intelligence is not None else 0
        response = OpportunityWorkspaceResponse(
            opportunity=self._workspace_opportunity(record),
            latest_meeting=meeting_summaries[0] if meeting_summaries else None,
            recent_meetings=meeting_summaries,
            intelligence=intelligence,
            intelligence_sections_available=available_count,
            partial_data=(latest is not None and available_count < len(CAPABILITIES)),
            generated_at=datetime.now(UTC),
        )
        context = {
            "organisation_id": str(self.tenant.organisation_id),
            "opportunity_id": str(opportunity_id),
            "meeting_count": len(recent),
            "intelligence_sections_available": available_count,
        }
        logger.info("opportunity_workspace_viewed", extra=context)
        if latest is None:
            logger.info("opportunity_workspace_no_meeting", extra=context)
        else:
            logger.info(
                "opportunity_workspace_latest_meeting_selected",
                extra={**context, "meeting_id": str(latest.meeting.id)},
            )
        if response.partial_data:
            logger.info("opportunity_workspace_partial_data", extra=context)
        return response

    async def set_meeting_opportunity(
        self,
        meeting_id: UUID,
        request: MeetingOpportunityUpdate,
    ) -> Meeting:
        meeting = await self.repository.get_meeting_for_update(
            self.tenant.organisation_id,
            meeting_id,
        )
        if meeting is None:
            raise PublicAPIError(
                "meeting_not_found",
                "The requested meeting was not found.",
                404,
            )
        if not self._same_instant(meeting.updated_at, request.expected_updated_at):
            raise PublicAPIError(
                "stale_write",
                "This meeting changed after it was loaded. Refresh and try again.",
                409,
            )
        target = None
        if request.opportunity_id is not None:
            target = await self.repository.get_opportunity(
                self.tenant.organisation_id,
                request.opportunity_id,
            )
            if target is None:
                raise PublicAPIError(
                    "opportunity_not_found",
                    "The requested opportunity was not found.",
                    404,
                )
            if (
                meeting.company_id is not None
                and target.opportunity.company_id is not None
                and meeting.company_id != target.opportunity.company_id
            ):
                raise PublicAPIError(
                    "inconsistent_relationship",
                    "The meeting and opportunity must refer to the same company.",
                    422,
                )
        previous_id = meeting.opportunity_id
        if previous_id == request.opportunity_id:
            return meeting

        meeting.opportunity_id = request.opportunity_id
        meeting.updated_by = self.tenant.user_id
        meeting.updated_at = datetime.now(UTC)
        self.repository.add(
            MeetingAuditEvent(
                organisation_id=self.tenant.organisation_id,
                meeting_id=meeting.id,
                actor_user_id=self.tenant.user_id,
                action=MeetingAuditAction.UPDATED.value,
                entity_type=MeetingAuditEntityType.MEETING.value,
                entity_id=meeting.id,
                changed_fields=["opportunity_id", "updated_by"],
                metadata_json={
                    "association_changed": True,
                    "associated": request.opportunity_id is not None,
                },
            )
        )
        if previous_id is not None:
            self.repository.add(
                self._opportunity_audit(
                    previous_id,
                    OpportunityAuditAction.MEETING_DISASSOCIATED,
                    meeting.id,
                )
            )
        if request.opportunity_id is not None:
            self.repository.add(
                self._opportunity_audit(
                    request.opportunity_id,
                    OpportunityAuditAction.MEETING_ASSOCIATED,
                    meeting.id,
                )
            )
        try:
            await self.repository.flush()
            await self.repository.refresh(meeting)
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "conflict",
                "The meeting association conflicts with existing or related data.",
                409,
            ) from exc
        if previous_id is not None:
            logger.info(
                "opportunity_meeting_disassociated",
                extra={
                    "organisation_id": str(self.tenant.organisation_id),
                    "opportunity_id": str(previous_id),
                    "meeting_id": str(meeting.id),
                },
            )
        if request.opportunity_id is not None:
            logger.info(
                "opportunity_meeting_associated",
                extra={
                    "organisation_id": str(self.tenant.organisation_id),
                    "opportunity_id": str(request.opportunity_id),
                    "meeting_id": str(meeting.id),
                },
            )
        return meeting

    @staticmethod
    def _workspace_opportunity(
        record: OpportunityDisplayRecord,
    ) -> OpportunityWorkspaceOpportunityResponse:
        opportunity = record.opportunity
        return OpportunityWorkspaceOpportunityResponse(
            id=opportunity.id,
            company_id=opportunity.company_id,
            company_name=record.company_name,
            name=opportunity.name,
            stage=OpportunityStage(opportunity.stage),
            status=OpportunityStatus(opportunity.status),
            estimated_value=opportunity.estimated_value,
            currency=opportunity.currency,
            expected_close_date=opportunity.expected_close_date,
            owner_user_id=opportunity.owner_user_id,
            owner_name=record.owner_name,
            description=opportunity.description,
            created_at=opportunity.created_at,
            updated_at=opportunity.updated_at,
        )

    @staticmethod
    def _meeting_summary(
        record: MeetingSummaryRecord,
        available_count: int,
    ) -> OpportunityMeetingSummaryResponse:
        readiness: IntelligenceReadiness
        if record.transcript_version is None:
            readiness = "unavailable"
        elif available_count == 0:
            readiness = "not_generated"
        elif available_count == len(CAPABILITIES):
            readiness = "ready"
        else:
            readiness = "partial"
        meeting = record.meeting
        return OpportunityMeetingSummaryResponse(
            id=meeting.id,
            title=meeting.title,
            meeting_date=meeting.meeting_date,
            status=MeetingStatus(meeting.status),
            company_id=meeting.company_id,
            company_name=record.company_name,
            participant_count=record.participant_count,
            transcript_available=record.transcript_id is not None,
            transcript_version=record.transcript_version,
            intelligence_readiness=readiness,
            intelligence_sections_available=available_count,
            updated_at=meeting.updated_at,
        )

    @staticmethod
    def _valid_section_counts(artifacts: list[AIArtifact]) -> dict[UUID, int]:
        counts: dict[UUID, set[str]] = {}
        for artifact in artifacts:
            try:
                configuration = next(item for item in CAPABILITIES if item.artifact_type == artifact.artifact_type)
                MeetingIntelligenceService._validated_content(configuration.name, artifact)
            except (StopIteration, ValidationError):
                continue
            counts.setdefault(artifact.meeting_id, set()).add(artifact.artifact_type)
        return {meeting_id: len(types) for meeting_id, types in counts.items()}

    @staticmethod
    def _previews(artifacts: list[AIArtifact]) -> dict[UUID, dict[str, str]]:
        previews: dict[UUID, dict[str, str]] = {}
        for artifact in artifacts:
            meeting = previews.setdefault(artifact.meeting_id, {})
            try:
                if artifact.artifact_type == "buying_signals" and "momentum" not in meeting:
                    buying_signals = BuyingSignalsArtifactContent.model_validate(artifact.content_json)
                    meeting["momentum"] = buying_signals.overall_momentum
                elif artifact.artifact_type == "next_best_action" and "next_best_action" not in meeting:
                    next_best_action = NextBestActionArtifactContent.model_validate(artifact.content_json)
                    meeting["next_best_action"] = next_best_action.overall_recommendation
            except ValidationError:
                continue
        return previews

    def _opportunity_audit(
        self,
        opportunity_id: UUID,
        action: OpportunityAuditAction,
        meeting_id: UUID,
    ) -> OpportunityAuditEvent:
        return OpportunityAuditEvent(
            organisation_id=self.tenant.organisation_id,
            opportunity_id=opportunity_id,
            actor_user_id=self.tenant.user_id,
            action=action.value,
            changed_fields=["meeting_association"],
            metadata_json={"meeting_id": str(meeting_id)},
        )

    @staticmethod
    def _same_instant(first: datetime, second: datetime) -> bool:
        def normalise(value: datetime) -> datetime:
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            return value.astimezone(UTC)

        return normalise(first) == normalise(second)
