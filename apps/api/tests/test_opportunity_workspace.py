from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import get_current_user
from revenueos.models import OpportunityAuditEvent

from .conftest import TEST_DB_URL
from .test_business_api import create_company, create_opportunity
from .test_meeting_api import cast_auth_dependency, create_meeting, secondary_user
from .test_meeting_intelligence_workspace import _run_worker_once


def _audit_actions(opportunity_id: str) -> list[str]:
    async def read() -> list[str]:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            events = await session.scalars(
                select(OpportunityAuditEvent)
                .where(OpportunityAuditEvent.opportunity_id == UUID(opportunity_id))
                .order_by(OpportunityAuditEvent.created_at.asc())
            )
            actions = [event.action for event in events]
        await engine.dispose()
        return actions

    return asyncio.run(read())


def _associate(client: TestClient, meeting: dict[str, object], opportunity_id: str) -> dict[str, object]:
    response = client.patch(
        f"/api/v1/meetings/{meeting['id']}/opportunity",
        json={
            "opportunityId": opportunity_id,
            "expectedUpdatedAt": meeting["updatedAt"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_list_and_workspace_are_product_safe_without_meetings(client: TestClient) -> None:
    company = create_company(client)
    opportunity = create_opportunity(client, str(company["id"]))

    listing = client.get("/api/v1/opportunities")
    assert listing.status_code == 200
    item = listing.json()["items"][0]
    assert item["companyName"] == company["name"]
    assert item["latestMeetingId"] is None
    assert item["latestMeetingMomentum"] is None
    assert item["latestNextBestAction"] is None
    assert "probability" not in listing.text.lower()
    assert "forecast" not in listing.text.lower()

    response = client.get(f"/api/v1/opportunities/{opportunity['id']}/workspace")
    assert response.status_code == 200
    body = response.json()
    assert body["opportunity"]["name"] == opportunity["name"]
    assert body["opportunity"]["ownerName"] == "Alex Morgan"
    assert body["latestMeeting"] is None
    assert body["recentMeetings"] == []
    assert body["intelligence"] is None
    assert body["partialData"] is False
    for prohibited in (
        "rawText",
        "transcriptBody",
        "providerKey",
        "modelName",
        "promptVersion",
        "schemaVersion",
        "workerId",
        "jobId",
        "artifactId",
        "probability",
        "forecast",
    ):
        assert prohibited not in response.text
    assert _audit_actions(str(opportunity["id"])) == ["created"]


def test_association_disassociation_stale_writes_and_audits(client: TestClient) -> None:
    company_id = str(create_company(client)["id"])
    opportunity = create_opportunity(client, company_id)
    meeting = create_meeting(
        client,
        company_id=company_id,
        participants=[{"displayName": "Jordan Lee", "attendanceStatus": "attended"}],
        transcript={
            "rawText": "Jordan confirmed the next meeting and requested the proposal.",
            "language": "en-AU",
            "source": "manual",
        },
    )

    associated = _associate(client, meeting, str(opportunity["id"]))
    assert associated["opportunityId"] == opportunity["id"]

    stale = client.patch(
        f"/api/v1/meetings/{meeting['id']}/opportunity",
        json={"opportunityId": None, "expectedUpdatedAt": meeting["updatedAt"]},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_write"

    workspace = client.get(f"/api/v1/opportunities/{opportunity['id']}/workspace")
    assert workspace.status_code == 200, workspace.text
    body = workspace.json()
    assert body["latestMeeting"]["id"] == meeting["id"]
    assert body["latestMeeting"]["participantCount"] == 1
    assert body["latestMeeting"]["transcriptAvailable"] is True
    assert body["latestMeeting"]["intelligenceReadiness"] == "not_generated"
    assert body["intelligence"]["overallState"] == "not_started"
    assert "rawText" not in workspace.text

    history = client.get(f"/api/v1/meetings/{meeting['id']}/history")
    assert history.status_code == 200
    assert any("opportunity_id" in event["changedFields"] for event in history.json())

    disassociated = client.patch(
        f"/api/v1/meetings/{meeting['id']}/opportunity",
        json={"opportunityId": None, "expectedUpdatedAt": associated["updatedAt"]},
    )
    assert disassociated.status_code == 200
    assert disassociated.json()["opportunityId"] is None
    assert _audit_actions(str(opportunity["id"])) == [
        "created",
        "meeting_associated",
        "meeting_disassociated",
    ]


def test_association_rejects_cross_company_and_cross_tenant_ids(
    app: FastAPI,
    client: TestClient,
) -> None:
    first_company = create_company(client, name="First Company")
    second_company = create_company(client, name="Second Company")
    first_opportunity = create_opportunity(client, str(first_company["id"]))
    meeting = create_meeting(client, company_id=str(second_company["id"]))

    inconsistent = client.patch(
        f"/api/v1/meetings/{meeting['id']}/opportunity",
        json={
            "opportunityId": first_opportunity["id"],
            "expectedUpdatedAt": meeting["updatedAt"],
        },
    )
    assert inconsistent.status_code == 422
    assert inconsistent.json()["code"] == "inconsistent_relationship"

    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    other_company = create_company(client, name="Other Tenant Company")
    other_opportunity = create_opportunity(client, str(other_company["id"]))
    app.dependency_overrides.pop(get_current_user)

    cross_tenant = client.patch(
        f"/api/v1/meetings/{meeting['id']}/opportunity",
        json={
            "opportunityId": other_opportunity["id"],
            "expectedUpdatedAt": meeting["updatedAt"],
        },
    )
    assert cross_tenant.status_code == 404
    assert cross_tenant.json()["code"] == "opportunity_not_found"
    assert client.get(f"/api/v1/opportunities/{other_opportunity['id']}/workspace").status_code == 404


def test_latest_meeting_rule_is_deterministic_and_excludes_cancelled(client: TestClient) -> None:
    company_id = str(create_company(client)["id"])
    opportunity = create_opportunity(client, company_id)
    first = create_meeting(client, title="First tied meeting", company_id=company_id)
    second = create_meeting(client, title="Second tied meeting", company_id=company_id)
    cancelled = create_meeting(client, title="Later cancelled meeting", company_id=company_id)

    for meeting in (first, second):
        updated = client.patch(
            f"/api/v1/meetings/{meeting['id']}",
            json={"meetingDate": "2026-09-01T10:00:00+10:00"},
        )
        assert updated.status_code == 200
        meeting.update(updated.json())
        meeting.update(_associate(client, meeting, str(opportunity["id"])))
    cancelled_update = client.patch(
        f"/api/v1/meetings/{cancelled['id']}",
        json={
            "meetingDate": "2026-10-01T10:00:00+10:00",
            "status": "cancelled",
        },
    )
    assert cancelled_update.status_code == 200
    cancelled.update(cancelled_update.json())
    _associate(client, cancelled, str(opportunity["id"]))

    response = client.get(f"/api/v1/opportunities/{opportunity['id']}/workspace")
    assert response.status_code == 200
    body = response.json()
    expected_latest = max(str(first["id"]), str(second["id"]))
    assert body["latestMeeting"]["id"] == expected_latest
    assert [meeting["id"] for meeting in body["recentMeetings"]] == [
        expected_latest,
        min(str(first["id"]), str(second["id"])),
    ]
    assert str(cancelled["id"]) not in response.text


def test_workspace_composes_current_validated_intelligence_only(client: TestClient) -> None:
    company_id = str(create_company(client)["id"])
    opportunity = create_opportunity(client, company_id)
    meeting = create_meeting(
        client,
        title="Expansion review",
        company_id=company_id,
        transcript={
            "rawText": (
                "The customer confirmed budget and procurement timing. Jordan will send the "
                "security pack by 2026-08-10. The final legal reviewer remains unknown."
            ),
            "language": "en-AU",
            "source": "manual",
        },
    )
    _associate(client, meeting, str(opportunity["id"]))

    endpoint = f"/api/v1/meetings/{meeting['id']}/intelligence/generate"
    assert client.post(endpoint).status_code == 202
    for _ in range(8):
        _run_worker_once()
    assert client.post(endpoint).status_code == 202
    _run_worker_once()
    _run_worker_once()

    response = client.get(f"/api/v1/opportunities/{opportunity['id']}/workspace")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["intelligenceSectionsAvailable"] == 10
    assert body["intelligence"]["nextBestAction"]["content"]["recommendedActions"]
    assert body["intelligence"]["buyingSignals"]["content"] is not None
    assert body["intelligence"]["objectionsCompetitiveSignals"]["content"] is not None
    assert body["intelligence"]["stakeholderIntelligence"]["content"] is not None
    assert body["intelligence"]["followUpEmail"]["content"] is not None
    assert body["partialData"] is False
    for prohibited in ("rawText", "providerKey", "modelName", "jobId", "artifactId"):
        assert prohibited not in response.text

    transcript = client.get(f"/api/v1/meetings/{meeting['id']}/transcript").json()
    updated = client.patch(
        f"/api/v1/meetings/{meeting['id']}/transcript",
        json={
            "rawText": "A deliberately replaced transcript version.",
            "language": "en-AU",
            "version": transcript["version"],
        },
    )
    assert updated.status_code == 200

    stale_excluded = client.get(f"/api/v1/opportunities/{opportunity['id']}/workspace")
    assert stale_excluded.status_code == 200
    stale_body = stale_excluded.json()
    assert stale_body["intelligenceSectionsAvailable"] == 0
    assert stale_body["intelligence"]["overallState"] == "not_started"
    assert stale_body["intelligence"]["nextBestAction"]["content"] is None
    assert stale_body["partialData"] is True


def test_opportunity_update_rejects_stale_metadata(client: TestClient) -> None:
    opportunity = create_opportunity(client, str(create_company(client)["id"]))
    first = client.patch(
        f"/api/v1/opportunities/{opportunity['id']}",
        json={
            "stage": "evaluation",
            "expectedUpdatedAt": opportunity["updatedAt"],
        },
    )
    assert first.status_code == 200
    stale = client.patch(
        f"/api/v1/opportunities/{opportunity['id']}",
        json={
            "stage": "proposal",
            "expectedUpdatedAt": opportunity["updatedAt"],
        },
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_write"


def test_workspace_query_count_is_bounded_as_recent_meetings_grow(
    app: FastAPI,
    client: TestClient,
) -> None:
    company_id = str(create_company(client)["id"])
    opportunity = create_opportunity(client, company_id)
    for index in range(6):
        meeting = create_meeting(
            client,
            title=f"Meeting {index}",
            company_id=company_id,
            transcript={
                "rawText": f"Synthetic authorised test transcript {index}.",
                "language": "en-AU",
                "source": "manual",
            },
        )
        _associate(client, meeting, str(opportunity["id"]))

    select_count = 0

    def count_selects(
        connection: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        del connection, cursor, parameters, context, executemany
        nonlocal select_count
        if statement.lstrip().upper().startswith("SELECT"):
            select_count += 1

    engine = app.state.engine.sync_engine
    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        response = client.get(f"/api/v1/opportunities/{opportunity['id']}/workspace")
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)

    assert response.status_code == 200, response.text
    assert len(response.json()["recentMeetings"]) == 6
    assert select_count <= 5
