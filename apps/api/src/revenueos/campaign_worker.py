from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.campaign_repositories import CampaignRepository
from revenueos.campaign_services import CampaignService
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.domain import (
    CampaignApprovalMode,
    CampaignEnrollmentState,
    CampaignState,
    CampaignStepState,
    OutreachContactability,
)
from revenueos.errors import PublicAPIError
from revenueos.integration_contracts import ExecutionConfirmRequest
from revenueos.integration_services import ActionExecutionService
from revenueos.models import (
    ActionExecution,
    Contact,
    EngageCampaign,
    EngageCampaignEnrollment,
    EngageCampaignVersion,
    EngageEnrollmentStep,
    EngageSequenceStep,
    Organisation,
    OutreachMessage,
    OutreachPolicy,
)
from revenueos.outreach_contracts import OutreachApproveRequest
from revenueos.outreach_repositories import OutreachRepository
from revenueos.outreach_services import CampaignOutreachContext, OutreachService, evaluate_contactability
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.campaign_worker")
DISCOVERY_LIMIT = 1000


@dataclass(frozen=True)
class ClaimedCampaignStep:
    organisation_id: UUID
    step_instance_id: UUID
    worker_id: str
    operation: Literal["prepare", "send", "reconcile"]


class CampaignWorkerService:
    """Leased, idempotent Campaign scheduler inside the existing durable worker."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], settings: Settings) -> None:
        self._session_factory = session_factory
        self._settings = settings

    async def run_once(self, worker_id: str) -> bool:
        if not self._features_enabled():
            return False
        processed = False
        for organisation_id in await self.discover_eligible_organisations():
            recovered = await self.recover_abandoned_steps(organisation_id)
            claim = await self.claim_next(organisation_id, worker_id)
            processed = processed or bool(recovered or claim)
            if claim is not None:
                await self.execute_claimed(claim)
        return processed

    async def discover_eligible_organisations(self) -> list[UUID]:
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            if session.get_bind().dialect.name == "postgresql":
                values = await session.scalars(
                    text(
                        """SELECT organisation_id
                        FROM public.revenueos_campaign_worker_eligible_organisations(
                            :eligible_at,
                            :result_limit
                        )"""
                    ),
                    {"eligible_at": now, "result_limit": DISCOVERY_LIMIT},
                )
                return [UUID(str(item)) for item in values.all()]
            eligible_step_ids = select(EngageEnrollmentStep.organisation_id).where(
                or_(
                    and_(
                        EngageEnrollmentStep.state.in_(("pending", "deferred")),
                        EngageEnrollmentStep.prepare_at <= now,
                    ),
                    and_(
                        EngageEnrollmentStep.state == "prepared",
                        EngageEnrollmentStep.scheduled_at <= now,
                    ),
                    EngageEnrollmentStep.state.in_(("queued", "ready_for_review")),
                    and_(
                        EngageEnrollmentStep.state == "processing",
                        EngageEnrollmentStep.lease_expires_at.is_not(None),
                        EngageEnrollmentStep.lease_expires_at <= now,
                    ),
                )
            )
            values = await session.scalars(
                select(Organisation.id)
                .where(Organisation.id.in_(eligible_step_ids))
                .order_by(Organisation.id)
                .limit(DISCOVERY_LIMIT)
            )
            return list(values.all())

    async def recover_abandoned_steps(self, organisation_id: UUID) -> int:
        now = datetime.now(UTC)
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, organisation_id)
            values = await session.scalars(
                select(EngageEnrollmentStep)
                .where(
                    EngageEnrollmentStep.organisation_id == organisation_id,
                    EngageEnrollmentStep.state == CampaignStepState.PROCESSING.value,
                    EngageEnrollmentStep.lease_expires_at.is_not(None),
                    EngageEnrollmentStep.lease_expires_at <= now,
                )
                .with_for_update(skip_locked=True)
            )
            steps = list(values.all())
            for step in steps:
                if step.outreach_message_id is None:
                    step.state = CampaignStepState.PENDING.value
                elif await self._latest_execution(session, organisation_id, step.outreach_message_id) is not None:
                    step.state = CampaignStepState.QUEUED.value
                else:
                    approval_mode = await self._approval_mode_for_step(session, organisation_id, step.enrollment_id)
                    step.state = (
                        CampaignStepState.PREPARED.value
                        if approval_mode == CampaignApprovalMode.APPROVED_CAMPAIGN_AUTO_SEND.value
                        else CampaignStepState.READY_FOR_REVIEW.value
                    )
                step.safe_status_code = "worker_lease_recovered"
                step.worker_id = None
                step.lease_expires_at = None
                step.updated_at = now
            return len(steps)

    async def claim_next(self, organisation_id: UUID, worker_id: str) -> ClaimedCampaignStep | None:
        now = datetime.now(UTC)
        review_has_execution = exists(
            select(ActionExecution.id)
            .select_from(OutreachMessage)
            .join(
                ActionExecution,
                and_(
                    ActionExecution.organisation_id == OutreachMessage.organisation_id,
                    ActionExecution.action_id == OutreachMessage.action_id,
                ),
            )
            .where(
                OutreachMessage.organisation_id == EngageEnrollmentStep.organisation_id,
                OutreachMessage.id == EngageEnrollmentStep.outreach_message_id,
            )
        )
        async with self._session_factory() as session, session.begin():
            await set_tenant_database_context(session, organisation_id)
            step = cast(
                EngageEnrollmentStep | None,
                await session.scalar(
                    select(EngageEnrollmentStep)
                    .join(
                        EngageCampaignEnrollment,
                        and_(
                            EngageCampaignEnrollment.organisation_id == EngageEnrollmentStep.organisation_id,
                            EngageCampaignEnrollment.id == EngageEnrollmentStep.enrollment_id,
                        ),
                    )
                    .join(
                        EngageCampaign,
                        and_(
                            EngageCampaign.organisation_id == EngageCampaignEnrollment.organisation_id,
                            EngageCampaign.id == EngageCampaignEnrollment.campaign_id,
                        ),
                    )
                    .where(
                        EngageEnrollmentStep.organisation_id == organisation_id,
                        EngageCampaign.state == CampaignState.ACTIVE.value,
                        EngageCampaignEnrollment.state.in_(("ready", "active")),
                        or_(
                            and_(
                                EngageEnrollmentStep.state.in_(("pending", "deferred")),
                                EngageEnrollmentStep.prepare_at <= now,
                            ),
                            and_(
                                EngageEnrollmentStep.state == CampaignStepState.PREPARED.value,
                                EngageEnrollmentStep.scheduled_at <= now,
                            ),
                            EngageEnrollmentStep.state == CampaignStepState.QUEUED.value,
                            and_(
                                EngageEnrollmentStep.state == CampaignStepState.READY_FOR_REVIEW.value,
                                review_has_execution,
                            ),
                        ),
                    )
                    .order_by(
                        EngageEnrollmentStep.prepare_at,
                        EngageEnrollmentStep.scheduled_at,
                        EngageEnrollmentStep.created_at,
                        EngageEnrollmentStep.id,
                    )
                    .with_for_update(skip_locked=True)
                    .limit(1)
                ),
            )
            if step is None:
                return None
            operation: Literal["prepare", "send", "reconcile"]
            if step.state in {CampaignStepState.PENDING.value, CampaignStepState.DEFERRED.value}:
                operation = "prepare"
            elif step.state == CampaignStepState.PREPARED.value:
                operation = "send"
            else:
                operation = "reconcile"
            step.state = CampaignStepState.PROCESSING.value
            step.worker_id = worker_id
            step.lease_expires_at = now + timedelta(seconds=self._settings.worker_lease_duration_seconds)
            step.attempt_count += 1
            step.updated_at = now
            claim = ClaimedCampaignStep(organisation_id, step.id, worker_id, operation)
        logger.info(
            "campaign_step_claimed",
            extra={
                "organisation_id": str(organisation_id),
                "campaign_step_id": str(claim.step_instance_id),
                "operation": claim.operation,
                "worker_id": worker_id,
            },
        )
        return claim

    async def execute_claimed(self, claim: ClaimedCampaignStep) -> None:
        async with self._session_factory() as session:
            try:
                await set_tenant_database_context(session, claim.organisation_id)
                row = await self._claimed_row(session, claim)
                if row is None:
                    return
                step, sequence, enrollment, campaign, version = row
                tenant = TenantContext(
                    organisation_id=claim.organisation_id,
                    user_id=enrollment.sender_user_id,
                    role="member",
                )
                if claim.operation == "reconcile":
                    await self._reconcile(session, tenant, step, sequence, enrollment, campaign, version)
                    return
                contact, policy = await self._preflight(
                    session,
                    tenant,
                    step,
                    enrollment,
                    campaign,
                    version,
                    check_frequency_limits=claim.operation == "send",
                )
                if contact is None or policy is None:
                    return
                if claim.operation == "prepare":
                    await self._prepare(session, tenant, step, sequence, enrollment, campaign, version)
                else:
                    await self._send(session, tenant, step, sequence, enrollment, campaign, version)
            except Exception as exc:
                await session.rollback()
                code = exc.code if isinstance(exc, PublicAPIError) else "campaign_worker_failed"
                await self._fail_claim(session, claim, code)
                logger.error(
                    "campaign_step_failed_closed",
                    extra={
                        "organisation_id": str(claim.organisation_id),
                        "campaign_step_id": str(claim.step_instance_id),
                        "operation": claim.operation,
                        "safe_status_code": code,
                        "error_type": type(exc).__name__,
                    },
                )

    async def _prepare(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        step: EngageEnrollmentStep,
        sequence: EngageSequenceStep,
        enrollment: EngageCampaignEnrollment,
        campaign: EngageCampaign,
        version: EngageCampaignVersion,
    ) -> None:
        now = datetime.now(UTC)
        start = datetime.combine(now.date(), time.min, tzinfo=UTC)
        campaign_repository = CampaignRepository(session)
        if (
            await campaign_repository.prepared_drafts_since(tenant.organisation_id, start)
            >= self._settings.private_beta_max_campaign_drafts_per_day
        ):
            scheduler = CampaignService(session, tenant, self._settings)
            step.state = CampaignStepState.DEFERRED.value
            step.safe_status_code = "campaign_generation_quota_deferred"
            step.prepare_at = scheduler._next_send_time(now + timedelta(days=1), version)
            step.worker_id = None
            step.lease_expires_at = None
            step.updated_at = now
            await session.commit()
            return
        previous_sent_at = None
        if sequence.step_order > 1:
            previous = await session.scalar(
                select(EngageEnrollmentStep)
                .join(
                    EngageSequenceStep,
                    and_(
                        EngageSequenceStep.organisation_id == EngageEnrollmentStep.organisation_id,
                        EngageSequenceStep.id == EngageEnrollmentStep.sequence_step_id,
                    ),
                )
                .where(
                    EngageEnrollmentStep.organisation_id == tenant.organisation_id,
                    EngageEnrollmentStep.enrollment_id == enrollment.id,
                    EngageSequenceStep.step_order == sequence.step_order - 1,
                    EngageEnrollmentStep.state == CampaignStepState.SENT.value,
                )
            )
            previous_sent_at = previous.sent_at if previous is not None else None
        total_steps = int(
            await session.scalar(
                select(func.count())
                .select_from(EngageSequenceStep)
                .where(
                    EngageSequenceStep.organisation_id == tenant.organisation_id,
                    EngageSequenceStep.campaign_version_id == version.id,
                    EngageSequenceStep.enabled.is_(True),
                )
            )
            or 0
        )
        outreach = OutreachService(session, tenant, self._settings)
        record = await outreach.prepare_campaign_draft(
            cast(UUID, enrollment.contact_id),
            CampaignOutreachContext(
                step_instance_id=step.id,
                objective=sequence.objective,
                content_strategy=sequence.content_strategy,
                step_order=sequence.step_order,
                total_steps=total_steps,
                previous_sent_at=previous_sent_at,
                excluded_source_ids=frozenset(UUID(item) for item in enrollment.used_source_ids_json),
            ),
        )
        step.outreach_message_id = record.message.id
        step.prepared_at = now
        step.state = (
            CampaignStepState.PREPARED.value
            if version.approval_mode == CampaignApprovalMode.APPROVED_CAMPAIGN_AUTO_SEND.value
            else CampaignStepState.READY_FOR_REVIEW.value
        )
        step.safe_status_code = None
        step.worker_id = None
        step.lease_expires_at = None
        step.updated_at = now
        enrollment.state = CampaignEnrollmentState.ACTIVE.value
        enrollment.updated_at = now
        await session.commit()
        logger.info(
            "campaign_step_prepared",
            extra=self._log_context(campaign, enrollment, step, sequence, version),
        )

    async def _send(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        step: EngageEnrollmentStep,
        sequence: EngageSequenceStep,
        enrollment: EngageCampaignEnrollment,
        campaign: EngageCampaign,
        version: EngageCampaignVersion,
    ) -> None:
        if step.outreach_message_id is None:
            await self._block_step(session, step, enrollment, "campaign_draft_missing", attention=True)
            return
        outreach = OutreachService(session, tenant, self._settings)
        outreach_record = await outreach._message(step.outreach_message_id)
        if not await outreach.campaign_sources_are_current(
            cast(UUID, enrollment.contact_id), outreach_record.version.id
        ):
            await self._block_step(session, step, enrollment, "campaign_source_stale", attention=True)
            return
        campaign_repository = CampaignRepository(session)
        connection = await campaign_repository.active_email_connection_for_user(
            tenant.organisation_id, enrollment.sender_user_id
        )
        if connection is None:
            campaign.state = CampaignState.NEEDS_ATTENTION.value
            campaign.needs_attention_reason = "campaign_mailbox_unavailable"
            campaign.updated_at = datetime.now(UTC)
            await self._block_step(session, step, enrollment, "campaign_mailbox_unavailable", attention=True)
            return
        approved = await outreach.approve_campaign_authorized(
            step.outreach_message_id,
            OutreachApproveRequest(expected_version=outreach_record.message.current_version),
            campaign_step_id=step.id,
        )
        executions = ActionExecutionService(session, tenant, self._settings)
        preview = await executions.preview(approved.action_id, connection.id)
        execution = await executions.confirm(
            approved.action_id,
            ExecutionConfirmRequest(connection_id=connection.id, preview_id=preview.id, confirmed=True),
        )
        step.state = CampaignStepState.QUEUED.value
        step.safe_status_code = "simulation_queued" if execution.simulation_only else "provider_queued"
        step.worker_id = None
        step.lease_expires_at = None
        step.updated_at = datetime.now(UTC)
        await session.commit()
        logger.info(
            "campaign_step_queued",
            extra={
                **self._log_context(campaign, enrollment, step, sequence, version),
                "execution_id": str(execution.id),
                "simulation_only": execution.simulation_only,
            },
        )

    async def _reconcile(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        step: EngageEnrollmentStep,
        sequence: EngageSequenceStep,
        enrollment: EngageCampaignEnrollment,
        campaign: EngageCampaign,
        version: EngageCampaignVersion,
    ) -> None:
        if step.outreach_message_id is None:
            step.state = CampaignStepState.PENDING.value
            step.worker_id = None
            step.lease_expires_at = None
            await session.commit()
            return
        execution = await self._latest_execution(session, tenant.organisation_id, step.outreach_message_id)
        if execution is None:
            step.state = (
                CampaignStepState.PREPARED.value
                if version.approval_mode == CampaignApprovalMode.APPROVED_CAMPAIGN_AUTO_SEND.value
                else CampaignStepState.READY_FOR_REVIEW.value
            )
            step.worker_id = None
            step.lease_expires_at = None
            await session.commit()
            return
        if execution.execution_status in {"queued", "executing", "failed_retryable"}:
            step.state = CampaignStepState.QUEUED.value
            step.worker_id = None
            step.lease_expires_at = None
            await session.commit()
            return
        now = datetime.now(UTC)
        if execution.execution_status == "unknown_external_state":
            step.state = CampaignStepState.UNKNOWN_DELIVERY_STATE.value
            step.safe_status_code = "unknown_delivery_state"
            enrollment.state = CampaignEnrollmentState.NEEDS_ATTENTION.value
            enrollment.stop_reason = "unknown_delivery_state"
            enrollment.next_scheduled_at = None
            campaign.state = CampaignState.NEEDS_ATTENTION.value
            campaign.needs_attention_reason = "unknown_delivery_state"
            campaign.updated_at = now
            step.worker_id = None
            step.lease_expires_at = None
            await session.commit()
            return
        if execution.execution_status not in {"simulated_success", "succeeded"}:
            await self._block_step(
                session,
                step,
                enrollment,
                execution.safe_failure_code or "campaign_send_failed",
                attention=False,
            )
            await self._complete_campaign_if_terminal(session, campaign)
            return
        sent_at = execution.completed_at or now
        step.state = CampaignStepState.SENT.value
        step.sent_at = sent_at
        step.safe_status_code = "simulated" if execution.execution_mode == "simulation" else "provider_accepted"
        step.worker_id = None
        step.lease_expires_at = None
        step.updated_at = now
        outreach_record = await OutreachService(session, tenant, self._settings)._message(step.outreach_message_id)
        used = outreach_record.version.personalization_plan_json.get("sourceIds", [])
        if isinstance(used, list):
            enrollment.used_source_ids_json = list(
                dict.fromkeys([*enrollment.used_source_ids_json, *(str(item) for item in used)])
            )
        next_sequence = await session.scalar(
            select(EngageSequenceStep)
            .where(
                EngageSequenceStep.organisation_id == tenant.organisation_id,
                EngageSequenceStep.campaign_version_id == version.id,
                EngageSequenceStep.enabled.is_(True),
                EngageSequenceStep.step_order > sequence.step_order,
            )
            .order_by(EngageSequenceStep.step_order)
            .limit(1)
        )
        if next_sequence is None:
            enrollment.state = CampaignEnrollmentState.COMPLETED.value
            enrollment.next_scheduled_at = None
            enrollment.updated_at = now
            await session.commit()
            await self._complete_campaign_if_terminal(session, campaign)
            return
        scheduler = CampaignService(session, tenant, self._settings)
        scheduled = scheduler._next_send_time(
            CampaignService._as_utc(sent_at) + timedelta(days=next_sequence.delay_days), version
        )
        session.add(
            EngageEnrollmentStep(
                id=uuid.uuid4(),
                organisation_id=tenant.organisation_id,
                enrollment_id=enrollment.id,
                sequence_step_id=next_sequence.id,
                scheduled_at=scheduled,
                prepare_at=max(now, scheduled - timedelta(hours=self._settings.campaign_draft_preparation_hours)),
                state=CampaignStepState.PENDING.value,
                attempt_count=0,
                created_at=now,
                updated_at=now,
            )
        )
        enrollment.current_step_order = next_sequence.step_order
        enrollment.next_scheduled_at = scheduled
        enrollment.updated_at = now
        await session.commit()
        logger.info(
            "campaign_step_sent",
            extra={
                **self._log_context(campaign, enrollment, step, sequence, version),
                "execution_id": str(execution.id),
                "execution_mode": execution.execution_mode,
            },
        )

    async def _preflight(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        step: EngageEnrollmentStep,
        enrollment: EngageCampaignEnrollment,
        campaign: EngageCampaign,
        version: EngageCampaignVersion,
        *,
        check_frequency_limits: bool,
    ) -> tuple[Contact | None, OutreachPolicy | None]:
        outreach_repository = OutreachRepository(session)
        contact = (
            await outreach_repository.contact(tenant.organisation_id, enrollment.contact_id)
            if enrollment.contact_id is not None
            else None
        )
        if contact is None:
            await self._stop_enrollment(session, step, enrollment, "contact_deleted")
            return None, None
        if (
            contact.email is None
            or contact.email.casefold() != enrollment.recipient_email.casefold()
            or contact.company_id != enrollment.company_id
            or contact.job_title != enrollment.job_title_snapshot
        ):
            await self._block_step(session, step, enrollment, "campaign_recipient_context_changed", attention=True)
            return None, None
        policy = await outreach_repository.policy(tenant.organisation_id)
        if (
            policy is None
            or version.policy_fingerprint is None
            or CampaignService._policy_fingerprint(policy) != version.policy_fingerprint
        ):
            campaign.state = CampaignState.NEEDS_ATTENTION.value
            campaign.needs_attention_reason = "campaign_policy_changed"
            campaign.updated_at = datetime.now(UTC)
            await self._block_step(session, step, enrollment, "campaign_policy_changed", attention=True)
            return None, None
        result = await evaluate_contactability(
            outreach_repository,
            tenant,
            self._settings,
            contact,
            action_id=(
                (await self._outreach_action_id(session, tenant.organisation_id, step.outreach_message_id))
                if step.outreach_message_id is not None
                else None
            ),
            sender_user_id=enrollment.sender_user_id,
            check_frequency_limits=check_frequency_limits,
        )
        if result.state is OutreachContactability.QUOTA_REACHED:
            scheduler = CampaignService(session, tenant, self._settings)
            scheduled = scheduler._next_send_time(datetime.now(UTC) + timedelta(days=1), version)
            step.state = (
                CampaignStepState.PREPARED.value
                if step.outreach_message_id is not None
                else CampaignStepState.DEFERRED.value
            )
            step.scheduled_at = scheduled
            step.prepare_at = scheduled if step.outreach_message_id is None else step.prepare_at
            step.safe_status_code = "campaign_quota_deferred"
            step.worker_id = None
            step.lease_expires_at = None
            enrollment.next_scheduled_at = scheduled
            await session.commit()
            return None, None
        if result.state is OutreachContactability.COOLDOWN:
            scheduler = CampaignService(session, tenant, self._settings)
            scheduled = scheduler._next_send_time(
                datetime.now(UTC) + timedelta(hours=max(1, policy.cooldown_hours)), version
            )
            step.state = (
                CampaignStepState.PREPARED.value
                if step.outreach_message_id is not None
                else CampaignStepState.DEFERRED.value
            )
            step.scheduled_at = scheduled
            step.prepare_at = scheduled if step.outreach_message_id is None else step.prepare_at
            step.safe_status_code = "campaign_cooldown_deferred"
            step.worker_id = None
            step.lease_expires_at = None
            enrollment.next_scheduled_at = scheduled
            await session.commit()
            return None, None
        if not result.allowed:
            if result.state is OutreachContactability.SUPPRESSED:
                await self._stop_enrollment(session, step, enrollment, "suppressed")
            else:
                campaign.state = CampaignState.NEEDS_ATTENTION.value
                campaign.needs_attention_reason = result.state.value
                campaign.updated_at = datetime.now(UTC)
                await self._block_step(session, step, enrollment, result.state.value, attention=True)
            return None, None
        if version.stop_on_active_opportunity and await outreach_repository.has_active_opportunity(
            tenant.organisation_id, contact.company_id
        ):
            await self._stop_enrollment(session, step, enrollment, "active_opportunity")
            return None, None
        collision = await CampaignRepository(session).active_campaign_collision(
            tenant.organisation_id, contact.id, excluding_campaign_id=campaign.id
        )
        if collision:
            await self._block_step(session, step, enrollment, "active_campaign_collision", attention=True)
            return None, None
        return contact, policy

    async def _claimed_row(
        self, session: AsyncSession, claim: ClaimedCampaignStep
    ) -> (
        tuple[
            EngageEnrollmentStep,
            EngageSequenceStep,
            EngageCampaignEnrollment,
            EngageCampaign,
            EngageCampaignVersion,
        ]
        | None
    ):
        row = (
            await session.execute(
                select(
                    EngageEnrollmentStep,
                    EngageSequenceStep,
                    EngageCampaignEnrollment,
                    EngageCampaign,
                    EngageCampaignVersion,
                )
                .join(
                    EngageSequenceStep,
                    and_(
                        EngageSequenceStep.organisation_id == EngageEnrollmentStep.organisation_id,
                        EngageSequenceStep.id == EngageEnrollmentStep.sequence_step_id,
                    ),
                )
                .join(
                    EngageCampaignEnrollment,
                    and_(
                        EngageCampaignEnrollment.organisation_id == EngageEnrollmentStep.organisation_id,
                        EngageCampaignEnrollment.id == EngageEnrollmentStep.enrollment_id,
                    ),
                )
                .join(
                    EngageCampaign,
                    and_(
                        EngageCampaign.organisation_id == EngageCampaignEnrollment.organisation_id,
                        EngageCampaign.id == EngageCampaignEnrollment.campaign_id,
                    ),
                )
                .join(
                    EngageCampaignVersion,
                    and_(
                        EngageCampaignVersion.organisation_id == EngageCampaignEnrollment.organisation_id,
                        EngageCampaignVersion.id == EngageCampaignEnrollment.campaign_version_id,
                    ),
                )
                .where(
                    EngageEnrollmentStep.organisation_id == claim.organisation_id,
                    EngageEnrollmentStep.id == claim.step_instance_id,
                )
                .with_for_update()
            )
        ).one_or_none()
        if row is None:
            return None
        step = row[0]
        if (
            step.state != CampaignStepState.PROCESSING.value
            or step.worker_id != claim.worker_id
            or step.lease_expires_at is None
            or self._as_utc(step.lease_expires_at) <= datetime.now(UTC)
        ):
            return None
        return row[0], row[1], row[2], row[3], row[4]

    async def _fail_claim(self, session: AsyncSession, claim: ClaimedCampaignStep, code: str) -> None:
        await set_tenant_database_context(session, claim.organisation_id)
        row = (
            await session.execute(
                select(EngageEnrollmentStep, EngageCampaignEnrollment, EngageCampaign)
                .join(
                    EngageCampaignEnrollment,
                    and_(
                        EngageCampaignEnrollment.organisation_id == EngageEnrollmentStep.organisation_id,
                        EngageCampaignEnrollment.id == EngageEnrollmentStep.enrollment_id,
                    ),
                )
                .join(
                    EngageCampaign,
                    and_(
                        EngageCampaign.organisation_id == EngageCampaignEnrollment.organisation_id,
                        EngageCampaign.id == EngageCampaignEnrollment.campaign_id,
                    ),
                )
                .where(
                    EngageEnrollmentStep.organisation_id == claim.organisation_id,
                    EngageEnrollmentStep.id == claim.step_instance_id,
                    EngageEnrollmentStep.state == CampaignStepState.PROCESSING.value,
                    EngageEnrollmentStep.worker_id == claim.worker_id,
                )
                .with_for_update()
            )
        ).one_or_none()
        if row is None:
            await session.rollback()
            return
        now = datetime.now(UTC)
        step, enrollment, campaign = row
        step.state = CampaignStepState.BLOCKED.value
        step.safe_status_code = code[:64]
        step.worker_id = None
        step.lease_expires_at = None
        step.updated_at = now
        enrollment.state = CampaignEnrollmentState.NEEDS_ATTENTION.value
        enrollment.stop_reason = code[:64]
        enrollment.next_scheduled_at = None
        enrollment.updated_at = now
        campaign.state = CampaignState.NEEDS_ATTENTION.value
        campaign.needs_attention_reason = code[:64]
        campaign.updated_at = now
        await session.commit()

    async def _complete_campaign_if_terminal(self, session: AsyncSession, campaign: EngageCampaign) -> None:
        remaining = int(
            await session.scalar(
                select(func.count())
                .select_from(EngageCampaignEnrollment)
                .where(
                    EngageCampaignEnrollment.organisation_id == campaign.organisation_id,
                    EngageCampaignEnrollment.campaign_id == campaign.id,
                    EngageCampaignEnrollment.state.in_(("ready", "active", "paused", "needs_attention")),
                )
            )
            or 0
        )
        if remaining == 0 and campaign.state not in {"stopped", "completed"}:
            campaign.state = CampaignState.COMPLETED.value
            campaign.completed_at = datetime.now(UTC)
            campaign.updated_at = datetime.now(UTC)
        await session.commit()

    async def _block_step(
        self,
        session: AsyncSession,
        step: EngageEnrollmentStep,
        enrollment: EngageCampaignEnrollment,
        code: str,
        *,
        attention: bool,
    ) -> None:
        now = datetime.now(UTC)
        step.state = CampaignStepState.BLOCKED.value
        step.safe_status_code = code
        step.worker_id = None
        step.lease_expires_at = None
        step.updated_at = now
        enrollment.state = (
            CampaignEnrollmentState.NEEDS_ATTENTION.value if attention else CampaignEnrollmentState.BLOCKED.value
        )
        enrollment.stop_reason = code
        enrollment.next_scheduled_at = None
        enrollment.updated_at = now
        await session.commit()

    async def _stop_enrollment(
        self,
        session: AsyncSession,
        step: EngageEnrollmentStep,
        enrollment: EngageCampaignEnrollment,
        code: str,
    ) -> None:
        now = datetime.now(UTC)
        step.state = CampaignStepState.BLOCKED.value
        step.safe_status_code = code
        step.worker_id = None
        step.lease_expires_at = None
        step.updated_at = now
        enrollment.state = CampaignEnrollmentState.STOPPED.value
        enrollment.stop_reason = code
        enrollment.next_scheduled_at = None
        enrollment.updated_at = now
        await session.commit()

    @staticmethod
    async def _latest_execution(
        session: AsyncSession, organisation_id: UUID, outreach_id: UUID
    ) -> ActionExecution | None:
        return cast(
            ActionExecution | None,
            await session.scalar(
                select(ActionExecution)
                .join(
                    OutreachMessage,
                    and_(
                        OutreachMessage.organisation_id == ActionExecution.organisation_id,
                        OutreachMessage.action_id == ActionExecution.action_id,
                    ),
                )
                .where(
                    ActionExecution.organisation_id == organisation_id,
                    OutreachMessage.id == outreach_id,
                )
                .order_by(ActionExecution.created_at.desc())
                .limit(1)
            ),
        )

    @staticmethod
    async def _outreach_action_id(
        session: AsyncSession, organisation_id: UUID, outreach_id: UUID | None
    ) -> UUID | None:
        if outreach_id is None:
            return None
        return cast(
            UUID | None,
            await session.scalar(
                select(OutreachMessage.action_id).where(
                    OutreachMessage.organisation_id == organisation_id,
                    OutreachMessage.id == outreach_id,
                )
            ),
        )

    @staticmethod
    async def _approval_mode_for_step(session: AsyncSession, organisation_id: UUID, enrollment_id: UUID) -> str:
        return cast(
            str,
            await session.scalar(
                select(EngageCampaignVersion.approval_mode)
                .join(
                    EngageCampaignEnrollment,
                    and_(
                        EngageCampaignEnrollment.organisation_id == EngageCampaignVersion.organisation_id,
                        EngageCampaignEnrollment.campaign_version_id == EngageCampaignVersion.id,
                    ),
                )
                .where(
                    EngageCampaignVersion.organisation_id == organisation_id,
                    EngageCampaignEnrollment.id == enrollment_id,
                )
            ),
        )

    def _features_enabled(self) -> bool:
        return (
            self._settings.feature_engage_enabled
            and self._settings.feature_engage_campaigns_enabled
            and self._settings.feature_integrations_enabled
            and self._settings.feature_action_execution_enabled
            and self._settings.feature_action_layer_enabled
            and self._settings.environment != "production"
            and self._settings.feature_mock_connectors_enabled
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @staticmethod
    def _log_context(
        campaign: EngageCampaign,
        enrollment: EngageCampaignEnrollment,
        step: EngageEnrollmentStep,
        sequence: EngageSequenceStep,
        version: EngageCampaignVersion,
    ) -> dict[str, object]:
        return {
            "organisation_id": str(campaign.organisation_id),
            "campaign_id": str(campaign.id),
            "campaign_version": version.version,
            "enrollment_id": str(enrollment.id),
            "campaign_step_id": str(step.id),
            "sequence_step_order": sequence.step_order,
            "approval_mode": version.approval_mode,
            "step_state": step.state,
        }
