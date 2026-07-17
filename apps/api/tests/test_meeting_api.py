from __future__ import annotations

import asyncio
from collections.abc import Callable
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import AuthenticatedUser, get_current_user
from revenueos.models import Meeting, MeetingAuditEvent, MeetingParticipant, Transcript

from .conftest import (
    PRIMARY_ORGANISATION_ID,
    SECONDARY_ORGANISATION_ID,
    SECONDARY_USER_ID,
    TEST_DB_URL,
)
from .test_business_api import create_company, create_contact


def create_meeting(
    client: TestClient,
    *,
    title: str = "Discovery call",
    company_id: str | None = None,
    participants: list[dict[str, object]] | None = None,
    transcript: dict[str, object] | None = None,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/meetings",
        json={
            "title": title,
            "description": "Discuss the expansion requirements.",
            "meetingDate": "2026-08-01T10:00:00+10:00",
            "meetingType": "remote",
            "status": "scheduled",
            "companyId": company_id,
            "participants": participants or [],
            "transcript": transcript,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def secondary_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=SECONDARY_USER_ID,
        external_auth_id="user_other_001",
        display_name="Other User",
        email="other@example.test",
        organisation_id=SECONDARY_ORGANISATION_ID,
        organisation_name="Other Revenue Team",
        organisation_slug="other-revenue-team",
        role="admin",
        auth_mode="mock",
    )


def cast_auth_dependency(user: AuthenticatedUser) -> Callable[[], AuthenticatedUser]:
    return lambda: user


def test_meeting_crud_filters_and_nested_creation(client: TestClient) -> None:
    company_id = str(create_company(client)["id"])
    contact_id = str(create_contact(client, company_id)["id"])
    meeting = create_meeting(
        client,
        company_id=company_id,
        participants=[
            {
                "contactId": contact_id,
                "displayName": "Jordan Lee",
                "email": "jordan@example.com",
                "attendanceStatus": "attended",
                "role": "attendee",
            }
        ],
        transcript={
            "rawText": "Jordan confirmed the next discovery session.",
            "language": "en-AU",
            "source": "upload",
        },
    )
    meeting_id = str(meeting["id"])
    assert meeting["organisationId"] == str(PRIMARY_ORGANISATION_ID)
    assert meeting["createdBy"] == "00000000-0000-4000-8000-000000000001"
    assert meeting["updatedBy"] == "00000000-0000-4000-8000-000000000001"

    response = client.get(
        "/api/v1/meetings",
        params={
            "search": "Discovery",
            "status": "scheduled",
            "meetingType": "remote",
            "companyId": company_id,
            "page": 1,
            "pageSize": 1,
            "sortBy": "meeting_date",
            "sortOrder": "desc",
        },
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == meeting_id

    response = client.patch(
        f"/api/v1/meetings/{meeting_id}",
        json={
            "title": "Expansion discovery",
            "description": None,
            "meetingDate": "2026-08-02T09:30:00+10:00",
            "meetingType": "phone",
            "status": "completed",
            "companyId": None,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Expansion discovery"
    assert response.json()["companyId"] is None
    assert response.json()["status"] == "completed"

    assert client.get(f"/api/v1/meetings/{meeting_id}").status_code == 200
    assert client.get(f"/api/v1/meetings/{meeting_id}/participants").json()[0]["contactId"] == contact_id
    transcript_response = client.get(f"/api/v1/meetings/{meeting_id}/transcript")
    assert transcript_response.status_code == 200
    assert transcript_response.json()["version"] == 1
    assert transcript_response.json()["source"] == "upload"


def test_participant_crud_and_validation(client: TestClient) -> None:
    company_id = str(create_company(client)["id"])
    contact_id = str(create_contact(client, company_id)["id"])
    meeting_id = str(create_meeting(client)["id"])

    response = client.post(
        f"/api/v1/meetings/{meeting_id}/participants",
        json={
            "contactId": contact_id,
            "displayName": "Jordan Lee",
            "email": "jordan@example.com",
            "attendanceStatus": "invited",
            "role": "host",
        },
    )
    assert response.status_code == 201, response.text
    participant_id = response.json()["id"]
    assert client.get(f"/api/v1/meetings/{meeting_id}/participants/{participant_id}").status_code == 200

    response = client.patch(
        f"/api/v1/meetings/{meeting_id}/participants/{participant_id}",
        json={
            "displayName": "Jordan Morgan",
            "attendanceStatus": "attended",
            "role": "attendee",
        },
    )
    assert response.status_code == 200
    assert response.json()["displayName"] == "Jordan Morgan"
    assert response.json()["attendanceStatus"] == "attended"

    invalid = client.post(
        f"/api/v1/meetings/{meeting_id}/participants",
        json={"displayName": "Invalid", "email": "not-an-email"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "invalid_request"

    assert client.delete(f"/api/v1/meetings/{meeting_id}/participants/{participant_id}").status_code == 204
    assert client.get(f"/api/v1/meetings/{meeting_id}/participants/{participant_id}").status_code == 404


def test_transcript_crud_version_conflict_and_restoration(client: TestClient) -> None:
    meeting_id = str(create_meeting(client)["id"])
    missing = client.get(f"/api/v1/meetings/{meeting_id}/transcript")
    assert missing.status_code == 404

    response = client.post(
        f"/api/v1/meetings/{meeting_id}/transcript",
        json={
            "rawText": "Initial plain text.",
            "language": "en",
            "source": "manual",
        },
    )
    assert response.status_code == 201
    assert response.json()["version"] == 1

    response = client.patch(
        f"/api/v1/meetings/{meeting_id}/transcript",
        json={
            "rawText": "Corrected plain text.",
            "language": "en-AU",
            "version": 1,
        },
    )
    assert response.status_code == 200
    assert response.json()["version"] == 2
    assert response.json()["rawText"] == "Corrected plain text."

    stale = client.patch(
        f"/api/v1/meetings/{meeting_id}/transcript",
        json={"rawText": "Stale edit.", "version": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "transcript_version_conflict"

    assert client.delete(f"/api/v1/meetings/{meeting_id}/transcript").status_code == 204
    assert client.get(f"/api/v1/meetings/{meeting_id}/transcript").status_code == 404

    restored = client.post(
        f"/api/v1/meetings/{meeting_id}/transcript",
        json={"rawText": "Restored text.", "language": "en", "source": "manual"},
    )
    assert restored.status_code == 201
    assert restored.json()["version"] == 3


def test_meeting_validation_and_safe_not_found_responses(client: TestClient) -> None:
    invalid_requests = [
        {
            "title": " ",
            "meetingDate": "2026-08-01T10:00:00+10:00",
        },
        {
            "title": "Missing date",
        },
        {
            "title": "Naive date",
            "meetingDate": "2026-08-01T10:00:00",
        },
        {
            "title": "Bad participant",
            "meetingDate": "2026-08-01T10:00:00Z",
            "participants": [{}],
        },
    ]
    for body in invalid_requests:
        response = client.post("/api/v1/meetings", json=body)
        assert response.status_code == 422
        assert response.json()["code"] == "invalid_request"
        assert set(response.json()) == {"code", "message", "requestId"}

    missing_id = "00000000-0000-4000-8000-000000000099"
    assert client.get(f"/api/v1/meetings/{missing_id}").status_code == 404
    assert client.get(f"/api/v1/meetings/{missing_id}/participants").status_code == 404
    assert client.get(f"/api/v1/meetings/{missing_id}/transcript").status_code == 404


def test_cross_tenant_relationships_and_meetings_are_denied(
    app: FastAPI,
    client: TestClient,
) -> None:
    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    other_company_id = str(create_company(client, name="Other Company")["id"])
    other_contact_id = str(create_contact(client, other_company_id)["id"])
    other_meeting_id = str(create_meeting(client, company_id=other_company_id)["id"])
    app.dependency_overrides.pop(get_current_user)

    assert client.get(f"/api/v1/meetings/{other_meeting_id}").status_code == 404
    assert client.patch(f"/api/v1/meetings/{other_meeting_id}", json={"title": "Stolen"}).status_code == 404
    assert client.delete(f"/api/v1/meetings/{other_meeting_id}").status_code == 404
    assert client.get(f"/api/v1/meetings/{other_meeting_id}/participants").status_code == 404
    assert client.get(f"/api/v1/meetings/{other_meeting_id}/history").status_code == 404

    response = client.post(
        "/api/v1/meetings",
        json={
            "title": "Cross-tenant company",
            "meetingDate": "2026-08-01T10:00:00Z",
            "companyId": other_company_id,
        },
    )
    assert response.status_code == 404
    assert response.json()["code"] == "company_not_found"

    meeting_id = str(create_meeting(client)["id"])
    response = client.post(
        f"/api/v1/meetings/{meeting_id}/participants",
        json={"contactId": other_contact_id},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "contact_not_found"

    assert client.get(f"/api/v1/meetings/{other_meeting_id}/transcript").status_code == 404


def test_missing_membership_is_forbidden(
    app: FastAPI,
    client: TestClient,
) -> None:
    unprovisioned = AuthenticatedUser(
        user_id=uuid4(),
        external_auth_id="user_unprovisioned",
        display_name="Unprovisioned User",
        email="unprovisioned@example.test",
        organisation_id=PRIMARY_ORGANISATION_ID,
        organisation_name="Example Revenue Team",
        organisation_slug="example-revenue-team",
        role="member",
        auth_mode="mock",
    )
    app.dependency_overrides[get_current_user] = cast_auth_dependency(unprovisioned)
    response = client.get("/api/v1/meetings")
    app.dependency_overrides.pop(get_current_user)

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_soft_delete_and_content_minimised_history(client: TestClient) -> None:
    meeting = create_meeting(
        client,
        participants=[{"displayName": "Guest", "email": "guest@example.com"}],
        transcript={
            "rawText": "Sensitive customer transcript text.",
            "language": "en",
            "source": "manual",
        },
    )
    meeting_id = UUID(str(meeting["id"]))

    update = client.patch(
        f"/api/v1/meetings/{meeting_id}/transcript",
        json={"rawText": "Updated sensitive text.", "version": 1},
    )
    assert update.status_code == 200

    history = client.get(f"/api/v1/meetings/{meeting_id}/history")
    assert history.status_code == 200
    assert {event["entityType"] for event in history.json()} == {
        "meeting",
        "participant",
        "transcript",
    }
    assert {"created", "updated"}.issubset({event["action"] for event in history.json()})
    assert "Sensitive customer transcript" not in history.text
    assert "Updated sensitive text" not in history.text

    assert client.delete(f"/api/v1/meetings/{meeting_id}").status_code == 204
    assert client.get(f"/api/v1/meetings/{meeting_id}").status_code == 404
    assert client.get("/api/v1/meetings").json()["items"] == []

    async def verify_soft_delete() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            stored_meeting = await session.scalar(select(Meeting).where(Meeting.id == meeting_id))
            stored_participant = await session.scalar(
                select(MeetingParticipant).where(MeetingParticipant.meeting_id == meeting_id)
            )
            stored_transcript = await session.scalar(select(Transcript).where(Transcript.meeting_id == meeting_id))
            audit_count = len(
                list(await session.scalars(select(MeetingAuditEvent).where(MeetingAuditEvent.meeting_id == meeting_id)))
            )
            assert stored_meeting is not None and stored_meeting.deleted_at is not None
            assert stored_participant is not None and stored_participant.deleted_at is not None
            assert stored_transcript is not None and stored_transcript.deleted_at is not None
            assert audit_count >= 6
        await engine.dispose()

    asyncio.run(verify_soft_delete())
