from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import stat
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from revenueos.auth import identity_organisation_id, identity_user_id
from revenueos.billing_provider import build_billing_provider
from revenueos.billing_services import authoritative_provider_prices
from revenueos.commercial_services import (
    PLAN_CATALOGUE,
    CommercialService,
    ensure_plan_catalogue,
    require_seat_available,
)
from revenueos.config import Settings, get_settings
from revenueos.credit_services import LARGE_MANUAL_PAID_GRANT_CREDITS, MAX_CREDITS, CreditService
from revenueos.database import create_engine, create_session_factory, set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import (
    ActionExecution,
    AIJob,
    CommercialPlanVersion,
    CommercialStateEvent,
    CreatePresentationVersion,
    CreateTemplateVersion,
    CRMImportBatch,
    CRMRecordMerge,
    EngageEnrollmentStep,
    OnboardingProgress,
    OperatorProvisioningEvent,
    Organisation,
    OrganisationBetaSettings,
    OrganisationCommercialState,
    OrganisationCreditBalance,
    OrganisationCRMSetting,
    OrganisationMembership,
    OrganisationModuleEntitlement,
    ProspectResearchRun,
    SalesPipeline,
    User,
)
from revenueos.routes.health import EXPECTED_MIGRATION_HEAD
from revenueos.visual_storage import VisualStorageError, create_visual_storage

CheckStatus = Literal["pass", "fail"]
AddOnModule = Literal["prospect", "engage", "create", "crm"]


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    status: CheckStatus
    detail: str


@dataclass(frozen=True)
class ProvisioningResult:
    organisation_id: str
    user_id: str
    action: str
    already_applied: bool


def _hash_key(value: str) -> str:
    stripped = value.strip()
    if len(stripped) < 8 or len(stripped) > 200:
        raise ValueError("Idempotency keys must contain 8 to 200 characters.")
    return hashlib.sha256(stripped.encode("utf-8")).hexdigest()


def _normalise_email(value: str) -> str:
    try:
        return validate_email(value, check_deliverability=False).normalized.casefold()
    except EmailNotValidError as exc:
        raise ValueError("A valid administrator business email is required.") from exc


def _validate_operator_reference(value: str) -> str:
    resolved = value.strip()
    if not resolved or len(resolved) > 200 or any(ord(character) < 32 for character in resolved):
        raise ValueError("Operator reference must contain 1 to 200 printable characters.")
    return resolved


def _validate_manual_paid_reason(value: str) -> str:
    resolved = value.strip()
    if (
        len(resolved) < 8
        or len(resolved) > 500
        or any(ord(character) < 32 for character in resolved)
        or "<" in resolved
        or ">" in resolved
    ):
        raise ValueError("Reason must contain 8 to 500 characters of plain printable text.")
    return resolved


def _validate_manual_paid_operator_reference(value: str) -> str:
    resolved = _validate_operator_reference(value)
    if "<" in resolved or ">" in resolved:
        raise ValueError("Operator reference must be plain printable text.")
    return resolved


class _StoreOnce(argparse.Action):
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: object,
        option_string: str | None = None,
    ) -> None:
        marker = f"_provided_once_{self.dest}"
        if getattr(namespace, marker, False):
            raise argparse.ArgumentError(self, f"{option_string or self.dest} may be supplied only once")
        setattr(namespace, self.dest, values)
        setattr(namespace, marker, True)


def _parse_exact_amount_minor_units(value: str) -> int:
    candidate = value.strip()
    if len(candidate) > 32 or re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", candidate) is None:
        raise argparse.ArgumentTypeError("Amount received must be a plain exact decimal with up to two places.")
    try:
        amount = Decimal(candidate)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError("Amount received must be an exact decimal value.") from exc
    if not amount.is_finite() or amount <= 0:
        raise argparse.ArgumentTypeError("Amount received must be positive with no more than two decimal places.")
    minor_units = amount * 100
    if minor_units != minor_units.to_integral_value() or minor_units > 9_000_000_000_000:
        raise argparse.ArgumentTypeError("Amount received exceeds the supported exact AUD range.")
    return int(minor_units)


def _parse_credit_quantity(value: str) -> int:
    candidate = value.strip()
    if len(candidate) > 13 or not candidate.isascii() or not candidate.isdecimal():
        raise argparse.ArgumentTypeError("Credits must be a plain integer.")
    try:
        credits = int(candidate)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Credits must be an integer.") from exc
    if credits <= 0 or credits > MAX_CREDITS:
        raise argparse.ArgumentTypeError("Credits must be positive and within the supported technical bound.")
    return credits


def _parse_aware_datetime(value: str) -> datetime:
    candidate = value.strip()
    try:
        parsed = datetime.fromisoformat(candidate[:-1] + "+00:00" if candidate.endswith("Z") else candidate)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use an ISO 8601 payment timestamp with a timezone.") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("The payment timestamp must include a timezone.")
    return parsed


def _format_minor_units(amount_minor_units: int) -> str:
    return f"{Decimal(amount_minor_units) / Decimal(100):.2f}"


def _manual_paid_confirmation(
    organisation_id: uuid.UUID,
    credits: int,
    amount_received_minor_units: int,
    currency: str,
    payment_method: str,
    payment_reference: str,
    payment_received_at: datetime,
    operator_reference: str,
    reason: str,
) -> str:
    received_at = payment_received_at.astimezone(UTC).isoformat()
    review_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "organisationId": str(organisation_id),
                "credits": credits,
                "amountReceivedMinorUnits": amount_received_minor_units,
                "currency": currency,
                "paymentMethod": payment_method,
                "paymentReference": payment_reference.strip(),
                "paymentReceivedAt": received_at,
                "operatorReference": operator_reference.strip(),
                "reason": reason.strip(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:16]
    return (
        f"GRANT {credits} PAID CREDITS TO {organisation_id} FOR "
        f"{currency} {_format_minor_units(amount_received_minor_units)} VIA {payment_method} "
        f"RECEIVED {received_at} REF {payment_reference.strip()} REVIEW {review_fingerprint}"
    )


async def manual_paid_credit_grant_preview(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    organisation_id: uuid.UUID,
    credits: int,
    amount_received_minor_units: int,
    currency: str,
    payment_method: str,
    payment_reference: str,
    payment_received_at: datetime,
    operator_reference: str,
    reason: str,
) -> dict[str, object]:
    reference = payment_reference.strip()
    operator = _validate_manual_paid_operator_reference(operator_reference)
    resolved_reason = _validate_manual_paid_reason(reason)
    if (
        not 1 <= len(reference) <= 120
        or not reference[0].isalnum()
        or not all(character.isascii() and (character.isalnum() or character in " ._:/#-") for character in reference)
    ):
        raise PublicAPIError(
            "manual_paid_credit_reference_invalid",
            "Use a bounded payment or invoice reference with ordinary printable characters.",
            422,
        )
    if payment_received_at.astimezone(UTC) > datetime.now(UTC) + timedelta(minutes=5):
        raise PublicAPIError(
            "manual_paid_credit_received_at_invalid",
            "The cleared-funds timestamp cannot be in the future.",
            422,
        )
    async with session_factory() as session:
        await set_tenant_database_context(session, organisation_id)
        organisation = await session.scalar(select(Organisation).where(Organisation.id == organisation_id))
        if organisation is None:
            raise PublicAPIError(
                "manual_paid_credit_organisation_invalid", "The target organisation is unavailable.", 404
            )
        commercial = await session.get(OrganisationCommercialState, organisation_id)
        if commercial is None or commercial.status == "inactive":
            raise PublicAPIError(
                "manual_paid_credit_organisation_inactive",
                "Paid Credits cannot be granted to an inactive organisation.",
                409,
            )
        active_members = await session.scalar(
            select(func.count())
            .select_from(OrganisationMembership)
            .join(User, User.id == OrganisationMembership.user_id)
            .where(
                OrganisationMembership.organisation_id == organisation_id,
                OrganisationMembership.status == "active",
                User.status == "active",
            )
        )
        if not active_members:
            raise PublicAPIError(
                "manual_paid_credit_organisation_disabled",
                "Paid Credits cannot be granted to an organisation without an active member.",
                409,
            )
        plan = await session.get(CommercialPlanVersion, commercial.plan_version_id)
        balance = await session.get(OrganisationCreditBalance, organisation_id)
        purchased_available = balance.purchased_available if balance is not None else 0
        promotional_available = balance.promotional_available if balance is not None else 0
        reserved = balance.purchased_reserved + balance.promotional_reserved if balance is not None else 0
        expected_version = balance.lock_version if balance is not None else 0
        return {
            "status": "ready_for_confirmation",
            "operation": "grant_manual_paid_credits",
            "organisation": {
                "id": str(organisation.id),
                "name": organisation.name,
                "commercialStatus": commercial.status,
                "plan": plan.code if plan is not None else "unavailable",
            },
            "creditsToGrant": credits,
            "amountReceivedMinorUnits": amount_received_minor_units,
            "amountReceived": f"{currency} {_format_minor_units(amount_received_minor_units)}",
            "currency": currency,
            "paymentMethod": payment_method,
            "paymentReference": reference,
            "paymentReceivedAt": payment_received_at.astimezone(UTC).isoformat(),
            "operatorReference": operator,
            "reason": resolved_reason,
            "currentCreditBalance": {
                "available": purchased_available + promotional_available,
                "purchasedAvailable": purchased_available,
                "promotionalAvailable": promotional_available,
                "reserved": reserved,
                "lockVersion": expected_version,
            },
            "expectedBalanceVersion": expected_version,
            "largeGrantWarning": (
                "This is a large manual paid Credit grant. Confirm the values carefully."
                if credits >= LARGE_MANUAL_PAID_GRANT_CREDITS
                else None
            ),
            "clearedFundsRequired": True,
            "confirmationRequired": _manual_paid_confirmation(
                organisation_id,
                credits,
                amount_received_minor_units,
                currency,
                payment_method,
                reference,
                payment_received_at,
                operator,
                resolved_reason,
            ),
            "providerExecutionAuthorisedByGrant": False,
            "marginReviewStatus": "production_execution_blocked_pending_policy",
        }


def _add_manual_paid_purchase_arguments(parser: argparse.ArgumentParser, *, execute: bool) -> None:
    parser.add_argument("--organisation-id", required=True, type=uuid.UUID, action=_StoreOnce)
    parser.add_argument("--credits", required=True, type=_parse_credit_quantity, action=_StoreOnce)
    parser.add_argument(
        "--amount-received",
        required=True,
        type=_parse_exact_amount_minor_units,
        action=_StoreOnce,
    )
    parser.add_argument("--currency", required=True, choices=("AUD",), action=_StoreOnce)
    parser.add_argument(
        "--payment-method",
        required=True,
        choices=("BANK_TRANSFER", "CARD_OUTSIDE_AUTOMATIC_FLOW", "OTHER_APPROVED"),
        action=_StoreOnce,
    )
    parser.add_argument("--payment-reference", required=True, action=_StoreOnce)
    parser.add_argument("--payment-received-at", required=True, type=_parse_aware_datetime, action=_StoreOnce)
    parser.add_argument("--operator-reference", required=True, action=_StoreOnce)
    parser.add_argument("--reason", required=True, action=_StoreOnce)
    if execute:
        parser.add_argument("--expected-balance-version", required=True, type=int, action=_StoreOnce)
        parser.add_argument("--idempotency-key", required=True, action=_StoreOnce)
        parser.add_argument("--cleared-funds-confirmed", action="count", default=0)
        parser.add_argument("--large-grant-reviewed", action="count", default=0)
        parser.add_argument("--confirm", required=True, action=_StoreOnce)


async def inspect_runtime_database(engine: AsyncEngine) -> list[PreflightCheck]:
    checks: list[PreflightCheck] = []
    try:
        async with engine.connect() as connection:
            role = (
                (
                    await connection.execute(
                        text(
                            """SELECT current_user AS role_name, roles.rolsuper AS is_superuser,
                    roles.rolbypassrls AS bypasses_rls
                    FROM pg_roles AS roles WHERE roles.rolname = current_user"""
                        )
                    )
                )
                .mappings()
                .one()
            )
            checks.append(
                PreflightCheck(
                    "database_runtime_role",
                    "pass" if not role.is_superuser and not role.bypasses_rls else "fail",
                    "Runtime role is non-superuser and does not bypass RLS."
                    if not role.is_superuser and not role.bypasses_rls
                    else "Runtime role has superuser or BYPASSRLS privilege.",
                )
            )
            migration = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            checks.append(
                PreflightCheck(
                    "database_migration_head",
                    "pass" if migration == EXPECTED_MIGRATION_HEAD else "fail",
                    f"Migration head is {migration}."
                    if migration == EXPECTED_MIGRATION_HEAD
                    else "Migration head is stale.",
                )
            )
            before = await connection.scalar(text("SELECT current_setting('app.organisation_id', true)"))
            await connection.commit()
            probe_organisation_id = uuid.uuid4()
            async with connection.begin():
                await connection.execute(
                    text("SELECT set_config('app.organisation_id', :organisation_id, true)"),
                    {"organisation_id": str(probe_organisation_id)},
                )
                during = await connection.scalar(text("SELECT current_setting('app.organisation_id', true)"))
            after = await connection.scalar(text("SELECT current_setting('app.organisation_id', true)"))
            clean_before = before in {None, ""}
            clean_after = after in {None, ""}
            checks.append(
                PreflightCheck(
                    "database_tenant_context_reset",
                    "pass" if clean_before and str(during) == str(probe_organisation_id) and clean_after else "fail",
                    "Transaction-local tenant context is absent before and after the probe."
                    if clean_before and str(during) == str(probe_organisation_id) and clean_after
                    else "Transaction-local tenant context leaked or could not be established.",
                )
            )
    except (OSError, SQLAlchemyError):
        return [PreflightCheck("database_connectivity", "fail", "Database safety inspection failed.")]
    return checks


async def inspect_object_storage(settings: Settings) -> PreflightCheck:
    storage = create_visual_storage(settings)
    key = f"operations/preflight/{uuid.uuid4()}.probe"
    content = b"revenueos-storage-preflight-v1"
    try:
        await storage.write(key, content, "application/octet-stream")
        restored = await storage.read(key)
        await storage.delete(key)
        remaining = await storage.list_keys(key)
    except (OSError, VisualStorageError):
        return PreflightCheck("private_object_storage", "fail", "Private object storage probe failed.")
    passed = restored == content and not remaining
    return PreflightCheck(
        "private_object_storage",
        "pass" if passed else "fail",
        "Private object storage write/read/delete probe passed."
        if passed
        else "Object storage integrity probe failed.",
    )


async def inspect_export_storage(settings: Settings) -> PreflightCheck:
    if settings.visual_storage_backend == "s3_compatible":
        storage = create_visual_storage(settings)
        key = f"operations/preflight/exports/{uuid.uuid4()}.probe"
        content = b"revenueos-export-preflight-v1"
        try:
            await storage.write(key, content, "application/octet-stream")
            restored = await storage.read(key)
            await storage.delete(key)
            remaining = await storage.list_keys(key)
        except (OSError, VisualStorageError):
            return PreflightCheck("private_export_storage", "fail", "Private export object storage probe failed.")
        passed = restored == content and not remaining
        return PreflightCheck(
            "private_export_storage",
            "pass" if passed else "fail",
            "Private export object storage write/read/delete probe passed."
            if passed
            else "Private export object storage integrity probe failed.",
        )

    root = Path(settings.private_beta_export_directory).resolve()
    probe = root / f".revenueos-preflight-{uuid.uuid4().hex}"
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
        descriptor = os.open(probe, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, b"revenueos-export-preflight-v1")
        finally:
            os.close(descriptor)
        directory_mode = stat.S_IMODE(root.stat().st_mode)
        file_mode = stat.S_IMODE(probe.stat().st_mode)
        passed = directory_mode & 0o077 == 0 and file_mode & 0o077 == 0
    except OSError:
        return PreflightCheck("private_export_storage", "fail", "Private export directory probe failed.")
    finally:
        probe.unlink(missing_ok=True)
    return PreflightCheck(
        "private_export_storage",
        "pass" if passed else "fail",
        "Private export directory has owner-only permissions."
        if passed
        else "Private export directory or probe file is accessible to other users.",
    )


async def production_preflight(settings: Settings) -> dict[str, object]:
    engine = create_engine(settings)
    if engine is None:
        checks = [PreflightCheck("database_connectivity", "fail", "Database is not configured.")]
    else:
        checks = await inspect_runtime_database(engine)
    checks.extend((await inspect_export_storage(settings), await inspect_object_storage(settings)))
    if settings.billing_provider_name == "stripe" and settings.billing_mode == "live":
        try:
            provider = build_billing_provider(settings)
            await provider.verify_configuration(authoritative_provider_prices(settings))
        except (PublicAPIError, RuntimeError):
            checks.append(
                PreflightCheck(
                    "live_stripe_billing",
                    "fail",
                    "Live Stripe price and portal configuration could not be verified.",
                )
            )
        else:
            checks.append(
                PreflightCheck(
                    "live_stripe_billing",
                    "pass",
                    "All six live prices and the live portal configuration match the approved billing contract.",
                )
            )
    checks.append(
        PreflightCheck(
            "real_data_release_approvals",
            "pass"
            if settings.private_beta_real_data_enabled
            and settings.private_beta_legal_approval_reference is not None
            and settings.private_beta_support_email is not None
            else "fail",
            "Real-data mode, legal approval reference and support contact are configured."
            if settings.private_beta_real_data_enabled
            and settings.private_beta_legal_approval_reference is not None
            and settings.private_beta_support_email is not None
            else "Real-data release approvals are incomplete.",
        )
    )
    if engine is not None:
        await engine.dispose()
    passed = all(check.status == "pass" for check in checks)
    return {
        "status": "ready" if passed else "blocked",
        "checkedAt": datetime.now(UTC).isoformat(),
        "environment": settings.environment,
        "checks": [asdict(check) for check in checks],
        "featureFlags": settings.safe_feature_flags(),
    }


async def provision_organisation(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    external_organisation_id: str,
    organisation_name: str,
    timezone: str,
    admin_external_user_id: str,
    admin_email: str,
    admin_display_name: str,
    idempotency_key: str,
    operator_reference: str,
    selected_add_ons: tuple[AddOnModule, ...] = (),
    retention_days: int | None = 90,
    native_crm: bool = True,
) -> ProvisioningResult:
    external_organisation_id = external_organisation_id.strip()
    admin_external_user_id = admin_external_user_id.strip()
    organisation_name = organisation_name.strip()
    admin_display_name = admin_display_name.strip()
    if not external_organisation_id or len(external_organisation_id) > 255:
        raise ValueError("External organisation ID must contain 1 to 255 characters.")
    if not admin_external_user_id or len(admin_external_user_id) > 255:
        raise ValueError("External administrator ID must contain 1 to 255 characters.")
    if not organisation_name or len(organisation_name) > 200:
        raise ValueError("Organisation name must contain 1 to 200 characters.")
    if not admin_display_name or len(admin_display_name) > 200:
        raise ValueError("Administrator display name must contain 1 to 200 characters.")
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Organisation timezone must be a valid IANA timezone.") from exc
    email = _normalise_email(admin_email)
    operator = _validate_operator_reference(operator_reference)
    key_hash = _hash_key(idempotency_key)
    add_ons = tuple(sorted(set(selected_add_ons)))
    if any(item not in {"prospect", "engage", "create", "crm"} for item in add_ons):
        raise ValueError("Selected add-ons must be Prospect, Engage, Create or CRM.")
    if retention_days not in {30, 90, 180, None}:
        raise ValueError("Retention days must be 30, 90, 180 or manual.")
    organisation_id = identity_organisation_id(external_organisation_id)
    user_id = identity_user_id(admin_external_user_id)

    async with session_factory() as session:
        await set_tenant_database_context(session, organisation_id)
        existing_event = await session.scalar(
            select(OperatorProvisioningEvent).where(
                OperatorProvisioningEvent.organisation_id == organisation_id,
                OperatorProvisioningEvent.action == "organisation_provisioned",
                OperatorProvisioningEvent.idempotency_key_hash == key_hash,
            )
        )
        if existing_event is not None:
            expected_metadata = {
                "crmMode": "native" if native_crm else "unconfigured",
                "dataNoticeAcknowledged": False,
                "enabledAddOns": list(add_ons),
                "onboardingStatus": "not_started",
                "retentionDays": retention_days,
                "role": "admin",
                "timezone": timezone,
            }
            if existing_event.subject_user_id != user_id or existing_event.metadata_json != expected_metadata:
                raise ValueError("The provisioning idempotency key was already used for different inputs.")
            return ProvisioningResult(
                str(organisation_id), str(existing_event.subject_user_id), existing_event.action, True
            )

        organisation = await session.scalar(
            select(Organisation).where(
                Organisation.id == organisation_id,
                Organisation.external_auth_id == external_organisation_id,
            )
        )
        if organisation is None:
            from revenueos.auth import _organisation_slug

            organisation = Organisation(
                id=organisation_id,
                external_auth_id=external_organisation_id,
                name=organisation_name,
                slug=_organisation_slug(external_organisation_id),
                timezone=timezone,
            )
            session.add(organisation)
        elif organisation.name != organisation_name or organisation.timezone != timezone:
            raise ValueError("Provisioning input conflicts with the existing organisation.")

        user = await session.scalar(select(User).where(User.external_auth_id == admin_external_user_id))
        if user is None:
            user = User(
                id=user_id,
                external_auth_id=admin_external_user_id,
                email=email,
                display_name=admin_display_name,
                status="active",
            )
            session.add(user)
        elif user.id != user_id or user.email.casefold() != email:
            raise ValueError("Provisioning input conflicts with the existing identity user.")
        elif user.status != "active":
            raise ValueError("The requested administrator is disabled.")

        await session.flush()
        membership = await session.get(OrganisationMembership, (organisation_id, user_id))
        if membership is None:
            membership = OrganisationMembership(
                organisation_id=organisation_id,
                user_id=user_id,
                role="admin",
                status="active",
            )
            session.add(membership)
        elif membership.role != "admin" or membership.status != "active":
            raise ValueError("Existing administrator membership is not active with the required role.")
        await session.flush()
        now = datetime.now(UTC)
        await ensure_plan_catalogue(session)
        commercial_state = await session.get(OrganisationCommercialState, organisation_id)
        if commercial_state is None:
            core_plan = next(plan for plan in PLAN_CATALOGUE if plan.code == "core")
            commercial_add_ons = add_ons
            entitled_modules = ["core", *commercial_add_ons]
            session.add(
                OrganisationCommercialState(
                    organisation_id=organisation_id,
                    plan_version_id=core_plan.id,
                    status="active",
                    billing_interval=None,
                    add_on_modules_json=list(commercial_add_ons),
                    seat_limit_status="within_limit",
                    effective_at=now,
                    source="manual_support",
                    actor_reference=operator,
                    reason="Operator-authorised private-beta provisioning.",
                )
            )
            for module in ("core", "prospect", "engage", "create", "crm"):
                enabled = module in entitled_modules
                session.add(
                    OrganisationModuleEntitlement(
                        organisation_id=organisation_id,
                        module_key=module,
                        enabled=enabled,
                        access_level="write" if enabled else "none",
                        source="add_on" if module in commercial_add_ons else "commercial_plan",
                        configured_by_user_id=None,
                        configured_by_actor=operator,
                        enabled_at=now if enabled else None,
                        disabled_at=None if enabled else now,
                    )
                )
            session.add(
                CommercialStateEvent(
                    id=uuid.uuid4(),
                    organisation_id=organisation_id,
                    plan_version_id=core_plan.id,
                    event_type="plan_assigned",
                    effective_status="active",
                    billing_interval=None,
                    entitled_modules_json=entitled_modules,
                    readable_modules_json=entitled_modules,
                    included_user_limit=5,
                    active_user_count=1,
                    seat_limit_status="within_limit",
                    effective_at=now,
                    source="manual_support",
                    actor_reference=operator,
                    reason="Operator-authorised private-beta provisioning.",
                    state_version=1,
                )
            )
        elif commercial_state.status != "inactive":
            raise ValueError("The existing organisation already has commercial access.")
        crm_setting = await session.get(OrganisationCRMSetting, organisation_id)
        if native_crm:
            if crm_setting is None:
                session.add(
                    OrganisationCRMSetting(
                        organisation_id=organisation_id,
                        mode="native",
                        external_provider=None,
                        configured_by_user_id=user_id,
                        configured_at=now,
                    )
                )
            elif crm_setting.mode != "native":
                raise ValueError("Existing CRM mode is not Native CRM.")
        elif crm_setting is not None:
            raise ValueError("Existing CRM mode is configured; use the reviewed admin workflow to change it.")
        beta_settings = await session.get(OrganisationBetaSettings, organisation_id)
        if beta_settings is None:
            session.add(OrganisationBetaSettings(organisation_id=organisation_id, retention_days=retention_days))
        elif beta_settings.retention_days != retention_days:
            raise ValueError("Existing retention policy differs; use the reviewed admin workflow to change it.")
        onboarding = await session.get(OnboardingProgress, (organisation_id, user_id))
        if onboarding is None:
            session.add(OnboardingProgress(organisation_id=organisation_id, user_id=user_id, current_step=0))
        event = OperatorProvisioningEvent(
            id=uuid.uuid4(),
            organisation_id=organisation_id,
            action="organisation_provisioned",
            idempotency_key_hash=key_hash,
            subject_user_id=user_id,
            operator_reference=operator,
            metadata_json={
                "crmMode": "native" if native_crm else "unconfigured",
                "dataNoticeAcknowledged": False,
                "enabledAddOns": list(add_ons),
                "onboardingStatus": "not_started",
                "retentionDays": retention_days,
                "role": "admin",
                "timezone": timezone,
            },
        )
        session.add(event)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            await set_tenant_database_context(session, organisation_id)
            concurrent = await session.scalar(
                select(OperatorProvisioningEvent).where(
                    OperatorProvisioningEvent.organisation_id == organisation_id,
                    OperatorProvisioningEvent.action == "organisation_provisioned",
                    OperatorProvisioningEvent.idempotency_key_hash == key_hash,
                )
            )
            if concurrent is None:
                raise
            return ProvisioningResult(str(organisation_id), str(concurrent.subject_user_id), concurrent.action, True)
    return ProvisioningResult(str(organisation_id), str(user_id), "organisation_provisioned", False)


async def provision_member(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    organisation_id: uuid.UUID,
    external_user_id: str,
    email: str,
    display_name: str,
    role: Literal["admin", "member"],
    idempotency_key: str,
    operator_reference: str,
) -> ProvisioningResult:
    external_user_id = external_user_id.strip()
    display_name = display_name.strip()
    if not external_user_id or len(external_user_id) > 255:
        raise ValueError("External user ID must contain 1 to 255 characters.")
    if not display_name or len(display_name) > 200:
        raise ValueError("Member display name must contain 1 to 200 characters.")
    resolved_email = _normalise_email(email)
    operator = _validate_operator_reference(operator_reference)
    key_hash = _hash_key(idempotency_key)
    user_id = identity_user_id(external_user_id)
    expected_metadata = {"role": role, "status": "active"}
    async with session_factory() as session:
        await set_tenant_database_context(session, organisation_id)
        organisation = await session.scalar(
            select(Organisation).where(Organisation.id == organisation_id).with_for_update()
        )
        if organisation is None:
            raise ValueError("The organisation must be provisioned before members are added.")
        existing_event = await session.scalar(
            select(OperatorProvisioningEvent).where(
                OperatorProvisioningEvent.organisation_id == organisation_id,
                OperatorProvisioningEvent.action == "member_provisioned",
                OperatorProvisioningEvent.idempotency_key_hash == key_hash,
            )
        )
        if existing_event is not None:
            if existing_event.subject_user_id != user_id or existing_event.metadata_json != expected_metadata:
                raise ValueError("The provisioning idempotency key was already used for different inputs.")
            return ProvisioningResult(str(organisation_id), str(user_id), "member_provisioned", True)
        user = await session.scalar(select(User).where(User.external_auth_id == external_user_id))
        if user is None:
            user = User(
                id=user_id,
                external_auth_id=external_user_id,
                email=resolved_email,
                display_name=display_name,
                status="active",
            )
            session.add(user)
        elif user.id != user_id or user.email.casefold() != resolved_email or user.status != "active":
            raise ValueError("Member input conflicts with the existing identity user.")
        await session.flush()
        membership = await session.get(OrganisationMembership, (organisation_id, user_id))
        if membership is None or membership.status != "active":
            try:
                await require_seat_available(session, organisation_id, now=datetime.now(UTC))
            except PublicAPIError as exc:
                raise ValueError(exc.message) from exc
        if membership is None:
            session.add(
                OrganisationMembership(
                    organisation_id=organisation_id,
                    user_id=user_id,
                    role=role,
                    status="active",
                )
            )
        elif membership.role != role:
            raise ValueError("Existing member role differs; use the reviewed admin workflow to change it.")
        else:
            membership.status = "active"
        await session.flush()
        session.add(
            OperatorProvisioningEvent(
                id=uuid.uuid4(),
                organisation_id=organisation_id,
                action="member_provisioned",
                idempotency_key_hash=key_hash,
                subject_user_id=user_id,
                operator_reference=operator,
                metadata_json=expected_metadata,
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            await set_tenant_database_context(session, organisation_id)
            concurrent = await session.scalar(
                select(OperatorProvisioningEvent).where(
                    OperatorProvisioningEvent.organisation_id == organisation_id,
                    OperatorProvisioningEvent.action == "member_provisioned",
                    OperatorProvisioningEvent.idempotency_key_hash == key_hash,
                )
            )
            if concurrent is None:
                raise
            return ProvisioningResult(str(organisation_id), str(user_id), "member_provisioned", True)
    return ProvisioningResult(str(organisation_id), str(user_id), "member_provisioned", False)


async def tenant_preflight(
    session_factory: async_sessionmaker[AsyncSession], organisation_id: uuid.UUID
) -> dict[str, object]:
    async with session_factory() as session:
        await set_tenant_database_context(session, organisation_id)
        organisation = await session.get(Organisation, organisation_id)
        if organisation is None:
            return {"status": "blocked", "organisationId": str(organisation_id), "checks": {"exists": False}}
        active_admins = await session.scalar(
            select(func.count())
            .select_from(OrganisationMembership)
            .where(
                OrganisationMembership.organisation_id == organisation_id,
                OrganisationMembership.role == "admin",
                OrganisationMembership.status == "active",
            )
        )
        crm_setting = await session.get(OrganisationCRMSetting, organisation_id)
        import_batches = await session.scalar(
            select(func.count()).select_from(CRMImportBatch).where(CRMImportBatch.organisation_id == organisation_id)
        )
        merges = await session.scalar(
            select(func.count()).select_from(CRMRecordMerge).where(CRMRecordMerge.organisation_id == organisation_id)
        )
        pipelines = await session.scalar(
            select(func.count())
            .select_from(SalesPipeline)
            .where(
                SalesPipeline.organisation_id == organisation_id,
                SalesPipeline.active.is_(True),
            )
        )
    checks = {
        "exists": True,
        "activeAdminPresent": bool(active_admins),
        "nativeCrmEnabled": bool(crm_setting and crm_setting.mode == "native"),
        "activePipelinePresentOrCreatedOnFirstOpportunity": bool(pipelines) or not import_batches,
    }
    return {
        "status": "ready" if all(checks.values()) else "blocked",
        "organisationId": str(organisation_id),
        "checks": checks,
        "safeCounts": {"importBatches": import_batches or 0, "recordMerges": merges or 0},
    }


async def queue_status(
    session_factory: async_sessionmaker[AsyncSession], organisation_id: uuid.UUID
) -> dict[str, object]:
    """Return tenant-scoped worker state counts without customer content."""

    now = datetime.now(UTC)
    queue_definitions = (
        ("ai", AIJob, AIJob.status, AIJob.lease_expires_at),
        ("prospect", ProspectResearchRun, ProspectResearchRun.status, ProspectResearchRun.lease_expires_at),
        ("actions", ActionExecution, ActionExecution.execution_status, ActionExecution.lease_expires_at),
        ("campaigns", EngageEnrollmentStep, EngageEnrollmentStep.state, EngageEnrollmentStep.lease_expires_at),
        (
            "createTemplates",
            CreateTemplateVersion,
            CreateTemplateVersion.processing_state,
            CreateTemplateVersion.lease_expires_at,
        ),
        (
            "createPresentations",
            CreatePresentationVersion,
            CreatePresentationVersion.state,
            CreatePresentationVersion.lease_expires_at,
        ),
    )
    queues: dict[str, object] = {}
    async with session_factory() as session:
        await set_tenant_database_context(session, organisation_id)
        organisation_exists = await session.scalar(
            select(func.count()).select_from(Organisation).where(Organisation.id == organisation_id)
        )
        if not organisation_exists:
            return {"status": "blocked", "organisationId": str(organisation_id), "code": "tenant_not_found"}
        for name, model, state_column, lease_column in queue_definitions:
            grouped = (
                await session.execute(
                    select(state_column, func.count())
                    .select_from(model)
                    .where(model.organisation_id == organisation_id)
                    .group_by(state_column)
                )
            ).all()
            stale_leases = await session.scalar(
                select(func.count())
                .select_from(model)
                .where(
                    model.organisation_id == organisation_id,
                    lease_column.is_not(None),
                    lease_column <= now,
                )
            )
            queues[name] = {
                "states": {str(state): int(count) for state, count in grouped},
                "staleLeases": int(stale_leases or 0),
            }
    return {
        "status": "ok",
        "organisationId": str(organisation_id),
        "checkedAt": now.isoformat(),
        "queues": queues,
    }


async def support_bundle(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    organisation_id: uuid.UUID,
) -> dict[str, object]:
    tenant = await tenant_preflight(session_factory, organisation_id)
    queues = await queue_status(session_factory, organisation_id)
    return {
        "status": tenant["status"],
        "schemaVersion": 1,
        "generatedAt": datetime.now(UTC).isoformat(),
        "environment": settings.environment,
        "expectedMigrationHead": EXPECTED_MIGRATION_HEAD,
        "featureFlags": settings.safe_feature_flags(),
        "tenant": tenant,
        "workerQueues": queues,
        "contentIncluded": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RevenueOS real-data operations")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("production-preflight")

    provision = subparsers.add_parser("provision-organisation")
    provision.add_argument("--external-organisation-id", required=True)
    provision.add_argument("--organisation-name", required=True)
    provision.add_argument("--timezone", required=True)
    provision.add_argument("--admin-external-user-id", required=True)
    provision.add_argument("--admin-email", required=True)
    provision.add_argument("--admin-display-name", required=True)
    provision.add_argument("--idempotency-key", required=True)
    provision.add_argument("--operator-reference", required=True)
    provision.add_argument(
        "--enable-addon",
        action="append",
        choices=("prospect", "engage", "create", "crm"),
        default=[],
    )
    provision.add_argument("--retention-days", type=int, choices=(30, 90, 180), default=90)
    provision.add_argument("--crm-mode", choices=("native", "unconfigured"), default="native")
    provision.add_argument("--confirm", required=True)

    member = subparsers.add_parser("provision-member")
    member.add_argument("--organisation-id", required=True, type=uuid.UUID)
    member.add_argument("--external-user-id", required=True)
    member.add_argument("--email", required=True)
    member.add_argument("--display-name", required=True)
    member.add_argument("--role", choices=("admin", "member"), default="member")
    member.add_argument("--idempotency-key", required=True)
    member.add_argument("--operator-reference", required=True)
    member.add_argument("--confirm", required=True)

    inspect_commercial = subparsers.add_parser("commercial-inspect")
    inspect_commercial.add_argument("--organisation-id", required=True, type=uuid.UUID)

    start_trial = subparsers.add_parser("commercial-start-trial")
    start_trial.add_argument("--organisation-id", required=True, type=uuid.UUID)
    start_trial.add_argument("--expected-lock-version", required=True, type=int)
    start_trial.add_argument("--operator-reference", required=True)
    start_trial.add_argument("--reason", required=True)
    start_trial.add_argument("--confirm", required=True)

    assign_plan = subparsers.add_parser("commercial-assign-plan")
    assign_plan.add_argument("--organisation-id", required=True, type=uuid.UUID)
    assign_plan.add_argument("--plan", required=True, choices=("core", "growth", "complete", "enterprise"))
    assign_plan.add_argument("--interval", required=True, choices=("monthly", "annual"))
    assign_plan.add_argument("--expected-lock-version", required=True, type=int)
    assign_plan.add_argument("--add-on", action="append", choices=("prospect", "engage", "create", "crm"), default=[])
    assign_plan.add_argument("--custom-user-limit", type=int)
    assign_plan.add_argument("--operator-reference", required=True)
    assign_plan.add_argument("--reason", required=True)
    assign_plan.add_argument("--confirm", required=True)

    change_commercial = subparsers.add_parser("commercial-change-state")
    change_commercial.add_argument("--organisation-id", required=True, type=uuid.UUID)
    change_commercial.add_argument("--state", required=True, choices=("inactive", "suspended"))
    change_commercial.add_argument("--expected-lock-version", required=True, type=int)
    change_commercial.add_argument("--operator-reference", required=True)
    change_commercial.add_argument("--reason", required=True)
    change_commercial.add_argument("--confirm", required=True)

    manual_paid_preview = subparsers.add_parser("credits-manual-paid-preview")
    _add_manual_paid_purchase_arguments(manual_paid_preview, execute=False)

    manual_paid_grant = subparsers.add_parser("credits-manual-paid-grant")
    _add_manual_paid_purchase_arguments(manual_paid_grant, execute=True)

    tenant = subparsers.add_parser("tenant-preflight")
    tenant.add_argument("--organisation-id", required=True, type=uuid.UUID)
    queues = subparsers.add_parser("queue-status")
    queues.add_argument("--organisation-id", required=True, type=uuid.UUID)
    support = subparsers.add_parser("support-bundle")
    support.add_argument("--organisation-id", required=True, type=uuid.UUID)
    return parser


async def _run(arguments: argparse.Namespace, settings: Settings) -> tuple[int, dict[str, object]]:
    if arguments.command == "production-preflight":
        result = await production_preflight(settings)
        return (0 if result["status"] == "ready" else 1), result

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    if engine is None or session_factory is None:
        return 1, {"status": "blocked", "code": "database_unavailable"}
    try:
        if arguments.command == "provision-organisation":
            expected_confirmation = f"PROVISION {arguments.external_organisation_id}"
            if arguments.confirm != expected_confirmation:
                return 2, {"status": "blocked", "code": "confirmation_mismatch"}
            provisioning_result = await provision_organisation(
                session_factory,
                external_organisation_id=arguments.external_organisation_id,
                organisation_name=arguments.organisation_name,
                timezone=arguments.timezone,
                admin_external_user_id=arguments.admin_external_user_id,
                admin_email=arguments.admin_email,
                admin_display_name=arguments.admin_display_name,
                idempotency_key=arguments.idempotency_key,
                operator_reference=arguments.operator_reference,
                selected_add_ons=tuple(arguments.enable_addon),
                retention_days=arguments.retention_days,
                native_crm=arguments.crm_mode == "native",
            )
            return 0, {"status": "complete", **asdict(provisioning_result)}
        if arguments.command == "provision-member":
            expected_confirmation = f"PROVISION MEMBER {arguments.external_user_id} TO {arguments.organisation_id}"
            if arguments.confirm != expected_confirmation:
                return 2, {"status": "blocked", "code": "confirmation_mismatch"}
            member_result = await provision_member(
                session_factory,
                organisation_id=arguments.organisation_id,
                external_user_id=arguments.external_user_id,
                email=arguments.email,
                display_name=arguments.display_name,
                role=arguments.role,
                idempotency_key=arguments.idempotency_key,
                operator_reference=arguments.operator_reference,
            )
            return 0, {"status": "complete", **asdict(member_result)}
        if arguments.command == "commercial-inspect":
            async with session_factory() as session:
                await set_tenant_database_context(session, arguments.organisation_id)
                projection = await CommercialService(session, settings).projection(arguments.organisation_id)
                return 0, {"status": "complete", "commercial": projection.model_dump(mode="json", by_alias=True)}
        if arguments.command == "commercial-start-trial":
            expected_confirmation = f"START TRIAL {arguments.organisation_id}"
            if arguments.confirm != expected_confirmation:
                return 2, {"status": "blocked", "code": "confirmation_mismatch"}
            async with session_factory() as session:
                await set_tenant_database_context(session, arguments.organisation_id)
                projection = await CommercialService(session, settings).start_trial(
                    arguments.organisation_id,
                    actor_reference=_validate_operator_reference(arguments.operator_reference),
                    reason=arguments.reason,
                    expected_lock_version=arguments.expected_lock_version,
                )
                return 0, {"status": "complete", "commercial": projection.model_dump(mode="json", by_alias=True)}
        if arguments.command == "commercial-assign-plan":
            expected_confirmation = f"ASSIGN {arguments.plan.upper()} TO {arguments.organisation_id}"
            if arguments.confirm != expected_confirmation:
                return 2, {"status": "blocked", "code": "confirmation_mismatch"}
            async with session_factory() as session:
                await set_tenant_database_context(session, arguments.organisation_id)
                projection = await CommercialService(session, settings).assign_plan(
                    arguments.organisation_id,
                    plan_code=arguments.plan,
                    billing_interval=arguments.interval,
                    actor_reference=_validate_operator_reference(arguments.operator_reference),
                    reason=arguments.reason,
                    expected_lock_version=arguments.expected_lock_version,
                    add_ons=tuple(arguments.add_on),
                    custom_user_limit=arguments.custom_user_limit,
                )
                return 0, {"status": "complete", "commercial": projection.model_dump(mode="json", by_alias=True)}
        if arguments.command == "commercial-change-state":
            expected_confirmation = f"SET {arguments.organisation_id} {arguments.state.upper()}"
            if arguments.confirm != expected_confirmation:
                return 2, {"status": "blocked", "code": "confirmation_mismatch"}
            async with session_factory() as session:
                await set_tenant_database_context(session, arguments.organisation_id)
                projection = await CommercialService(session, settings).change_state(
                    arguments.organisation_id,
                    status=arguments.state,
                    actor_reference=_validate_operator_reference(arguments.operator_reference),
                    reason=arguments.reason,
                    expected_lock_version=arguments.expected_lock_version,
                )
                return 0, {"status": "complete", "commercial": projection.model_dump(mode="json", by_alias=True)}
        if arguments.command == "credits-manual-paid-preview":
            preview = await manual_paid_credit_grant_preview(
                session_factory,
                organisation_id=arguments.organisation_id,
                credits=arguments.credits,
                amount_received_minor_units=arguments.amount_received,
                currency=arguments.currency,
                payment_method=arguments.payment_method,
                payment_reference=arguments.payment_reference,
                payment_received_at=arguments.payment_received_at,
                operator_reference=arguments.operator_reference,
                reason=arguments.reason,
            )
            return 0, preview
        if arguments.command == "credits-manual-paid-grant":
            if arguments.cleared_funds_confirmed > 1 or arguments.large_grant_reviewed > 1:
                return 2, {"status": "blocked", "code": "duplicate_argument"}
            operator_reference = _validate_manual_paid_operator_reference(arguments.operator_reference)
            reason = _validate_manual_paid_reason(arguments.reason)
            expected_confirmation = _manual_paid_confirmation(
                arguments.organisation_id,
                arguments.credits,
                arguments.amount_received,
                arguments.currency,
                arguments.payment_method,
                arguments.payment_reference,
                arguments.payment_received_at,
                operator_reference,
                reason,
            )
            if arguments.confirm != expected_confirmation:
                return 2, {"status": "blocked", "code": "confirmation_mismatch"}
            async with session_factory() as session:
                await set_tenant_database_context(session, arguments.organisation_id)
                grant_result = await CreditService(session, settings).grant_manual_paid_purchase(
                    arguments.organisation_id,
                    credits=arguments.credits,
                    amount_received_minor_units=arguments.amount_received,
                    currency=arguments.currency,
                    payment_method=arguments.payment_method,
                    payment_reference=arguments.payment_reference,
                    payment_received_at=arguments.payment_received_at,
                    cleared_funds_confirmed=arguments.cleared_funds_confirmed == 1,
                    idempotency_key=arguments.idempotency_key,
                    expected_balance_version=arguments.expected_balance_version,
                    operator_reference=operator_reference,
                    reason=reason,
                    large_grant_reviewed=arguments.large_grant_reviewed == 1,
                )
                reconciliation = await CreditService(session, settings).reconcile_balance(arguments.organisation_id)
                return 0, {
                    "status": "complete",
                    "operation": "grant_manual_paid_credits",
                    "grantId": str(grant_result.grant.id),
                    "creditLotId": str(grant_result.lot.id),
                    "organisationId": str(arguments.organisation_id),
                    "creditsGranted": grant_result.grant.credits_granted,
                    "amountReceivedMinorUnits": grant_result.grant.amount_received_minor_units,
                    "currency": grant_result.grant.currency,
                    "paymentMethod": grant_result.grant.payment_method,
                    "paymentReference": grant_result.grant.payment_reference,
                    "paymentReceivedAt": grant_result.grant.payment_received_at.isoformat(),
                    "clearedFundsConfirmed": grant_result.grant.cleared_funds_confirmed,
                    "creditType": grant_result.lot.credit_type,
                    "expiresAt": grant_result.lot.expires_at,
                    "availableBalance": grant_result.balance.available,
                    "purchasedAvailable": grant_result.balance.purchased_available,
                    "alreadyApplied": grant_result.already_applied,
                    "ledgerReconciled": reconciliation.consistent,
                    "providerExecutionAuthorisedByGrant": False,
                    "marginReviewStatus": grant_result.grant.margin_review_status,
                }
        if arguments.command == "tenant-preflight":
            tenant_result = await tenant_preflight(session_factory, arguments.organisation_id)
            return (0 if tenant_result["status"] == "ready" else 1), tenant_result
        if arguments.command == "queue-status":
            queue_result = await queue_status(session_factory, arguments.organisation_id)
            return (0 if queue_result["status"] == "ok" else 1), queue_result
        support_result = await support_bundle(settings, session_factory, arguments.organisation_id)
        return (0 if support_result["status"] == "ready" else 1), support_result
    finally:
        await engine.dispose()


def main() -> None:
    parser = _parser()
    arguments = parser.parse_args()
    try:
        settings = get_settings()
        exit_code, result = asyncio.run(_run(arguments, settings))
    except PublicAPIError as exc:
        exit_code, result = 1, {"status": "blocked", "code": exc.code, "message": exc.message}
    except (ValueError, SQLAlchemyError):
        exit_code, result = 1, {"status": "blocked", "code": "operation_failed"}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
