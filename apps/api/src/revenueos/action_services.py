from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.action_contracts import (
    ActionEditRequest,
    ActionGenerationResponse,
    ActionListResponse,
    ActionPayload,
    ActionProposalResponse,
    ActionRejectRequest,
    ActionReviewRequest,
    ActionSourceReference,
    ContactUpdatePayload,
    CreateTaskPayload,
    FollowUpEmailPayload,
    OpportunityUpdatePayload,
    OtherActionPayload,
    PrepareNextInteractionPayload,
    RecordCommitmentPayload,
    RecordDecisionPayload,
    RecordRiskPayload,
    RequestedMaterialPayload,
    ResolveOpenQuestionPayload,
    ReviewConflictPayload,
    ScheduleInteractionPayload,
    StakeholderUpdatePayload,
    UpdateProcurementPayload,
    UpdateSecurityLegalPayload,
    UpdateTimelinePayload,
)
from revenueos.action_repositories import ActionRecord, ActionRepository
from revenueos.ai_contracts import (
    ActionItemsArtifactContent,
    DecisionsArtifactContent,
    FollowUpEmailArtifactContent,
    NextBestActionArtifactContent,
    OpenQuestionsArtifactContent,
    RisksBlockersArtifactContent,
    StakeholderIntelligenceArtifactContent,
)
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.domain import (
    ActionAudience,
    ActionPriority,
    ActionRejectionReason,
    ActionRiskClass,
    ActionStatus,
    ActionType,
)
from revenueos.errors import PublicAPIError
from revenueos.methodology_contracts import MethodologyGapContext
from revenueos.methodology_services import SalesMethodologyProjectionService
from revenueos.models import (
    ActionAuditEvent,
    ActionProposal,
    ActionProposalVersion,
    AIArtifact,
    InteractionIntelligenceSnapshot,
    Opportunity,
    RevenueBrainSourceSnapshot,
)
from revenueos.opportunity_repositories import OpportunityWorkspaceRepository
from revenueos.source_evidence_repositories import SourceEvidenceRepository
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.actions")

ACTION_SCHEMA_VERSION = 1
MAX_PROPOSALS_PER_GENERATION = 8
MAX_ACTIVE_PROPOSALS_PER_OPPORTUNITY = 50
_PAYLOAD_ADAPTER: TypeAdapter[ActionPayload] = TypeAdapter(ActionPayload)
_ACTIVE_REVIEW_STATUSES = {"proposed", "edited"}
_STAGE_VALUES = {
    "qualification",
    "discovery",
    "evaluation",
    "proposal",
    "negotiation",
    "procurement",
    "closed_won",
    "closed_lost",
    "other",
}
_STATUS_VALUES = {"open", "won", "lost", "on_hold"}
_DATA_MUTATION_TYPES = {
    ActionType.UPDATE_OPPORTUNITY,
    ActionType.UPDATE_CONTACT,
    ActionType.UPDATE_STAKEHOLDER,
}
_CUSTOMER_FACING_TYPES = {
    ActionType.FOLLOW_UP_EMAIL,
    ActionType.SEND_REQUESTED_MATERIAL,
    ActionType.FOLLOW_UP_STAKEHOLDER,
    ActionType.SCHEDULE_INTERACTION,
}


@dataclass(frozen=True)
class ActionCandidate:
    logical_key: str
    interaction_id: UUID | None
    action_type: ActionType
    priority: ActionPriority
    title: str
    description: str
    proposed_due_at: datetime | None
    target_entity_type: str | None
    target_entity_id: UUID | None
    payload: BaseModel
    source_refs: tuple[ActionSourceReference, ...]
    provenance_summary: str


class ActionService:
    """Deterministic review layer over final, validated intelligence only."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = ActionRepository(session)
        self.workspace_repository = OpportunityWorkspaceRepository(session)
        self.source_repository = SourceEvidenceRepository(session)
        self.methodology = SalesMethodologyProjectionService(session, tenant, settings)

    async def generate(self, opportunity_id: UUID) -> ActionGenerationResponse:
        opportunity = await self.repository.opportunity_for_update(
            self.tenant.organisation_id,
            opportunity_id,
        )
        if opportunity is None:
            raise PublicAPIError("opportunity_not_found", "The requested opportunity was not found.", 404)
        now = datetime.now(UTC)
        start_of_day = datetime.combine(now.date(), time.min, tzinfo=UTC)
        generated_today = await self.repository.generation_count_since(
            self.tenant.organisation_id,
            start_of_day,
        )
        if generated_today >= self.settings.private_beta_max_action_generations_per_day:
            raise PublicAPIError(
                "action_generation_quota_exceeded",
                "The private-beta Action generation limit has been reached for today.",
                429,
            )
        active_count = await self.repository.active_count(
            self.tenant.organisation_id,
            opportunity_id,
        )
        available_slots = max(0, MAX_ACTIVE_PROPOSALS_PER_OPPORTUNITY - active_count)
        if available_slots == 0:
            raise PublicAPIError(
                "active_action_limit_reached",
                "Review existing Actions before generating more for this opportunity.",
                409,
            )

        candidates = (await self._candidates(opportunity))[: min(MAX_PROPOSALS_PER_GENERATION, available_slots)]
        created_ids: list[UUID] = []
        reused_ids: list[UUID] = []
        superseded_count = 0
        for candidate in candidates:
            source_fingerprint = self._candidate_fingerprint(opportunity, candidate)
            existing = await self.repository.by_source_fingerprint(
                self.tenant.organisation_id,
                opportunity_id,
                source_fingerprint,
            )
            if existing is not None:
                reused_ids.append(existing.proposal.id)
                continue
            semantic_key = self._sha256(
                {
                    "schemaVersion": ACTION_SCHEMA_VERSION,
                    "organisationId": str(self.tenant.organisation_id),
                    "opportunityId": str(opportunity_id),
                    "logicalKey": candidate.logical_key,
                }
            )
            superseded = await self.repository.active_by_semantic_key(
                self.tenant.organisation_id,
                opportunity_id,
                semantic_key,
            )
            proposal_id = uuid.uuid4()
            for prior in superseded:
                prior.status = ActionStatus.SUPERSEDED.value
                self.repository.add(
                    ActionAuditEvent(
                        id=uuid.uuid4(),
                        organisation_id=self.tenant.organisation_id,
                        action_id=prior.id,
                        actor_user_id=self.tenant.user_id,
                        event_type="superseded",
                        proposal_version=prior.current_version,
                        metadata_json={"replacement_action_id": str(proposal_id)},
                        created_at=now,
                    )
                )
                superseded_count += 1
            audience, risk_class = self._classification(candidate.action_type)
            proposal = ActionProposal(
                id=proposal_id,
                organisation_id=self.tenant.organisation_id,
                opportunity_id=opportunity_id,
                interaction_id=candidate.interaction_id,
                action_type=candidate.action_type.value,
                status=ActionStatus.PROPOSED.value,
                priority=candidate.priority.value,
                audience=audience.value,
                risk_class=risk_class.value,
                current_version=1,
                source_fingerprint=source_fingerprint,
                semantic_key=semantic_key,
                created_by_user_id=self.tenant.user_id,
                generated_at=now,
                supersedes_action_id=superseded[0].id if superseded else None,
            )
            version = self._version_record(proposal, candidate, version=1, created_at=now)
            self.repository.add(proposal)
            self.repository.add(version)
            await self.repository.flush()
            self.repository.add(
                ActionAuditEvent(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    action_id=proposal.id,
                    actor_user_id=self.tenant.user_id,
                    event_type="proposed",
                    proposal_version=1,
                    metadata_json={
                        "action_type": candidate.action_type.value,
                        "priority": candidate.priority.value,
                        "source_count": len(candidate.source_refs),
                        "audience": audience.value,
                    },
                    created_at=now,
                )
            )
            created_ids.append(proposal.id)
        try:
            await self.repository.flush()
            await self.repository.commit()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
        except IntegrityError as exc:
            await self.repository.rollback()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
            concurrent: list[ActionRecord] = []
            for candidate in candidates:
                existing = await self.repository.by_source_fingerprint(
                    self.tenant.organisation_id,
                    opportunity_id,
                    self._candidate_fingerprint(opportunity, candidate),
                )
                if existing is None:
                    raise PublicAPIError(
                        "action_generation_conflict",
                        "Equivalent Actions were generated concurrently. Refresh and try again.",
                        409,
                    ) from exc
                concurrent.append(existing)
            logger.info(
                "actions_generation_concurrent_reuse",
                extra={
                    "organisation_id": str(self.tenant.organisation_id),
                    "opportunity_id": str(opportunity_id),
                    "reused_count": len(concurrent),
                },
            )
            return ActionGenerationResponse(
                actions=[self._response(record) for record in concurrent],
                created_count=0,
                reused_count=len(concurrent),
                superseded_count=0,
                proposal_limit=MAX_PROPOSALS_PER_GENERATION,
            )

        selected_ids = [*created_ids, *reused_ids]
        records = await self.repository.list_actions(
            self.tenant.organisation_id,
            opportunity_id=opportunity_id,
            limit=MAX_ACTIVE_PROPOSALS_PER_OPPORTUNITY,
        )
        by_id = {record.proposal.id: record for record in records}
        actions = [self._response(by_id[action_id]) for action_id in selected_ids if action_id in by_id]
        logger.info(
            "actions_generated",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "opportunity_id": str(opportunity_id),
                "proposal_count": len(actions),
                "created_count": len(created_ids),
                "reused_count": len(reused_ids),
                "superseded_count": superseded_count,
            },
        )
        return ActionGenerationResponse(
            actions=actions,
            created_count=len(created_ids),
            reused_count=len(reused_ids),
            superseded_count=superseded_count,
            proposal_limit=MAX_PROPOSALS_PER_GENERATION,
        )

    async def list_actions(
        self,
        opportunity_id: UUID,
        *,
        statuses: set[str] | None,
    ) -> ActionListResponse:
        if await self.repository.opportunity_for_update(self.tenant.organisation_id, opportunity_id) is None:
            raise PublicAPIError("opportunity_not_found", "The requested opportunity was not found.", 404)
        records = await self.repository.list_actions(
            self.tenant.organisation_id,
            opportunity_id=opportunity_id,
            statuses=statuses,
            limit=100,
        )
        return ActionListResponse(items=[self._response(item) for item in records], total=len(records))

    async def get(self, action_id: UUID) -> ActionProposalResponse:
        return self._response(await self._require_action(action_id))

    async def edit(self, action_id: UUID, request: ActionEditRequest) -> ActionProposalResponse:
        record = await self._require_action(action_id, for_update=True)
        proposal = record.proposal
        self._require_expected_version(proposal, request.expected_version)
        if proposal.status not in _ACTIVE_REVIEW_STATUSES:
            raise PublicAPIError("invalid_action_transition", "Only pending Actions can be edited.", 409)
        self._require_payload_type(proposal.action_type, request.proposed_payload)
        await self._validate_payload_relationships(proposal.opportunity_id, request.proposed_payload)
        await self._require_current_sources(record)
        now = datetime.now(UTC)
        next_version = proposal.current_version + 1
        payload_json = request.proposed_payload.model_dump(mode="json", by_alias=True)
        version = ActionProposalVersion(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            action_id=proposal.id,
            version=next_version,
            title=request.title,
            description=request.description,
            proposed_due_at=request.proposed_due_at,
            target_entity_type=record.version.target_entity_type,
            target_entity_id=record.version.target_entity_id,
            payload_json=payload_json,
            source_refs_json=record.version.source_refs_json,
            provenance_summary=record.version.provenance_summary,
            content_fingerprint=self._content_fingerprint(
                request.title,
                request.description,
                request.proposed_due_at,
                payload_json,
                record.version.source_refs_json,
            ),
            created_by_user_id=self.tenant.user_id,
            created_at=now,
        )
        proposal.current_version = next_version
        proposal.status = ActionStatus.EDITED.value
        self.repository.add(version)
        self.repository.add(
            ActionAuditEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                action_id=proposal.id,
                actor_user_id=self.tenant.user_id,
                event_type="edited",
                proposal_version=next_version,
                metadata_json={"changed_fields": ["title", "description", "proposed_due_at", "payload"]},
                created_at=now,
            )
        )
        await self._commit("The Action edit could not be saved.")
        logger.info(
            "action_edited",
            extra=self._log_context(proposal, proposal_version=next_version),
        )
        return self._response(await self._require_action(action_id))

    async def approve(self, action_id: UUID, request: ActionReviewRequest) -> ActionProposalResponse:
        record = await self._require_action(action_id, for_update=True)
        proposal = record.proposal
        self._require_expected_version(proposal, request.expected_version)
        if proposal.status not in _ACTIVE_REVIEW_STATUSES:
            raise PublicAPIError("invalid_action_transition", "Only pending Actions can be approved.", 409)
        payload = self._payload(record.version.payload_json)
        await self._validate_payload_relationships(proposal.opportunity_id, payload)
        await self._require_current_sources(record)
        now = datetime.now(UTC)
        proposal.status = ActionStatus.APPROVED.value
        proposal.approved_version = proposal.current_version
        proposal.reviewed_by_user_id = self.tenant.user_id
        proposal.reviewed_at = now
        proposal.approved_at = now
        self.repository.add(
            ActionAuditEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                action_id=proposal.id,
                actor_user_id=self.tenant.user_id,
                event_type="approved",
                proposal_version=proposal.current_version,
                metadata_json={
                    "action_type": proposal.action_type,
                    "audience": proposal.audience,
                    "risk_class": proposal.risk_class,
                    "external_execution": False,
                },
                created_at=now,
            )
        )
        await self._commit("The Action could not be approved.")
        logger.info("action_approved", extra=self._log_context(proposal))
        return self._response(await self._require_action(action_id))

    async def reject(self, action_id: UUID, request: ActionRejectRequest) -> ActionProposalResponse:
        record = await self._require_action(action_id, for_update=True)
        proposal = record.proposal
        self._require_expected_version(proposal, request.expected_version)
        if proposal.status not in _ACTIVE_REVIEW_STATUSES:
            raise PublicAPIError("invalid_action_transition", "Only pending Actions can be rejected.", 409)
        now = datetime.now(UTC)
        proposal.status = ActionStatus.REJECTED.value
        proposal.reviewed_by_user_id = self.tenant.user_id
        proposal.reviewed_at = now
        proposal.rejected_at = now
        proposal.rejection_reason_code = request.reason_code.value
        self.repository.add(
            ActionAuditEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                action_id=proposal.id,
                actor_user_id=self.tenant.user_id,
                event_type="rejected",
                proposal_version=proposal.current_version,
                metadata_json={"reason_code": request.reason_code.value},
                created_at=now,
            )
        )
        await self._commit("The Action could not be rejected.")
        logger.info(
            "action_rejected",
            extra={**self._log_context(proposal), "rejection_reason": request.reason_code.value},
        )
        return self._response(await self._require_action(action_id))

    async def complete(self, action_id: UUID, request: ActionReviewRequest) -> ActionProposalResponse:
        record = await self._require_action(action_id, for_update=True)
        proposal = record.proposal
        self._require_expected_version(proposal, request.expected_version)
        if proposal.status != ActionStatus.APPROVED.value:
            raise PublicAPIError(
                "invalid_action_transition",
                "Only an approved Action can be marked complete.",
                409,
            )
        if proposal.audience != ActionAudience.INTERNAL.value:
            raise PublicAPIError(
                "manual_completion_unavailable",
                "Customer-facing Actions cannot be marked complete without separate confirmation.",
                409,
            )
        now = datetime.now(UTC)
        proposal.status = ActionStatus.COMPLETED_MANUALLY.value
        proposal.completed_by_user_id = self.tenant.user_id
        proposal.completed_at = now
        self.repository.add(
            ActionAuditEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                action_id=proposal.id,
                actor_user_id=self.tenant.user_id,
                event_type="completed_manually",
                proposal_version=proposal.current_version,
                metadata_json={"confirmation_source": "user_reported", "external_confirmation": False},
                created_at=now,
            )
        )
        await self._commit("The Action could not be marked complete.")
        logger.info("action_completed_manually", extra=self._log_context(proposal))
        return self._response(await self._require_action(action_id))

    async def _candidates(self, opportunity: Opportunity) -> list[ActionCandidate]:
        candidates: list[ActionCandidate] = []
        recent = await self.workspace_repository.recent_meetings(
            self.tenant.organisation_id,
            opportunity.id,
            limit=1,
        )
        if recent and recent[0].meeting.status == "completed" and recent[0].transcript_version is not None:
            artifacts = await self.workspace_repository.current_completed_artifacts(
                self.tenant.organisation_id,
                recent,
                artifact_types={
                    "action_items",
                    "decisions",
                    "risks_blockers",
                    "open_questions",
                    "stakeholder_intelligence",
                    "next_best_action",
                    "follow_up_email",
                },
            )
            selected = self._validated_artifacts(artifacts)
            meeting = recent[0].meeting
            candidates.extend(self._artifact_candidates(opportunity, meeting.interaction_id, selected))

        display = await self.workspace_repository.get_opportunity(
            self.tenant.organisation_id,
            opportunity.id,
        )
        if display is not None:
            for snapshot in (display.reported_intelligence, display.visual_intelligence):
                if snapshot is not None:
                    candidates.extend(self._interaction_snapshot_candidates(opportunity, snapshot))

        snapshots = await self.source_repository.list_snapshots_for_opportunity(
            self.tenant.organisation_id,
            opportunity.id,
            limit=20,
        )
        candidates.extend(self._source_snapshot_candidates(opportunity, snapshots))
        if self.settings.feature_sales_methodology_enabled:
            candidates.extend(
                self._methodology_candidates(
                    opportunity,
                    await self.methodology.gap_context(opportunity.id, limit=2),
                )
            )
        return self._deduplicate_candidates(candidates)

    @staticmethod
    def _methodology_candidates(
        opportunity: Opportunity,
        gaps: tuple[MethodologyGapContext, ...],
    ) -> list[ActionCandidate]:
        values: list[ActionCandidate] = []
        for gap in gaps:
            source = ActionSourceReference(
                source_type="methodology_projection",
                source_id=gap.projection_id,
                item_key=f"field:{gap.field_key}",
                label=f"Current {gap.methodology_key.upper()} view: {gap.display_name}",
                origin="methodology",
            )
            if gap.state == "conflicting":
                source_labels = tuple(item.label for item in gap.sources[:5])
                claims = (
                    source_labels
                    if len(source_labels) >= 2
                    else (
                        "One current source supports this field.",
                        "Another current source disagrees with it.",
                    )
                )
                payload: BaseModel = ReviewConflictPayload(
                    kind="review_conflict",
                    subject=gap.display_name,
                    conflicting_claims=claims,
                )
                action_type = ActionType.REVIEW_CONFLICT
                title = f"Review conflicting {gap.display_name.lower()} evidence"
                description = "Resolve the conflicting evidence before relying on this deal view."
                priority = ActionPriority.HIGH
            else:
                payload = PrepareNextInteractionPayload(
                    kind="prepare_next_interaction",
                    objective=gap.suggested_question,
                    preparation_notes=(
                        f"The current methodology field is {gap.state.replace('_', ' ')}.",
                        "Use this as guidance; it is not a stage gate.",
                    ),
                )
                action_type = ActionType.PREPARE_NEXT_INTERACTION
                title = f"Clarify {gap.display_name.lower()}"
                description = "Prepare to close an evidence gap in the current methodology view."
                priority = ActionPriority.NORMAL if gap.state == "partially_supported" else ActionPriority.HIGH
            values.append(
                ActionCandidate(
                    logical_key=f"methodology:{gap.projection_id}:{gap.field_key}",
                    interaction_id=None,
                    action_type=action_type,
                    priority=priority,
                    title=title,
                    description=description,
                    proposed_due_at=None,
                    target_entity_type="opportunity",
                    target_entity_id=opportunity.id,
                    payload=payload,
                    source_refs=(source,),
                    provenance_summary=(
                        f"Suggested from the current evidence-backed methodology gap for {gap.display_name}."
                    ),
                )
            )
        return values

    def _artifact_candidates(
        self,
        opportunity: Opportunity,
        interaction_id: UUID,
        artifacts: dict[str, tuple[AIArtifact, BaseModel]],
    ) -> list[ActionCandidate]:
        values: list[ActionCandidate] = []
        action_items_entry = artifacts.get("action_items")
        if action_items_entry is not None:
            artifact, parsed = action_items_entry
            action_items_content = cast(ActionItemsArtifactContent, parsed)
            for index, action_item in enumerate(action_items_content.action_items[:3]):
                due_at = self._date_at_utc(action_item.due_date)
                source = self._artifact_ref(artifact, f"action_item:{index}", "Final Action Item")
                values.append(
                    ActionCandidate(
                        logical_key=f"action_items:{index}",
                        interaction_id=interaction_id,
                        action_type=ActionType.CREATE_TASK,
                        priority=self._priority(action_item.priority),
                        title=action_item.task,
                        description=(
                            "Prepare this internal task from a final validated Action Item. "
                            "Approval will not create a task in another system."
                        ),
                        proposed_due_at=due_at,
                        target_entity_type="opportunity",
                        target_entity_id=opportunity.id,
                        payload=CreateTaskPayload(
                            kind="create_task",
                            title=action_item.task,
                            owner_name=action_item.owner,
                            owner_user_id=None,
                            due_at=due_at,
                            context=action_item.evidence,
                            linked_opportunity_id=opportunity.id,
                            linked_interaction_id=interaction_id,
                        ),
                        source_refs=(source,),
                        provenance_summary=(
                            f"Suggested because final Action Item intelligence recorded: {action_item.evidence}"
                        ),
                    )
                )

        email_entry = artifacts.get("follow_up_email")
        if email_entry is not None:
            artifact, parsed = email_entry
            email_content = cast(FollowUpEmailArtifactContent, parsed)
            source = self._artifact_ref(artifact, "follow_up_email:0", "Existing Follow-up Email draft")
            values.append(
                ActionCandidate(
                    logical_key="follow_up_email:0",
                    interaction_id=interaction_id,
                    action_type=ActionType.FOLLOW_UP_EMAIL,
                    priority=ActionPriority.NORMAL,
                    title="Review the follow-up email draft",
                    description=(
                        "Review and edit the existing Follow-up Email draft. Approval records intent only; "
                        "RevenueOS will not send it."
                    ),
                    proposed_due_at=None,
                    target_entity_type=None,
                    target_entity_id=None,
                    payload=FollowUpEmailPayload(
                        kind="follow_up_email",
                        draft_artifact_id=artifact.id,
                        recipient_contact_id=None,
                        recipient_email=None,
                        recipient_confirmed=False,
                        subject=email_content.subject,
                        body=self._email_body(email_content),
                    ),
                    source_refs=(source,),
                    provenance_summary="Suggested from the existing current, validated Follow-up Email draft.",
                )
            )

        nba_entry = artifacts.get("next_best_action")
        if nba_entry is not None:
            artifact, parsed = nba_entry
            nba_content = cast(NextBestActionArtifactContent, parsed)
            for index, recommendation in enumerate(nba_content.recommended_actions[:2]):
                source = self._artifact_ref(artifact, f"recommended_action:{index}", "Next Best Action")
                lowered = recommendation.action.casefold()
                if any(term in lowered for term in ("schedule", "workshop", "meeting")):
                    action_type = ActionType.SCHEDULE_INTERACTION
                    payload: BaseModel = ScheduleInteractionPayload(
                        kind="schedule_interaction",
                        interaction_type="online_meeting",
                        timeframe=None,
                        participant_contact_ids=(),
                        purpose=recommendation.action,
                        objective=recommendation.reason,
                    )
                    title = recommendation.action
                elif "prepare" in lowered:
                    action_type = ActionType.PREPARE_NEXT_INTERACTION
                    payload = PrepareNextInteractionPayload(
                        kind="prepare_next_interaction",
                        objective=recommendation.action,
                        preparation_notes=(recommendation.reason,),
                    )
                    title = recommendation.action
                else:
                    action_type = ActionType.OTHER
                    payload = OtherActionPayload(kind="other", instruction=recommendation.action)
                    title = recommendation.action
                values.append(
                    ActionCandidate(
                        logical_key=f"next_best_action:{index}",
                        interaction_id=interaction_id,
                        action_type=action_type,
                        priority=self._priority(recommendation.priority),
                        title=title,
                        description=recommendation.reason,
                        proposed_due_at=None,
                        target_entity_type="opportunity",
                        target_entity_id=opportunity.id,
                        payload=payload,
                        source_refs=(source,),
                        provenance_summary=(
                            f"Suggested because the current Next Best Action states: {recommendation.reason}"
                        ),
                    )
                )

        questions_entry = artifacts.get("open_questions")
        if questions_entry is not None:
            artifact, parsed = questions_entry
            questions_content = cast(OpenQuestionsArtifactContent, parsed)
            for index, open_question in enumerate(questions_content.open_questions[:1]):
                values.append(
                    ActionCandidate(
                        logical_key=f"open_questions:{index}",
                        interaction_id=interaction_id,
                        action_type=ActionType.RESOLVE_OPEN_QUESTION,
                        priority=self._priority(open_question.importance),
                        title=f"Resolve: {open_question.question}",
                        description="Review this unresolved question before the next customer interaction.",
                        proposed_due_at=None,
                        target_entity_type="opportunity",
                        target_entity_id=opportunity.id,
                        payload=ResolveOpenQuestionPayload(
                            kind="resolve_open_question",
                            question=open_question.question,
                            owner_name=open_question.owner,
                        ),
                        source_refs=(self._artifact_ref(artifact, f"open_question:{index}", "Final Open Question"),),
                        provenance_summary=(
                            f"Suggested because final intelligence left this open: {open_question.evidence}"
                        ),
                    )
                )

        risks_entry = artifacts.get("risks_blockers")
        if risks_entry is not None:
            artifact, parsed = risks_entry
            risks_content = cast(RisksBlockersArtifactContent, parsed)
            for index, risk_item in enumerate(risks_content.risks[:1]):
                values.append(
                    ActionCandidate(
                        logical_key=f"risks:{index}",
                        interaction_id=interaction_id,
                        action_type=ActionType.ADD_RISK,
                        priority=self._priority(risk_item.severity),
                        title=f"Record risk: {risk_item.risk}",
                        description="Review and record this validated risk in the opportunity context.",
                        proposed_due_at=None,
                        target_entity_type="opportunity",
                        target_entity_id=opportunity.id,
                        payload=RecordRiskPayload(
                            kind="add_risk",
                            risk=risk_item.risk,
                            severity=self._priority(risk_item.severity).value,
                            owner_name=risk_item.owner,
                        ),
                        source_refs=(self._artifact_ref(artifact, f"risk:{index}", "Final Risk or Blocker"),),
                        provenance_summary=(f"Suggested because final intelligence recorded: {risk_item.evidence}"),
                    )
                )

        stakeholder_entry = artifacts.get("stakeholder_intelligence")
        if stakeholder_entry is not None:
            artifact, parsed = stakeholder_entry
            stakeholders_content = cast(StakeholderIntelligenceArtifactContent, parsed)
            for index, stakeholder in enumerate(stakeholders_content.stakeholders[:1]):
                role = self._stakeholder_role(stakeholder.role)
                if role is None:
                    continue
                values.append(
                    ActionCandidate(
                        logical_key=f"stakeholder:{index}",
                        interaction_id=interaction_id,
                        action_type=ActionType.UPDATE_STAKEHOLDER,
                        priority=ActionPriority.NORMAL,
                        title=f"Review {stakeholder.name}'s stakeholder role",
                        description="Review this role before accepting it into future execution intent.",
                        proposed_due_at=None,
                        target_entity_type="stakeholder",
                        target_entity_id=None,
                        payload=StakeholderUpdatePayload(
                            kind="update_stakeholder",
                            contact_id=None,
                            stakeholder_name=stakeholder.name,
                            role=role,
                            current_role=None,
                            reason=stakeholder.evidence,
                        ),
                        source_refs=(
                            self._artifact_ref(artifact, f"stakeholder:{index}", "Final Stakeholder Intelligence"),
                        ),
                        provenance_summary=(
                            f"Suggested because final Stakeholder Intelligence recorded: {stakeholder.evidence}"
                        ),
                    )
                )
        return values

    def _interaction_snapshot_candidates(
        self,
        opportunity: Opportunity,
        snapshot: InteractionIntelligenceSnapshot,
    ) -> list[ActionCandidate]:
        raw_items = snapshot.content_json.get("items")
        if not isinstance(raw_items, list):
            return []
        values: list[ActionCandidate] = []
        origin: Literal["salesperson_reported", "validated_intelligence"] = (
            "salesperson_reported" if snapshot.schema_version == 1 else "validated_intelligence"
        )
        label = "Reviewed salesperson report" if snapshot.schema_version == 1 else "Reviewed visual intelligence"
        for index, raw in enumerate(raw_items):
            if not isinstance(raw, dict):
                continue
            category = raw.get("category")
            statement = raw.get("statement")
            if not isinstance(category, str) or not isinstance(statement, str) or not statement.strip():
                continue
            reference = ActionSourceReference(
                source_type="interaction_intelligence",
                source_id=snapshot.id,
                item_key=f"item:{index}",
                label=label,
                origin=origin,
            )
            candidate = self._structured_item_candidate(
                opportunity,
                interaction_id=snapshot.interaction_id,
                logical_key=f"interaction:{snapshot.schema_version}:{category}:{index}",
                category=category,
                statement=statement,
                source=reference,
                provenance=self._source_wording(origin, statement),
            )
            if candidate is not None:
                values.append(candidate)
        return values

    def _source_snapshot_candidates(
        self,
        opportunity: Opportunity,
        snapshots: list[RevenueBrainSourceSnapshot],
    ) -> list[ActionCandidate]:
        values: list[ActionCandidate] = []
        conflicts: dict[str, list[tuple[str, ActionSourceReference, UUID | None]]] = {}
        for snapshot in snapshots:
            raw_items = snapshot.content_json.get("items")
            if not isinstance(raw_items, list):
                continue
            for index, raw in enumerate(raw_items):
                if not isinstance(raw, dict):
                    continue
                category = raw.get("category")
                statement = raw.get("statement")
                evidence_id = raw.get("evidenceId")
                origin = raw.get("originClass")
                source_label = raw.get("sourceLabel")
                if (
                    not isinstance(category, str)
                    or not isinstance(statement, str)
                    or not isinstance(evidence_id, str)
                    or not isinstance(source_label, str)
                    or origin not in {"customer_direct", "salesperson_reported"}
                ):
                    continue
                try:
                    evidence_uuid = UUID(evidence_id)
                except ValueError:
                    continue
                reference = ActionSourceReference(
                    source_type="accepted_evidence",
                    source_id=evidence_uuid,
                    item_key=f"item:{index}",
                    label=source_label,
                    origin=cast(Literal["customer_direct", "salesperson_reported"], origin),
                )
                interaction_id = snapshot.interaction_id
                candidate = self._structured_item_candidate(
                    opportunity,
                    interaction_id=interaction_id,
                    logical_key=f"source:{category}:{index}:{snapshot.source_kind}",
                    category=category,
                    statement=statement,
                    source=reference,
                    provenance=self._source_wording(origin, statement),
                )
                if candidate is not None:
                    values.append(candidate)
                if raw.get("conflictState") == "conflicting":
                    conflicts.setdefault(category, []).append((statement, reference, interaction_id))
        for category, items in conflicts.items():
            if len(items) < 2:
                continue
            values.append(
                ActionCandidate(
                    logical_key=f"conflict:{category}",
                    interaction_id=items[0][2],
                    action_type=ActionType.REVIEW_CONFLICT,
                    priority=ActionPriority.HIGH,
                    title=f"Resolve {category.replace('_', ' ')} discrepancy",
                    description="Review the conflicting accepted evidence. RevenueOS has not selected either claim.",
                    proposed_due_at=None,
                    target_entity_type="opportunity",
                    target_entity_id=opportunity.id,
                    payload=ReviewConflictPayload(
                        kind="review_conflict",
                        subject=category.replace("_", " "),
                        conflicting_claims=tuple(item[0] for item in items[:5]),
                    ),
                    source_refs=tuple(item[1] for item in items[:5]),
                    provenance_summary="Suggested because accepted evidence contains unresolved conflicting claims.",
                )
            )
        return values

    def _structured_item_candidate(
        self,
        opportunity: Opportunity,
        *,
        interaction_id: UUID | None,
        logical_key: str,
        category: str,
        statement: str,
        source: ActionSourceReference,
        provenance: str,
    ) -> ActionCandidate | None:
        if category == "customer_request":
            material = self._requested_material(statement)
            return ActionCandidate(
                logical_key=logical_key,
                interaction_id=interaction_id,
                action_type=ActionType.SEND_REQUESTED_MATERIAL,
                priority=ActionPriority.NORMAL,
                title=f"Prepare requested material: {material}",
                description="Confirm the requested material and recipient. No document will be attached or sent.",
                proposed_due_at=None,
                target_entity_type=None,
                target_entity_id=None,
                payload=RequestedMaterialPayload(
                    kind="send_requested_material",
                    material=material,
                    requested_by=None,
                    recipient_contact_id=None,
                ),
                source_refs=(source,),
                provenance_summary=provenance,
            )
        if category == "action_item":
            return ActionCandidate(
                logical_key=logical_key,
                interaction_id=interaction_id,
                action_type=ActionType.CREATE_TASK,
                priority=ActionPriority.NORMAL,
                title=statement[:240],
                description="Prepare an internal task from reviewed final Interaction Intelligence.",
                proposed_due_at=None,
                target_entity_type="opportunity",
                target_entity_id=opportunity.id,
                payload=CreateTaskPayload(
                    kind="create_task",
                    title=statement[:240],
                    owner_name=None,
                    owner_user_id=None,
                    due_at=None,
                    context=statement,
                    linked_opportunity_id=opportunity.id,
                    linked_interaction_id=interaction_id,
                ),
                source_refs=(source,),
                provenance_summary=provenance,
            )
        if category == "commitment":
            return ActionCandidate(
                logical_key=logical_key,
                interaction_id=interaction_id,
                action_type=ActionType.ADD_COMMITMENT,
                priority=ActionPriority.NORMAL,
                title="Record customer commitment",
                description=statement,
                proposed_due_at=None,
                target_entity_type="opportunity",
                target_entity_id=opportunity.id,
                payload=RecordCommitmentPayload(
                    kind="add_commitment", commitment=statement, owner_name=None, due_at=None
                ),
                source_refs=(source,),
                provenance_summary=provenance,
            )
        if category == "decision":
            return ActionCandidate(
                logical_key=logical_key,
                interaction_id=interaction_id,
                action_type=ActionType.ADD_DECISION,
                priority=ActionPriority.NORMAL,
                title="Record validated decision",
                description=statement,
                proposed_due_at=None,
                target_entity_type="opportunity",
                target_entity_id=opportunity.id,
                payload=RecordDecisionPayload(kind="add_decision", decision=statement, owner_name=None),
                source_refs=(source,),
                provenance_summary=provenance,
            )
        if category == "risk":
            return ActionCandidate(
                logical_key=logical_key,
                interaction_id=interaction_id,
                action_type=ActionType.ADD_RISK,
                priority=ActionPriority.NORMAL,
                title="Review and record risk",
                description=statement,
                proposed_due_at=None,
                target_entity_type="opportunity",
                target_entity_id=opportunity.id,
                payload=RecordRiskPayload(kind="add_risk", risk=statement, severity="normal", owner_name=None),
                source_refs=(source,),
                provenance_summary=provenance,
            )
        if category == "open_question":
            question = statement if statement.endswith("?") else f"{statement.rstrip('.')}?"
            return ActionCandidate(
                logical_key=logical_key,
                interaction_id=interaction_id,
                action_type=ActionType.RESOLVE_OPEN_QUESTION,
                priority=ActionPriority.NORMAL,
                title=f"Resolve: {question}"[:240],
                description="Review this unresolved question before relying on an answer.",
                proposed_due_at=None,
                target_entity_type="opportunity",
                target_entity_id=opportunity.id,
                payload=ResolveOpenQuestionPayload(kind="resolve_open_question", question=question, owner_name=None),
                source_refs=(source,),
                provenance_summary=provenance,
            )
        if category == "timeline":
            opportunity_update = self._opportunity_update_candidate(
                opportunity,
                interaction_id,
                logical_key,
                statement,
                source,
                provenance,
            )
            if opportunity_update is not None:
                return opportunity_update
            return ActionCandidate(
                logical_key=logical_key,
                interaction_id=interaction_id,
                action_type=ActionType.UPDATE_TIMELINE,
                priority=ActionPriority.NORMAL,
                title="Review opportunity timeline",
                description=statement,
                proposed_due_at=None,
                target_entity_type="opportunity",
                target_entity_id=opportunity.id,
                payload=UpdateTimelinePayload(
                    kind="update_timeline", current_value=None, proposed_value=statement, reason=statement
                ),
                source_refs=(source,),
                provenance_summary=provenance,
            )
        if category == "procurement":
            return ActionCandidate(
                logical_key=logical_key,
                interaction_id=interaction_id,
                action_type=ActionType.UPDATE_PROCUREMENT,
                priority=ActionPriority.NORMAL,
                title="Review procurement status",
                description=statement,
                proposed_due_at=None,
                target_entity_type="opportunity",
                target_entity_id=opportunity.id,
                payload=UpdateProcurementPayload(
                    kind="update_procurement", current_value=None, proposed_value=statement, reason=statement
                ),
                source_refs=(source,),
                provenance_summary=provenance,
            )
        if category == "security_legal":
            return ActionCandidate(
                logical_key=logical_key,
                interaction_id=interaction_id,
                action_type=ActionType.UPDATE_SECURITY_LEGAL,
                priority=ActionPriority.NORMAL,
                title="Review security and legal status",
                description=statement,
                proposed_due_at=None,
                target_entity_type="opportunity",
                target_entity_id=opportunity.id,
                payload=UpdateSecurityLegalPayload(
                    kind="update_security_legal",
                    area="security_and_legal",
                    current_value=None,
                    proposed_value=statement,
                    reason=statement,
                ),
                source_refs=(source,),
                provenance_summary=provenance,
            )
        return None

    def _opportunity_update_candidate(
        self,
        opportunity: Opportunity,
        interaction_id: UUID | None,
        logical_key: str,
        statement: str,
        source: ActionSourceReference,
        provenance: str,
    ) -> ActionCandidate | None:
        close_match = re.fullmatch(r"Expected close date:\s*(\d{4}-\d{2}-\d{2})", statement, re.IGNORECASE)
        if close_match:
            try:
                proposed = date.fromisoformat(close_match.group(1)).isoformat()
            except ValueError:
                return None
            current = opportunity.expected_close_date.isoformat() if opportunity.expected_close_date else None
            if proposed == current:
                return None
            return self._opportunity_update(
                opportunity,
                interaction_id,
                logical_key,
                "expected_close_date",
                current,
                proposed,
                statement,
                source,
                provenance,
            )
        stage_match = re.fullmatch(r"Opportunity stage:\s*([a-z_]+)", statement, re.IGNORECASE)
        if stage_match and stage_match.group(1).casefold() in _STAGE_VALUES:
            proposed = stage_match.group(1).casefold()
            if proposed == opportunity.stage:
                return None
            return self._opportunity_update(
                opportunity,
                interaction_id,
                logical_key,
                "stage",
                opportunity.stage,
                proposed,
                statement,
                source,
                provenance,
            )
        status_match = re.fullmatch(r"Opportunity status:\s*([a-z_]+)", statement, re.IGNORECASE)
        if status_match and status_match.group(1).casefold() in _STATUS_VALUES:
            proposed = status_match.group(1).casefold()
            if proposed == opportunity.status:
                return None
            return self._opportunity_update(
                opportunity,
                interaction_id,
                logical_key,
                "status",
                opportunity.status,
                proposed,
                statement,
                source,
                provenance,
            )
        value_match = re.fullmatch(r"Opportunity value:\s*(\d+(?:\.\d{1,2})?)\s+([A-Z]{3})", statement)
        if value_match:
            proposed_value = Decimal(value_match.group(1))
            proposed_currency = value_match.group(2)
            if proposed_value == opportunity.estimated_value and proposed_currency == opportunity.currency:
                return None
            return self._opportunity_update(
                opportunity,
                interaction_id,
                logical_key,
                "estimated_value",
                opportunity.estimated_value,
                proposed_value,
                statement,
                source,
                provenance,
            )
        return None

    @staticmethod
    def _opportunity_update(
        opportunity: Opportunity,
        interaction_id: UUID | None,
        logical_key: str,
        field: Literal["stage", "status", "expected_close_date", "description", "estimated_value", "currency"],
        current_value: str | Decimal | None,
        proposed_value: str | Decimal | None,
        statement: str,
        source: ActionSourceReference,
        provenance: str,
    ) -> ActionCandidate:
        return ActionCandidate(
            logical_key=logical_key,
            interaction_id=interaction_id,
            action_type=ActionType.UPDATE_OPPORTUNITY,
            priority=ActionPriority.NORMAL,
            title=f"Review opportunity {field.replace('_', ' ')} update",
            description=statement,
            proposed_due_at=None,
            target_entity_type="opportunity",
            target_entity_id=opportunity.id,
            payload=OpportunityUpdatePayload(
                kind="update_opportunity",
                field=field,
                current_value=current_value,
                proposed_value=proposed_value,
                reason=statement,
            ),
            source_refs=(source,),
            provenance_summary=provenance,
        )

    @staticmethod
    def _validated_artifacts(artifacts: list[AIArtifact]) -> dict[str, tuple[AIArtifact, BaseModel]]:
        validators: dict[str, type[BaseModel]] = {
            "action_items": ActionItemsArtifactContent,
            "decisions": DecisionsArtifactContent,
            "risks_blockers": RisksBlockersArtifactContent,
            "open_questions": OpenQuestionsArtifactContent,
            "stakeholder_intelligence": StakeholderIntelligenceArtifactContent,
            "next_best_action": NextBestActionArtifactContent,
            "follow_up_email": FollowUpEmailArtifactContent,
        }
        selected: dict[str, tuple[AIArtifact, BaseModel]] = {}
        for artifact in artifacts:
            if artifact.artifact_type in selected or artifact.superseded_at is not None:
                continue
            validator = validators.get(artifact.artifact_type)
            if validator is None:
                continue
            try:
                selected[artifact.artifact_type] = (artifact, validator.model_validate(artifact.content_json))
            except ValidationError:
                continue
        return selected

    async def _require_action(self, action_id: UUID, *, for_update: bool = False) -> ActionRecord:
        record = await self.repository.get_action(
            self.tenant.organisation_id,
            action_id,
            for_update=for_update,
        )
        if record is None:
            raise PublicAPIError("action_not_found", "The requested Action was not found.", 404)
        return record

    async def _require_current_sources(self, record: ActionRecord) -> None:
        references = self._source_refs(record.version.source_refs_json)
        for reference in references:
            if reference.source_type == "methodology_projection":
                methodology = await self.methodology.read(record.proposal.opportunity_id)
                is_current = methodology.state == "current" and methodology.projection_id == reference.source_id
            else:
                is_current = await self.repository.source_is_current(
                    self.tenant.organisation_id,
                    record.proposal.opportunity_id,
                    reference,
                )
            if is_current:
                continue
            now = datetime.now(UTC)
            record.proposal.status = ActionStatus.SUPERSEDED.value
            self.repository.add(
                ActionAuditEvent(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    action_id=record.proposal.id,
                    actor_user_id=self.tenant.user_id,
                    event_type="superseded",
                    proposal_version=record.proposal.current_version,
                    metadata_json={"reason": "source_no_longer_current"},
                    created_at=now,
                )
            )
            await self._commit("The stale Action could not be invalidated.")
            raise PublicAPIError(
                "action_source_stale",
                "This Action is no longer supported by current validated evidence. Generate a new proposal.",
                409,
            )

    async def _validate_payload_relationships(
        self,
        opportunity_id: UUID,
        payload: ActionPayload,
    ) -> None:
        if isinstance(payload, FollowUpEmailPayload) and payload.recipient_contact_id is not None:
            contact = await self.repository.contact(
                self.tenant.organisation_id,
                payload.recipient_contact_id,
            )
            if contact is None or contact.email.casefold() != cast(str, payload.recipient_email).casefold():
                raise PublicAPIError(
                    "unsupported_recipient",
                    "Choose a validated Contact and its stored email address.",
                    422,
                )
        if isinstance(payload, CreateTaskPayload) and payload.linked_opportunity_id != opportunity_id:
            raise PublicAPIError(
                "invalid_action_payload",
                "The task proposal must remain linked to this opportunity.",
                422,
            )
        if isinstance(payload, OpportunityUpdatePayload):
            if payload.field == "stage" and payload.proposed_value not in _STAGE_VALUES:
                raise PublicAPIError("invalid_action_payload", "The proposed opportunity stage is invalid.", 422)
            if payload.field == "status" and payload.proposed_value not in _STATUS_VALUES:
                raise PublicAPIError("invalid_action_payload", "The proposed opportunity status is invalid.", 422)
            if payload.field == "expected_close_date" and isinstance(payload.proposed_value, str):
                try:
                    date.fromisoformat(payload.proposed_value)
                except ValueError as exc:
                    raise PublicAPIError(
                        "invalid_action_payload",
                        "The proposed close date must be an exact calendar date.",
                        422,
                    ) from exc
        if isinstance(payload, ContactUpdatePayload) and payload.contact_id is not None:
            if await self.repository.contact(self.tenant.organisation_id, payload.contact_id) is None:
                raise PublicAPIError("unsupported_contact", "The selected Contact is unavailable.", 422)

    async def _commit(self, message: str) -> None:
        try:
            await self.repository.flush()
            await self.repository.commit()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError("action_conflict", message, 409) from exc

    def _version_record(
        self,
        proposal: ActionProposal,
        candidate: ActionCandidate,
        *,
        version: int,
        created_at: datetime,
    ) -> ActionProposalVersion:
        payload_json = candidate.payload.model_dump(mode="json", by_alias=True)
        refs_json = [item.model_dump(mode="json", by_alias=True) for item in candidate.source_refs]
        return ActionProposalVersion(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            action_id=proposal.id,
            version=version,
            title=candidate.title[:240],
            description=candidate.description[:2000],
            proposed_due_at=candidate.proposed_due_at,
            target_entity_type=candidate.target_entity_type,
            target_entity_id=candidate.target_entity_id,
            payload_json=payload_json,
            source_refs_json=refs_json,
            provenance_summary=candidate.provenance_summary[:2000],
            content_fingerprint=self._content_fingerprint(
                candidate.title,
                candidate.description,
                candidate.proposed_due_at,
                payload_json,
                refs_json,
            ),
            created_by_user_id=self.tenant.user_id,
            created_at=created_at,
        )

    def _candidate_fingerprint(self, opportunity: Opportunity, candidate: ActionCandidate) -> str:
        return self._sha256(
            {
                "schemaVersion": ACTION_SCHEMA_VERSION,
                "organisationId": str(self.tenant.organisation_id),
                "opportunityId": str(opportunity.id),
                "interactionId": str(candidate.interaction_id) if candidate.interaction_id else None,
                "actionType": candidate.action_type.value,
                "targetEntityType": candidate.target_entity_type,
                "targetEntityId": str(candidate.target_entity_id) if candidate.target_entity_id else None,
                "payload": candidate.payload.model_dump(mode="json", by_alias=True),
                "sourceRefs": [item.model_dump(mode="json", by_alias=True) for item in candidate.source_refs],
            }
        )

    @staticmethod
    def _content_fingerprint(
        title: str,
        description: str,
        due_at: datetime | None,
        payload: dict[str, object],
        source_refs: list[dict[str, object]],
    ) -> str:
        return ActionService._sha256(
            {
                "title": title,
                "description": description,
                "proposedDueAt": due_at.isoformat() if due_at else None,
                "payload": payload,
                "sourceRefs": source_refs,
            }
        )

    @staticmethod
    def _sha256(value: dict[str, object]) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _classification(action_type: ActionType) -> tuple[ActionAudience, ActionRiskClass]:
        if action_type in _CUSTOMER_FACING_TYPES:
            return ActionAudience.CUSTOMER_FACING, ActionRiskClass.EXTERNAL_CUSTOMER_FACING
        if action_type in _DATA_MUTATION_TYPES:
            return ActionAudience.INTERNAL, ActionRiskClass.DATA_MUTATION
        return ActionAudience.INTERNAL, ActionRiskClass.INTERNAL_LOW_RISK

    @staticmethod
    def _priority(value: str) -> ActionPriority:
        return {
            "high": ActionPriority.HIGH,
            "medium": ActionPriority.NORMAL,
            "normal": ActionPriority.NORMAL,
            "low": ActionPriority.LOW,
        }[value]

    @staticmethod
    def _stakeholder_role(
        value: str,
    ) -> (
        Literal[
            "economic_buyer_candidate",
            "decision_maker",
            "champion",
            "technical_buyer",
            "procurement",
            "legal_security",
            "blocker",
            "participant",
            "unknown",
        ]
        | None
    ):
        mapping = {
            "economic_buyer": "economic_buyer_candidate",
            "decision_maker": "decision_maker",
            "champion": "champion",
            "technical_buyer": "technical_buyer",
            "technical_evaluator": "technical_buyer",
            "procurement": "procurement",
            "legal": "legal_security",
            "security": "legal_security",
            "blocker": "blocker",
        }
        return cast(
            Literal[
                "economic_buyer_candidate",
                "decision_maker",
                "champion",
                "technical_buyer",
                "procurement",
                "legal_security",
                "blocker",
                "participant",
                "unknown",
            ]
            | None,
            mapping.get(value),
        )

    @staticmethod
    def _artifact_ref(
        artifact: AIArtifact,
        item_key: str,
        label: str,
    ) -> ActionSourceReference:
        return ActionSourceReference(
            source_type="ai_artifact",
            source_id=artifact.id,
            item_key=item_key,
            label=label,
            origin="validated_intelligence",
        )

    @staticmethod
    def _source_wording(origin: str, statement: str) -> str:
        if origin == "customer_direct":
            return f"Suggested because customer-direct accepted evidence states: {statement}"
        if origin == "salesperson_reported":
            return f"Suggested because you reported and confirmed: {statement}"
        return f"Suggested because reviewed final intelligence states: {statement}"

    @staticmethod
    def _requested_material(statement: str) -> str:
        value = re.sub(
            r"^(?:the\s+)?customer\s+(?:has\s+)?requested\s+",
            "",
            statement.strip(),
            flags=re.IGNORECASE,
        )
        value = re.sub(r"^requested material:\s*", "", value, flags=re.IGNORECASE)
        return value.rstrip(".")[:240] or statement[:240]

    @staticmethod
    def _date_at_utc(value: str | None) -> datetime | None:
        if value is None:
            return None
        return datetime.combine(date.fromisoformat(value), time.min, tzinfo=UTC)

    @staticmethod
    def _email_body(content: FollowUpEmailArtifactContent) -> str:
        sections = [content.greeting, "", content.summary]
        if content.decisions:
            sections.extend(("", "Decisions", *[f"- {item}" for item in content.decisions]))
        if content.action_items:
            sections.extend(("", "Action items", *[f"- {item}" for item in content.action_items]))
        if content.open_questions:
            sections.extend(("", "Open questions", *[f"- {item}" for item in content.open_questions]))
        sections.extend(("", content.closing))
        return "\n".join(sections)

    @staticmethod
    def _deduplicate_candidates(candidates: list[ActionCandidate]) -> list[ActionCandidate]:
        selected: list[ActionCandidate] = []
        keys: set[tuple[str, str]] = set()
        for candidate in candidates:
            payload_json = json.dumps(
                candidate.payload.model_dump(mode="json", by_alias=True),
                sort_keys=True,
                separators=(",", ":"),
            )
            key = (candidate.action_type.value, payload_json.casefold())
            if key in keys:
                continue
            keys.add(key)
            selected.append(candidate)
        return selected

    @staticmethod
    def _require_payload_type(action_type: str, payload: ActionPayload) -> None:
        if payload.kind != action_type:
            raise PublicAPIError(
                "invalid_action_payload",
                "The edited payload must keep the original Action type.",
                422,
            )

    @staticmethod
    def _require_expected_version(proposal: ActionProposal, expected_version: int) -> None:
        if proposal.current_version != expected_version:
            raise PublicAPIError(
                "stale_action",
                "This Action changed after it was loaded. Refresh and try again.",
                409,
            )

    @staticmethod
    def _payload(raw: dict[str, object]) -> ActionPayload:
        try:
            return _PAYLOAD_ADAPTER.validate_python(raw, strict=False)
        except ValidationError as exc:
            raise PublicAPIError(
                "action_content_unavailable",
                "This Action has invalid stored content and cannot be reviewed.",
                409,
            ) from exc

    @staticmethod
    def _source_refs(raw: list[dict[str, object]]) -> list[ActionSourceReference]:
        values: list[ActionSourceReference] = []
        try:
            for item in raw:
                values.append(ActionSourceReference.model_validate(item, strict=False))
        except ValidationError as exc:
            raise PublicAPIError(
                "action_provenance_unavailable",
                "This Action has invalid provenance and cannot be reviewed.",
                409,
            ) from exc
        return values

    @staticmethod
    def _response(record: ActionRecord) -> ActionProposalResponse:
        proposal = record.proposal
        version = record.version
        payload = ActionService._payload(version.payload_json)
        send_ready = (
            isinstance(payload, FollowUpEmailPayload)
            and payload.recipient_contact_id is not None
            and payload.recipient_confirmed
        )
        return ActionProposalResponse(
            id=proposal.id,
            organisation_id=proposal.organisation_id,
            opportunity_id=proposal.opportunity_id,
            interaction_id=proposal.interaction_id,
            action_type=ActionType(proposal.action_type),
            status=ActionStatus(proposal.status),
            priority=ActionPriority(proposal.priority),
            audience=ActionAudience(proposal.audience),
            risk_class=ActionRiskClass(proposal.risk_class),
            current_version=proposal.current_version,
            approved_version=proposal.approved_version,
            title=version.title,
            description=version.description,
            proposed_due_at=version.proposed_due_at,
            target_entity_type=version.target_entity_type,
            target_entity_id=version.target_entity_id,
            proposed_payload=payload,
            source_refs=ActionService._source_refs(version.source_refs_json),
            provenance_summary=version.provenance_summary,
            generated_at=proposal.generated_at,
            version_created_at=version.created_at,
            created_by_user_id=proposal.created_by_user_id,
            reviewed_by_user_id=proposal.reviewed_by_user_id,
            reviewed_at=proposal.reviewed_at,
            approved_at=proposal.approved_at,
            rejected_at=proposal.rejected_at,
            rejection_reason_code=(
                ActionRejectionReason(proposal.rejection_reason_code)
                if proposal.rejection_reason_code is not None
                else None
            ),
            supersedes_action_id=proposal.supersedes_action_id,
            completed_by_user_id=proposal.completed_by_user_id,
            completed_at=proposal.completed_at,
            send_ready=send_ready,
        )

    @staticmethod
    def _log_context(
        proposal: ActionProposal,
        *,
        proposal_version: int | None = None,
    ) -> dict[str, object]:
        return {
            "organisation_id": str(proposal.organisation_id),
            "opportunity_id": str(proposal.opportunity_id),
            "interaction_id": str(proposal.interaction_id) if proposal.interaction_id else None,
            "action_id": str(proposal.id),
            "action_type": proposal.action_type,
            "status": proposal.status,
            "priority": proposal.priority,
            "proposal_version": proposal_version or proposal.current_version,
        }
