from __future__ import annotations

import math
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.commercial_contracts import (
    BillingInterval,
    CommercialModuleResponse,
    CommercialPlanResponse,
    CommercialProjectionResponse,
    CommercialStatus,
    CommercialTrialResponse,
    InternalPlanVersionResponse,
    ModuleAccess,
    ModuleCode,
    OperationalStatus,
    PlanCode,
)
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import (
    ActionExecution,
    CommercialPlanVersion,
    CommercialStateEvent,
    EngageCampaign,
    EngageCampaignEnrollment,
    EngageEnrollmentStep,
    Organisation,
    OrganisationCommercialState,
    OrganisationMembership,
    OrganisationModuleEntitlement,
    OutreachMessage,
    User,
)

TRIAL_LENGTH = timedelta(days=14)
TRIAL_GRACE = timedelta(days=30)
PLAN_NAMESPACE = UUID("12c90c95-e6f8-48fc-bb56-4d473215b4d9")
ALL_MODULES: tuple[ModuleCode, ...] = ("core", "prospect", "engage", "create", "crm")
MODULE_NAMES: dict[ModuleCode, str] = {
    "core": "Core",
    "prospect": "Prospect",
    "engage": "Engage",
    "create": "Create",
    "crm": "CRM connectors",
}


@dataclass(frozen=True)
class PlanDefinition:
    code: PlanCode
    display_name: str
    version: int
    monthly_price_amount: Decimal | None
    annual_price_amount: Decimal | None
    included_user_limit: int | None
    modules: tuple[ModuleCode, ...]

    @property
    def id(self) -> UUID:
        return uuid.uuid5(PLAN_NAMESPACE, f"{self.code}:v{self.version}")


PLAN_CATALOGUE: tuple[PlanDefinition, ...] = (
    PlanDefinition("core", "Core", 1, Decimal("200.00"), Decimal("2000.00"), 5, ("core",)),
    PlanDefinition(
        "growth",
        "Growth",
        1,
        Decimal("350.00"),
        Decimal("3500.00"),
        10,
        ("core", "prospect", "engage"),
    ),
    PlanDefinition(
        "complete",
        "Complete",
        1,
        Decimal("500.00"),
        Decimal("5000.00"),
        15,
        ALL_MODULES,
    ),
    PlanDefinition("enterprise", "Enterprise", 1, None, None, None, ALL_MODULES),
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def effective_status(state: OrganisationCommercialState, now: datetime) -> CommercialStatus:
    if state.status == "active":
        return "active"
    if state.status == "inactive":
        return "inactive"
    if state.status == "suspended":
        return "suspended"
    trial_ends_at = _aware(cast(datetime, state.trial_ends_at))
    grace_ends_at = _aware(cast(datetime, state.grace_ends_at))
    if now < trial_ends_at:
        return "trial_active"
    if now < grace_ends_at:
        return "grace"
    return "expired"


def effective_access(
    state: OrganisationCommercialState,
    entitlement: OrganisationModuleEntitlement | None,
    now: datetime,
) -> ModuleAccess:
    status = effective_status(state, now)
    if status in {"inactive", "suspended", "expired"} or entitlement is None:
        return "none"
    stored = cast(ModuleAccess, entitlement.access_level)
    if status == "grace" and stored != "none":
        return "read"
    return stored


async def ensure_plan_catalogue(session: AsyncSession) -> None:
    effective_from = datetime(2026, 9, 4, tzinfo=UTC)
    records = {record.id: record for record in (await session.scalars(select(CommercialPlanVersion))).all()}
    for definition in PLAN_CATALOGUE:
        expected = {
            "code": definition.code,
            "display_name": definition.display_name,
            "version": definition.version,
            "monthly_price_amount": definition.monthly_price_amount,
            "annual_price_amount": definition.annual_price_amount,
            "currency": "AUD",
            "included_user_limit": definition.included_user_limit,
            "modules_json": list(definition.modules),
            "status": "active",
        }
        existing = records.get(definition.id)
        if existing is None:
            session.add(
                CommercialPlanVersion(
                    id=definition.id,
                    effective_from=effective_from,
                    effective_to=None,
                    **expected,
                )
            )
            continue
        actual = {key: getattr(existing, key) for key in expected}
        if actual != expected:
            raise RuntimeError(f"Commercial plan {definition.code} v{definition.version} is not immutable.")
    await session.flush()


async def active_user_count(session: AsyncSession, organisation_id: UUID) -> int:
    value = await session.scalar(
        select(func.count())
        .select_from(OrganisationMembership)
        .join(User, User.id == OrganisationMembership.user_id)
        .where(
            OrganisationMembership.organisation_id == organisation_id,
            OrganisationMembership.status == "active",
            User.status == "active",
        )
    )
    return int(value or 0)


async def commercial_user_limit(
    session: AsyncSession,
    organisation_id: UUID,
    *,
    now: datetime,
    lock: bool = False,
) -> tuple[int | None, CommercialStatus]:
    statement = select(OrganisationCommercialState).where(
        OrganisationCommercialState.organisation_id == organisation_id
    )
    if lock:
        statement = statement.with_for_update()
    state = await session.scalar(statement)
    if state is None:
        raise PublicAPIError(
            "commercial_access_inactive",
            "Your organisation does not have an active plan or trial.",
            403,
        )
    status = effective_status(state, now)
    if status not in {"trial_active", "active"}:
        raise PublicAPIError(
            "commercial_access_inactive",
            "Your organisation cannot add active members in its current commercial state.",
            403,
        )
    plan = await session.get(CommercialPlanVersion, state.plan_version_id)
    if plan is None:
        raise PublicAPIError("commercial_state_invalid", "Commercial access is temporarily unavailable.", 503)
    return (state.custom_user_limit if plan.code == "enterprise" else plan.included_user_limit, status)


async def require_seat_available(
    session: AsyncSession,
    organisation_id: UUID,
    *,
    now: datetime,
) -> None:
    organisation = await session.scalar(
        select(Organisation).where(Organisation.id == organisation_id).with_for_update()
    )
    if organisation is None:
        raise PublicAPIError("organisation_not_found", "The organisation was not found.", 404)
    limit, _ = await commercial_user_limit(session, organisation_id, now=now, lock=True)
    count = await active_user_count(session, organisation_id)
    if limit is not None and count >= limit:
        raise PublicAPIError(
            "included_user_limit_reached",
            f"This organisation has reached its included limit of {limit} active users. Disable another member or contact support before adding one.",
            409,
        )


async def refresh_seat_limit_status(session: AsyncSession, organisation_id: UUID) -> None:
    state = await session.get(OrganisationCommercialState, organisation_id)
    if state is None:
        return
    plan = await session.get(CommercialPlanVersion, state.plan_version_id)
    if plan is None:
        return
    count = await active_user_count(session, organisation_id)
    limit = state.custom_user_limit if plan.code == "enterprise" else plan.included_user_limit
    state.seat_limit_status = "requires_resolution" if limit is not None and count > limit else "within_limit"


class CommercialService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self.session = session
        self.settings = settings
        self._now = now

    async def projection(self, organisation_id: UUID) -> CommercialProjectionResponse:
        await ensure_plan_catalogue(self.session)
        state = await self.session.get(OrganisationCommercialState, organisation_id)
        if state is None:
            raise PublicAPIError(
                "commercial_state_unavailable",
                "Commercial plan information is not available for this organisation.",
                404,
            )
        plan = await self.session.get(CommercialPlanVersion, state.plan_version_id)
        if plan is None:
            raise PublicAPIError("commercial_state_invalid", "Commercial plan information is unavailable.", 503)
        now = _aware(self._now())
        status = effective_status(state, now)
        entitlements = {
            cast(ModuleCode, row.module_key): row
            for row in (
                await self.session.scalars(
                    select(OrganisationModuleEntitlement).where(
                        OrganisationModuleEntitlement.organisation_id == organisation_id
                    )
                )
            ).all()
        }
        commercially_included = set(cast(list[ModuleCode], plan.modules_json)) | set(
            cast(list[ModuleCode], state.add_on_modules_json)
        )
        modules = [
            CommercialModuleResponse(
                code=module,
                display_name=MODULE_NAMES[module],
                access_level=effective_access(state, entitlements.get(module), now),
                commercially_included=module in commercially_included,
                operational_status=self._operational_status(module),
            )
            for module in ALL_MODULES
        ]
        count = await active_user_count(self.session, organisation_id)
        limit = state.custom_user_limit if plan.code == "enterprise" else plan.included_user_limit
        seat_status: Literal["within_limit", "requires_resolution"] = (
            "requires_resolution" if limit is not None and count > limit else "within_limit"
        )
        seats_available = None if limit is None else max(0, limit - count)
        trial_end = _aware(state.trial_ends_at) if state.trial_ends_at is not None else None
        remaining = 0
        if status == "trial_active" and trial_end is not None:
            remaining = min(14, max(0, math.ceil((trial_end - now).total_seconds() / 86_400)))
        can_create = status in {"trial_active", "active"}
        return CommercialProjectionResponse(
            plan=CommercialPlanResponse(
                code=cast(PlanCode, plan.code), display_name=plan.display_name, version=plan.version
            ),
            status=status,
            billing_interval=cast(BillingInterval | None, state.billing_interval),
            trial=CommercialTrialResponse(
                started_at=_aware(state.trial_started_at) if state.trial_started_at is not None else None,
                ends_at=trial_end,
                grace_ends_at=_aware(state.grace_ends_at) if state.grace_ends_at is not None else None,
                days_remaining=remaining,
            ),
            included_user_limit=limit,
            active_user_count=count,
            seats_available=seats_available,
            seat_limit_status=seat_status,
            modules=modules,
            effective_at=_aware(state.effective_at),
            state_version=state.lock_version,
            can_create_new_work=can_create,
            read_access_ends_at=_aware(state.grace_ends_at) if status == "grace" and state.grace_ends_at else None,
            message=self._status_message(status),
        )

    async def module_access(
        self,
        organisation_id: UUID,
        module: ModuleCode,
        *,
        lock_for_write: bool = False,
    ) -> ModuleAccess:
        state_statement = select(OrganisationCommercialState).where(
            OrganisationCommercialState.organisation_id == organisation_id
        )
        if lock_for_write:
            state_statement = state_statement.with_for_update(read=True)
        state = await self.session.scalar(state_statement)
        if state is None:
            return "none"
        entitlement = await self.session.get(OrganisationModuleEntitlement, (organisation_id, module))
        return effective_access(state, entitlement, _aware(self._now()))

    async def require_module_write(self, organisation_id: UUID, module: ModuleCode) -> None:
        if await self.module_access(organisation_id, module, lock_for_write=True) != "write":
            raise PublicAPIError(
                f"{module}_not_in_plan",
                f"{MODULE_NAMES[module]} isn't included in your organisation's current plan.",
                403,
            )

    async def start_trial(
        self,
        organisation_id: UUID,
        *,
        actor_reference: str,
        reason: str,
        expected_lock_version: int = 0,
    ) -> CommercialProjectionResponse:
        actor_reference, reason = self._validate_operator_metadata(actor_reference, reason)
        now = _aware(self._now())
        await ensure_plan_catalogue(self.session)
        await self._lock_organisation(organisation_id)
        state = await self.session.scalar(
            select(OrganisationCommercialState)
            .where(OrganisationCommercialState.organisation_id == organisation_id)
            .with_for_update()
        )
        if state is not None and state.lock_version != expected_lock_version:
            raise PublicAPIError("commercial_state_stale", "Commercial state changed; inspect it and retry.", 409)
        if state is not None and state.trial_used_at is not None:
            raise PublicAPIError("trial_already_used", "This organisation has already used its trial.", 409)
        plan = await self._plan("complete")
        if state is None:
            state = OrganisationCommercialState(
                organisation_id=organisation_id,
                plan_version_id=plan.id,
                status="trial",
                billing_interval=None,
                trial_started_at=now,
                trial_ends_at=now + TRIAL_LENGTH,
                grace_ends_at=now + TRIAL_LENGTH + TRIAL_GRACE,
                trial_used_at=now,
                custom_user_limit=None,
                add_on_modules_json=[],
                effective_at=now,
                source="manual_support",
                actor_reference=actor_reference,
                reason=reason,
                lock_version=1,
            )
            self.session.add(state)
            await self.session.flush()
        else:
            self._apply_state(
                state,
                plan=plan,
                status="trial",
                billing_interval=None,
                custom_user_limit=None,
                add_ons=(),
                now=now,
                actor_reference=actor_reference,
                reason=reason,
            )
            state.trial_started_at = now
            state.trial_ends_at = now + TRIAL_LENGTH
            state.grace_ends_at = now + TRIAL_LENGTH + TRIAL_GRACE
            state.trial_used_at = now
        count = await active_user_count(self.session, organisation_id)
        state.seat_limit_status = "requires_resolution" if count > 15 else "within_limit"
        await self._sync_entitlements(state, plan, (), source="trial", now=now)
        await self._add_event(state, plan, "trial_started", "trial_active", count)
        await self._commit(organisation_id, "The trial could not be started.")
        return await self.projection(organisation_id)

    async def assign_plan(
        self,
        organisation_id: UUID,
        *,
        plan_code: PlanCode,
        billing_interval: BillingInterval,
        actor_reference: str,
        reason: str,
        expected_lock_version: int,
        add_ons: Iterable[ModuleCode] = (),
        custom_user_limit: int | None = None,
    ) -> CommercialProjectionResponse:
        actor_reference, reason = self._validate_operator_metadata(actor_reference, reason)
        now = _aware(self._now())
        requested_add_ons = tuple(sorted(set(add_ons)))
        invalid = set(requested_add_ons) - set(ALL_MODULES[1:])
        if invalid:
            raise PublicAPIError("invalid_add_on", "Only approved module add-ons may be assigned.", 422)
        if plan_code == "enterprise":
            if custom_user_limit is None or custom_user_limit < 1:
                raise PublicAPIError(
                    "enterprise_user_limit_required", "Enterprise requires an approved custom user limit.", 422
                )
        elif custom_user_limit is not None:
            raise PublicAPIError("custom_user_limit_not_allowed", "This plan has a fixed included-user limit.", 422)
        await ensure_plan_catalogue(self.session)
        await self._lock_organisation(organisation_id)
        state = await self.session.scalar(
            select(OrganisationCommercialState)
            .where(OrganisationCommercialState.organisation_id == organisation_id)
            .with_for_update()
        )
        if state is None and expected_lock_version != 0:
            raise PublicAPIError("commercial_state_stale", "Commercial state changed; inspect it and retry.", 409)
        if state is not None and state.lock_version != expected_lock_version:
            raise PublicAPIError("commercial_state_stale", "Commercial state changed; inspect it and retry.", 409)
        plan = await self._plan(plan_code)
        previous_plan_id = state.plan_version_id if state is not None else None
        trial_used_at = state.trial_used_at if state is not None else None
        if state is None:
            state = OrganisationCommercialState(
                organisation_id=organisation_id,
                plan_version_id=plan.id,
                status="active",
                billing_interval=billing_interval,
                trial_used_at=trial_used_at,
                custom_user_limit=custom_user_limit,
                add_on_modules_json=list(requested_add_ons),
                effective_at=now,
                source="manual_support",
                actor_reference=actor_reference,
                reason=reason,
                lock_version=1,
            )
            self.session.add(state)
            await self.session.flush()
        else:
            self._apply_state(
                state,
                plan=plan,
                status="active",
                billing_interval=billing_interval,
                custom_user_limit=custom_user_limit,
                add_ons=requested_add_ons,
                now=now,
                actor_reference=actor_reference,
                reason=reason,
            )
        count = await active_user_count(self.session, organisation_id)
        limit = custom_user_limit if plan.code == "enterprise" else plan.included_user_limit
        state.seat_limit_status = "requires_resolution" if limit is not None and count > limit else "within_limit"
        await self._sync_entitlements(state, plan, requested_add_ons, source="commercial_plan", now=now)
        event_type = "plan_assigned" if previous_plan_id is None else "plan_changed"
        await self._add_event(state, plan, event_type, "active", count)
        await self._commit(organisation_id, "The commercial plan could not be assigned.")
        return await self.projection(organisation_id)

    async def change_state(
        self,
        organisation_id: UUID,
        *,
        status: Literal["inactive", "suspended"],
        actor_reference: str,
        reason: str,
        expected_lock_version: int,
    ) -> CommercialProjectionResponse:
        actor_reference, reason = self._validate_operator_metadata(actor_reference, reason)
        now = _aware(self._now())
        await self._lock_organisation(organisation_id)
        state = await self.session.scalar(
            select(OrganisationCommercialState)
            .where(OrganisationCommercialState.organisation_id == organisation_id)
            .with_for_update()
        )
        if state is None:
            raise PublicAPIError("commercial_state_unavailable", "Commercial state was not found.", 404)
        if state.lock_version != expected_lock_version:
            raise PublicAPIError("commercial_state_stale", "Commercial state changed; inspect it and retry.", 409)
        plan = await self.session.get(CommercialPlanVersion, state.plan_version_id)
        if plan is None:
            raise PublicAPIError("commercial_state_invalid", "Commercial plan information is unavailable.", 503)
        state.status = status
        state.effective_at = now
        state.actor_reference = actor_reference
        state.reason = reason
        state.source = "manual_support"
        state.lock_version += 1
        count = await active_user_count(self.session, organisation_id)
        await self._add_event(state, plan, "state_changed", status, count)
        await self._commit(organisation_id, "The commercial state could not be changed.")
        return await self.projection(organisation_id)

    async def catalogue(self) -> list[InternalPlanVersionResponse]:
        await ensure_plan_catalogue(self.session)
        rows = (
            await self.session.scalars(
                select(CommercialPlanVersion).order_by(CommercialPlanVersion.version, CommercialPlanVersion.code)
            )
        ).all()
        return [
            InternalPlanVersionResponse(
                id=str(row.id),
                code=cast(PlanCode, row.code),
                display_name=row.display_name,
                version=row.version,
                monthly_price_amount=str(row.monthly_price_amount) if row.monthly_price_amount is not None else None,
                annual_price_amount=str(row.annual_price_amount) if row.annual_price_amount is not None else None,
                currency="AUD",
                included_user_limit=row.included_user_limit,
                modules=cast(list[ModuleCode], row.modules_json),
                status=cast(Literal["active", "retired"], row.status),
            )
            for row in rows
        ]

    async def _plan(self, code: PlanCode) -> CommercialPlanVersion:
        plan = await self.session.scalar(
            select(CommercialPlanVersion)
            .where(
                CommercialPlanVersion.code == code,
                CommercialPlanVersion.status == "active",
            )
            .order_by(CommercialPlanVersion.version.desc())
        )
        if plan is None:
            raise PublicAPIError("commercial_catalogue_unavailable", "Commercial plan information is unavailable.", 503)
        return plan

    async def _lock_organisation(self, organisation_id: UUID) -> None:
        organisation = await self.session.scalar(
            select(Organisation).where(Organisation.id == organisation_id).with_for_update()
        )
        if organisation is None:
            raise PublicAPIError("organisation_not_found", "The organisation was not found.", 404)

    def _apply_state(
        self,
        state: OrganisationCommercialState,
        *,
        plan: CommercialPlanVersion,
        status: str,
        billing_interval: BillingInterval | None,
        custom_user_limit: int | None,
        add_ons: tuple[ModuleCode, ...],
        now: datetime,
        actor_reference: str,
        reason: str,
    ) -> None:
        state.plan_version_id = plan.id
        state.status = status
        state.billing_interval = billing_interval
        state.custom_user_limit = custom_user_limit
        state.add_on_modules_json = list(add_ons)
        state.effective_at = now
        state.source = "manual_support"
        state.actor_reference = actor_reference
        state.reason = reason
        state.lock_version += 1

    async def _sync_entitlements(
        self,
        state: OrganisationCommercialState,
        plan: CommercialPlanVersion,
        add_ons: tuple[ModuleCode, ...],
        *,
        source: Literal["commercial_plan", "trial"],
        now: datetime,
    ) -> None:
        plan_modules = set(cast(list[ModuleCode], plan.modules_json))
        target_modules = plan_modules | set(add_ons)
        engage_was_writable = False
        for module in ALL_MODULES:
            entitlement = await self.session.get(OrganisationModuleEntitlement, (state.organisation_id, module))
            target_write = module in target_modules
            previous_level = entitlement.access_level if entitlement is not None else "none"
            if module == "engage" and previous_level == "write":
                engage_was_writable = True
            target_level = "write" if target_write else ("read" if previous_level != "none" else "none")
            module_source = "add_on" if module in add_ons and module not in plan_modules else source
            if entitlement is None:
                entitlement = OrganisationModuleEntitlement(
                    organisation_id=state.organisation_id,
                    module_key=module,
                    enabled=target_write,
                    access_level=target_level,
                    source=module_source,
                    configured_by_user_id=None,
                    configured_by_actor=state.actor_reference,
                    enabled_at=now if target_write else None,
                    disabled_at=None if target_write else now,
                )
                self.session.add(entitlement)
            else:
                entitlement.enabled = target_write
                entitlement.access_level = target_level
                entitlement.source = module_source
                entitlement.configured_by_user_id = None
                entitlement.configured_by_actor = state.actor_reference
                entitlement.enabled_at = now if target_write else entitlement.enabled_at
                entitlement.disabled_at = None if target_write else now
        if engage_was_writable and "engage" not in target_modules:
            await self._halt_engage_work(state.organisation_id, now)

    async def _halt_engage_work(self, organisation_id: UUID, now: datetime) -> None:
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
                safe_failure_code="engage_not_in_plan",
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
                safe_status_code="engage_not_in_plan",
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
                stop_reason="engage_not_in_plan",
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
            .values(state="needs_attention", needs_attention_reason="engage_not_in_plan", updated_at=now)
        )

    async def _add_event(
        self,
        state: OrganisationCommercialState,
        plan: CommercialPlanVersion,
        event_type: str,
        status: str,
        count: int,
    ) -> None:
        entitlement_rows = (
            await self.session.scalars(
                select(OrganisationModuleEntitlement).where(
                    OrganisationModuleEntitlement.organisation_id == state.organisation_id
                )
            )
        ).all()
        readable = (
            []
            if status in {"inactive", "suspended", "expired"}
            else sorted(row.module_key for row in entitlement_rows if row.access_level != "none")
        )
        entitled = sorted(
            set(cast(list[ModuleCode], plan.modules_json)) | set(cast(list[ModuleCode], state.add_on_modules_json))
        )
        limit = state.custom_user_limit if plan.code == "enterprise" else plan.included_user_limit
        self.session.add(
            CommercialStateEvent(
                id=uuid.uuid4(),
                organisation_id=state.organisation_id,
                plan_version_id=plan.id,
                event_type=event_type,
                effective_status=status,
                billing_interval=state.billing_interval,
                entitled_modules_json=entitled,
                readable_modules_json=readable,
                included_user_limit=limit,
                active_user_count=count,
                seat_limit_status=state.seat_limit_status,
                trial_started_at=state.trial_started_at,
                trial_ends_at=state.trial_ends_at,
                grace_ends_at=state.grace_ends_at,
                effective_at=state.effective_at,
                source=state.source,
                actor_reference=state.actor_reference,
                reason=state.reason,
                state_version=state.lock_version,
            )
        )

    async def _commit(self, organisation_id: UUID, message: str) -> None:
        try:
            await self.session.commit()
            await set_tenant_database_context(self.session, organisation_id)
        except (IntegrityError, SQLAlchemyError, RuntimeError) as exc:
            await self.session.rollback()
            raise PublicAPIError("commercial_state_conflict", message, 409) from exc

    def _operational_status(self, module: ModuleCode) -> OperationalStatus:
        if module == "core":
            return "available"
        flags = {
            "prospect": self.settings.feature_prospect_enabled,
            "engage": self.settings.feature_engage_enabled,
            "create": self.settings.feature_create_enabled,
            "crm": self.settings.feature_hubspot_crm_enabled,
        }
        if not flags[module]:
            return "unavailable"
        if module == "prospect" and self.settings.prospect_research_provider_name == "mock":
            return "mock_only"
        if module == "engage":
            return "mock_only"
        return "available"

    @staticmethod
    def _validate_operator_metadata(actor_reference: str, reason: str) -> tuple[str, str]:
        actor = actor_reference.strip()
        explanation = reason.strip()
        if not actor or len(actor) > 200 or not actor.isprintable():
            raise PublicAPIError(
                "invalid_operator_reference",
                "A printable operator reference between 1 and 200 characters is required.",
                422,
            )
        if not explanation or len(explanation) > 500 or not explanation.isprintable():
            raise PublicAPIError(
                "invalid_commercial_reason",
                "A printable reason between 1 and 500 characters is required.",
                422,
            )
        return actor, explanation

    @staticmethod
    def _status_message(status: CommercialStatus) -> str:
        if status == "trial_active":
            return (
                "Your 14-day trial is active. No payment method is required and you will not be charged automatically."
            )
        if status == "grace":
            return (
                "Your trial has ended. Your workspace remains available for viewing and export during the grace period."
            )
        if status == "expired":
            return "Your trial and viewing grace period have ended. Contact support to reactivate the workspace."
        if status == "active":
            return "Your organisation's plan is active."
        if status == "suspended":
            return "Your organisation's commercial access is suspended. Contact support for help."
        return "Your organisation's commercial access is inactive. Contact support to reactivate it."
