from __future__ import annotations

import hashlib
import json
import logging
import math
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.campaign_contracts import (
    CampaignAudienceItemResponse,
    CampaignConfirmedRequest,
    CampaignCreateRequest,
    CampaignDraftFields,
    CampaignEnrollmentListResponse,
    CampaignEnrollmentResponse,
    CampaignEnrollmentStepResponse,
    CampaignLaunchRequest,
    CampaignListItemResponse,
    CampaignListResponse,
    CampaignMetricsResponse,
    CampaignOutcomeRequest,
    CampaignResponse,
    CampaignSequenceStepResponse,
    CampaignUpdateRequest,
)
from revenueos.campaign_repositories import CampaignRecord, CampaignRepository
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.domain import (
    CampaignApprovalMode,
    CampaignEnrollmentState,
    CampaignOutcome,
    CampaignState,
    CampaignStepState,
    SequenceStepObjective,
)
from revenueos.errors import PublicAPIError
from revenueos.models import (
    Contact,
    EngageCampaign,
    EngageCampaignAudience,
    EngageCampaignEnrollment,
    EngageCampaignVersion,
    EngageEnrollmentStep,
    EngageSequenceStep,
    EventCampaignLink,
    OutreachPolicy,
)
from revenueos.outreach_repositories import OutreachRepository
from revenueos.outreach_services import OutreachService, evaluate_contactability
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.campaigns")
_ACTIVE_ENROLLMENT_STATES = frozenset(("ready", "active", "paused", "needs_attention"))
_UNSENT_STEP_STATES = frozenset(("pending", "processing", "ready_for_review", "prepared", "queued", "deferred"))


class CampaignService:
    def __init__(self, session: AsyncSession, tenant: TenantContext, settings: Settings) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = CampaignRepository(session)
        self.outreach_repository = OutreachRepository(session)

    async def list_campaigns(self) -> CampaignListResponse:
        self._require_feature()
        items: list[CampaignListItemResponse] = []
        for record in await self.repository.campaigns(self.tenant.organisation_id):
            if not self.tenant.can_manage() and record.campaign.owner_user_id != self.tenant.user_id:
                continue
            audience = await self.repository.audience(self.tenant.organisation_id, record.version.id)
            items.append(
                CampaignListItemResponse(
                    id=record.campaign.id,
                    name=record.version.name,
                    purpose=record.version.purpose,
                    state=CampaignState(record.campaign.state),
                    approval_mode=CampaignApprovalMode(record.version.approval_mode),
                    owner_user_id=record.campaign.owner_user_id,
                    audience_count=len(audience),
                    eligible_count=sum(item.eligible for item in audience),
                    blocked_count=sum(not item.eligible for item in audience),
                    current_version=record.campaign.current_version,
                    launched_at=record.campaign.launched_at,
                    updated_at=record.campaign.updated_at,
                )
            )
        return CampaignListResponse(
            items=items,
            total=len(items),
            can_create=await self._entitled(),
            simulation_only=self.settings.environment != "production",
        )

    async def create(self, request: CampaignCreateRequest) -> CampaignResponse:
        await self._require_mutation_available()
        self._validate_draft_limits(request)
        now = datetime.now(UTC)
        campaign = EngageCampaign(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            owner_user_id=self.tenant.user_id,
            state=CampaignState.DRAFT.value,
            current_version=1,
            created_at=now,
            updated_at=now,
        )
        version = EngageCampaignVersion(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            campaign_id=campaign.id,
            version=1,
            status="draft",
            name=request.name,
            purpose=request.purpose,
            approval_mode=request.approval_mode.value,
            sender_user_id=self.tenant.user_id,
            source_type=request.source_type,
            sender_timezone=request.sender_timezone,
            send_days_json=sorted(request.send_days),
            send_window_start_minutes=request.send_window_start_minutes,
            send_window_end_minutes=request.send_window_end_minutes,
            stop_on_active_opportunity=request.stop_on_active_opportunity,
            audience_count=len(request.contact_ids),
            created_by_user_id=self.tenant.user_id,
            created_at=now,
        )
        self.repository.add(campaign)
        await self._flush("The campaign could not be created.")
        self.repository.add(version)
        await self._flush("The campaign version could not be created.")
        await self._replace_draft_children(campaign, version, request)
        await self._sync_event_link(campaign, request)
        campaign.state = CampaignState.READY.value
        await self._commit("The campaign could not be created.")
        logger.info(
            "campaign_created",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "campaign_id": str(campaign.id),
                "owner_user_id": str(self.tenant.user_id),
                "recipient_count": len(request.contact_ids),
                "step_count": len(request.steps),
                "approval_mode": request.approval_mode.value,
            },
        )
        return await self.get(campaign.id)

    async def update(self, campaign_id: UUID, request: CampaignUpdateRequest) -> CampaignResponse:
        await self._require_mutation_available()
        self._validate_draft_limits(request)
        record = await self._campaign(campaign_id, for_update=True)
        self._require_owner(record)
        if record.campaign.state not in {CampaignState.DRAFT.value, CampaignState.READY.value}:
            raise PublicAPIError("campaign_immutable", "A launched campaign cannot be edited. Stop and clone it.", 409)
        if record.campaign.current_version != request.expected_version:
            raise PublicAPIError("campaign_stale", "This campaign changed after it was loaded.", 409)
        version = record.version
        version.name = request.name
        version.purpose = request.purpose
        version.approval_mode = request.approval_mode.value
        version.source_type = request.source_type
        version.sender_timezone = request.sender_timezone
        version.send_days_json = sorted(request.send_days)
        version.send_window_start_minutes = request.send_window_start_minutes
        version.send_window_end_minutes = request.send_window_end_minutes
        version.stop_on_active_opportunity = request.stop_on_active_opportunity
        version.audience_count = len(request.contact_ids)
        await self.repository.delete_draft_children(self.tenant.organisation_id, version.id)
        await self._flush("The previous campaign draft could not be replaced.")
        await self._replace_draft_children(record.campaign, version, request)
        await self._sync_event_link(record.campaign, request)
        record.campaign.state = CampaignState.READY.value
        record.campaign.updated_at = datetime.now(UTC)
        await self._commit("The campaign draft could not be updated.")
        logger.info(
            "campaign_draft_updated",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "campaign_id": str(campaign_id),
                "version": record.campaign.current_version,
                "recipient_count": len(request.contact_ids),
                "step_count": len(request.steps),
            },
        )
        return await self.get(campaign_id)

    async def get(self, campaign_id: UUID) -> CampaignResponse:
        self._require_feature()
        record = await self._campaign(campaign_id)
        self._require_view(record)
        return await self._response(record)

    async def launch(self, campaign_id: UUID, request: CampaignLaunchRequest) -> CampaignResponse:
        await self._require_mutation_available()
        record = await self._campaign(campaign_id, for_update=True)
        self._require_owner(record)
        campaign, version = record.campaign, record.version
        if campaign.state == CampaignState.ACTIVE.value and version.status == "published":
            return await self._response(record)
        if campaign.state not in {CampaignState.DRAFT.value, CampaignState.READY.value} or version.status != "draft":
            raise PublicAPIError("campaign_not_launchable", "Only a reviewed draft campaign can be launched.", 409)
        if campaign.current_version != request.expected_version:
            raise PublicAPIError("campaign_stale", "This campaign changed after it was loaded.", 409)
        policy = await self.outreach_repository.policy(self.tenant.organisation_id, for_update=True)
        if policy is None or not policy.configured or not policy.outbound_enabled:
            raise PublicAPIError(
                "campaign_policy_unavailable", "Configure and enable Engage outreach before launch.", 409
            )
        if version.approval_mode == CampaignApprovalMode.APPROVED_CAMPAIGN_AUTO_SEND.value:
            if not policy.campaign_auto_send_allowed:
                raise PublicAPIError(
                    "campaign_auto_send_not_allowed",
                    "An administrator has not enabled bounded campaign auto-send.",
                    409,
                )
            if not request.auto_send_confirmed:
                raise PublicAPIError(
                    "campaign_auto_send_confirmation_required",
                    "Confirm that future validated sequence steps may be sent automatically.",
                    409,
                )
        connection = await self.repository.active_email_connection_for_user(
            self.tenant.organisation_id, version.sender_user_id
        )
        if self.settings.environment == "production" or connection is None:
            raise PublicAPIError(
                "campaign_mailbox_unavailable",
                "Campaign launch is unavailable until the sender has a supported production mailbox connection.",
                409,
            )
        owner_count, organisation_count = await self.repository.active_campaign_counts(
            self.tenant.organisation_id, campaign.owner_user_id
        )
        if owner_count >= self.settings.private_beta_max_active_campaigns_per_user:
            raise PublicAPIError("campaign_owner_limit", "The sender already has five active campaigns.", 409)
        if organisation_count >= self.settings.private_beta_max_active_campaigns_per_organisation:
            raise PublicAPIError("campaign_org_limit", "The organisation already has ten active campaigns.", 409)
        steps = await self.repository.steps(self.tenant.organisation_id, version.id)
        self._validate_step_policy(steps, policy)
        audience = await self._refresh_audience(campaign, version)
        eligible = [item for item in audience if item.eligible and item.contact_id is not None]
        if not eligible:
            raise PublicAPIError(
                "campaign_audience_empty", "No selected Contacts are currently eligible for launch.", 409
            )
        now = datetime.now(UTC)
        policy_fingerprint = self._policy_fingerprint(policy)
        launch_fingerprint = self._launch_fingerprint(version, steps, audience, policy_fingerprint)
        version.status = "published"
        version.policy_version = policy.version
        version.policy_fingerprint = policy_fingerprint
        version.launch_fingerprint = launch_fingerprint
        version.audience_count = len(audience)
        version.approved_by_user_id = self.tenant.user_id
        version.approved_at = now
        version.auto_send_confirmed_at = (
            now if version.approval_mode == CampaignApprovalMode.APPROVED_CAMPAIGN_AUTO_SEND.value else None
        )
        campaign.state = CampaignState.ACTIVE.value
        campaign.launched_at = now
        campaign.updated_at = now
        first_step = steps[0]
        for index, item in enumerate(eligible):
            assert item.contact_id is not None and item.recipient_email is not None
            contact = await self.outreach_repository.contact(self.tenant.organisation_id, item.contact_id)
            assert contact is not None
            scheduled = self._next_send_time(
                now + timedelta(minutes=index * self.settings.campaign_recipient_spacing_minutes), version
            )
            enrollment = EngageCampaignEnrollment(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                campaign_id=campaign.id,
                campaign_version_id=version.id,
                contact_id=contact.id,
                company_id=contact.company_id,
                sender_user_id=version.sender_user_id,
                recipient_name=item.recipient_name,
                recipient_email=item.recipient_email,
                recipient_trust=item.recipient_trust,
                job_title_snapshot=contact.job_title,
                state=CampaignEnrollmentState.ACTIVE.value,
                current_step_order=1,
                next_scheduled_at=scheduled,
                used_source_ids_json=[],
                created_by_user_id=self.tenant.user_id,
                created_at=now,
                updated_at=now,
            )
            self.repository.add(enrollment)
            await self._flush("A campaign Contact could not be enrolled.")
            self.repository.add(
                EngageEnrollmentStep(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    enrollment_id=enrollment.id,
                    sequence_step_id=first_step.id,
                    scheduled_at=scheduled,
                    prepare_at=max(now, scheduled - timedelta(hours=self.settings.campaign_draft_preparation_hours)),
                    state=CampaignStepState.PENDING.value,
                    attempt_count=0,
                    created_at=now,
                    updated_at=now,
                )
            )
        await self._commit("The campaign could not be launched.")
        logger.info(
            "campaign_launched",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "campaign_id": str(campaign.id),
                "version": version.version,
                "eligible_recipient_count": len(eligible),
                "blocked_recipient_count": len(audience) - len(eligible),
                "step_count": len(steps),
                "approval_mode": version.approval_mode,
                "simulation_only": True,
            },
        )
        return await self.get(campaign.id)

    async def pause(self, campaign_id: UUID, request: CampaignConfirmedRequest) -> CampaignResponse:
        del request
        await self._require_mutation_available()
        record = await self._campaign(campaign_id, for_update=True)
        self._require_manage(record)
        if record.campaign.state == CampaignState.PAUSED.value:
            return await self._response(record)
        if record.campaign.state not in {CampaignState.ACTIVE.value, CampaignState.NEEDS_ATTENTION.value}:
            raise PublicAPIError("campaign_not_active", "Only an active campaign can be paused.", 409)
        now = datetime.now(UTC)
        record.campaign.state = CampaignState.PAUSED.value
        record.campaign.paused_at = now
        record.campaign.updated_at = now
        for enrollment in await self.repository.enrollments(self.tenant.organisation_id, campaign_id):
            if enrollment.state in {"ready", "active", "needs_attention"}:
                enrollment.state = CampaignEnrollmentState.PAUSED.value
                enrollment.updated_at = now
        await self._commit("The campaign could not be paused.")
        logger.info("campaign_paused", extra=self._log_context(campaign_id))
        return await self.get(campaign_id)

    async def resume(self, campaign_id: UUID, request: CampaignConfirmedRequest) -> CampaignResponse:
        del request
        await self._require_mutation_available()
        record = await self._campaign(campaign_id, for_update=True)
        self._require_manage(record)
        if record.campaign.state == CampaignState.ACTIVE.value:
            return await self._response(record)
        if record.campaign.state != CampaignState.PAUSED.value:
            raise PublicAPIError("campaign_not_paused", "Only a paused campaign can be resumed.", 409)
        now = datetime.now(UTC)
        record.campaign.state = CampaignState.ACTIVE.value
        record.campaign.paused_at = None
        record.campaign.updated_at = now
        spacing_index = 0
        for enrollment in await self.repository.enrollments(self.tenant.organisation_id, campaign_id):
            if enrollment.state != CampaignEnrollmentState.PAUSED.value:
                continue
            enrollment.state = CampaignEnrollmentState.ACTIVE.value
            enrollment.updated_at = now
            for step, _, _ in await self.repository.enrollment_steps(self.tenant.organisation_id, enrollment.id):
                if step.state in _UNSENT_STEP_STATES and self._as_utc(step.scheduled_at) <= now:
                    scheduled = self._next_send_time(
                        now + timedelta(minutes=spacing_index * self.settings.campaign_recipient_spacing_minutes),
                        record.version,
                    )
                    step.scheduled_at = scheduled
                    step.prepare_at = max(
                        now, scheduled - timedelta(hours=self.settings.campaign_draft_preparation_hours)
                    )
                    step.state = (
                        CampaignStepState.PENDING.value
                        if step.outreach_message_id is None
                        else CampaignStepState.PREPARED.value
                    )
                    step.safe_status_code = "rescheduled_after_pause"
                    step.updated_at = now
                    enrollment.next_scheduled_at = scheduled
                    spacing_index += 1
        await self._commit("The campaign could not be resumed.")
        logger.info("campaign_resumed", extra=self._log_context(campaign_id))
        return await self.get(campaign_id)

    async def stop(self, campaign_id: UUID, request: CampaignConfirmedRequest) -> CampaignResponse:
        del request
        await self._require_mutation_available()
        record = await self._campaign(campaign_id, for_update=True)
        self._require_manage(record)
        if record.campaign.state == CampaignState.STOPPED.value:
            return await self._response(record)
        if record.campaign.state in {CampaignState.COMPLETED.value, CampaignState.DRAFT.value}:
            raise PublicAPIError("campaign_not_stoppable", "This campaign cannot be stopped in its current state.", 409)
        now = datetime.now(UTC)
        record.campaign.state = CampaignState.STOPPED.value
        record.campaign.stopped_at = now
        record.campaign.updated_at = now
        for enrollment in await self.repository.enrollments(self.tenant.organisation_id, campaign_id):
            if enrollment.state in _ACTIVE_ENROLLMENT_STATES:
                enrollment.state = CampaignEnrollmentState.STOPPED.value
                enrollment.stop_reason = "campaign_stopped"
                enrollment.next_scheduled_at = None
                enrollment.updated_at = now
            await self._cancel_unsent_steps(enrollment.id, "campaign_stopped", now)
        await self._commit("The campaign could not be stopped.")
        logger.info("campaign_stopped", extra=self._log_context(campaign_id))
        return await self.get(campaign_id)

    async def list_enrollments(self, campaign_id: UUID) -> CampaignEnrollmentListResponse:
        record = await self._campaign(campaign_id)
        self._require_view(record)
        items = [
            await self._enrollment_response(item)
            for item in await self.repository.enrollments(self.tenant.organisation_id, campaign_id)
        ]
        return CampaignEnrollmentListResponse(items=items, total=len(items))

    async def get_enrollment(self, enrollment_id: UUID) -> CampaignEnrollmentResponse:
        enrollment = await self._enrollment(enrollment_id)
        record = await self._campaign(enrollment.campaign_id)
        self._require_view(record)
        return await self._enrollment_response(enrollment)

    async def stop_enrollment(
        self, enrollment_id: UUID, request: CampaignConfirmedRequest
    ) -> CampaignEnrollmentResponse:
        del request
        await self._require_mutation_available()
        enrollment = await self._enrollment(enrollment_id, for_update=True)
        record = await self._campaign(enrollment.campaign_id)
        self._require_manage(record)
        if enrollment.state in {"completed", "stopped", "blocked"}:
            return await self._enrollment_response(enrollment)
        now = datetime.now(UTC)
        enrollment.state = CampaignEnrollmentState.STOPPED.value
        enrollment.stop_reason = "removed_by_user"
        enrollment.next_scheduled_at = None
        enrollment.updated_at = now
        await self._cancel_unsent_steps(enrollment.id, "removed_by_user", now)
        await self._commit("The campaign recipient could not be stopped.")
        logger.info(
            "campaign_enrollment_stopped",
            extra={**self._log_context(enrollment.campaign_id), "enrollment_id": str(enrollment.id)},
        )
        return await self._enrollment_response(enrollment)

    async def report_outcome(self, enrollment_id: UUID, request: CampaignOutcomeRequest) -> CampaignEnrollmentResponse:
        await self._require_mutation_available()
        enrollment = await self._enrollment(enrollment_id, for_update=True)
        record = await self._campaign(enrollment.campaign_id)
        self._require_manage(record)
        now = datetime.now(UTC)
        enrollment.state = CampaignEnrollmentState.STOPPED.value
        enrollment.stop_reason = f"seller_reported_{request.outcome.value}"
        enrollment.outcome = request.outcome.value
        enrollment.outcome_provenance = "seller_reported"
        enrollment.outcome_reported_by_user_id = self.tenant.user_id
        enrollment.outcome_reported_at = now
        enrollment.next_scheduled_at = None
        enrollment.updated_at = now
        await self._cancel_unsent_steps(enrollment.id, enrollment.stop_reason, now)
        await self._commit("The seller-reported campaign outcome could not be saved.")
        logger.info(
            "campaign_outcome_reported",
            extra={
                **self._log_context(enrollment.campaign_id),
                "enrollment_id": str(enrollment.id),
                "outcome": request.outcome.value,
                "provenance": "seller_reported",
            },
        )
        return await self._enrollment_response(enrollment)

    async def _replace_draft_children(
        self,
        campaign: EngageCampaign,
        version: EngageCampaignVersion,
        request: CampaignDraftFields,
    ) -> None:
        policy = await self.outreach_repository.policy(self.tenant.organisation_id)
        if policy is not None:
            self._validate_requested_step_policy(request, policy)
        for index, item in enumerate(request.steps, start=1):
            self.repository.add(
                EngageSequenceStep(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    campaign_version_id=version.id,
                    step_order=index,
                    delay_days=item.delay_days,
                    objective=item.objective.value,
                    content_strategy=item.content_strategy,
                    enabled=item.enabled,
                    created_at=datetime.now(UTC),
                )
            )
        await self._flush("The campaign sequence could not be saved.")
        contacts = await self.repository.contacts(self.tenant.organisation_id, request.contact_ids)
        if len(contacts) != len(request.contact_ids):
            raise PublicAPIError("contact_not_found", "One or more selected Contacts were not found.", 404)
        if request.source_type == "event_attendees":
            if request.event_id is None or not await self.repository.event_accepts_contacts(
                self.tenant.organisation_id, request.event_id, request.contact_ids
            ):
                raise PublicAPIError(
                    "event_audience_invalid",
                    "Every Event campaign recipient must be a canonical Contact linked to that Event.",
                    422,
                )
        contact_map = {item.id: item for item in contacts}
        for contact_id in request.contact_ids:
            contact = contact_map[contact_id]
            eligibility = await self._eligibility(contact, campaign, version)
            self.repository.add(
                EngageCampaignAudience(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    campaign_version_id=version.id,
                    contact_id=contact.id,
                    company_id=contact.company_id,
                    recipient_name=f"{contact.first_name} {contact.last_name}",
                    recipient_email=contact.email,
                    recipient_trust=eligibility[2],
                    eligible=eligibility[0],
                    eligibility_code=eligibility[1],
                    eligibility_reason=eligibility[3],
                    created_at=datetime.now(UTC),
                )
            )
        await self._flush("The campaign audience could not be saved.")

    async def _sync_event_link(self, campaign: EngageCampaign, request: CampaignDraftFields) -> None:
        await self.repository.delete_event_campaign_link(self.tenant.organisation_id, campaign.id)
        if request.source_type != "event_attendees":
            return
        if request.event_id is None or request.event_stage is None:
            raise PublicAPIError("event_context_required", "Event campaign context is required.", 422)
        self.repository.add(
            EventCampaignLink(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                event_id=request.event_id,
                campaign_id=campaign.id,
                stage=request.event_stage,
                created_by_user_id=self.tenant.user_id,
                created_at=datetime.now(UTC),
            )
        )
        await self._flush("The Event campaign link could not be saved.")

    async def _refresh_audience(
        self, campaign: EngageCampaign, version: EngageCampaignVersion
    ) -> list[EngageCampaignAudience]:
        audience = await self.repository.audience(self.tenant.organisation_id, version.id)
        for item in audience:
            if item.contact_id is None:
                item.eligible = False
                item.eligibility_code = "contact_deleted"
                item.eligibility_reason = "The selected Contact was deleted."
                continue
            contact = await self.outreach_repository.contact(self.tenant.organisation_id, item.contact_id)
            if contact is None:
                item.eligible = False
                item.eligibility_code = "contact_deleted"
                item.eligibility_reason = "The selected Contact was deleted."
                continue
            eligible, code, trust, reason = await self._eligibility(contact, campaign, version)
            item.recipient_name = f"{contact.first_name} {contact.last_name}"
            item.recipient_email = contact.email
            item.recipient_trust = trust
            item.eligible = eligible
            item.eligibility_code = code
            item.eligibility_reason = reason
        await self._flush("The campaign audience could not be revalidated.")
        return audience

    async def _eligibility(
        self, contact: Contact, campaign: EngageCampaign, version: EngageCampaignVersion
    ) -> tuple[bool, str, Literal["verified", "provider_supplied", "unknown"], str]:
        result = await evaluate_contactability(
            self.outreach_repository,
            self.tenant,
            self.settings,
            contact,
            sender_user_id=version.sender_user_id,
            check_frequency_limits=False,
        )
        if not result.allowed:
            return False, result.state.value, result.trust_state, result.reason
        if version.stop_on_active_opportunity and await self.outreach_repository.has_active_opportunity(
            self.tenant.organisation_id, contact.company_id
        ):
            return (
                False,
                "active_opportunity",
                result.trust_state,
                "This Contact's Account has an active Opportunity, so cold prospecting is blocked.",
            )
        if await self.repository.active_campaign_collision(
            self.tenant.organisation_id, contact.id, excluding_campaign_id=campaign.id
        ):
            return (
                False,
                "active_campaign_collision",
                result.trust_state,
                "This Contact is already enrolled in another active prospecting campaign.",
            )
        return True, "ready", result.trust_state, "Ready under current Contact, suppression and outreach policy."

    async def _response(self, record: CampaignRecord) -> CampaignResponse:
        campaign, version = record.campaign, record.version
        steps = await self.repository.steps(self.tenant.organisation_id, version.id)
        audience = await self.repository.audience(self.tenant.organisation_id, version.id)
        policy = await self.outreach_repository.policy(self.tenant.organisation_id)
        metrics = await self.repository.campaign_counts(self.tenant.organisation_id, campaign.id)
        can_manage = self.tenant.can_manage() or campaign.owner_user_id == self.tenant.user_id
        auto = version.approval_mode == CampaignApprovalMode.APPROVED_CAMPAIGN_AUTO_SEND.value
        event_link = await self.repository.event_campaign_link(self.tenant.organisation_id, campaign.id)
        return CampaignResponse(
            id=campaign.id,
            version_id=version.id,
            version=version.version,
            name=version.name,
            purpose=version.purpose,
            state=CampaignState(campaign.state),
            approval_mode=CampaignApprovalMode(version.approval_mode),
            owner_user_id=campaign.owner_user_id,
            sender_user_id=version.sender_user_id,
            source_type=cast(Literal["manual_contacts", "target_market", "event_attendees"], version.source_type),
            event_id=event_link.event_id if event_link is not None else None,
            event_stage=(
                cast(Literal["pre_event", "post_event"], event_link.stage) if event_link is not None else None
            ),
            sender_timezone=version.sender_timezone,
            send_days=list(version.send_days_json),
            send_window_start_minutes=version.send_window_start_minutes,
            send_window_end_minutes=version.send_window_end_minutes,
            stop_on_active_opportunity=version.stop_on_active_opportunity,
            policy_version=version.policy_version,
            audience_count=len(audience),
            eligible_count=sum(item.eligible for item in audience),
            blocked_count=sum(not item.eligible for item in audience),
            steps=[
                CampaignSequenceStepResponse(
                    id=item.id,
                    step_order=item.step_order,
                    delay_days=item.delay_days,
                    objective=SequenceStepObjective(item.objective),
                    content_strategy=item.content_strategy,
                    enabled=item.enabled,
                )
                for item in steps
            ],
            audience=[
                CampaignAudienceItemResponse(
                    id=item.id,
                    contact_id=item.contact_id,
                    company_id=item.company_id,
                    recipient_name=item.recipient_name,
                    recipient_email=item.recipient_email,
                    recipient_trust=cast(Literal["verified", "provider_supplied", "unknown"], item.recipient_trust),
                    eligible=item.eligible,
                    eligibility_code=item.eligibility_code,
                    eligibility_reason=item.eligibility_reason,
                )
                for item in audience
            ],
            metrics=CampaignMetricsResponse(**metrics),
            can_manage=can_manage,
            can_launch=(
                can_manage
                and campaign.state in {CampaignState.DRAFT.value, CampaignState.READY.value}
                and version.status == "draft"
                and any(item.eligible for item in audience)
            ),
            campaign_auto_send_allowed=bool(policy and policy.campaign_auto_send_allowed),
            simulation_only=self.settings.environment != "production",
            launch_warning=(
                "RevenueOS will prepare and simulate future approved sequence steps automatically when all safety checks pass."
                if auto
                else None
            ),
            needs_attention_reason=campaign.needs_attention_reason,
            launched_at=campaign.launched_at,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
        )

    async def _enrollment_response(self, enrollment: EngageCampaignEnrollment) -> CampaignEnrollmentResponse:
        rows = await self.repository.enrollment_steps(self.tenant.organisation_id, enrollment.id)
        current_outreach = None
        current_message_id = next(
            (
                step.outreach_message_id
                for step, sequence, _ in rows
                if sequence.step_order == enrollment.current_step_order and step.outreach_message_id is not None
            ),
            None,
        )
        if current_message_id is not None:
            outreach = OutreachService(self.session, self.tenant, self.settings)
            outreach_record = await outreach._message(current_message_id)
            current_outreach = await outreach._response(outreach_record)
        return CampaignEnrollmentResponse(
            id=enrollment.id,
            campaign_id=enrollment.campaign_id,
            contact_id=enrollment.contact_id,
            company_id=enrollment.company_id,
            recipient_name=enrollment.recipient_name,
            recipient_email=enrollment.recipient_email,
            recipient_trust=cast(Literal["verified", "provider_supplied"], enrollment.recipient_trust),
            state=CampaignEnrollmentState(enrollment.state),
            current_step_order=enrollment.current_step_order,
            next_scheduled_at=enrollment.next_scheduled_at,
            stop_reason=enrollment.stop_reason,
            outcome=CampaignOutcome(enrollment.outcome) if enrollment.outcome else None,
            outcome_provenance=cast(Literal["seller_reported"] | None, enrollment.outcome_provenance),
            steps=[
                CampaignEnrollmentStepResponse(
                    id=step.id,
                    step_order=sequence.step_order,
                    objective=SequenceStepObjective(sequence.objective),
                    scheduled_at=step.scheduled_at,
                    state=CampaignStepState(step.state),
                    safe_status_code=step.safe_status_code,
                    outreach_message_id=step.outreach_message_id,
                    prepared_at=step.prepared_at,
                    sent_at=step.sent_at,
                )
                for step, sequence, _ in rows
            ],
            current_outreach=current_outreach,
            created_at=enrollment.created_at,
            updated_at=enrollment.updated_at,
        )

    async def _cancel_unsent_steps(self, enrollment_id: UUID, reason: str, now: datetime) -> None:
        for step, _, _ in await self.repository.enrollment_steps(self.tenant.organisation_id, enrollment_id):
            if step.state in _UNSENT_STEP_STATES:
                step.state = CampaignStepState.CANCELLED.value
                step.safe_status_code = reason
                step.worker_id = None
                step.lease_expires_at = None
                step.updated_at = now

    def _validate_draft_limits(self, request: CampaignDraftFields) -> None:
        self._timezone(request.sender_timezone)
        if len(request.contact_ids) > self.settings.private_beta_max_campaign_recipients:
            raise PublicAPIError("campaign_recipient_limit", "A campaign may contain at most 50 Contacts.", 422)
        enabled_steps = [item for item in request.steps if item.enabled]
        if not enabled_steps or len(enabled_steps) > self.settings.private_beta_max_campaign_steps:
            raise PublicAPIError("campaign_step_limit", "A campaign must contain one to four enabled steps.", 422)

    @staticmethod
    def _validate_requested_step_policy(request: CampaignDraftFields, policy: OutreachPolicy) -> None:
        enabled = [item for item in request.steps if item.enabled]
        for step in enabled[1:]:
            if step.delay_days * 24 < policy.cooldown_hours:
                minimum_days = math.ceil(policy.cooldown_hours / 24)
                raise PublicAPIError(
                    "campaign_delay_below_cooldown",
                    f"Follow-up steps must wait at least {minimum_days} calendar days under organisation policy.",
                    422,
                )

    @staticmethod
    def _validate_step_policy(steps: list[EngageSequenceStep], policy: OutreachPolicy) -> None:
        if not steps or len(steps) > 4 or steps[0].delay_days != 0:
            raise PublicAPIError("campaign_sequence_invalid", "The campaign sequence is invalid.", 409)
        for step in steps[1:]:
            if step.delay_days * 24 < policy.cooldown_hours:
                raise PublicAPIError(
                    "campaign_delay_below_cooldown",
                    "A follow-up delay is shorter than the current organisation cooldown.",
                    409,
                )

    def _next_send_time(self, candidate: datetime, version: EngageCampaignVersion) -> datetime:
        zone = self._timezone(version.sender_timezone)
        allowed_days = set(version.send_days_json)
        local = self._as_utc(candidate).astimezone(zone)
        for day_offset in range(0, 15):
            local_date = local.date() + timedelta(days=day_offset)
            if local_date.isoweekday() not in allowed_days:
                continue
            start = self._local_datetime(local_date, version.send_window_start_minutes, zone)
            end = self._local_datetime(local_date, version.send_window_end_minutes, zone)
            if day_offset == 0 and local <= end:
                return max(local, start).astimezone(UTC)
            if day_offset > 0:
                return start.astimezone(UTC)
        raise PublicAPIError("campaign_send_window_invalid", "No valid send window could be calculated.", 409)

    @staticmethod
    def _local_datetime(local_date: date, minutes: int, zone: ZoneInfo) -> datetime:
        return datetime.combine(local_date, time(hour=minutes // 60, minute=minutes % 60), tzinfo=zone)

    @staticmethod
    def _timezone(value: str) -> ZoneInfo:
        try:
            return ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise PublicAPIError("campaign_timezone_invalid", "Choose a recognised sender timezone.", 422) from exc

    @staticmethod
    def _policy_fingerprint(policy: OutreachPolicy) -> str:
        return CampaignService._hash(
            {
                "version": policy.version,
                "outboundEnabled": policy.outbound_enabled,
                "providerSuppliedAllowed": policy.provider_supplied_email_allowed,
                "cooldownHours": policy.cooldown_hours,
                "maxDailySendsUser": policy.max_daily_sends_user,
                "maxDailySendsOrg": policy.max_daily_sends_org,
                "requireOptOut": policy.require_opt_out_mechanism,
                "campaignAutoSendAllowed": policy.campaign_auto_send_allowed,
                "offering": policy.offering_name,
                "value": policy.value_proposition,
                "cta": policy.approved_cta,
            }
        )

    @staticmethod
    def _launch_fingerprint(
        version: EngageCampaignVersion,
        steps: list[EngageSequenceStep],
        audience: list[EngageCampaignAudience],
        policy_fingerprint: str,
    ) -> str:
        return CampaignService._hash(
            {
                "campaignId": str(version.campaign_id),
                "version": version.version,
                "senderId": str(version.sender_user_id),
                "approvalMode": version.approval_mode,
                "timezone": version.sender_timezone,
                "sendDays": version.send_days_json,
                "window": [version.send_window_start_minutes, version.send_window_end_minutes],
                "stopOnActiveOpportunity": version.stop_on_active_opportunity,
                "steps": [[item.step_order, item.delay_days, item.objective, item.content_strategy] for item in steps],
                "audience": sorted(str(item.contact_id) for item in audience if item.contact_id is not None),
                "policyFingerprint": policy_fingerprint,
            }
        )

    @staticmethod
    def _hash(value: dict[str, object]) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest()

    async def _campaign(self, campaign_id: UUID, *, for_update: bool = False) -> CampaignRecord:
        record = await self.repository.campaign(self.tenant.organisation_id, campaign_id, for_update=for_update)
        if record is None:
            raise PublicAPIError("campaign_not_found", "The requested campaign was not found.", 404)
        return record

    async def _enrollment(self, enrollment_id: UUID, *, for_update: bool = False) -> EngageCampaignEnrollment:
        enrollment = await self.repository.enrollment(self.tenant.organisation_id, enrollment_id, for_update=for_update)
        if enrollment is None:
            raise PublicAPIError("campaign_enrollment_not_found", "The campaign recipient was not found.", 404)
        return enrollment

    def _require_view(self, record: CampaignRecord) -> None:
        if not self.tenant.can_manage() and record.campaign.owner_user_id != self.tenant.user_id:
            raise PublicAPIError("campaign_not_found", "The requested campaign was not found.", 404)

    def _require_owner(self, record: CampaignRecord) -> None:
        if record.campaign.owner_user_id != self.tenant.user_id:
            raise PublicAPIError("campaign_sender_required", "Only the sender can change or launch this campaign.", 403)

    def _require_manage(self, record: CampaignRecord) -> None:
        if not self.tenant.can_manage() and record.campaign.owner_user_id != self.tenant.user_id:
            raise PublicAPIError("forbidden", "You do not have permission to manage this campaign.", 403)

    async def _entitled(self) -> bool:
        entitlement = await self.outreach_repository.entitlement(self.tenant.organisation_id)
        return bool(
            self.settings.feature_engage_enabled
            and self.settings.feature_engage_campaigns_enabled
            and entitlement is not None
            and entitlement.enabled
        )

    def _require_feature(self) -> None:
        if not self.settings.feature_engage_campaigns_enabled:
            raise PublicAPIError("campaigns_unavailable", "Campaigns are unavailable in this environment.", 404)

    async def _require_mutation_available(self) -> None:
        self._require_feature()
        if not await self._entitled():
            raise PublicAPIError("engage_unavailable", "RevenueOS Engage is not enabled for this organisation.", 403)

    async def _commit(self, message: str) -> None:
        try:
            await self.repository.flush()
            await self.repository.commit()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError("campaign_conflict", message, 409) from exc

    async def _flush(self, message: str) -> None:
        try:
            await self.repository.flush()
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError("campaign_conflict", message, 409) from exc

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    def _log_context(self, campaign_id: UUID) -> dict[str, object]:
        return {
            "organisation_id": str(self.tenant.organisation_id),
            "campaign_id": str(campaign_id),
            "actor_user_id": str(self.tenant.user_id),
        }
