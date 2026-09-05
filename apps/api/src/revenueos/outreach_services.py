from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.action_contracts import PersonalizedOutreachPayload
from revenueos.action_repositories import ActionRecord
from revenueos.commercial_services import CommercialService
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.domain import (
    ActionAudience,
    ActionPriority,
    ActionRiskClass,
    ActionStatus,
    ActionType,
    OutreachContactability,
    OutreachPurpose,
    OutreachState,
    ProspectTrustState,
    SuppressionReason,
)
from revenueos.errors import PublicAPIError
from revenueos.models import (
    ActionAuditEvent,
    ActionExecution,
    ActionProposal,
    ActionProposalVersion,
    Contact,
    ContactSuppression,
    EngageCampaign,
    EngageCampaignEnrollment,
    EngageEnrollmentStep,
    OutreachMessage,
    OutreachPersonalizationSource,
    OutreachPolicy,
    OutreachVersion,
    ProspectResearchObservation,
    ProspectResearchSource,
    User,
)
from revenueos.outreach_contracts import (
    ContactabilityResponse,
    ContactOutreachWorkspaceResponse,
    ContactSuppressionRequest,
    ContactSuppressionResponse,
    EngageAvailabilityResponse,
    EngageEntitlementUpdate,
    OutreachApproveRequest,
    OutreachCreateRequest,
    OutreachEditRequest,
    OutreachExecutionSummary,
    OutreachHistoryItem,
    OutreachPolicyResponse,
    OutreachPolicyUpdate,
    OutreachResponse,
    OutreachSourceResponse,
    OutreachVersionResponse,
)
from revenueos.outreach_repositories import OutreachRecord, OutreachRepository
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.outreach")
_ZERO_UUID = UUID(int=0)
_USABLE_TRUST = frozenset((ProspectTrustState.VERIFIED.value, ProspectTrustState.PROVIDER_SUPPLIED.value))
_COMPANY_CATEGORIES = frozenset(
    (
        "strategic_initiative",
        "expansion",
        "hiring",
        "leadership_change",
        "technology",
        "regulatory",
        "partnership",
        "trigger",
    )
)
_PERSON_CATEGORIES = frozenset(
    (
        "current_role",
        "responsibility",
        "expertise",
        "professional_activity",
        "public_statement",
        "authored_content",
        "conference_activity",
    )
)
_SENSITIVE_TERMS = re.compile(
    r"\b(religion|religious|politic(?:s|al)|health|medical|disability|sexuality|ethnicity|"
    r"family|children|kids|home|personal travel|vacation|personality|risk[- ]averse|vulnerability)\b",
    re.IGNORECASE,
)
_PROHIBITED_COPY = re.compile(
    r"\b(i(?:'|’)ve been following your work|mutual (?:friend|connection)|last chance|"
    r"final notice|given your personality|you (?:probably|must) fear|save \d+%|"
    r"reduce costs? by \d+%|i (?:saw|read) your (?:recent )?(?:post|article)|"
    r"great (?:speaking|meeting) with you|following up on our (?:conversation|meeting)|"
    r"congratulations on (?:your|the) recent (?:acquisition|funding|promotion|launch|expansion))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ContactabilityResult:
    state: OutreachContactability
    reason: str
    trust_state: Literal["verified", "provider_supplied", "unknown"]

    @property
    def allowed(self) -> bool:
        return self.state is OutreachContactability.ALLOWED

    def response(self) -> ContactabilityResponse:
        return ContactabilityResponse(
            state=self.state,
            allowed=self.allowed,
            reason=self.reason,
            trust_state=self.trust_state,
        )


@dataclass(frozen=True)
class SelectedSource:
    observation: ProspectResearchObservation
    source: ProspectResearchSource
    scope: Literal["company", "person"]


@dataclass(frozen=True)
class CampaignOutreachContext:
    step_instance_id: UUID
    objective: str
    content_strategy: str
    step_order: int
    total_steps: int
    previous_sent_at: datetime | None
    excluded_source_ids: frozenset[UUID]


@dataclass(frozen=True)
class AdditionalOutreachSource:
    source_type: Literal["event_attendance", "event_encounter"]
    source_id: UUID
    label: str
    trust_state: Literal["provider_supplied", "seller_reported"]


def _normalise_address(value: str) -> str:
    return value.strip().casefold()


def _contact_value_fingerprint(value: str) -> str:
    return hashlib.sha256(_normalise_address(value).encode()).hexdigest()


def suppression_fingerprint(settings: Settings, value: str) -> str:
    return hmac.new(
        settings.outreach_suppression_hmac_key.get_secret_value().encode(),
        _normalise_address(value).encode(),
        hashlib.sha256,
    ).hexdigest()


def _policy_snapshot_is_current(policy: OutreachPolicy | None, version: OutreachVersion) -> bool:
    return bool(
        policy
        and policy.configured
        and policy.offering_name == version.offering_name
        and policy.value_proposition == version.value_proposition
        and policy.approved_cta == version.approved_cta
    )


async def evaluate_contactability(
    repository: OutreachRepository,
    tenant: TenantContext,
    settings: Settings,
    contact: Contact,
    *,
    action_id: UUID | None = None,
    sender_user_id: UUID | None = None,
    check_frequency_limits: bool = True,
) -> ContactabilityResult:
    access = await CommercialService(repository.session, settings).module_access(tenant.organisation_id, "engage")
    if not settings.feature_engage_enabled or access != "write":
        return ContactabilityResult(
            OutreachContactability.ENGAGE_UNAVAILABLE,
            "RevenueOS Engage is not enabled for this organisation.",
            "unknown",
        )
    sender_id = sender_user_id or tenant.user_id
    membership = await repository.active_membership(tenant.organisation_id, sender_id)
    sender = await repository.user(sender_id)
    if membership is None or sender is None or sender.status != "active":
        return ContactabilityResult(
            OutreachContactability.SENDER_DISABLED,
            "The sender no longer has active organisation access.",
            "unknown",
        )
    if contact.email is None:
        return ContactabilityResult(
            OutreachContactability.NO_BUSINESS_EMAIL,
            "This Contact does not have a supported business email address.",
            "unknown",
        )
    field_source = await repository.email_source(
        tenant.organisation_id,
        contact.id,
        _contact_value_fingerprint(contact.email),
    )
    trust: Literal["verified", "provider_supplied", "unknown"] = (
        cast(Literal["verified", "provider_supplied"], field_source.trust_state)
        if field_source is not None and field_source.trust_state in _USABLE_TRUST
        else "unknown"
    )
    if trust == "unknown":
        return ContactabilityResult(
            OutreachContactability.EMAIL_TRUST_UNKNOWN,
            "The exact Contact email does not have a sendable business-contact trust state.",
            trust,
        )
    suppression = await repository.suppression(
        tenant.organisation_id,
        suppression_fingerprint(settings, contact.email),
    )
    if suppression is not None and suppression.active:
        labels = {
            "manual_do_not_contact": "This Contact is marked Do not contact.",
            "recipient_opt_out": "This recipient opted out of outreach.",
            "complaint": "This address is suppressed after a complaint.",
            "permanent_bounce": "This address is suppressed after a permanent bounce.",
        }
        return ContactabilityResult(
            OutreachContactability.SUPPRESSED,
            labels.get(suppression.reason, "This Contact is suppressed."),
            trust,
        )
    policy = await repository.policy(tenant.organisation_id)
    if policy is None or not policy.configured:
        return ContactabilityResult(
            OutreachContactability.POLICY_NOT_CONFIGURED,
            "An administrator must configure the Engage sending policy before email can be sent.",
            trust,
        )
    if not policy.outbound_enabled:
        return ContactabilityResult(
            OutreachContactability.OUTBOUND_DISABLED,
            "Outbound email is disabled by organisation policy.",
            trust,
        )
    if trust == "provider_supplied" and not policy.provider_supplied_email_allowed:
        return ContactabilityResult(
            OutreachContactability.PROVIDER_SUPPLIED_BLOCKED,
            "Organisation policy allows only verified business email addresses.",
            trust,
        )
    if check_frequency_limits:
        excluded_action_id = action_id or _ZERO_UUID
        if policy.cooldown_hours > 0 and await repository.successful_contact_send_since(
            tenant.organisation_id,
            contact.id,
            datetime.now(UTC) - timedelta(hours=policy.cooldown_hours),
            excluding_action_id=excluded_action_id,
        ):
            return ContactabilityResult(
                OutreachContactability.COOLDOWN,
                f"This Contact is within the organisation's {policy.cooldown_hours}-hour outreach cooldown.",
                trust,
            )
        start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
        user_count, org_count = await repository.send_counts_since(
            tenant.organisation_id,
            sender_id,
            start,
            excluding_action_id=excluded_action_id,
        )
        if user_count >= min(policy.max_daily_sends_user, settings.private_beta_max_outreach_per_user_per_day):
            return ContactabilityResult(
                OutreachContactability.QUOTA_REACHED,
                "The sender's one-to-one outreach limit has been reached for today.",
                trust,
            )
        if org_count >= min(policy.max_daily_sends_org, settings.private_beta_max_outreach_per_organisation_per_day):
            return ContactabilityResult(
                OutreachContactability.QUOTA_REACHED,
                "The organisation's one-to-one outreach limit has been reached for today.",
                trust,
            )
    if policy.require_opt_out_mechanism:
        return ContactabilityResult(
            OutreachContactability.POLICY_NOT_CONFIGURED,
            "This policy requires an opt-out mechanism; production mailbox sending is not yet available.",
            trust,
        )
    return ContactabilityResult(
        OutreachContactability.ALLOWED,
        "Allowed under the configured organisation policy. Address trust does not itself establish permission.",
        trust,
    )


async def validate_personalized_outreach_action(
    session: AsyncSession,
    tenant: TenantContext,
    settings: Settings,
    action_record: ActionRecord,
) -> OutreachRecord:
    repository = OutreachRepository(session)
    record = await repository.message_by_action(tenant.organisation_id, action_record.proposal.id)
    if record is None:
        raise PublicAPIError("outreach_not_found", "The approved outreach message is unavailable.", 409)
    message, version = record.message, record.version
    if (
        message.state != OutreachState.APPROVED.value
        or message.approved_version is None
        or message.approved_version != message.current_version
        or version.version != message.approved_version
        or action_record.proposal.approved_version != action_record.proposal.current_version
    ):
        raise PublicAPIError("outreach_not_approved", "Approve the current outreach version before sending.", 409)
    if message.contact_id is None:
        raise PublicAPIError("outreach_contact_unavailable", "The outreach Contact is no longer available.", 409)
    if message.sender_user_id != tenant.user_id:
        raise PublicAPIError("outreach_sender_mismatch", "Only the message sender can send this outreach.", 403)
    contact = await repository.contact(tenant.organisation_id, message.contact_id)
    sender = await repository.user(message.sender_user_id)
    if contact is None or sender is None:
        raise PublicAPIError("outreach_target_stale", "The outreach sender or recipient is unavailable.", 409)
    if (
        contact.email is None
        or _normalise_address(contact.email) != _normalise_address(version.recipient_email)
        or sender.email.casefold() != version.sender_email.casefold()
    ):
        raise PublicAPIError(
            "outreach_preview_stale",
            "The sender or recipient changed. Create and approve a new outreach version.",
            409,
        )
    contactability = await evaluate_contactability(
        repository,
        tenant,
        settings,
        contact,
        action_id=message.action_id,
        sender_user_id=message.sender_user_id,
    )
    if not contactability.allowed:
        raise PublicAPIError(contactability.state.value, contactability.reason, 409)
    policy = await repository.policy(tenant.organisation_id)
    if not _policy_snapshot_is_current(policy, version):
        raise PublicAPIError(
            "outreach_policy_changed",
            "The approved seller context changed. Create and approve a new outreach draft.",
            409,
        )
    return record


class OutreachService:
    def __init__(self, session: AsyncSession, tenant: TenantContext, settings: Settings) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = OutreachRepository(session)

    async def availability(self) -> EngageAvailabilityResponse:
        access = await CommercialService(self.session, self.settings).module_access(
            self.tenant.organisation_id, "engage"
        )
        if access == "none":
            return EngageAvailabilityResponse(
                state="not_in_plan",
                enabled=False,
                can_manage=self.tenant.can_manage(),
                message="Engage isn't included in your organisation's current plan.",
            )
        if access == "read":
            return EngageAvailabilityResponse(
                state="read_only",
                enabled=False,
                can_manage=False,
                message="Historical Engage records remain available to view and export. New sending is blocked.",
            )
        if not self.settings.feature_engage_enabled:
            return EngageAvailabilityResponse(
                state="temporarily_unavailable",
                enabled=False,
                can_manage=self.tenant.can_manage(),
                message="RevenueOS Engage is unavailable in this environment.",
            )
        return EngageAvailabilityResponse(
            state="available",
            enabled=True,
            can_manage=self.tenant.can_manage(),
            message="RevenueOS Engage is available for this organisation.",
        )

    async def update_entitlement(self, request: EngageEntitlementUpdate) -> EngageAvailabilityResponse:
        del request
        self._require_admin()
        raise PublicAPIError(
            "commercial_plan_managed",
            "Module access is managed by your organisation's commercial plan. Contact support to change it.",
            403,
        )

    async def get_policy(self) -> OutreachPolicyResponse:
        policy = await self.repository.policy(self.tenant.organisation_id)
        return self._policy_response(policy)

    async def update_policy(self, request: OutreachPolicyUpdate) -> OutreachPolicyResponse:
        await self._require_entitled()
        self._require_admin()
        now = datetime.now(UTC)
        policy = await self.repository.policy(self.tenant.organisation_id, for_update=True)
        values = request.model_dump()
        materially_changed = policy is not None and any(getattr(policy, key) != value for key, value in values.items())
        if policy is None:
            policy = OutreachPolicy(
                organisation_id=self.tenant.organisation_id,
                configured=True,
                configured_by_user_id=self.tenant.user_id,
                **values,
            )
            self.repository.add(policy)
        else:
            for key, value in values.items():
                setattr(policy, key, value)
            policy.version += 1
            policy.configured = True
            policy.configured_by_user_id = self.tenant.user_id
            policy.updated_at = now
        if materially_changed:
            await self._halt_active_campaigns("campaign_policy_changed", now)
        await self._commit("The Engage sending policy could not be saved.")
        logger.info(
            "outreach_policy_updated",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "actor_user_id": str(self.tenant.user_id),
                "outbound_enabled": request.outbound_enabled,
                "provider_supplied_allowed": request.provider_supplied_email_allowed,
                "cooldown_hours": request.cooldown_hours,
            },
        )
        return self._policy_response(policy)

    async def workspace(self, contact_id: UUID) -> ContactOutreachWorkspaceResponse:
        await self._require_entitled(write=False)
        contact = await self._contact(contact_id)
        company = await self.repository.company(self.tenant.organisation_id, contact.company_id)
        assert company is not None
        availability = await self.availability()
        contactability = await evaluate_contactability(self.repository, self.tenant, self.settings, contact)
        policy = await self.repository.policy(self.tenant.organisation_id)
        history = [
            self._history_response(*item)
            for item in await self.repository.history(self.tenant.organisation_id, contact.id)
        ]
        simulation_connection = await self.repository.active_email_connection_for_user(
            self.tenant.organisation_id,
            self.tenant.user_id,
        )
        return ContactOutreachWorkspaceResponse(
            availability=availability,
            contact_id=contact.id,
            contact_name=f"{contact.first_name} {contact.last_name}",
            company_id=company.id,
            company_name=company.name,
            job_title=contact.job_title,
            email=contact.email,
            email_trust=contactability.trust_state,
            permission_status=("assessed_by_organisation_policy" if policy and policy.configured else "not_assessed"),
            contactability=contactability.response(),
            policy_configured=bool(policy and policy.configured),
            simulation_available=(
                simulation_connection is not None
                and self.settings.environment != "production"
                and self.settings.feature_mock_connectors_enabled
            ),
            history=history,
        )

    async def create(self, contact_id: UUID, request: OutreachCreateRequest) -> OutreachResponse:
        await self._require_entitled()
        contact = await self._contact(contact_id)
        company = await self.repository.company(self.tenant.organisation_id, contact.company_id)
        policy = await self.repository.policy(self.tenant.organisation_id)
        sender = await self.repository.user(self.tenant.user_id)
        organisation = await self.repository.organisation(self.tenant.organisation_id)
        assert company is not None and sender is not None and organisation is not None
        if policy is None or not policy.configured:
            raise PublicAPIError(
                "outreach_profile_required",
                "An administrator must add an approved offering before a trustworthy draft can be created.",
                409,
            )
        sources = await self._selected_sources(contact)
        subject, body, used = self._compose(
            contact=contact,
            company_name=company.name,
            sender_name=sender.display_name,
            organisation_name=organisation.name,
            policy=policy,
            purpose=request.purpose,
            sources=sources,
        )
        self._validate_copy(subject, body)
        record = await self._persist_draft(
            contact=contact,
            policy=policy,
            sender=sender,
            purpose=request.purpose,
            subject=subject,
            body=body,
            used=used,
            composer_version="outreach_deterministic_v1",
            plan_extra={},
            commit=True,
        )
        logger.info(
            "outreach_draft_created",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "outreach_id": str(record.message.id),
                "contact_id": str(contact.id),
                "purpose": request.purpose.value,
                "source_count": len(used),
            },
        )
        return await self.get(record.message.id)

    async def prepare_campaign_draft(
        self,
        contact_id: UUID,
        context: CampaignOutreachContext,
    ) -> OutreachRecord:
        """Prepare one campaign step within the caller's transaction."""
        await self._require_entitled()
        contact = await self._contact(contact_id)
        company = await self.repository.company(self.tenant.organisation_id, contact.company_id)
        policy = await self.repository.policy(self.tenant.organisation_id)
        sender = await self.repository.user(self.tenant.user_id)
        organisation = await self.repository.organisation(self.tenant.organisation_id)
        assert company is not None and sender is not None and organisation is not None
        if policy is None or not policy.configured:
            raise PublicAPIError("outreach_profile_required", "The approved seller context is unavailable.", 409)
        sources = await self._selected_sources(contact, excluded_source_ids=context.excluded_source_ids)
        purpose = self._campaign_purpose(context.objective)
        subject, body, used = self._compose_campaign(
            contact=contact,
            company_name=company.name,
            sender_name=sender.display_name,
            organisation_name=organisation.name,
            policy=policy,
            purpose=purpose,
            sources=sources,
            context=context,
        )
        self._validate_copy(subject, body)
        return await self._persist_draft(
            contact=contact,
            policy=policy,
            sender=sender,
            purpose=purpose,
            subject=subject,
            body=body,
            used=used,
            composer_version="outreach_campaign_deterministic_v1",
            plan_extra={
                "campaignStepInstanceId": str(context.step_instance_id),
                "sequenceObjective": context.objective,
                "sequenceStepOrder": context.step_order,
                "previousSentAt": context.previous_sent_at.isoformat() if context.previous_sent_at else None,
            },
            commit=False,
        )

    async def prepare_event_draft(
        self,
        contact_id: UUID,
        *,
        event_id: UUID,
        attendee_id: UUID,
        event_name: str,
        event_date_label: str,
        stage: Literal["pre_event", "post_event"],
        met: bool,
        encounter_id: UUID | None,
    ) -> OutreachRecord:
        """Prepare one truthful Event message while retaining the canonical Contact boundary."""
        await self._require_entitled()
        contact = await self._contact(contact_id)
        company = await self.repository.company(self.tenant.organisation_id, contact.company_id)
        policy = await self.repository.policy(self.tenant.organisation_id)
        sender = await self.repository.user(self.tenant.user_id)
        organisation = await self.repository.organisation(self.tenant.organisation_id)
        assert company is not None and sender is not None and organisation is not None
        if policy is None or not policy.configured:
            raise PublicAPIError("outreach_profile_required", "The approved seller context is unavailable.", 409)
        sources = await self._selected_sources(contact)
        _, base_body, used = self._compose(
            contact=contact,
            company_name=company.name,
            sender_name=sender.display_name,
            organisation_name=organisation.name,
            policy=policy,
            purpose=(OutreachPurpose.REQUEST_MEETING if stage == "pre_event" else OutreachPurpose.RE_ENGAGE),
            sources=sources,
        )
        base_parts = base_body.split("\n\n")
        research_hook = base_parts[1] if len(base_parts) > 1 and used else None
        if stage == "pre_event":
            subject = f"Meeting at {event_name}"[:200]
            event_line = (
                f"An authorised attendee list indicates you may be attending {event_name} on {event_date_label}. "
                "If so, I would value a short conversation."
            )
            purpose_line = policy.approved_cta
        else:
            subject = (f"Following up after {event_name}" if met else f"After {event_name}")[:200]
            event_line = (
                f"Good meeting you at {event_name}." if met else f"I wanted to get in touch following {event_name}."
            )
            purpose_line = "Would it be useful to compare notes?"
        paragraphs = [f"Hi {contact.first_name},", event_line]
        if research_hook:
            paragraphs.append(research_hook)
        paragraphs.extend(
            (
                f"{policy.value_proposition} {purpose_line}",
                f"Kind regards,\n{sender.display_name}\n{organisation.name}",
            )
        )
        body = "\n\n".join(paragraphs)
        self._validate_copy(subject, body)
        additional_sources = [
            AdditionalOutreachSource(
                source_type="event_attendance",
                source_id=attendee_id,
                label=f"Authorised Event attendee list: {event_name}",
                trust_state="provider_supplied",
            )
        ]
        if met and encounter_id is not None:
            additional_sources.append(
                AdditionalOutreachSource(
                    source_type="event_encounter",
                    source_id=encounter_id,
                    label=f"Seller-recorded encounter at {event_name}",
                    trust_state="seller_reported",
                )
            )
        return await self._persist_draft(
            contact=contact,
            policy=policy,
            sender=sender,
            purpose=(OutreachPurpose.REQUEST_MEETING if stage == "pre_event" else OutreachPurpose.RE_ENGAGE),
            subject=subject,
            body=body,
            used=used,
            composer_version="outreach_event_deterministic_v1",
            plan_extra={
                "eventId": str(event_id),
                "eventStage": stage,
                "eventMet": met,
                "eventConversationClaimsIncluded": False,
            },
            additional_sources=tuple(additional_sources),
            commit=False,
        )

    async def _persist_draft(
        self,
        *,
        contact: Contact,
        policy: OutreachPolicy,
        sender: User,
        purpose: OutreachPurpose,
        subject: str,
        body: str,
        used: list[SelectedSource],
        composer_version: str,
        plan_extra: dict[str, object],
        commit: bool,
        additional_sources: tuple[AdditionalOutreachSource, ...] = (),
    ) -> OutreachRecord:
        trust = await self._sendable_trust(contact)
        now = datetime.now(UTC)
        outreach_id = uuid.uuid4()
        action_id = uuid.uuid4()
        version_id = uuid.uuid4()
        payload = PersonalizedOutreachPayload(
            kind="personalized_outreach",
            outreach_id=outreach_id,
            outreach_version=1,
            sender_user_id=sender.id,
            sender_name=sender.display_name,
            sender_email=sender.email,
            recipient_contact_id=contact.id,
            recipient_name=f"{contact.first_name} {contact.last_name}",
            recipient_email=cast(str, contact.email),
            recipient_trust=trust,
            subject=subject,
            body=body,
        )
        payload_json = payload.model_dump(mode="json", by_alias=True)
        source_fingerprint = self._hash_json(
            {"outreachId": str(outreach_id), "contactId": str(contact.id), "version": 1}
        )
        action = ActionProposal(
            id=action_id,
            organisation_id=self.tenant.organisation_id,
            opportunity_id=None,
            interaction_id=None,
            action_type=ActionType.PERSONALIZED_OUTREACH.value,
            status=ActionStatus.PROPOSED.value,
            priority=ActionPriority.NORMAL.value,
            audience=ActionAudience.CUSTOMER_FACING.value,
            risk_class=ActionRiskClass.EXTERNAL_CUSTOMER_FACING.value,
            current_version=1,
            approved_version=None,
            source_fingerprint=source_fingerprint,
            semantic_key=self._hash_json(
                {
                    "contactId": str(contact.id),
                    "senderId": str(sender.id),
                    "purpose": purpose.value,
                    "outreachId": str(outreach_id),
                }
            ),
            created_by_user_id=self.tenant.user_id,
            generated_at=now,
        )
        message = OutreachMessage(
            id=outreach_id,
            organisation_id=self.tenant.organisation_id,
            contact_id=contact.id,
            sender_user_id=sender.id,
            action_id=action_id,
            purpose=purpose.value,
            state=OutreachState.DRAFT.value,
            current_version=1,
            created_at=now,
            updated_at=now,
        )
        version = OutreachVersion(
            id=version_id,
            organisation_id=self.tenant.organisation_id,
            outreach_id=outreach_id,
            version=1,
            subject=subject,
            body=body,
            sender_name=sender.display_name,
            sender_email=sender.email,
            recipient_name=f"{contact.first_name} {contact.last_name}",
            recipient_email=cast(str, contact.email),
            recipient_trust=trust,
            offering_name=policy.offering_name,
            value_proposition=policy.value_proposition,
            approved_cta=policy.approved_cta,
            personalization_plan_json={
                "schemaVersion": 1,
                "purpose": purpose.value,
                "sourceIds": [str(item.observation.id) for item in used],
                "noReliablePersonalizedHook": not used,
                **plan_extra,
            },
            composer_version=composer_version,
            creation_type="generated",
            content_fingerprint=self._content_fingerprint(subject, body, payload_json),
            created_by_user_id=self.tenant.user_id,
            created_at=now,
        )
        action_version = self._action_version(action, version, payload, now)
        self.repository.add(action)
        await self._flush("The outreach Action could not be created.")
        self.repository.add(message)
        await self._flush("The outreach message could not be created.")
        self.repository.add(version)
        self.repository.add(action_version)
        await self._flush("The outreach version could not be created.")
        self.repository.add(
            ActionAuditEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                action_id=action.id,
                actor_user_id=self.tenant.user_id,
                event_type="proposed",
                proposal_version=1,
                metadata_json={
                    "action_type": "personalized_outreach",
                    "purpose": purpose.value,
                    "source_count": len(used) + len(additional_sources) + 1,
                },
                created_at=now,
            )
        )
        for item in used:
            self.repository.add(
                OutreachPersonalizationSource(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    outreach_version_id=version_id,
                    source_type=("prospect_person_observation" if item.scope == "person" else "prospect_observation"),
                    source_id=item.observation.id,
                    supporting_source_id=item.source.id,
                    label=self._source_label(item.observation),
                    trust_state=item.observation.trust_state,
                    created_at=now,
                )
            )
        for additional_source in additional_sources:
            self.repository.add(
                OutreachPersonalizationSource(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    outreach_version_id=version_id,
                    source_type=additional_source.source_type,
                    source_id=additional_source.source_id,
                    supporting_source_id=None,
                    label=additional_source.label,
                    trust_state=additional_source.trust_state,
                    created_at=now,
                )
            )
        self.repository.add(
            OutreachPersonalizationSource(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                outreach_version_id=version_id,
                source_type="approved_seller_context",
                source_id=self.tenant.organisation_id,
                supporting_source_id=None,
                label=f"Approved seller offering: {policy.offering_name}",
                trust_state="approved",
                created_at=now,
            )
        )
        if commit:
            await self._commit("The outreach draft could not be created.")
        else:
            await self._flush("The campaign outreach draft could not be prepared.")
        return OutreachRecord(message, version)

    async def get(self, outreach_id: UUID) -> OutreachResponse:
        await self._require_entitled(write=False)
        record = await self._message(outreach_id)
        return await self._response(record)

    async def edit(self, outreach_id: UUID, request: OutreachEditRequest) -> OutreachResponse:
        await self._require_entitled()
        record = await self._message(outreach_id, for_update=True)
        message, current = record.message, record.version
        self._require_sender(message)
        if message.current_version != request.expected_version:
            raise PublicAPIError("stale_outreach", "This outreach changed after it was loaded.", 409)
        self._validate_copy(request.subject, request.body)
        contact = await self._contact(cast(UUID, message.contact_id))
        sender = await self.repository.user(message.sender_user_id)
        assert sender is not None
        if contact.email is None or contact.email.casefold() != current.recipient_email.casefold():
            raise PublicAPIError("outreach_recipient_changed", "The Contact email changed. Create a new draft.", 409)
        now = datetime.now(UTC)
        next_number = message.current_version + 1
        next_id = uuid.uuid4()
        payload = PersonalizedOutreachPayload(
            kind="personalized_outreach",
            outreach_id=message.id,
            outreach_version=next_number,
            sender_user_id=message.sender_user_id,
            sender_name=current.sender_name,
            sender_email=current.sender_email,
            recipient_contact_id=contact.id,
            recipient_name=current.recipient_name,
            recipient_email=current.recipient_email,
            recipient_trust=cast(Literal["verified", "provider_supplied"], current.recipient_trust),
            subject=request.subject,
            body=request.body,
        )
        payload_json = payload.model_dump(mode="json", by_alias=True)
        version = OutreachVersion(
            id=next_id,
            organisation_id=self.tenant.organisation_id,
            outreach_id=message.id,
            version=next_number,
            subject=request.subject,
            body=request.body,
            sender_name=current.sender_name,
            sender_email=current.sender_email,
            recipient_name=current.recipient_name,
            recipient_email=current.recipient_email,
            recipient_trust=current.recipient_trust,
            offering_name=current.offering_name,
            value_proposition=current.value_proposition,
            approved_cta=current.approved_cta,
            personalization_plan_json=current.personalization_plan_json,
            composer_version=current.composer_version,
            creation_type="user_edited",
            content_fingerprint=self._content_fingerprint(request.subject, request.body, payload_json),
            created_by_user_id=self.tenant.user_id,
            created_at=now,
        )
        action = await self.repository.action(
            self.tenant.organisation_id,
            message.action_id,
            for_update=True,
        )
        assert action is not None
        action.current_version = next_number
        action.approved_version = None
        action.status = ActionStatus.EDITED.value
        action.reviewed_by_user_id = None
        action.reviewed_at = None
        action.approved_at = None
        message.current_version = next_number
        message.approved_version = None
        message.approved_by_user_id = None
        message.approved_at = None
        message.state = OutreachState.DRAFT.value
        message.updated_at = now
        self.repository.add(version)
        self.repository.add(self._action_version(action, version, payload, now))
        await self._flush("The outreach edit could not be saved.")
        for source in await self.repository.version_sources(self.tenant.organisation_id, current.id):
            self.repository.add(
                OutreachPersonalizationSource(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    outreach_version_id=next_id,
                    source_type=source.source_type,
                    source_id=source.source_id,
                    supporting_source_id=source.supporting_source_id,
                    label=source.label,
                    trust_state=source.trust_state,
                    created_at=now,
                )
            )
        self.repository.add(
            ActionAuditEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                action_id=action.id,
                actor_user_id=self.tenant.user_id,
                event_type="edited",
                proposal_version=next_number,
                metadata_json={"changed_fields": ["subject", "body"], "approval_invalidated": True},
                created_at=now,
            )
        )
        await self._commit("The outreach edit could not be saved.")
        logger.info(
            "outreach_draft_edited",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "outreach_id": str(message.id),
                "version": next_number,
            },
        )
        return await self.get(message.id)

    async def approve(self, outreach_id: UUID, request: OutreachApproveRequest) -> OutreachResponse:
        return await self._approve(outreach_id, request, campaign_step_id=None)

    async def approve_campaign_authorized(
        self,
        outreach_id: UUID,
        request: OutreachApproveRequest,
        *,
        campaign_step_id: UUID,
    ) -> OutreachResponse:
        """Approve an auto-send draft under the immutable campaign launch authority."""

        return await self._approve(outreach_id, request, campaign_step_id=campaign_step_id)

    async def _approve(
        self,
        outreach_id: UUID,
        request: OutreachApproveRequest,
        *,
        campaign_step_id: UUID | None,
    ) -> OutreachResponse:
        await self._require_entitled()
        record = await self._message(outreach_id, for_update=True)
        message, version = record.message, record.version
        self._require_sender(message)
        if message.current_version != request.expected_version:
            raise PublicAPIError("stale_outreach", "This outreach changed after it was loaded.", 409)
        if message.state == OutreachState.APPROVED.value and message.approved_version == message.current_version:
            return await self._response(record)
        contact = await self._contact(cast(UUID, message.contact_id))
        contactability = await evaluate_contactability(
            self.repository,
            self.tenant,
            self.settings,
            contact,
            action_id=message.action_id,
            sender_user_id=message.sender_user_id,
        )
        if not contactability.allowed:
            raise PublicAPIError(contactability.state.value, contactability.reason, 409)
        policy = await self.repository.policy(self.tenant.organisation_id)
        if not _policy_snapshot_is_current(policy, version):
            raise PublicAPIError(
                "outreach_policy_changed",
                "The approved seller context changed. Create and approve a new outreach draft.",
                409,
            )
        if contact.email is None or contact.email.casefold() != version.recipient_email.casefold():
            raise PublicAPIError("outreach_recipient_changed", "The Contact email changed. Create a new draft.", 409)
        self._validate_copy(version.subject, version.body)
        now = datetime.now(UTC)
        action = await self.repository.action(
            self.tenant.organisation_id,
            message.action_id,
            for_update=True,
        )
        assert action is not None
        message.state = OutreachState.APPROVED.value
        message.approved_version = message.current_version
        message.approved_by_user_id = self.tenant.user_id
        message.approved_at = now
        message.updated_at = now
        action.status = ActionStatus.APPROVED.value
        action.approved_version = action.current_version
        action.reviewed_by_user_id = self.tenant.user_id
        action.reviewed_at = now
        action.approved_at = now
        self.repository.add(
            ActionAuditEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                action_id=action.id,
                actor_user_id=self.tenant.user_id,
                event_type="approved",
                proposal_version=action.current_version,
                metadata_json={
                    "action_type": "personalized_outreach",
                    "external_execution": False,
                    "contactability": "allowed",
                    "approval_basis": ("campaign_launch" if campaign_step_id is not None else "seller_review"),
                    **({"campaign_step_instance_id": str(campaign_step_id)} if campaign_step_id is not None else {}),
                },
                created_at=now,
            )
        )
        await self._commit("The outreach approval could not be saved.")
        logger.info(
            "outreach_approved",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "outreach_id": str(message.id),
                "version": message.current_version,
                "approval_basis": "campaign_launch" if campaign_step_id is not None else "seller_review",
                **({"campaign_step_id": str(campaign_step_id)} if campaign_step_id is not None else {}),
            },
        )
        return await self.get(message.id)

    async def suppress(
        self,
        contact_id: UUID,
        request: ContactSuppressionRequest,
    ) -> ContactSuppressionResponse:
        await self._require_entitled()
        if (
            request.reason in (SuppressionReason.COMPLAINT, SuppressionReason.PERMANENT_BOUNCE)
            and not self.tenant.can_manage()
        ):
            raise PublicAPIError("forbidden", "Administrator access is required for this suppression reason.", 403)
        contact = await self._contact(contact_id)
        if contact.email is None:
            raise PublicAPIError("no_business_email", "This Contact has no email address to suppress.", 409)
        fingerprint = suppression_fingerprint(self.settings, contact.email)
        existing = await self.repository.suppression(self.tenant.organisation_id, fingerprint)
        if existing is not None and existing.active:
            if existing.reason == request.reason.value:
                return self._suppression_response(existing)
            if existing.reason != SuppressionReason.MANUAL_DO_NOT_CONTACT.value:
                raise PublicAPIError(
                    "suppression_not_overridable",
                    "Recipient opt-outs, complaints and permanent bounces cannot be replaced by a user suppression.",
                    409,
                )
        now = datetime.now(UTC)
        source = (
            "recipient"
            if request.reason is SuppressionReason.RECIPIENT_OPT_OUT
            else (
                "provider"
                if request.reason in (SuppressionReason.COMPLAINT, SuppressionReason.PERMANENT_BOUNCE)
                else "user"
            )
        )
        if existing is None:
            existing = ContactSuppression(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                contact_id=contact.id,
                email_fingerprint=fingerprint,
                reason=request.reason.value,
                source=source,
                active=True,
                created_by_user_id=self.tenant.user_id,
                created_at=now,
            )
            self.repository.add(existing)
        else:
            existing.contact_id = contact.id
            existing.reason = request.reason.value
            existing.source = source
            existing.active = True
            existing.created_by_user_id = self.tenant.user_id
            existing.created_at = now
            existing.revoked_by_user_id = None
            existing.revoked_at = None
        await self._commit("The Contact suppression could not be saved.")
        logger.info(
            "contact_suppression_changed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "contact_id": str(contact.id),
                "reason": request.reason.value,
                "active": True,
            },
        )
        return self._suppression_response(existing)

    async def restore_manual_suppression(self, contact_id: UUID) -> ContactSuppressionResponse:
        self._require_admin()
        await self._require_entitled()
        contact = await self._contact(contact_id)
        if contact.email is None:
            raise PublicAPIError("suppression_not_found", "No active Contact suppression was found.", 404)
        existing = await self.repository.suppression(
            self.tenant.organisation_id,
            suppression_fingerprint(self.settings, contact.email),
        )
        if existing is None or not existing.active:
            raise PublicAPIError("suppression_not_found", "No active Contact suppression was found.", 404)
        if existing.reason != SuppressionReason.MANUAL_DO_NOT_CONTACT.value:
            raise PublicAPIError(
                "suppression_not_overridable",
                "Recipient opt-outs, complaints and permanent bounces cannot be restored here.",
                409,
            )
        existing.active = False
        existing.revoked_by_user_id = self.tenant.user_id
        existing.revoked_at = datetime.now(UTC)
        await self._commit("The manual suppression could not be restored.")
        logger.info(
            "contact_suppression_changed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "contact_id": str(contact.id),
                "reason": existing.reason,
                "active": False,
            },
        )
        return self._suppression_response(existing)

    async def _selected_sources(
        self,
        contact: Contact,
        *,
        excluded_source_ids: frozenset[UUID] = frozenset(),
    ) -> list[SelectedSource]:
        person = await self.repository.prospect_person_for_contact(self.tenant.organisation_id, contact.id)
        if person is None or person.employment_state != "current":
            return []
        results: list[SelectedSource] = []
        for scope, person_id, allowed in (
            ("person", person.id, _PERSON_CATEGORIES),
            ("company", None, _COMPANY_CATEGORIES),
        ):
            run = await self.repository.current_run(
                self.tenant.organisation_id,
                person.target_id,
                person_id=person_id,
            )
            if run is None:
                continue
            selected = 0
            for observation, source in await self.repository.observations_with_sources(
                self.tenant.organisation_id,
                run.id,
            ):
                if observation.id in excluded_source_ids:
                    continue
                if observation.category not in allowed or observation.trust_state not in _USABLE_TRUST:
                    continue
                if _SENSITIVE_TERMS.search(observation.statement):
                    continue
                if observation.freshness == "time_sensitive":
                    observed_at = observation.observed_at
                    if observed_at is not None and observed_at.tzinfo is None:
                        observed_at = observed_at.replace(tzinfo=UTC)
                    if observed_at is None or observed_at < datetime.now(UTC) - timedelta(days=365):
                        continue
                results.append(SelectedSource(observation, source, cast(Literal["company", "person"], scope)))
                selected += 1
                if selected >= 3:
                    break
        return results

    async def campaign_sources_are_current(self, contact_id: UUID, outreach_version_id: UUID) -> bool:
        """Revalidate every unsent campaign claim against the current Prospect run."""
        contact = await self._contact(contact_id)
        person = await self.repository.prospect_person_for_contact(self.tenant.organisation_id, contact.id)
        sources = await self.repository.version_sources(self.tenant.organisation_id, outreach_version_id)
        for source in sources:
            if source.source_type in {"approved_seller_context", "event_attendance", "event_encounter"}:
                continue
            if person is None or person.employment_state != "current":
                return False
            observation = await self.repository.observation(self.tenant.organisation_id, source.source_id)
            if observation is None or observation.trust_state not in _USABLE_TRUST:
                return False
            is_person = source.source_type == "prospect_person_observation"
            if observation.category not in (_PERSON_CATEGORIES if is_person else _COMPANY_CATEGORIES):
                return False
            if _SENSITIVE_TERMS.search(observation.statement):
                return False
            if observation.freshness == "time_sensitive":
                observed_at = observation.observed_at
                if observed_at is not None and observed_at.tzinfo is None:
                    observed_at = observed_at.replace(tzinfo=UTC)
                if observed_at is None or observed_at < datetime.now(UTC) - timedelta(days=365):
                    return False
            run = await self.repository.current_run(
                self.tenant.organisation_id,
                person.target_id,
                person_id=person.id if is_person else None,
            )
            if run is None or observation.run_id != run.id:
                return False
        return True

    @staticmethod
    def _campaign_purpose(objective: str) -> OutreachPurpose:
        return {
            "introduction": OutreachPurpose.INTRODUCTION,
            "meeting_request": OutreachPurpose.REQUEST_MEETING,
            "share_relevant_information": OutreachPurpose.SHARE_RELEVANT_INFORMATION,
            "follow_up": OutreachPurpose.RE_ENGAGE,
            "different_angle": OutreachPurpose.RE_ENGAGE,
            "final_follow_up": OutreachPurpose.RE_ENGAGE,
        }[objective]

    @classmethod
    def _compose_campaign(
        cls,
        *,
        contact: Contact,
        company_name: str,
        sender_name: str,
        organisation_name: str,
        policy: OutreachPolicy,
        purpose: OutreachPurpose,
        sources: list[SelectedSource],
        context: CampaignOutreachContext,
    ) -> tuple[str, str, list[SelectedSource]]:
        if context.step_order == 1:
            return cls._compose(
                contact=contact,
                company_name=company_name,
                sender_name=sender_name,
                organisation_name=organisation_name,
                policy=policy,
                purpose=purpose,
                sources=sources,
            )
        if context.previous_sent_at is None:
            raise PublicAPIError(
                "campaign_sequence_context_invalid",
                "A follow-up cannot be prepared until the previous message was successfully sent.",
                409,
            )
        if context.objective == "final_follow_up" and context.step_order != context.total_steps:
            raise PublicAPIError(
                "campaign_sequence_context_invalid",
                "A final follow-up must be the last enabled sequence step.",
                409,
            )
        weekday = context.previous_sent_at.strftime("%A")
        follow_up = f"I wanted to follow up on my note from {weekday}."
        used: list[SelectedSource] = []
        if context.objective in {"different_angle", "share_relevant_information"}:
            _, generated_body, used = cls._compose(
                contact=contact,
                company_name=company_name,
                sender_name=sender_name,
                organisation_name=organisation_name,
                policy=policy,
                purpose=purpose,
                sources=sources,
            )
            if not used:
                consolidation = next(
                    (
                        item
                        for item in sources
                        if item.observation.observation_key == "technology_consolidation"
                        and "technology consolidation" in item.observation.statement.casefold()
                    ),
                    None,
                )
                if consolidation is not None:
                    used = [consolidation]
                    generated_body = (
                        f"Hi {contact.first_name},\n\n"
                        "Your public comments on technology consolidation during business growth offered another "
                        "relevant angle."
                    )
            paragraphs = generated_body.split("\n\n")
            angle = paragraphs[1] if len(paragraphs) > 1 else f"A different relevant angle for {company_name}."
            subject = (
                f"A different angle for {company_name}"
                if context.objective == "different_angle"
                else f"A useful overview for {company_name}"
            )[:200]
            body = (
                f"Hi {contact.first_name},\n\n"
                f"{follow_up}\n\n"
                f"{angle}\n\n"
                f"{policy.value_proposition} {policy.approved_cta}\n\n"
                f"Kind regards,\n{sender_name}\n{organisation_name}"
            )
            return subject, body, used
        if context.objective == "final_follow_up":
            subject = f"Leaving this with you — {policy.offering_name}"[:200]
            body = (
                f"Hi {contact.first_name},\n\n"
                f"{follow_up} I'll leave it here for now so I don't crowd your inbox.\n\n"
                f"If {policy.offering_name} becomes relevant, {policy.approved_cta.lower()}\n\n"
                f"Kind regards,\n{sender_name}\n{organisation_name}"
            )
            return subject, body, used
        subject = f"Following up — {policy.offering_name}"[:200]
        body = (
            f"Hi {contact.first_name},\n\n"
            f"{follow_up}\n\n"
            f"{policy.value_proposition} {policy.approved_cta}\n\n"
            f"Kind regards,\n{sender_name}\n{organisation_name}"
        )
        return subject, body, used

    @staticmethod
    def _compose(
        *,
        contact: Contact,
        company_name: str,
        sender_name: str,
        organisation_name: str,
        policy: OutreachPolicy,
        purpose: OutreachPurpose,
        sources: list[SelectedSource],
    ) -> tuple[str, str, list[SelectedSource]]:
        by_key = {item.observation.observation_key: item for item in sources}
        expansion = by_key.get("australian_expansion")
        consolidation = by_key.get("technology_consolidation")
        if (
            expansion is not None
            and "three additional australian locations" not in expansion.observation.statement.casefold()
        ):
            expansion = None
        if consolidation is not None and not all(
            phrase in consolidation.observation.statement.casefold()
            for phrase in ("public", "technology consolidation")
        ):
            consolidation = None
        used: list[SelectedSource] = []
        if expansion and consolidation:
            hook = (
                f"{company_name}'s expansion into three additional Australian locations, alongside your public "
                "comments on technology consolidation during that growth, prompted me to get in touch."
            )
            used = [expansion, consolidation]
            subject = f"Multi-site growth at {company_name}"[:200]
        elif expansion:
            hook = f"{company_name}'s expansion into three additional Australian locations prompted me to get in touch."
            used = [expansion]
            subject = f"Multi-site growth at {company_name}"[:200]
        else:
            role_context = f" {contact.job_title.lower()}" if contact.job_title else ""
            hook = f"I'm getting in touch with a concise idea for{role_context} teams at {company_name}."
            subject = f"{policy.offering_name} at {company_name}"[:200]
        purpose_line = {
            OutreachPurpose.INTRODUCTION: policy.approved_cta,
            OutreachPurpose.REQUEST_MEETING: policy.approved_cta,
            OutreachPurpose.SHARE_RELEVANT_INFORMATION: "Would it be useful if I shared a short overview?",
            OutreachPurpose.RE_ENGAGE: "Would it be useful to compare notes again?",
        }[purpose]
        body = (
            f"Hi {contact.first_name},\n\n"
            f"{hook}\n\n"
            f"{policy.value_proposition} {purpose_line}\n\n"
            f"Kind regards,\n{sender_name}\n{organisation_name}"
        )
        return subject, body, used

    @staticmethod
    def _validate_copy(subject: str, body: str) -> None:
        if subject.casefold().startswith(("re:", "fwd:")) or re.search(
            r"\b(urgent|final notice|last chance)\b", subject, re.IGNORECASE
        ):
            raise PublicAPIError("unsafe_outreach_copy", "The subject uses deceptive or unsupported urgency.", 422)
        if (
            _SENSITIVE_TERMS.search(subject)
            or _PROHIBITED_COPY.search(subject)
            or _SENSITIVE_TERMS.search(body)
            or _PROHIBITED_COPY.search(body)
        ):
            raise PublicAPIError(
                "unsafe_outreach_copy",
                "The message contains sensitive, manipulative or unsupported sales language.",
                422,
            )
        if any(
            (ord(character) < 32 and character not in {"\t", "\n", "\r"}) or ord(character) == 127 for character in body
        ):
            raise PublicAPIError("unsafe_outreach_copy", "The message contains unsupported control characters.", 422)

    async def _response(self, record: OutreachRecord) -> OutreachResponse:
        message, version = record.message, record.version
        contact = (
            await self.repository.contact(self.tenant.organisation_id, message.contact_id)
            if message.contact_id is not None
            else None
        )
        contactability = (
            await evaluate_contactability(
                self.repository,
                self.tenant,
                self.settings,
                contact,
                action_id=message.action_id,
                sender_user_id=message.sender_user_id,
            )
            if contact is not None
            else ContactabilityResult(
                OutreachContactability.NO_BUSINESS_EMAIL,
                "The original Contact is no longer available.",
                "unknown",
            )
        )
        sources = [
            await self._source_response(item)
            for item in await self.repository.version_sources(self.tenant.organisation_id, version.id)
        ]
        execution = await self.repository.latest_execution(self.tenant.organisation_id, message.action_id)
        relationship_warning = None
        if contact is not None and await self.repository.has_active_opportunity(
            self.tenant.organisation_id,
            contact.company_id,
        ):
            relationship_warning = "This Contact already has active sales history. Check that the purpose and wording fit the relationship."
        user_edited = version.creation_type == "user_edited"
        prospect_sources = [
            item for item in sources if item.source_type in {"prospect_observation", "prospect_person_observation"}
        ]
        event_sources = [item for item in sources if item.source_type in {"event_attendance", "event_encounter"}]
        warnings = (
            ["Edited by you. Source-backed provenance applies only to the generated personalisation you retained."]
            if user_edited
            else (
                ["No reliable professional research hook was available; RevenueOS did not invent one."]
                if not prospect_sources
                else []
            )
        )
        return OutreachResponse(
            id=message.id,
            action_id=message.action_id,
            contact_id=message.contact_id,
            purpose=OutreachPurpose(message.purpose),
            state=OutreachState(message.state),
            current_version=message.current_version,
            approved_version=message.approved_version,
            version=OutreachVersionResponse(
                id=version.id,
                version=version.version,
                subject=version.subject,
                body=version.body,
                sender_name=version.sender_name,
                sender_email=version.sender_email,
                recipient_name=version.recipient_name,
                recipient_email=version.recipient_email,
                recipient_trust=cast(Literal["verified", "provider_supplied"], version.recipient_trust),
                creation_type=cast(Literal["generated", "user_edited"], version.creation_type),
                composer_version=version.composer_version,
                personalization_used=bool(prospect_sources or event_sources),
                sources=sources,
                warnings=warnings,
                created_at=version.created_at,
            ),
            contactability=contactability.response(),
            relationship_warning=relationship_warning,
            execution=self._execution_response(execution) if execution is not None else None,
            created_at=message.created_at,
            updated_at=message.updated_at,
        )

    async def _source_response(self, item: OutreachPersonalizationSource) -> OutreachSourceResponse:
        if item.source_type == "approved_seller_context":
            return OutreachSourceResponse(
                id=item.id,
                source_type="approved_seller_context",
                source_id=item.source_id,
                label=item.label,
                trust_state="approved",
                publisher=None,
                published_at=None,
                url=None,
            )
        if item.source_type in {"event_attendance", "event_encounter"}:
            return OutreachSourceResponse(
                id=item.id,
                source_type=cast(Literal["event_attendance", "event_encounter"], item.source_type),
                source_id=item.source_id,
                label=item.label,
                trust_state=cast(Literal["provider_supplied", "seller_reported"], item.trust_state),
                publisher=None,
                published_at=None,
                url=None,
            )
        source = (
            await self.repository.research_source(self.tenant.organisation_id, item.supporting_source_id)
            if item.supporting_source_id is not None
            else None
        )
        observation = await self.repository.observation(
            self.tenant.organisation_id,
            item.source_id,
        )
        return OutreachSourceResponse(
            id=item.id,
            source_type=cast(
                Literal["prospect_observation", "prospect_person_observation"],
                item.source_type,
            ),
            source_id=item.source_id,
            label=observation.statement if observation is not None else item.label,
            trust_state=cast(Literal["verified", "provider_supplied"], item.trust_state),
            publisher=source.publisher if source is not None else None,
            published_at=source.published_at if source is not None else None,
            url=source.canonical_url if source is not None else None,
        )

    def _policy_response(self, policy: OutreachPolicy | None) -> OutreachPolicyResponse:
        return OutreachPolicyResponse(
            version=policy.version if policy else 1,
            configured=bool(policy and policy.configured),
            outbound_enabled=bool(policy and policy.outbound_enabled),
            provider_supplied_email_allowed=bool(policy and policy.provider_supplied_email_allowed),
            cooldown_hours=policy.cooldown_hours if policy else 72,
            max_daily_sends_user=policy.max_daily_sends_user
            if policy
            else self.settings.private_beta_max_outreach_per_user_per_day,
            max_daily_sends_org=policy.max_daily_sends_org
            if policy
            else self.settings.private_beta_max_outreach_per_organisation_per_day,
            require_opt_out_mechanism=bool(policy and policy.require_opt_out_mechanism),
            campaign_auto_send_allowed=bool(policy and policy.campaign_auto_send_allowed),
            offering_name=policy.offering_name if policy else None,
            value_proposition=policy.value_proposition if policy else None,
            approved_cta=policy.approved_cta if policy else None,
            can_manage=self.tenant.can_manage(),
            compliance_notice=(
                "RevenueOS provides configurable product controls, not legal advice. Your organisation remains responsible "
                "for applicable outreach, privacy and marketing obligations."
            ),
        )

    @staticmethod
    def _source_label(observation: ProspectResearchObservation) -> str:
        return observation.category.replace("_", " ").title()

    @staticmethod
    def _suppression_response(item: ContactSuppression) -> ContactSuppressionResponse:
        return ContactSuppressionResponse(
            id=item.id,
            contact_id=item.contact_id,
            reason=SuppressionReason(item.reason),
            active=item.active,
            created_at=item.created_at,
            revoked_at=item.revoked_at,
        )

    @staticmethod
    def _execution_response(execution: ActionExecution) -> OutreachExecutionSummary:
        status_map = {
            "queued": "queued",
            "executing": "sending",
            "simulated_success": "simulated",
            "succeeded": "sent",
            "failed_retryable": "failed",
            "failed_permanent": "failed",
            "cancelled": "cancelled",
            "unknown_external_state": "unknown_delivery_state",
        }
        simulation = execution.execution_mode == "simulation"
        safe_message = {
            "simulated_success": "Email simulation completed. No external email was sent.",
            "succeeded": "The mailbox provider accepted the email for sending. This is not delivery confirmation.",
            "unknown_external_state": "The provider outcome is uncertain. RevenueOS will not resend automatically.",
            "failed_permanent": "The email could not be sent.",
            "failed_retryable": "The email send attempt failed before confirmed acceptance.",
            "cancelled": "The email send was cancelled before confirmed acceptance.",
            "queued": "The reviewed email is queued for the execution worker.",
            "executing": "The execution worker is processing the reviewed email.",
        }.get(execution.execution_status, "Email status is unavailable.")
        return OutreachExecutionSummary(
            id=execution.id,
            status=cast(
                Literal[
                    "queued",
                    "sending",
                    "submitted",
                    "sent",
                    "failed",
                    "unknown_delivery_state",
                    "cancelled",
                    "simulated",
                ],
                status_map[execution.execution_status],
            ),
            simulation_only=simulation,
            safe_message=safe_message,
            created_at=execution.created_at,
            completed_at=execution.completed_at,
        )

    @staticmethod
    def _history_response(
        message: OutreachMessage,
        version: OutreachVersion,
        execution: ActionExecution | None,
    ) -> OutreachHistoryItem:
        summary = OutreachService._execution_response(execution) if execution is not None else None
        return OutreachHistoryItem(
            id=message.id,
            purpose=OutreachPurpose(message.purpose),
            subject=version.subject,
            status=summary.status if summary is not None else message.state,
            simulation_only=summary.simulation_only if summary is not None else False,
            created_at=message.created_at,
            completed_at=summary.completed_at if summary is not None else None,
        )

    @staticmethod
    def _action_version(
        action: ActionProposal,
        version: OutreachVersion,
        payload: PersonalizedOutreachPayload,
        created_at: datetime,
    ) -> ActionProposalVersion:
        payload_json = payload.model_dump(mode="json", by_alias=True)
        return ActionProposalVersion(
            id=uuid.uuid4(),
            organisation_id=action.organisation_id,
            action_id=action.id,
            version=version.version,
            title=f"Review outreach to {version.recipient_name}"[:240],
            description="Review this exact one-to-one email before any external execution.",
            proposed_due_at=None,
            target_entity_type="contact",
            target_entity_id=payload.recipient_contact_id,
            payload_json=payload_json,
            source_refs_json=[],
            provenance_summary=(
                "Source-backed Prospect observations and approved seller context are attached to the immutable outreach version."
            ),
            content_fingerprint=OutreachService._content_fingerprint(version.subject, version.body, payload_json),
            created_by_user_id=payload.sender_user_id,
            created_at=created_at,
        )

    async def _sendable_trust(self, contact: Contact) -> Literal["verified", "provider_supplied"]:
        if contact.email is None:
            raise PublicAPIError("no_business_email", "This Contact has no supported business email.", 409)
        source = await self.repository.email_source(
            self.tenant.organisation_id,
            contact.id,
            _contact_value_fingerprint(contact.email),
        )
        if source is None or source.trust_state not in _USABLE_TRUST:
            raise PublicAPIError(
                "email_trust_unknown",
                "The exact Contact email does not have a sendable business-contact trust state.",
                409,
            )
        return cast(Literal["verified", "provider_supplied"], source.trust_state)

    async def _contact(self, contact_id: UUID) -> Contact:
        contact = await self.repository.contact(self.tenant.organisation_id, contact_id)
        if contact is None:
            raise PublicAPIError("contact_not_found", "The requested Contact was not found.", 404)
        return contact

    async def _message(self, outreach_id: UUID, *, for_update: bool = False) -> OutreachRecord:
        record = await self.repository.message(self.tenant.organisation_id, outreach_id, for_update=for_update)
        if record is None:
            raise PublicAPIError("outreach_not_found", "The requested outreach message was not found.", 404)
        return record

    async def _halt_active_campaigns(self, reason: str, now: datetime) -> None:
        """Fail closed for every unsent step after an organisation-level control changes."""

        organisation_id = self.tenant.organisation_id
        campaign_ids = select(EngageCampaign.id).where(
            EngageCampaign.organisation_id == organisation_id,
            EngageCampaign.state.in_(("active", "paused", "needs_attention")),
        )
        enrollment_ids = select(EngageCampaignEnrollment.id).where(
            EngageCampaignEnrollment.organisation_id == organisation_id,
            EngageCampaignEnrollment.campaign_id.in_(campaign_ids),
            EngageCampaignEnrollment.state.in_(("ready", "active", "paused", "needs_attention")),
        )
        outreach_action_ids = (
            select(OutreachMessage.action_id)
            .join(
                EngageEnrollmentStep,
                and_(
                    EngageEnrollmentStep.organisation_id == OutreachMessage.organisation_id,
                    EngageEnrollmentStep.outreach_message_id == OutreachMessage.id,
                ),
            )
            .where(
                OutreachMessage.organisation_id == organisation_id,
                EngageEnrollmentStep.organisation_id == organisation_id,
                EngageEnrollmentStep.enrollment_id.in_(enrollment_ids),
            )
        )
        await self.session.execute(
            update(ActionExecution)
            .where(
                ActionExecution.organisation_id == organisation_id,
                ActionExecution.action_id.in_(outreach_action_ids),
                ActionExecution.execution_status.in_(("queued", "failed_retryable")),
            )
            .values(
                execution_status="cancelled",
                completed_at=now,
                next_attempt_at=None,
                safe_failure_code=reason,
                worker_id=None,
                lease_expires_at=None,
                updated_at=now,
            )
        )
        await self.session.execute(
            update(EngageEnrollmentStep)
            .where(
                EngageEnrollmentStep.organisation_id == organisation_id,
                EngageEnrollmentStep.enrollment_id.in_(enrollment_ids),
                EngageEnrollmentStep.state.in_(
                    ("pending", "processing", "ready_for_review", "prepared", "queued", "deferred")
                ),
            )
            .values(
                state="blocked",
                safe_status_code=reason,
                worker_id=None,
                lease_expires_at=None,
                updated_at=now,
            )
        )
        await self.session.execute(
            update(EngageCampaignEnrollment)
            .where(
                EngageCampaignEnrollment.organisation_id == organisation_id,
                EngageCampaignEnrollment.id.in_(enrollment_ids),
            )
            .values(
                state="needs_attention",
                stop_reason=reason,
                next_scheduled_at=None,
                updated_at=now,
            )
        )
        await self.session.execute(
            update(EngageCampaign)
            .where(
                EngageCampaign.organisation_id == organisation_id,
                EngageCampaign.id.in_(campaign_ids),
            )
            .values(state="needs_attention", needs_attention_reason=reason, updated_at=now)
        )

    def _require_sender(self, message: OutreachMessage) -> None:
        if message.sender_user_id != self.tenant.user_id:
            raise PublicAPIError("outreach_sender_mismatch", "Only the message sender can edit or approve it.", 403)

    async def _require_entitled(self, *, write: bool = True) -> None:
        commercial = CommercialService(self.session, self.settings)
        if self.settings.feature_engage_enabled and write:
            await commercial.require_module_write(self.tenant.organisation_id, "engage")
            return
        access = await commercial.module_access(self.tenant.organisation_id, "engage")
        if access == "none" or (write and (not self.settings.feature_engage_enabled or access != "write")):
            raise PublicAPIError(
                "engage_not_in_plan", "Engage isn't included in your organisation's current plan.", 403
            )

    def _require_admin(self) -> None:
        if not self.tenant.can_manage():
            raise PublicAPIError("forbidden", "Administrator access is required.", 403)

    async def _commit(self, message: str) -> None:
        try:
            await self.repository.flush()
            await self.repository.commit()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError("outreach_conflict", message, 409) from exc

    async def _flush(self, message: str) -> None:
        try:
            await self.repository.flush()
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError("outreach_conflict", message, 409) from exc

    @staticmethod
    def _content_fingerprint(subject: str, body: str, payload: dict[str, object]) -> str:
        return OutreachService._hash_json({"subject": subject, "body": body, "payload": payload})

    @staticmethod
    def _hash_json(value: dict[str, object]) -> str:
        return hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest()
