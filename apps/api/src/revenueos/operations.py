from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import stat
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from revenueos.auth import identity_organisation_id, identity_user_id
from revenueos.config import Settings, get_settings
from revenueos.database import create_engine, create_session_factory, set_tenant_database_context
from revenueos.models import (
    ActionExecution,
    AIJob,
    CreatePresentationVersion,
    CreateTemplateVersion,
    CRMImportBatch,
    CRMRecordMerge,
    EngageEnrollmentStep,
    OnboardingProgress,
    OperatorProvisioningEvent,
    Organisation,
    OrganisationBetaSettings,
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
AddOnModule = Literal["prospect", "engage", "create"]


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


def inspect_export_directory(settings: Settings) -> PreflightCheck:
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
    checks.extend((inspect_export_directory(settings), await inspect_object_storage(settings)))
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
    if any(item not in {"prospect", "engage", "create"} for item in add_ons):
        raise ValueError("Selected add-ons must be Prospect, Engage or Create.")
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
        requested_modules = {
            "crm": native_crm,
            **{module: module in add_ons for module in ("prospect", "engage", "create")},
        }
        for module, enabled in requested_modules.items():
            entitlement = await session.get(OrganisationModuleEntitlement, (organisation_id, module))
            if entitlement is None:
                session.add(
                    OrganisationModuleEntitlement(
                        organisation_id=organisation_id,
                        module_key=module,
                        enabled=enabled,
                        source="manual_private_beta",
                        configured_by_user_id=user_id,
                        enabled_at=now if enabled else None,
                        disabled_at=None if enabled else now,
                    )
                )
            elif entitlement.enabled != enabled:
                raise ValueError(
                    f"Existing {module} entitlement differs; use the reviewed admin workflow to change it."
                )
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
        crm_entitlement = await session.get(OrganisationModuleEntitlement, (organisation_id, "crm"))
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
        "nativeCrmEnabled": bool(
            crm_entitlement and crm_entitlement.enabled and crm_setting and crm_setting.mode == "native"
        ),
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
        choices=("prospect", "engage", "create"),
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
    except (ValueError, SQLAlchemyError):
        exit_code, result = 1, {"status": "blocked", "code": "operation_failed"}
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
