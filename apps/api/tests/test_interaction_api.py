from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import AuthenticatedUser, get_current_user
from revenueos.models import CaptureSession, Evidence, Interaction, InteractionIntelligenceSnapshot, InteractionMarker

from .conftest import (
    PRIMARY_ORGANISATION_ID,
    PRIMARY_USER_ID,
    SECONDARY_ORGANISATION_ID,
    SECONDARY_USER_ID,
    TEST_DB_URL,
)
from .test_business_api import create_company, create_contact, create_opportunity
from .test_meeting_api import cast_auth_dependency, create_meeting, secondary_user


def create_interaction(
    client: TestClient,
    *,
    title: str = "Pilot workshop",
    interaction_type: str = "workshop",
    company_id: str | None = None,
    opportunity_id: str | None = None,
    contact_id: str | None = None,
    call_direction: str | None = None,
    meeting_platform: str | None = None,
    meeting_url: str | None = None,
    external_meeting_id: str | None = None,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/interactions",
        json={
            "title": title,
            "interactionType": interaction_type,
            "lifecycleStatus": "planned",
            "companyId": company_id,
            "opportunityId": opportunity_id,
            **({"contactId": contact_id} if contact_id is not None else {}),
            **({"callDirection": call_direction} if call_direction is not None else {}),
            **({"meetingPlatform": meeting_platform} if meeting_platform is not None else {}),
            **({"meetingUrl": meeting_url} if meeting_url is not None else {}),
            **({"externalMeetingId": external_meeting_id} if external_meeting_id is not None else {}),
            "scheduledStartAt": "2026-08-12T09:00:00+10:00",
            "scheduledEndAt": "2026-08-12T11:00:00+10:00",
            "timezone": "Australia/Sydney",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_phone_call_metadata_contact_tenant_safety_outcomes_and_duration(client: TestClient) -> None:
    company_id = str(create_company(client, name="Phone account")["id"])
    contact_id = str(create_contact(client, company_id, first_name="Priya")["id"])
    opportunity_id = str(create_opportunity(client, company_id, name="Phone opportunity")["id"])
    call = create_interaction(
        client,
        title="Pricing follow-up call",
        interaction_type="phone_call",
        company_id=company_id,
        opportunity_id=opportunity_id,
        contact_id=contact_id,
        call_direction="outbound",
    )
    call_id = str(call["id"])
    assert call["contactId"] == contact_id
    assert call["callDirection"] == "outbound"
    assert call["callOutcome"] is None
    assert call["recordingAvailable"] is False
    assert call["captureMethods"] == []

    inbound = client.patch(
        f"/api/v1/interactions/{call_id}",
        json={"callDirection": "inbound"},
    )
    assert inbound.status_code == 200, inbound.text
    assert inbound.json()["callDirection"] == "inbound"
    unknown = client.patch(
        f"/api/v1/interactions/{call_id}",
        json={"callDirection": "unknown"},
    )
    assert unknown.status_code == 200, unknown.text
    assert unknown.json()["callDirection"] == "unknown"

    started = client.post(
        f"/api/v1/interactions/{call_id}/start",
        json={"actualStartAt": "2026-08-12T09:00:00+10:00"},
    )
    assert started.status_code == 200, started.text
    completed = client.post(
        f"/api/v1/interactions/{call_id}/complete",
        json={
            "actualEndAt": "2026-08-12T09:02:30+10:00",
            "callOutcome": "connected",
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["durationSeconds"] == 150
    assert completed.json()["callOutcome"] == "connected"

    invalid_non_call = client.post(
        "/api/v1/interactions",
        json={
            "title": "Not a phone call",
            "interactionType": "workshop",
            "contactId": contact_id,
            "callDirection": "inbound",
        },
    )
    assert invalid_non_call.status_code == 422
    assert invalid_non_call.json()["code"] == "invalid_phone_metadata"


def test_phone_contact_company_consistency_and_cross_tenant_hiding(
    app: FastAPI,
    client: TestClient,
) -> None:
    company_id = str(create_company(client, name="Primary phone company")["id"])
    opportunity_id = str(create_opportunity(client, company_id, name="Primary phone opportunity")["id"])
    other_company_id = str(create_company(client, name="Different phone company")["id"])
    other_contact_id = str(create_contact(client, other_company_id, first_name="Morgan")["id"])
    mismatch = client.post(
        "/api/v1/interactions",
        json={
            "title": "Mismatched contact call",
            "interactionType": "phone_call",
            "companyId": company_id,
            "opportunityId": opportunity_id,
            "contactId": other_contact_id,
            "callDirection": "unknown",
        },
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["code"] == "inconsistent_relationship"

    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    hidden_company_id = str(create_company(client, name="Hidden phone company")["id"])
    hidden_contact_id = str(create_contact(client, hidden_company_id, first_name="Hidden")["id"])
    app.dependency_overrides.pop(get_current_user)
    hidden = client.post(
        "/api/v1/interactions",
        json={
            "title": "Cross-tenant phone contact",
            "interactionType": "phone_call",
            "contactId": hidden_contact_id,
            "callDirection": "unknown",
        },
    )
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "contact_not_found"


@pytest.mark.parametrize("outcome", ["no_answer", "voicemail", "cancelled"])
def test_phone_non_connection_outcomes_remain_events_without_intelligence(
    client: TestClient,
    outcome: str,
) -> None:
    interaction = create_interaction(
        client,
        title=f"Phone call {outcome}",
        interaction_type="phone_call",
        call_direction="unknown",
    )

    completed = client.post(
        f"/api/v1/interactions/{interaction['id']}/complete",
        json={"callOutcome": outcome},
    )

    assert completed.status_code == 200, completed.text
    assert completed.json()["callOutcome"] == outcome
    assert completed.json()["intelligenceState"] == "not_applicable"


def test_interaction_crud_filters_completion_and_terminal_lifecycle(client: TestClient) -> None:
    company_id = str(create_company(client)["id"])
    opportunity_id = str(create_opportunity(client, company_id)["id"])
    interaction = create_interaction(
        client,
        title="Customer pilot workshop",
        company_id=company_id,
        opportunity_id=opportunity_id,
    )
    interaction_id = str(interaction["id"])
    assert interaction["organisationId"] == str(PRIMARY_ORGANISATION_ID)
    assert interaction["creationOrigin"] == "manual"
    assert interaction["meetingId"] is None
    assert interaction["createdByUserId"] == str(PRIMARY_USER_ID)

    listed = client.get(
        "/api/v1/interactions",
        params={
            "search": "pilot",
            "opportunityId": opportunity_id,
            "interactionType": "workshop",
            "status": "planned",
            "dateFrom": "2026-08-01T00:00:00Z",
            "dateTo": "2026-08-31T23:59:59Z",
        },
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == interaction_id

    started = client.patch(
        f"/api/v1/interactions/{interaction_id}",
        json={
            "lifecycleStatus": "in_progress",
            "actualStartAt": "2026-08-12T09:05:00+10:00",
        },
    )
    assert started.status_code == 200, started.text
    assert started.json()["lifecycleStatus"] == "in_progress"

    completed = client.post(
        f"/api/v1/interactions/{interaction_id}/complete",
        json={"actualEndAt": "2026-08-12T10:45:00+10:00"},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["lifecycleStatus"] == "completed"
    assert completed.json()["actualEndAt"] == "2026-08-12T00:45:00Z"

    repeated = client.post(f"/api/v1/interactions/{interaction_id}/complete", json={})
    assert repeated.status_code == 200
    assert repeated.json()["actualEndAt"] == completed.json()["actualEndAt"]

    invalid = client.patch(
        f"/api/v1/interactions/{interaction_id}",
        json={"lifecycleStatus": "planned"},
    )
    assert invalid.status_code == 409
    assert invalid.json()["code"] == "invalid_lifecycle_transition"


def test_companion_start_and_markers_are_idempotent_immutable_and_not_evidence(client: TestClient) -> None:
    interaction = create_interaction(client, interaction_type="face_to_face_meeting")
    interaction_id = str(interaction["id"])

    started = client.post(f"/api/v1/interactions/{interaction_id}/start", json={})
    assert started.status_code == 200, started.text
    assert started.json()["lifecycleStatus"] == "in_progress"
    actual_start_at = started.json()["actualStartAt"]
    repeated_start = client.post(f"/api/v1/interactions/{interaction_id}/start", json={})
    assert repeated_start.status_code == 200
    assert repeated_start.json()["actualStartAt"] == actual_start_at

    payload = {
        "markerType": "buying_signal",
        "recordingOffsetMs": 12_000,
        "idempotencyKey": "companion-marker-1",
    }
    created = client.post(f"/api/v1/interactions/{interaction_id}/companion/markers", json=payload)
    assert created.status_code == 201, created.text
    marker_id = created.json()["id"]
    assert created.json()["markerType"] == "buying_signal"
    assert created.json()["recordingOffsetMs"] == 12_000

    repeated = client.post(f"/api/v1/interactions/{interaction_id}/companion/markers", json=payload)
    assert repeated.status_code == 201
    assert repeated.json()["id"] == marker_id
    conflict = client.post(
        f"/api/v1/interactions/{interaction_id}/companion/markers",
        json={**payload, "markerType": "risk"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"
    assert (
        client.post(
            f"/api/v1/interactions/{interaction_id}/companion/markers",
            json={"markerType": "unsupported", "idempotencyKey": "invalid-marker"},
        ).status_code
        == 422
    )

    listed = client.get(f"/api/v1/interactions/{interaction_id}/companion/markers")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [marker_id]

    async def verify_not_evidence() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            markers = list(
                (
                    await session.scalars(
                        select(InteractionMarker).where(InteractionMarker.interaction_id == UUID(interaction_id))
                    )
                ).all()
            )
            snapshots = list(
                (
                    await session.scalars(
                        select(InteractionIntelligenceSnapshot).where(
                            InteractionIntelligenceSnapshot.interaction_id == UUID(interaction_id)
                        )
                    )
                ).all()
            )
            assert [str(item.id) for item in markers] == [marker_id]
            assert snapshots == []
        await engine.dispose()

    asyncio.run(verify_not_evidence())
    assert client.delete(f"/api/v1/interactions/{interaction_id}/companion/markers/{marker_id}").status_code == 200
    assert client.get(f"/api/v1/interactions/{interaction_id}/companion/markers").json() == []

    second = client.post(
        f"/api/v1/interactions/{interaction_id}/companion/markers",
        json={"markerType": "risk", "idempotencyKey": "companion-marker-2"},
    )
    assert second.status_code == 201
    assert client.post(f"/api/v1/interactions/{interaction_id}/complete", json={}).status_code == 200
    immutable = client.delete(f"/api/v1/interactions/{interaction_id}/companion/markers/{second.json()['id']}")
    assert immutable.status_code == 409
    assert immutable.json()["code"] == "marker_immutable"


def test_meeting_and_interaction_compatibility_stays_transactionally_aligned(client: TestClient) -> None:
    meeting = create_meeting(client, title="Compatibility discovery")
    meeting_id = str(meeting["id"])
    interaction_id = str(meeting["interactionId"])

    interaction = client.get(f"/api/v1/interactions/{interaction_id}")
    assert interaction.status_code == 200
    assert interaction.json()["meetingId"] == meeting_id
    assert interaction.json()["interactionType"] == "online_meeting"
    assert interaction.json()["title"] == "Compatibility discovery"

    updated_interaction = client.patch(
        f"/api/v1/interactions/{interaction_id}",
        json={
            "title": "Compatibility phone call",
            "interactionType": "phone_call",
            "lifecycleStatus": "in_progress",
            "scheduledStartAt": "2026-08-03T08:30:00Z",
        },
    )
    assert updated_interaction.status_code == 200, updated_interaction.text
    projected_meeting = client.get(f"/api/v1/meetings/{meeting_id}").json()
    assert projected_meeting["id"] == meeting_id
    assert projected_meeting["interactionId"] == interaction_id
    assert projected_meeting["title"] == "Compatibility phone call"
    assert projected_meeting["meetingType"] == "phone"
    assert projected_meeting["status"] == "scheduled"

    completed = client.post(f"/api/v1/interactions/{interaction_id}/complete", json={})
    assert completed.status_code == 200
    assert client.get(f"/api/v1/meetings/{meeting_id}").json()["status"] == "completed"

    incompatible = client.patch(
        f"/api/v1/interactions/{interaction_id}",
        json={"interactionType": "site_visit"},
    )
    assert incompatible.status_code == 422
    assert incompatible.json()["code"] == "incompatible_interaction_type"

    assert client.delete(f"/api/v1/meetings/{meeting_id}").status_code == 204
    assert client.get(f"/api/v1/interactions/{interaction_id}").status_code == 404

    async def verify_soft_delete() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            stored = await session.scalar(select(Interaction).where(Interaction.id == UUID(interaction_id)))
            assert stored is not None and stored.deleted_at is not None
        await engine.dispose()

    asyncio.run(verify_soft_delete())


def test_interactions_are_tenant_scoped_and_relationship_spoofing_is_hidden(
    app: FastAPI,
    client: TestClient,
) -> None:
    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    other_company_id = str(create_company(client, name="Other interaction company")["id"])
    other_interaction_id = str(create_interaction(client, company_id=other_company_id)["id"])
    app.dependency_overrides.pop(get_current_user)

    assert client.get(f"/api/v1/interactions/{other_interaction_id}").status_code == 404
    assert client.post(f"/api/v1/interactions/{other_interaction_id}/start", json={}).status_code == 404
    assert client.get(f"/api/v1/interactions/{other_interaction_id}/companion/markers").status_code == 404
    assert (
        client.patch(
            f"/api/v1/interactions/{other_interaction_id}",
            json={"title": "Cross-tenant overwrite"},
        ).status_code
        == 404
    )
    spoofed = client.post(
        "/api/v1/interactions",
        json={
            "title": "Cross-tenant link",
            "interactionType": "site_visit",
            "companyId": other_company_id,
            "organisationId": str(SECONDARY_ORGANISATION_ID),
        },
    )
    assert spoofed.status_code == 422
    assert spoofed.json()["code"] == "invalid_request"

    hidden_relationship = client.post(
        "/api/v1/interactions",
        json={
            "title": "Cross-tenant link",
            "interactionType": "site_visit",
            "companyId": other_company_id,
        },
    )
    assert hidden_relationship.status_code == 404
    assert hidden_relationship.json()["code"] == "company_not_found"


def test_interaction_api_requires_an_active_local_membership(
    app: FastAPI,
    client: TestClient,
) -> None:
    unprovisioned = AuthenticatedUser(
        user_id=uuid4(),
        external_auth_id="user_unprovisioned_interactions",
        display_name="Unprovisioned Interaction User",
        email="unprovisioned-interaction@example.test",
        organisation_id=PRIMARY_ORGANISATION_ID,
        organisation_name="Example Revenue Team",
        organisation_slug="example-revenue-team",
        role="member",
        auth_mode="mock",
    )
    app.dependency_overrides[get_current_user] = cast_auth_dependency(unprovisioned)
    response = client.get("/api/v1/interactions")
    app.dependency_overrides.pop(get_current_user)

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_evidence_and_capture_foundations_preserve_provenance_without_raw_content(client: TestClient) -> None:
    interaction_id = UUID(str(create_interaction(client)["id"]))
    capture_session_id = uuid4()
    evidence_id = uuid4()

    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            await session.execute(text("PRAGMA foreign_keys=ON"))
            session.add(
                CaptureSession(
                    id=capture_session_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    interaction_id=interaction_id,
                    capture_type="manual_notes",
                    status="completed",
                    started_by_user_id=PRIMARY_USER_ID,
                    started_at=datetime(2026, 8, 12, 1, tzinfo=UTC),
                    completed_at=datetime(2026, 8, 12, 1, 5, tzinfo=UTC),
                )
            )
            session.add(
                Evidence(
                    id=evidence_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    interaction_id=interaction_id,
                    capture_session_id=capture_session_id,
                    evidence_type="user_observation",
                    origin_class="salesperson_reported",
                    support_class="reported",
                    validation_state="unreviewed",
                    captured_by_user_id=PRIMARY_USER_ID,
                    lifecycle_status="available",
                )
            )
            await session.commit()
            evidence = await session.get(Evidence, evidence_id)
            assert evidence is not None
            evidence.validation_state = "verified"
            await session.commit()
            await session.refresh(evidence)
            assert evidence.validation_state == "verified"
            assert evidence.origin_class == "salesperson_reported"

            session.add(
                Evidence(
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    interaction_id=uuid4(),
                    evidence_type="system_metadata",
                    origin_class="system_metadata",
                    support_class="direct",
                    validation_state="not_applicable",
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()

            session.add(
                Evidence(
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    interaction_id=interaction_id,
                    evidence_type="unsupported_source",
                    origin_class="system_metadata",
                    support_class="direct",
                    validation_state="not_applicable",
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()
        await engine.dispose()

    asyncio.run(scenario())
    evidence_columns = set(Evidence.__table__.columns.keys())
    assert not {"raw_text", "content", "body", "blob", "storage_url"} & evidence_columns
    assert not {"raw_text", "content", "body", "blob"} & set(CaptureSession.__table__.columns.keys())


def test_interaction_validation_rejects_unknown_types_and_bad_ranges(client: TestClient) -> None:
    unknown = client.post(
        "/api/v1/interactions",
        json={"title": "Unknown", "interactionType": "voice_journal"},
    )
    assert unknown.status_code == 422

    bad_range = client.post(
        "/api/v1/interactions",
        json={
            "title": "Bad range",
            "interactionType": "presentation",
            "scheduledStartAt": "2026-08-12T11:00:00Z",
            "scheduledEndAt": "2026-08-12T10:00:00Z",
        },
    )
    assert bad_range.status_code == 422

    naive = client.post(
        "/api/v1/interactions",
        json={
            "title": "Naive time",
            "interactionType": "phone_call",
            "scheduledStartAt": "2026-08-12T10:00:00",
        },
    )
    assert naive.status_code == 422

    assert str(SECONDARY_USER_ID) not in client.get("/api/v1/interactions").text
