from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.requests import Request

from revenueos.auth import (
    AuthenticatedUser,
    AuthenticationError,
    ClerkAuthAdapter,
    VerifiedIdentity,
    _resolve_identity,
    get_current_user,
)
from revenueos.beta_maintenance import (
    delete_organisation,
    generate_export,
    purge_expired_exports,
    run_retention,
)
from revenueos.beta_services import BetaService
from revenueos.config import Settings
from revenueos.demo_data import (
    demo_companion_ids,
    demo_debrief_ids,
    demo_ids,
    demo_interaction_ids,
    demo_live_ids,
    demo_marker_ids,
    demo_source_evidence_ids,
    demo_visual_ids,
    reset_demo_data,
    seed_demo_data,
)
from revenueos.errors import PublicAPIError
from revenueos.main import create_app
from revenueos.models import (
    AIUsageCounter,
    BetaDataRequest,
    CaptureSession,
    Company,
    DataNoticeAcknowledgement,
    DebriefSession,
    DocumentSource,
    EmailSource,
    Evidence,
    Interaction,
    InteractionIntelligenceSnapshot,
    InteractionMarker,
    LiveBriefProgress,
    LiveInteractionSession,
    Meeting,
    OnlineMeetingMetadata,
    OnlineMeetingTranscriptImport,
    Organisation,
    OrganisationMembership,
    PreInteractionBrief,
    ProvisionalSignal,
    RecordingSession,
    RevenueBrainSourceSnapshot,
    SourceCandidateEvidence,
    Transcript,
    TranscriptVersion,
    User,
    VisualAsset,
    VisualCandidateEvidence,
)
from revenueos.routes.health import EXPECTED_MIGRATION_HEAD
from revenueos.source_evidence_contracts import SourceCandidateLocation
from revenueos.tenant import TenantContext
from tests.conftest import (
    PRIMARY_ORGANISATION_ID,
    PRIMARY_USER_ID,
    SECONDARY_ORGANISATION_ID,
    SECONDARY_USER_ID,
    TEST_DB_URL,
    TEST_VISUAL_STORAGE,
)


def beta_settings(**changes: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "auth_mode": "mock",
        "mock_auth_enabled": True,
        "database_url": TEST_DB_URL,
        "log_level": "WARNING",
        "cors_origins": "http://localhost:3000",
    }
    values.update(changes)
    return Settings(**values)  # type: ignore[arg-type]


def test_production_configuration_fails_closed_without_identity_or_postgresql() -> None:
    with pytest.raises(ValidationError, match="complete Clerk"):
        Settings(environment="production", auth_mode="clerk", mock_auth_enabled=False)

    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(
            environment="production",
            auth_mode="clerk",
            mock_auth_enabled=False,
            clerk_jwks_url="https://identity.example.test/jwks.json",
            clerk_issuer="https://identity.example.test",
            clerk_audience="revenueos-api",
            database_url="sqlite+aiosqlite:///unsafe.db",
        )
    with pytest.raises(ValidationError, match="feature flag"):
        beta_settings(
            ai_provider_name="openai",
            openai_api_key="sk-test-private-beta",
            openai_model="gpt-test",
            feature_openai_provider_enabled=False,
        )


def test_clerk_adapter_verifies_signature_audience_issuer_expiry_and_active_organisation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = rsa.generate_private_key(public_exponent=65_537, key_size=2048)
    public_key = private_key.public_key()

    class SigningKeys:
        def get_signing_key_from_jwt(self, token: str) -> object:
            assert token
            return SimpleNamespace(key=public_key)

    monkeypatch.setattr("revenueos.auth._jwks_client", lambda *_args: SigningKeys())
    settings = beta_settings(
        auth_mode="clerk",
        mock_auth_enabled=False,
        clerk_jwks_url="https://identity.example.test/jwks.json",
        clerk_issuer="https://identity.example.test",
        clerk_audience="revenueos-api",
    )
    adapter = ClerkAuthAdapter(settings)
    now = datetime.now(UTC)

    async def authenticate(claims: dict[str, object]) -> VerifiedIdentity:
        token = jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "beta-key"})
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/v1/me",
                "headers": [(b"authorization", f"Bearer {token}".encode())],
            }
        )
        return await adapter.authenticate(request)

    claims: dict[str, object] = {
        "sub": "user_clerk_beta",
        "org_id": "org_clerk_beta",
        "org_role": "org:admin",
        "iss": "https://identity.example.test",
        "aud": "revenueos-api",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    identity = asyncio.run(authenticate(claims))
    assert identity.external_organisation_id == "org_clerk_beta"
    assert identity.role == "admin"

    with pytest.raises(AuthenticationError):
        asyncio.run(authenticate({**claims, "aud": "wrong-api"}))
    with pytest.raises(AuthenticationError):
        asyncio.run(authenticate({**claims, "iss": "https://wrong.example.test"}))
    without_organisation = {key: value for key, value in claims.items() if key != "org_id"}
    with pytest.raises(AuthenticationError):
        asyncio.run(authenticate(without_organisation))
    with pytest.raises(AuthenticationError):
        asyncio.run(
            authenticate(
                {
                    **claims,
                    "iat": int((now - timedelta(hours=2)).timestamp()),
                    "exp": int((now - timedelta(hours=1)).timestamp()),
                }
            )
        )


def test_health_aliases_are_safe_and_migration_head_is_current(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert client.get("/health/live").json() == {"status": "healthy"}
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["dependencies"]["migration"]["status"] == "ready"
    assert EXPECTED_MIGRATION_HEAD == "0029_doc_email_evidence"
    assert "postgres" not in ready.text.lower()
    assert "secret" not in ready.text.lower()

    async def incompatible_migration(_engine: object) -> str:
        return "0019_revenue_brain_reasoning"

    monkeypatch.setattr(
        "revenueos.routes.health.database_migration_version",
        incompatible_migration,
    )
    mismatched = client.get("/health/ready")
    assert mismatched.status_code == 503
    assert mismatched.json()["dependencies"]["migration"] == {
        "status": "misconfigured",
        "detail": "Database migration is not compatible with this release.",
    }


def test_notice_version_requires_acknowledgement_and_stores_metadata_only() -> None:
    app = create_app(beta_settings(private_beta_data_notice_version=2))
    with TestClient(app) as client:
        notice = client.get("/api/v1/beta/data-notice")
        assert notice.status_code == 200
        assert notice.json()["version"] == 2
        assert notice.json()["acknowledged"] is False
        rejected = client.post(
            "/api/v1/meetings",
            json={
                "title": "Consent gate",
                "meetingDate": "2026-07-01T10:00:00+10:00",
                "transcript": {"rawText": "Authorised synthetic text.", "source": "manual"},
            },
        )
        assert rejected.status_code == 428
        assert rejected.json()["code"] == "data_notice_acknowledgement_required"
        spoofed = client.post(
            "/api/v1/beta/data-notice/acknowledgements",
            json={"acknowledged": True, "noticeVersion": 1, "organisationId": str(SECONDARY_ORGANISATION_ID)},
        )
        assert spoofed.status_code == 422
        acknowledged = client.post(
            "/api/v1/beta/data-notice/acknowledgements",
            json={"acknowledged": True},
        )
        assert acknowledged.status_code == 200
        assert acknowledged.json()["acknowledged"] is True
        accepted = client.post(
            "/api/v1/meetings",
            json={
                "title": "Consent gate",
                "meetingDate": "2026-07-01T10:00:00+10:00",
                "transcript": {"rawText": "Authorised synthetic text.", "source": "manual"},
            },
        )
        assert accepted.status_code == 201

    async def inspect() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            record = await session.scalar(
                select(DataNoticeAcknowledgement).where(
                    DataNoticeAcknowledgement.organisation_id == PRIMARY_ORGANISATION_ID,
                    DataNoticeAcknowledgement.user_id == PRIMARY_USER_ID,
                    DataNoticeAcknowledgement.notice_version == 2,
                )
            )
            assert record is not None
            assert set(record.__table__.columns.keys()) == {
                "id",
                "organisation_id",
                "user_id",
                "notice_version",
                "acknowledged_at",
            }
        await engine.dispose()

    asyncio.run(inspect())


def test_transcript_character_limit_is_enforced_server_side() -> None:
    app = create_app(beta_settings(private_beta_max_transcript_characters=1_000))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/meetings",
            json={
                "title": "Bounded transcript",
                "meetingDate": "2026-07-01T10:00:00+10:00",
                "transcript": {"rawText": "x" * 1_001, "source": "manual"},
            },
        )
        assert response.status_code == 413
        assert response.json()["code"] == "transcript_too_large"
        assert "x" * 100 not in response.text


@pytest.mark.parametrize("policy", ["days_30", "days_90", "days_180", "manual"])
def test_admin_can_set_each_retention_policy(client: TestClient, policy: str) -> None:
    response = client.patch("/api/v1/beta/admin/retention", json={"policy": policy})
    assert response.status_code == 200
    assert response.json() == {"policy": policy, "defaultApplied": False}


def test_member_cannot_open_admin_or_change_settings(app: FastAPI, client: TestClient) -> None:
    async def member() -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id=PRIMARY_USER_ID,
            external_auth_id="user_dev_001",
            display_name="Beta Member",
            email="member@example.test",
            organisation_id=PRIMARY_ORGANISATION_ID,
            organisation_name="Example Revenue Team",
            organisation_slug="example-revenue-team",
            role="member",
            auth_mode="mock",
        )

    app.dependency_overrides[get_current_user] = member
    assert client.get("/api/v1/beta/admin").status_code == 403
    assert client.patch("/api/v1/beta/admin/retention", json={"policy": "days_30"}).status_code == 403
    assert client.get("/api/v1/beta/admin/feedback").status_code == 403
    assert client.post("/api/v1/beta/admin/exports").status_code == 403
    assert (
        client.post(
            "/api/v1/beta/admin/organisation-deletion",
            json={"confirmation": "DELETE example-revenue-team"},
        ).status_code
        == 403
    )
    app.dependency_overrides.pop(get_current_user, None)


def test_onboarding_persists_advances_and_skips(client: TestClient) -> None:
    assert client.get("/api/v1/beta/onboarding").json()["currentStep"] == 0
    advanced = client.patch(
        "/api/v1/beta/onboarding",
        json={"action": "advance", "currentStep": 3},
    )
    assert advanced.json()["currentStep"] == 3
    resumed = client.get("/api/v1/beta/onboarding")
    assert resumed.json()["currentStep"] == 3
    skipped = client.patch("/api/v1/beta/onboarding", json={"action": "skip"})
    assert skipped.json()["completed"] is True
    assert skipped.json()["skipped"] is True


def test_feedback_is_bounded_rate_limited_and_tenant_safe() -> None:
    app = create_app(beta_settings(private_beta_feedback_per_user_per_day=1))
    with TestClient(app) as client:
        payload = {
            "category": "confusing",
            "rating": 3,
            "message": "The synthetic workflow needs a clearer next step.",
            "currentRoute": "/opportunities",
        }
        created = client.post("/api/v1/beta/feedback", json=payload)
        assert created.status_code == 201
        assert created.json()["meetingId"] is None
        assert "transcript" not in created.text.lower()
        listed = client.get("/api/v1/beta/admin/feedback")
        assert listed.status_code == 200
        assert [record["id"] for record in listed.json()] == [created.json()["id"]]
        limited = client.post("/api/v1/beta/feedback", json=payload)
        assert limited.status_code == 429
        assert limited.json()["code"] == "feedback_rate_limit_exceeded"

    validation_app = create_app(beta_settings())
    with TestClient(validation_app) as client:
        assert (
            client.post(
                "/api/v1/beta/feedback",
                json={**payload, "category": "unsafe_category"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/beta/feedback",
                json={**payload, "message": "x" * 2001},
            ).status_code
            == 422
        )


def test_generation_limit_counts_created_jobs_but_not_idempotent_reuse() -> None:
    app = create_app(beta_settings(private_beta_max_generations_per_day=1))
    with TestClient(app) as client:
        meeting = client.post(
            "/api/v1/meetings",
            json={
                "title": "Quota demo",
                "meetingDate": "2026-07-01T10:00:00+10:00",
                "transcript": {"rawText": "Synthetic authorised quota transcript.", "source": "manual"},
            },
        ).json()
        base = f"/api/v1/meetings/{meeting['id']}/intelligence"
        assert client.post(f"{base}/executive-summary").status_code == 202
        assert client.post(f"{base}/executive-summary").status_code == 200
        limited = client.post(f"{base}/decisions")
        assert limited.status_code == 429
        assert limited.json()["code"] == "daily_generation_limit_exceeded"
        usage = client.get("/api/v1/beta/admin").json()["usage"]
        assert usage["generations"] == 1


def test_provider_limit_counts_attempts_by_utc_day_and_leaves_mock_unaffected() -> None:
    openai_settings = beta_settings(
        ai_provider_name="openai",
        openai_api_key="sk-test-private-beta",
        openai_model="gpt-test",
        feature_openai_provider_enabled=True,
        private_beta_max_openai_requests_per_day=1,
    )

    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        async with factory() as session, session.begin():
            await BetaService(session, tenant, openai_settings).reserve_provider_request()
        async with factory() as session:
            with pytest.raises(PublicAPIError) as limited:
                await BetaService(session, tenant, openai_settings).reserve_provider_request()
            assert limited.value.code == "daily_provider_limit_exceeded"

        yesterday = datetime.now(UTC).date() - timedelta(days=1)
        async with factory() as session, session.begin():
            session.add(
                AIUsageCounter(
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    usage_date=yesterday,
                    generation_count=999,
                    provider_request_count=999,
                )
            )
        async with factory() as session:
            usage = await BetaService(session, tenant, openai_settings).get_usage()
            assert usage.generations == 0
            assert usage.provider_requests == 1

        mock_tenant = TenantContext(SECONDARY_ORGANISATION_ID, SECONDARY_USER_ID, "admin")
        async with factory() as session, session.begin():
            await BetaService(session, mock_tenant, beta_settings()).reserve_provider_request()
        async with factory() as session:
            mock_counter = await session.get(
                AIUsageCounter,
                (SECONDARY_ORGANISATION_ID, datetime.now(UTC).date()),
            )
            assert mock_counter is None
        await engine.dispose()

    asyncio.run(scenario())


def test_disabled_feature_routes_fail_closed_and_capabilities_are_safe() -> None:
    app = create_app(
        beta_settings(
            feature_revenue_brain_enabled=False,
            feature_opportunity_workspace_enabled=False,
            feature_data_export_enabled=False,
        )
    )
    with TestClient(app) as client:
        capabilities = client.get("/api/v1/beta/capabilities")
        assert capabilities.status_code == 200
        assert capabilities.json()["featureFlags"]["revenueBrain"] is False
        assert client.get(f"/api/v1/accounts/{uuid.uuid4()}/brain").status_code == 404
        assert client.post("/api/v1/beta/admin/exports").status_code == 404


def test_deletion_request_requires_flag_admin_and_exact_phrase() -> None:
    app = create_app(beta_settings(feature_organisation_deletion_enabled=True))
    with TestClient(app) as client:
        wrong = client.post(
            "/api/v1/beta/admin/organisation-deletion",
            json={"confirmation": "DELETE wrong-organisation"},
        )
        assert wrong.status_code == 422
        accepted = client.post(
            "/api/v1/beta/admin/organisation-deletion",
            json={"confirmation": "DELETE example-revenue-team"},
        )
        assert accepted.status_code == 202
        assert accepted.json()["status"] == "pending"


def test_disabled_membership_is_rejected_promptly(client: TestClient) -> None:
    del client

    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            identity = VerifiedIdentity(
                external_auth_id="user_clerk_disabled_test",
                external_organisation_id="org_clerk_disabled_test",
                display_name="Beta Member",
                email="member@example.test",
                organisation_name="Synthetic disabled-member test",
                role="admin",
                auth_mode="clerk",
            )
            resolved = await _resolve_identity(session, identity)
            membership = await session.get(
                OrganisationMembership,
                (resolved.organisation_id, resolved.user_id),
            )
            user = await session.get(User, resolved.user_id)
            organisation = await session.get(Organisation, resolved.organisation_id)
            assert membership is not None
            assert user is not None
            assert organisation is not None
            user.status = "disabled"
            await session.commit()
            with pytest.raises(AuthenticationError, match="inactive"):
                await _resolve_identity(session, identity)
            user.status = "active"
            membership.status = "disabled"
            await session.commit()
            with pytest.raises(AuthenticationError, match="disabled"):
                await _resolve_identity(session, identity)
            membership.status = "active"
            await session.commit()
            await session.delete(membership)
            await session.delete(organisation)
            await session.delete(user)
            await session.commit()
        await engine.dispose()

    asyncio.run(scenario())


def test_demo_seed_is_tenant_scoped_idempotent_and_resettable() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = beta_settings(visual_storage_directory=str(TEST_VISUAL_STORAGE))
        first = await seed_demo_data(factory, PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, settings)
        second = await seed_demo_data(factory, PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, settings)
        assert first == second
        assert first["provider_calls"] == 0
        online_interaction_ids = first["online_meeting_interaction_ids"]
        assert isinstance(online_interaction_ids, tuple)
        _, _, meeting_ids, _ = demo_ids(PRIMARY_ORGANISATION_ID)
        interaction_ids = demo_interaction_ids(PRIMARY_ORGANISATION_ID)
        debrief_ids = demo_debrief_ids(PRIMARY_ORGANISATION_ID)
        visual_ids = demo_visual_ids(PRIMARY_ORGANISATION_ID)
        source_evidence_ids = demo_source_evidence_ids(PRIMARY_ORGANISATION_ID)
        marker_ids = demo_marker_ids(PRIMARY_ORGANISATION_ID)
        live_ids = demo_live_ids(PRIMARY_ORGANISATION_ID)
        debrief_interaction_ids = debrief_ids[:5]
        companion_interaction_ids, companion_meeting_ids, _, brief_ids = demo_companion_ids(PRIMARY_ORGANISATION_ID)
        async with factory() as session:
            assert all([await session.get(Meeting, meeting_id) is not None for meeting_id in meeting_ids])
            assert all(
                [
                    await session.get(Transcript, transcript_id) is not None
                    for transcript_id in demo_ids(PRIMARY_ORGANISATION_ID)[3]
                ]
            )
            assert all(
                [
                    await session.get(
                        TranscriptVersion,
                        uuid.uuid5(
                            UUID("d7838892-ce0b-434a-a8e9-445767115063"),
                            f"{PRIMARY_ORGANISATION_ID}:transcript-version-{index + 1}",
                        ),
                    )
                    is not None
                    for index in range(2)
                ]
            )
            assert all(
                [await session.get(Interaction, interaction_id) is not None for interaction_id in interaction_ids]
            )
            assert all([await session.get(Meeting, meeting_id) is not None for meeting_id in companion_meeting_ids])
            assert all([await session.get(PreInteractionBrief, brief_id) is not None for brief_id in brief_ids])
            companion_types: set[str] = set()
            for interaction_id in companion_interaction_ids:
                companion_interaction = await session.get(Interaction, interaction_id)
                assert companion_interaction is not None
                companion_types.add(companion_interaction.interaction_type)
            assert companion_types == {"face_to_face_meeting", "phone_call", "presentation"}
            assert all(
                [
                    await session.get(Interaction, interaction_id) is not None
                    for interaction_id in debrief_interaction_ids
                ]
            )
            assert await session.get(DebriefSession, debrief_ids[5]) is not None
            assert await session.get(DebriefSession, debrief_ids[6]) is not None
            assert await session.get(InteractionIntelligenceSnapshot, debrief_ids[12]) is not None
            visual = await session.get(VisualAsset, visual_ids[0])
            assert visual is not None
            assert visual.storage_status == "available"
            assert await session.get(VisualCandidateEvidence, visual_ids[3]) is not None
            visual_snapshot = await session.get(InteractionIntelligenceSnapshot, visual_ids[4])
            assert visual_snapshot is not None
            assert visual_snapshot.schema_version == 2
            assert visual_snapshot.content_json["sourceLabel"] == "customer whiteboard"
            customer_document = await session.get(DocumentSource, source_evidence_ids["customer-rfp:source"])
            seller_document = await session.get(DocumentSource, source_evidence_ids["seller-proposal:source"])
            inbound_email = await session.get(EmailSource, source_evidence_ids["customer-inbound:source"])
            outbound_email = await session.get(EmailSource, source_evidence_ids["seller-outbound:source"])
            assert customer_document is not None
            assert customer_document.source_ownership == "customer_provided"
            assert seller_document is not None
            assert seller_document.source_ownership == "salesperson_provided"
            assert inbound_email is not None
            assert inbound_email.origin_class == "customer_direct"
            assert outbound_email is not None
            assert outbound_email.origin_class == "salesperson_reported"
            source_candidates = [
                await session.get(
                    SourceCandidateEvidence,
                    source_evidence_ids[f"{label}:candidate"],
                )
                for label in (
                    "customer-rfp",
                    "seller-proposal",
                    "customer-inbound",
                    "seller-outbound",
                )
            ]
            assert all(candidate is not None for candidate in source_candidates)
            for candidate in source_candidates:
                assert candidate is not None
                SourceCandidateLocation.model_validate(candidate.source_location_json)
            assert all(
                [
                    await session.get(
                        RevenueBrainSourceSnapshot,
                        source_evidence_ids[f"{label}:snapshot"],
                    )
                    is not None
                    for label in (
                        "customer-rfp",
                        "seller-proposal",
                        "customer-inbound",
                        "seller-outbound",
                    )
                ]
            )
            assert all([await session.get(InteractionMarker, marker_id) is not None for marker_id in marker_ids])
            live_session = await session.get(LiveInteractionSession, live_ids["session"])
            assert live_session is not None
            assert live_session.status == "completed"
            assert await session.get(ProvisionalSignal, live_ids["buying-signal"]) is not None
            live_progress = await session.get(LiveBriefProgress, live_ids["brief-progress"])
            assert live_progress is not None
            assert live_progress.progress_status == "possibly_addressed"
            metadata_rows = [
                await session.scalar(
                    select(OnlineMeetingMetadata).where(
                        OnlineMeetingMetadata.organisation_id == PRIMARY_ORGANISATION_ID,
                        OnlineMeetingMetadata.interaction_id == interaction_id,
                    )
                )
                for interaction_id in online_interaction_ids
            ]
            assert [item.meeting_platform for item in metadata_rows if item is not None] == [
                "microsoft_teams",
                "zoom",
                "google_meet",
            ]
            assert [item.capture_source for item in metadata_rows if item is not None] == [
                "platform_transcript",
                "platform_recording",
                "ai_debrief",
            ]
            assert (
                await session.scalar(
                    select(OnlineMeetingTranscriptImport).where(
                        OnlineMeetingTranscriptImport.organisation_id == PRIMARY_ORGANISATION_ID
                    )
                )
                is not None
            )
            assert (
                await session.scalar(
                    select(RecordingSession).where(
                        RecordingSession.organisation_id == PRIMARY_ORGANISATION_ID,
                        RecordingSession.recording_source == "platform_recording",
                    )
                )
                is not None
            )
            assert (TEST_VISUAL_STORAGE / visual.storage_key).is_file()
            assert not any(
                [
                    await session.get(Meeting, meeting_id) is not None
                    for meeting_id in demo_ids(SECONDARY_ORGANISATION_ID)[2]
                ]
            )
        retention = await run_retention(
            factory,
            beta_settings(private_beta_default_retention_days=90),
            PRIMARY_ORGANISATION_ID,
            dry_run=True,
            batch_size=100,
        )
        assert retention.eligible_meetings == 0
        reset = await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)
        assert reset["provider_calls"] == 0
        async with factory() as session:
            assert all([await session.get(Meeting, meeting_id) is None for meeting_id in meeting_ids])
            assert all([await session.get(Interaction, interaction_id) is None for interaction_id in interaction_ids])
            assert all(
                [await session.get(Interaction, interaction_id) is None for interaction_id in debrief_interaction_ids]
            )
            assert all([await session.get(PreInteractionBrief, brief_id) is None for brief_id in brief_ids])
            assert await session.get(VisualAsset, visual_ids[0]) is None
            assert all(
                [
                    await session.get(DocumentSource, source_evidence_ids[f"{label}:source"]) is None
                    for label in ("customer-rfp", "seller-proposal")
                ]
            )
            assert all(
                [
                    await session.get(EmailSource, source_evidence_ids[f"{label}:source"]) is None
                    for label in ("customer-inbound", "seller-outbound")
                ]
            )
            assert all([await session.get(InteractionMarker, marker_id) is None for marker_id in marker_ids])
            assert await session.get(LiveInteractionSession, live_ids["session"]) is None
            assert not (TEST_VISUAL_STORAGE / visual.storage_key).exists()
        await engine.dispose()

    asyncio.run(scenario())


def test_retention_dry_run_and_execution_are_bounded_and_idempotent() -> None:
    meeting_id = uuid.uuid4()
    interaction_id = uuid.uuid4()
    transcript_id = uuid.uuid4()
    other_meeting_id = uuid.uuid4()
    other_interaction_id = uuid.uuid4()
    other_transcript_id = uuid.uuid4()
    brief_id = uuid.uuid4()
    other_brief_id = uuid.uuid4()
    old = datetime.now(UTC) - timedelta(days=200)

    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            session.add(
                Interaction(
                    id=interaction_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    title="Old synthetic meeting",
                    interaction_type="online_meeting",
                    lifecycle_status="completed",
                    scheduled_start_at=old,
                    actual_end_at=old,
                    creation_origin="meeting_compatibility",
                    created_by_user_id=PRIMARY_USER_ID,
                    created_at=old,
                    updated_at=old,
                )
            )
            session.add(
                Meeting(
                    id=meeting_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    interaction_id=interaction_id,
                    title="Old synthetic meeting",
                    meeting_date=old,
                    meeting_type="remote",
                    status="completed",
                    owner_user_id=PRIMARY_USER_ID,
                    created_by=PRIMARY_USER_ID,
                    updated_by=PRIMARY_USER_ID,
                )
            )
            session.add(
                Transcript(
                    id=transcript_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    meeting_id=meeting_id,
                    raw_text="Old synthetic transcript.",
                    language="en",
                    source="manual",
                    created_at=old,
                    updated_at=old,
                )
            )
            session.add(
                PreInteractionBrief(
                    id=brief_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    interaction_id=interaction_id,
                    source_context_fingerprint="a" * 64,
                    brief_version=1,
                    schema_version=1,
                    status="completed",
                    content_json={"synthetic": "retention fixture"},
                    source_references_json=[],
                    created_by_user_id=PRIMARY_USER_ID,
                    created_at=old,
                )
            )
            session.add(
                Interaction(
                    id=other_interaction_id,
                    organisation_id=SECONDARY_ORGANISATION_ID,
                    title="Other tenant old synthetic meeting",
                    interaction_type="online_meeting",
                    lifecycle_status="completed",
                    scheduled_start_at=old,
                    actual_end_at=old,
                    creation_origin="meeting_compatibility",
                    created_by_user_id=SECONDARY_USER_ID,
                    created_at=old,
                    updated_at=old,
                )
            )
            session.add(
                Meeting(
                    id=other_meeting_id,
                    organisation_id=SECONDARY_ORGANISATION_ID,
                    interaction_id=other_interaction_id,
                    title="Other tenant old synthetic meeting",
                    meeting_date=old,
                    meeting_type="remote",
                    status="completed",
                    owner_user_id=SECONDARY_USER_ID,
                    created_by=SECONDARY_USER_ID,
                    updated_by=SECONDARY_USER_ID,
                )
            )
            session.add(
                Transcript(
                    id=other_transcript_id,
                    organisation_id=SECONDARY_ORGANISATION_ID,
                    meeting_id=other_meeting_id,
                    raw_text="Other tenant old synthetic transcript.",
                    language="en",
                    source="manual",
                    created_at=old,
                    updated_at=old,
                )
            )
            session.add(
                PreInteractionBrief(
                    id=other_brief_id,
                    organisation_id=SECONDARY_ORGANISATION_ID,
                    interaction_id=other_interaction_id,
                    source_context_fingerprint="b" * 64,
                    brief_version=1,
                    schema_version=1,
                    status="completed",
                    content_json={"synthetic": "other tenant retention fixture"},
                    source_references_json=[],
                    created_by_user_id=SECONDARY_USER_ID,
                    created_at=old,
                )
            )
            await session.commit()
        settings = beta_settings(private_beta_default_retention_days=90)
        dry_run = await run_retention(factory, settings, PRIMARY_ORGANISATION_ID, dry_run=True, batch_size=1)
        assert dry_run.eligible_meetings == 1
        assert dry_run.removed["pre_interaction_briefs"] == 1
        async with factory() as session:
            assert await session.get(Meeting, meeting_id) is not None
        removed = await run_retention(factory, settings, PRIMARY_ORGANISATION_ID, dry_run=False, batch_size=1)
        assert removed.removed["transcripts"] == 1
        assert removed.removed["interactions"] == 1
        assert removed.removed["pre_interaction_briefs"] == 1
        repeated = await run_retention(factory, settings, PRIMARY_ORGANISATION_ID, dry_run=False, batch_size=1)
        assert repeated.eligible_meetings == 0
        async with factory() as session:
            assert await session.get(Meeting, other_meeting_id) is not None
            assert await session.get(Transcript, other_transcript_id) is not None
            assert await session.get(PreInteractionBrief, other_brief_id) is not None
        await engine.dispose()

    asyncio.run(scenario())


def test_organisation_deletion_is_atomic_tenant_scoped_and_preserves_shared_user(tmp_path: Path) -> None:
    target_organisation_id = uuid.uuid4()
    target_company_id = uuid.uuid4()
    request_id = uuid.uuid4()
    export_request_id = uuid.uuid4()
    export_path = tmp_path / f"revenueos-export-{export_request_id}.json"
    export_path.write_text('{"synthetic":"authorised"}\n', encoding="utf-8")
    settings = beta_settings(private_beta_export_directory=str(tmp_path))

    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            session.add(
                Organisation(
                    id=target_organisation_id,
                    external_auth_id=f"org_delete_{target_organisation_id}",
                    name="Synthetic deletion target",
                    slug=f"synthetic-delete-{target_organisation_id.hex[:8]}",
                )
            )
            session.add(
                OrganisationMembership(
                    organisation_id=target_organisation_id,
                    user_id=PRIMARY_USER_ID,
                    role="admin",
                    status="active",
                )
            )
            await session.flush()
            session.add(
                Company(
                    id=target_company_id,
                    organisation_id=target_organisation_id,
                    name="Synthetic deletion company",
                    owner_user_id=PRIMARY_USER_ID,
                )
            )
            session.add(
                BetaDataRequest(
                    id=request_id,
                    organisation_id=target_organisation_id,
                    requested_by_user_id=PRIMARY_USER_ID,
                    request_type="organisation_deletion",
                    status="processing",
                    confirmed_at=datetime.now(UTC),
                )
            )
            session.add(
                BetaDataRequest(
                    id=export_request_id,
                    organisation_id=target_organisation_id,
                    requested_by_user_id=PRIMARY_USER_ID,
                    request_type="export",
                    status="completed",
                    confirmed_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                    output_path=str(export_path),
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
            await session.commit()

        assert (
            await delete_organisation(factory, settings, target_organisation_id, request_id) == target_organisation_id
        )
        assert not export_path.exists()
        async with factory() as session:
            assert await session.get(Organisation, target_organisation_id) is None
            assert await session.get(Company, target_company_id) is None
            assert await session.get(User, PRIMARY_USER_ID) is not None
            assert await session.get(Organisation, PRIMARY_ORGANISATION_ID) is not None
            assert await session.get(Organisation, SECONDARY_ORGANISATION_ID) is not None
        await engine.dispose()

    asyncio.run(scenario())


def test_organisation_deletion_reports_unsafe_export_path_and_retries_safely(tmp_path: Path) -> None:
    target_organisation_id = uuid.uuid4()
    request_id = uuid.uuid4()
    export_request_id = uuid.uuid4()
    export_root = tmp_path / "exports"
    outside_path = tmp_path / f"revenueos-export-{export_request_id}.json"
    outside_path.write_text('{"must":"remain"}\n', encoding="utf-8")
    settings = beta_settings(private_beta_export_directory=str(export_root))

    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            session.add(
                Organisation(
                    id=target_organisation_id,
                    external_auth_id=f"org_delete_retry_{target_organisation_id}",
                    name="Synthetic deletion retry target",
                    slug=f"synthetic-delete-retry-{target_organisation_id.hex[:8]}",
                )
            )
            session.add(
                OrganisationMembership(
                    organisation_id=target_organisation_id,
                    user_id=PRIMARY_USER_ID,
                    role="admin",
                    status="active",
                )
            )
            await session.flush()
            session.add_all(
                [
                    BetaDataRequest(
                        id=request_id,
                        organisation_id=target_organisation_id,
                        requested_by_user_id=PRIMARY_USER_ID,
                        request_type="organisation_deletion",
                        status="processing",
                        confirmed_at=datetime.now(UTC),
                    ),
                    BetaDataRequest(
                        id=export_request_id,
                        organisation_id=target_organisation_id,
                        requested_by_user_id=PRIMARY_USER_ID,
                        request_type="export",
                        status="completed",
                        confirmed_at=datetime.now(UTC),
                        completed_at=datetime.now(UTC),
                        output_path=str(outside_path),
                        expires_at=datetime.now(UTC) + timedelta(hours=1),
                    ),
                ]
            )
            await session.commit()

        with pytest.raises(ValueError, match="outside"):
            await delete_organisation(factory, settings, target_organisation_id, request_id)
        async with factory() as session:
            failed = await session.get(BetaDataRequest, request_id)
            unsafe_export = await session.get(BetaDataRequest, export_request_id)
            assert failed is not None and failed.status == "failed"
            assert failed.failure_code == "organisation_deletion_failed"
            assert unsafe_export is not None
            unsafe_export.output_path = None
            await session.commit()
        assert outside_path.exists()

        assert (
            await delete_organisation(factory, settings, target_organisation_id, request_id) == target_organisation_id
        )
        async with factory() as session:
            assert await session.get(Organisation, target_organisation_id) is None
        await engine.dispose()

    asyncio.run(scenario())


def test_export_is_deterministic_tenant_scoped_and_excludes_internal_fields(tmp_path: Path) -> None:
    settings = beta_settings(private_beta_export_directory=str(tmp_path))
    app = create_app(settings)
    with TestClient(app) as client:
        company = client.post(
            "/api/v1/companies",
            json={"name": "Export Test Company", "status": "prospect"},
        )
        assert company.status_code == 201
        interaction = client.post(
            "/api/v1/interactions",
            json={
                "title": "Export test online meeting",
                "interactionType": "online_meeting",
                "lifecycleStatus": "completed",
                "companyId": company.json()["id"],
                "actualEndAt": "2026-07-25T05:00:00Z",
                "meetingPlatform": "google_meet",
                "meetingUrl": "https://meet.google.com/abc-defg-hij?authuser=secret",
            },
        )
        assert interaction.status_code == 201
        brief = client.post(f"/api/v1/interactions/{interaction.json()['id']}/companion/brief")
        assert brief.status_code == 200
        assert brief.json()["state"] == "completed"
        transcript_import = client.post(
            f"/api/v1/interactions/{interaction.json()['id']}/online-meeting/transcript",
            json={
                "fileName": "export-meeting.txt",
                "contentBase64": base64.b64encode(b"Customer: Export-safe transcript").decode(),
                "provenance": "platform_generated",
                "language": "en-AU",
                "userAttestedAuthority": True,
                "externalProcessingAcknowledged": True,
                "idempotencyKey": "export-online-transcript",
            },
        )
        assert transcript_import.status_code == 201, transcript_import.text
        document_content = b"SECURITY REQUIREMENTS:\n\nThe customer requires SSO integration."
        document = client.post(
            "/api/v1/evidence/documents",
            json={
                "companyId": company.json()["id"],
                "documentType": "security_questionnaire",
                "sourceOwnership": "customer_provided",
                "filename": "export-security-requirements.txt",
                "mimeType": "text/plain",
                "contentBase64": base64.b64encode(document_content).decode(),
                "checksumSha256": hashlib.sha256(document_content).hexdigest(),
                "documentAt": "2026-07-25T04:00:00Z",
                "authorityConfirmed": True,
                "externalProcessingAcknowledged": True,
                "idempotencyKey": "export-document-evidence",
            },
        )
        assert document.status_code == 201, document.text
        processed_document = client.post(
            f"/api/v1/evidence/documents/{document.json()['id']}/process",
            json={"idempotencyKey": "export-document-process"},
        )
        assert processed_document.status_code == 200, processed_document.text
        reviewed_document = client.post(
            f"/api/v1/evidence/documents/{document.json()['id']}/review",
            json={
                "decisions": [
                    {"candidateId": candidate["id"], "decision": "accept"}
                    for candidate in processed_document.json()["candidates"]
                ],
                "idempotencyKey": "export-document-review",
            },
        )
        assert reviewed_document.status_code == 200, reviewed_document.text
        email_body = "We will proceed with the security review.\n\n--\nCasey"
        email = client.post(
            "/api/v1/evidence/emails",
            json={
                "companyId": company.json()["id"],
                "sourceType": "manually_pasted",
                "direction": "inbound",
                "subject": "Security review",
                "body": email_body,
                "messageAt": "2026-07-25T04:30:00Z",
                "authorityConfirmed": True,
                "externalProcessingAcknowledged": True,
                "idempotencyKey": "export-email-evidence",
            },
        )
        assert email.status_code == 201, email.text
        processed_email = client.post(
            f"/api/v1/evidence/emails/{email.json()['id']}/process",
            json={"idempotencyKey": "export-email-process"},
        )
        assert processed_email.status_code == 200, processed_email.text
        reviewed_email = client.post(
            f"/api/v1/evidence/emails/{email.json()['id']}/review",
            json={
                "decisions": [
                    {"candidateId": candidate["id"], "decision": "accept"}
                    for candidate in processed_email.json()["candidates"]
                ],
                "idempotencyKey": "export-email-review",
            },
        )
        assert reviewed_email.status_code == 200, reviewed_email.text
        request = client.post("/api/v1/beta/admin/exports")
        assert request.status_code == 202
        request_id = UUID(request.json()["id"])

    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        capture_session_id = uuid.uuid4()
        evidence_id = uuid.uuid4()
        marker_id = uuid.uuid4()
        async with factory() as session, session.begin():
            session.add(
                CaptureSession(
                    id=capture_session_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    interaction_id=UUID(interaction.json()["id"]),
                    capture_type="manual_notes",
                    status="completed",
                    started_by_user_id=PRIMARY_USER_ID,
                )
            )
            session.add(
                Evidence(
                    id=evidence_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    interaction_id=UUID(interaction.json()["id"]),
                    capture_session_id=capture_session_id,
                    evidence_type="user_observation",
                    origin_class="salesperson_reported",
                    support_class="reported",
                    validation_state="verified",
                    captured_by_user_id=PRIMARY_USER_ID,
                    lifecycle_status="available",
                )
            )
            session.add(
                InteractionMarker(
                    id=marker_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    interaction_id=UUID(interaction.json()["id"]),
                    created_by_user_id=PRIMARY_USER_ID,
                    marker_type="decision",
                    recording_offset_ms=15_000,
                    idempotency_key="export-marker-internal-key",
                )
            )
        path = await generate_export(factory, settings, PRIMARY_ORGANISATION_ID, request_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["exportVersion"] == 12
        assert payload["organisation"]["id"] == str(PRIMARY_ORGANISATION_ID)
        assert payload["interactions"][0]["id"] == interaction.json()["id"]
        exported_marker = next(item for item in payload["interactionMarkers"] if item["id"] == str(marker_id))
        assert exported_marker["marker_type"] == "decision"
        assert "idempotency_key" not in exported_marker
        exported_capture = next(item for item in payload["captureSessions"] if item["id"] == str(capture_session_id))
        assert exported_capture["status"] == "completed"
        exported_evidence = next(item for item in payload["evidence"] if item["id"] == str(evidence_id))
        assert exported_evidence["origin_class"] == "salesperson_reported"
        assert payload["preInteractionBriefs"][0]["interaction_id"] == interaction.json()["id"]
        assert payload["preInteractionBriefs"][0]["source_references_json"]
        assert payload["actionProposals"] == []
        assert payload["actionProposalVersions"] == []
        assert payload["actionAuditEvents"] == []
        assert payload["debriefSessions"] == []
        assert payload["debriefTurns"] == []
        assert payload["evidenceFragments"] == []
        assert payload["candidateEvidence"] == []
        assert payload["visualAssets"] == []
        assert payload["visualCandidateEvidence"] == []
        assert payload["documentSources"][0]["contentExportStatus"] == "included"
        assert base64.b64decode(payload["documentSources"][0]["contentBase64"]) == document_content
        assert payload["documentFragments"][0]["content_text"]
        assert payload["emailSources"][0]["body_text"] == email_body
        assert payload["emailSources"][0]["normalized_body_text"] == ("We will proceed with the security review.")
        assert payload["sourceCandidateEvidence"]
        assert {item["review_state"] for item in payload["sourceCandidateEvidence"]} == {"accepted"}
        assert payload["revenueBrainSourceSnapshots"]
        assert payload["interactionIntelligenceSnapshots"] == []
        assert payload["revenueBrainInteractionSnapshots"] == []
        assert payload["onlineMeetingMetadata"][0]["meeting_platform"] == "google_meet"
        assert payload["onlineMeetingMetadata"][0]["safe_meeting_url"] == ("https://meet.google.com/abc-defg-hij")
        assert payload["onlineMeetingTranscriptImports"][0]["provenance"] == "platform_generated"
        assert "idempotency_key" not in payload["onlineMeetingTranscriptImports"][0]
        exported_text = path.read_text(encoding="utf-8")
        assert str(SECONDARY_ORGANISATION_ID) not in exported_text
        forbidden = {"worker_id", "lease_expires_at", "last_error_message_safe", "provider_request_id"}
        assert not any(field in exported_text for field in forbidden)
        async with factory() as session:
            record = await session.get(BetaDataRequest, request_id)
            assert record is not None
            assert record.expires_at is not None
            expiry = (
                record.expires_at if record.expires_at.tzinfo is not None else record.expires_at.replace(tzinfo=UTC)
            )
            assert expiry > datetime.now(UTC)
        await engine.dispose()

    asyncio.run(scenario())
    with TestClient(app) as client:
        download = client.get(f"/api/v1/beta/admin/exports/{request_id}/download")
        assert download.status_code == 200
        assert download.json()["exportVersion"] == 12
        assert download.headers["Cache-Control"] == "private, no-store"
        assert download.headers["X-Content-Type-Options"] == "nosniff"

    async def tamper(*, output_path: str, expires_at: datetime) -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            record = await session.get(BetaDataRequest, request_id)
            assert record is not None
            record.output_path = output_path
            record.expires_at = expires_at
            await session.commit()
        await engine.dispose()

    asyncio.run(
        tamper(
            output_path=str(tmp_path.parent / "outside-export.json"),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    with TestClient(app) as client:
        assert client.get(f"/api/v1/beta/admin/exports/{request_id}/download").status_code == 404

    asyncio.run(
        tamper(
            output_path=str(tmp_path / f"revenueos-export-{request_id}.json"),
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
    )
    with TestClient(app) as client:
        assert client.get(f"/api/v1/beta/admin/exports/{request_id}/download").status_code == 410

    async def purge() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        assert (
            await purge_expired_exports(
                factory,
                settings,
                PRIMARY_ORGANISATION_ID,
                batch_size=1,
            )
            == 1
        )
        async with factory() as session:
            record = await session.get(BetaDataRequest, request_id)
            assert record is not None
            assert record.output_path is None
        await engine.dispose()

    asyncio.run(purge())
    assert not (tmp_path / f"revenueos-export-{request_id}.json").exists()
