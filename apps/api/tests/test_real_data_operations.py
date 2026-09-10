from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import AuthenticationError, VerifiedIdentity, _resolve_identity
from revenueos.config import Settings
from revenueos.main import create_app
from revenueos.models import OperatorProvisioningEvent, OrganisationMembership
from revenueos.operations import (
    _manual_paid_confirmation,
    _parse_credit_quantity,
    _parse_exact_amount_minor_units,
    _parser,
    _run,
    manual_paid_credit_grant_preview,
    provision_member,
    provision_organisation,
    queue_status,
    support_bundle,
    tenant_preflight,
)
from tests.conftest import PRIMARY_ORGANISATION_ID, TEST_DB_URL


def safe_real_data_settings(**changes: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "auth_mode": "clerk",
        "mock_auth_enabled": False,
        "identity_jit_provisioning_enabled": False,
        "clerk_jwks_url": "https://identity.example.test/jwks.json",
        "clerk_issuer": "https://identity.example.test",
        "clerk_audience": "revenueos-api",
        "database_url": "postgresql+asyncpg://runtime.example.test/revenueos",
        "release_sha": "a" * 40,
        "database_tls_mode": "verify_full_system",
        "cors_origins": "https://app.example.test",
        "allowed_hosts": "api.example.test",
        "private_beta_real_data_enabled": True,
        "private_beta_legal_approval_reference": "approval-private-beta-001",
        "private_beta_support_email": "support@example.test",
        "private_beta_export_directory": "/var/lib/revenueos/private-exports",
        "visual_storage_backend": "s3_compatible",
        "visual_s3_endpoint": "https://storage.example.test",
        "visual_s3_bucket": "private-real-data",
        "visual_s3_region": "ap-southeast-2",
        "visual_s3_access_key_id": "synthetic-access-key",
        "visual_s3_secret_access_key": "synthetic-secret-key",
        "feature_revenue_brain_enabled": False,
        "feature_ai_companion_enabled": False,
        "feature_ai_debrief_enabled": False,
        "feature_voice_journal_enabled": False,
        "feature_visual_evidence_enabled": False,
        "feature_recording_capture_enabled": False,
        "feature_transcription_enabled": False,
        "feature_online_meeting_capture_enabled": False,
        "feature_online_meeting_import_enabled": False,
        "feature_document_evidence_enabled": False,
        "feature_email_evidence_enabled": False,
        "feature_ask_revenueos_enabled": False,
        "feature_live_interaction_intelligence_enabled": False,
        "feature_prospect_enabled": False,
        "feature_engage_enabled": False,
        "feature_engage_campaigns_enabled": False,
        "feature_engage_events_enabled": False,
        "feature_create_enabled": False,
    }
    values.update(changes)
    return Settings(**values)  # type: ignore[arg-type]


def test_real_data_configuration_has_one_known_safe_restricted_profile() -> None:
    settings = safe_real_data_settings()

    assert settings.private_beta_real_data_enabled is True
    assert settings.safe_feature_flags()["nativeCrm"] is True
    assert settings.safe_feature_flags()["revenueBrain"] is False


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"identity_jit_provisioning_enabled": True}, "deliberate operator provisioning"),
        ({"cors_origins": "http://localhost:3000"}, "public HTTPS origins"),
        ({"allowed_hosts": "localhost"}, "allowed hosts must be explicit"),
        ({"visual_storage_backend": "local"}, "S3-compatible object storage"),
        ({"feature_revenue_brain_enabled": True}, "mock intelligence"),
        ({"log_level": "DEBUG"}, "must not be DEBUG"),
    ],
)
def test_real_data_configuration_rejects_unsafe_variants(change: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        safe_real_data_settings(**change)


def test_api_security_headers_cover_success_and_error_responses() -> None:
    app = create_app(
        Settings(environment="test", auth_mode="mock", mock_auth_enabled=True, database_url=None, log_level="WARNING")
    )
    client = TestClient(app)

    for path in ("/health", "/missing"):
        response = client.get(path)
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["Content-Security-Policy"] == (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
        assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=(), payment=()"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"


def test_operator_provisioning_is_audited_idempotent_and_disables_jit_identity_creation() -> None:
    suffix = uuid.uuid4().hex
    external_organisation_id = f"org_real_data_{suffix}"
    external_user_id = f"user_real_data_{suffix}"

    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        unprovisioned = VerifiedIdentity(
            external_auth_id=f"unprovisioned_user_{suffix}",
            external_organisation_id=f"unprovisioned_org_{suffix}",
            display_name="Unprovisioned User",
            email=f"unprovisioned-{suffix}@example.test",
            organisation_name="Unprovisioned Org",
            role="admin",
            auth_mode="clerk",
        )
        async with factory() as session:
            with pytest.raises(AuthenticationError, match="not been provisioned"):
                await _resolve_identity(session, unprovisioned, allow_provisioning=False)

        first = await provision_organisation(
            factory,
            external_organisation_id=external_organisation_id,
            organisation_name="Synthetic Design Partner",
            timezone="Australia/Sydney",
            admin_external_user_id=external_user_id,
            admin_email=f"admin-{suffix}@example.com",
            admin_display_name="Synthetic Admin",
            idempotency_key=f"provision-{suffix}",
            operator_reference="release-operator@example.test",
        )
        second = await provision_organisation(
            factory,
            external_organisation_id=external_organisation_id,
            organisation_name="Synthetic Design Partner",
            timezone="Australia/Sydney",
            admin_external_user_id=external_user_id,
            admin_email=f"admin-{suffix}@example.com",
            admin_display_name="Synthetic Admin",
            idempotency_key=f"provision-{suffix}",
            operator_reference="release-operator@example.test",
        )
        assert first.already_applied is False
        assert second.already_applied is True
        assert first.organisation_id == second.organisation_id
        identity = VerifiedIdentity(
            external_auth_id=external_user_id,
            external_organisation_id=external_organisation_id,
            display_name="Synthetic Admin",
            email=f"admin-{suffix}@example.com",
            organisation_name="Synthetic Design Partner",
            role="admin",
            auth_mode="clerk",
        )
        async with factory() as session:
            resolved = await _resolve_identity(session, identity, allow_provisioning=False)
            events = list(
                await session.scalars(
                    select(OperatorProvisioningEvent).where(
                        OperatorProvisioningEvent.organisation_id == resolved.organisation_id
                    )
                )
            )
            membership = await session.get(
                OrganisationMembership,
                (resolved.organisation_id, resolved.user_id),
            )
            assert membership is not None and membership.role == "admin" and membership.status == "active"
            assert len(events) == 1
            assert events[0].metadata_json == {
                "crmMode": "native",
                "dataNoticeAcknowledged": False,
                "enabledAddOns": [],
                "onboardingStatus": "not_started",
                "retentionDays": 90,
                "role": "admin",
                "timezone": "Australia/Sydney",
            }
            assert f"provision-{suffix}" not in events[0].idempotency_key_hash
        report = await tenant_preflight(factory, uuid.UUID(first.organisation_id))
        assert report["status"] == "ready"
        queues = await queue_status(factory, uuid.UUID(first.organisation_id))
        assert queues["status"] == "ok"
        assert queues["queues"] == {
            "actions": {"staleLeases": 0, "states": {}},
            "ai": {"staleLeases": 0, "states": {}},
            "campaigns": {"staleLeases": 0, "states": {}},
            "createPresentations": {"staleLeases": 0, "states": {}},
            "createTemplates": {"staleLeases": 0, "states": {}},
            "prospect": {"staleLeases": 0, "states": {}},
        }
        bundle = await support_bundle(Settings(environment="test"), factory, uuid.UUID(first.organisation_id))
        assert bundle["contentIncluded"] is False
        assert "Synthetic Design Partner" not in str(bundle)
        assert f"admin-{suffix}@example.com" not in str(bundle)

        member_external_id = f"member_real_data_{suffix}"
        member_first = await provision_member(
            factory,
            organisation_id=uuid.UUID(first.organisation_id),
            external_user_id=member_external_id,
            email=f"member-{suffix}@example.com",
            display_name="Synthetic Member",
            role="member",
            idempotency_key=f"provision-member-{suffix}",
            operator_reference="release-operator@example.test",
        )
        member_second = await provision_member(
            factory,
            organisation_id=uuid.UUID(first.organisation_id),
            external_user_id=member_external_id,
            email=f"member-{suffix}@example.com",
            display_name="Synthetic Member",
            role="member",
            idempotency_key=f"provision-member-{suffix}",
            operator_reference="release-operator@example.test",
        )
        assert member_first.already_applied is False
        assert member_second.already_applied is True
        member_identity = VerifiedIdentity(
            external_auth_id=member_external_id,
            external_organisation_id=external_organisation_id,
            display_name="Synthetic Member",
            email=f"member-{suffix}@example.com",
            organisation_name="Synthetic Design Partner",
            role="member",
            auth_mode="clerk",
        )
        async with factory() as session:
            resolved_member = await _resolve_identity(session, member_identity, allow_provisioning=False)
            member_membership = await session.get(
                OrganisationMembership,
                (resolved_member.organisation_id, resolved_member.user_id),
            )
            events = list(
                await session.scalars(
                    select(OperatorProvisioningEvent).where(
                        OperatorProvisioningEvent.organisation_id == resolved_member.organisation_id
                    )
                )
            )
            assert member_membership is not None
            assert member_membership.role == "member" and member_membership.status == "active"
            assert {event.action for event in events} == {"organisation_provisioned", "member_provisioned"}
        await engine.dispose()

    asyncio.run(scenario())


def test_owner_manual_paid_credit_cli_previews_confirms_executes_and_retries() -> None:
    async def scenario() -> None:
        settings = Settings(
            environment="test",
            auth_mode="mock",
            mock_auth_enabled=True,
            database_url=TEST_DB_URL,
            log_level="WARNING",
        )
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        received_at = datetime.now(UTC) - timedelta(hours=1)
        operator_reference = "owner-support-synthetic"
        reason = "Grant the synthetic negotiated bulk purchase after cleared payment verification."
        try:
            preview = await manual_paid_credit_grant_preview(
                factory,
                organisation_id=PRIMARY_ORGANISATION_ID,
                credits=50_000,
                amount_received_minor_units=1_234_567,
                currency="AUD",
                payment_method="BANK_TRANSFER",
                payment_reference="INV-SYNTHETIC-CLI-055",
                payment_received_at=received_at,
                operator_reference=operator_reference,
                reason=reason,
            )
            assert preview["status"] == "ready_for_confirmation"
            assert preview["organisation"] == {
                "id": str(PRIMARY_ORGANISATION_ID),
                "name": "Example Revenue Team",
                "commercialStatus": "active",
                "plan": "complete",
            }
            assert preview["amountReceived"] == "AUD 12345.67"
            assert preview["expectedBalanceVersion"] == 0
            assert preview["clearedFundsRequired"] is True
            assert preview["providerExecutionAuthorisedByGrant"] is False
            assert preview["operatorReference"] == operator_reference
            assert preview["reason"] == reason
            confirmation = _manual_paid_confirmation(
                PRIMARY_ORGANISATION_ID,
                50_000,
                1_234_567,
                "AUD",
                "BANK_TRANSFER",
                "INV-SYNTHETIC-CLI-055",
                received_at,
                operator_reference,
                reason,
            )
            assert preview["confirmationRequired"] == confirmation

            command = [
                "credits-manual-paid-grant",
                "--organisation-id",
                str(PRIMARY_ORGANISATION_ID),
                "--credits",
                "50000",
                "--amount-received",
                "12345.67",
                "--currency",
                "AUD",
                "--payment-method",
                "BANK_TRANSFER",
                "--payment-reference",
                "INV-SYNTHETIC-CLI-055",
                "--payment-received-at",
                received_at.isoformat(),
                "--expected-balance-version",
                "0",
                "--idempotency-key",
                "manual-paid-cli-synthetic-055",
                "--operator-reference",
                operator_reference,
                "--reason",
                reason,
                "--cleared-funds-confirmed",
                "--confirm",
                confirmation,
            ]
            wrong_confirmation = _parser().parse_args([*command[:-1], "WRONG"])
            wrong_code, wrong_result = await _run(wrong_confirmation, settings)
            assert wrong_code == 2 and wrong_result == {"status": "blocked", "code": "confirmation_mismatch"}

            changed_reason_command = list(command)
            changed_reason_command[changed_reason_command.index("--reason") + 1] = (
                "A different reason must require a fresh preview and confirmation."
            )
            changed_reason = _parser().parse_args(changed_reason_command)
            changed_reason_code, changed_reason_result = await _run(changed_reason, settings)
            assert changed_reason_code == 2
            assert changed_reason_result == {"status": "blocked", "code": "confirmation_mismatch"}

            duplicate_confirmation = _parser().parse_args([*command[:-2], "--cleared-funds-confirmed", *command[-2:]])
            duplicate_code, duplicate_result = await _run(duplicate_confirmation, settings)
            assert duplicate_code == 2
            assert duplicate_result == {"status": "blocked", "code": "duplicate_argument"}

            arguments = _parser().parse_args(command)
            assert arguments.amount_received == 1_234_567
            exit_code, result = await _run(arguments, settings)
            assert exit_code == 0
            assert result["status"] == "complete"
            assert result["creditType"] == "purchased"
            assert result["expiresAt"] is None
            assert result["clearedFundsConfirmed"] is True
            assert result["ledgerReconciled"] is True
            assert result["alreadyApplied"] is False

            retry_code, retry = await _run(arguments, settings)
            assert retry_code == 0
            assert retry["grantId"] == result["grantId"]
            assert retry["creditLotId"] == result["creditLotId"]
            assert retry["purchasedAvailable"] == 50_000
            assert retry["alreadyApplied"] is True
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_manual_paid_credit_cli_parses_exact_bounds_and_rejects_duplicate_facts() -> None:
    assert _parse_exact_amount_minor_units("0.01") == 1
    assert _parse_exact_amount_minor_units("12345.67") == 1_234_567
    assert _parse_exact_amount_minor_units("90000000000.00") == 9_000_000_000_000
    assert _parse_credit_quantity("1") == 1
    assert _parse_credit_quantity("9000000000000") == 9_000_000_000_000

    for value in (
        "0",
        "-0.01",
        "0.001",
        "1e3",
        "+1.00",
        "90000000000.01",
        "NaN",
        "Infinity",
        "1" * 1_000,
    ):
        with pytest.raises(argparse.ArgumentTypeError, match="Amount received"):
            _parse_exact_amount_minor_units(value)
    for value in ("0", "-1", "+1", "1.5", "1_000", "9000000000001", "1" * 1_000):
        with pytest.raises(argparse.ArgumentTypeError, match="Credits"):
            _parse_credit_quantity(value)

    preview_arguments = [
        "credits-manual-paid-preview",
        "--organisation-id",
        str(PRIMARY_ORGANISATION_ID),
        "--credits",
        "1",
        "--credits",
        "2",
        "--amount-received",
        "0.01",
        "--currency",
        "AUD",
        "--payment-method",
        "BANK_TRANSFER",
        "--payment-reference",
        "INV-SYNTHETIC-DUPLICATE-FLAG",
        "--payment-received-at",
        "2026-09-10T10:00:00+10:00",
        "--operator-reference",
        "owner-support-synthetic",
        "--reason",
        "Reject duplicate financial arguments.",
    ]
    with pytest.raises(SystemExit) as duplicate:
        _parser().parse_args(preview_arguments)
    assert duplicate.value.code == 2
