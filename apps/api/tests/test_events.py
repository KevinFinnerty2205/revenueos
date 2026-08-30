from __future__ import annotations

import asyncio
import base64
import logging
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import get_current_user
from revenueos.beta_maintenance import EXPORT_VERSION, _export_payload
from revenueos.event_import import EventImportError, decode_csv, parse_event_csv
from revenueos.models import (
    Contact,
    ContactFieldSource,
    EngageCampaign,
    EventAttendeeImport,
    Evidence,
    Interaction,
    OrganisationModuleEntitlement,
    SalesEvent,
)

from .conftest import PRIMARY_ORGANISATION_ID, TEST_DB_URL
from .test_campaigns import _campaign_request
from .test_meeting_api import cast_auth_dependency, secondary_user
from .test_outreach import _configure_policy


def _event_payload() -> dict[str, object]:
    return {
        "name": "Secure Infrastructure Summit",
        "eventType": "conference",
        "startAt": "2026-09-14T09:00:00+10:00",
        "endAt": "2026-09-15T17:00:00+10:00",
        "timezone": "Australia/Sydney",
        "locationName": "ICC Sydney",
        "city": "Sydney",
        "country": "Australia",
        "eventUrl": "https://events.example.com/summit",
        "organiser": "Example Events",
        "description": "Business infrastructure conference.",
        "goalType": "meet_new_prospects",
        "state": "upcoming",
    }


def _csv_payload(content: str) -> dict[str, object]:
    return {
        "fileName": "authorised-attendees.csv",
        "contentBase64": base64.b64encode(content.encode()).decode(),
        "columnMapping": {},
    }


def _create_event(client: TestClient) -> dict[str, object]:
    response = client.post("/api/v1/engage/events", json=_event_payload())
    assert response.status_code == 201, response.text
    return cast(dict[str, object], response.json())


def _import_attendees(client: TestClient, event_id: str) -> list[dict[str, object]]:
    content = (
        "First Name,Last Name,Company,Job Title,Business Email,Company Domain,Personal Phone\n"
        "Asha,Nguyen,Northstar Systems,Chief Information Officer,asha@northstar.example,northstar.example,0400000000\n"
        "Morgan,Lee,Harbour Security,Partner Director,morgan@harbour.example,harbour.example,0411111111\n"
    )
    preview = client.post(
        f"/api/v1/engage/events/{event_id}/attendee-imports/preview",
        json=_csv_payload(content),
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["validRowCount"] == 2
    assert {item["sourceColumn"] for item in body["ignored"]} == {"Personal Phone"}
    assert body["authorityStatement"].startswith("I confirm my organisation")
    denied = client.post(
        f"/api/v1/engage/events/{event_id}/attendee-imports/{body['id']}/confirm",
        json={"confirmed": True, "authorityAttested": False, "attestationVersion": 1},
    )
    assert denied.status_code == 422
    confirmed = client.post(
        f"/api/v1/engage/events/{event_id}/attendee-imports/{body['id']}/confirm",
        json={"confirmed": True, "authorityAttested": True, "attestationVersion": 1},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["importedCount"] == 2
    duplicate = client.post(
        f"/api/v1/engage/events/{event_id}/attendee-imports/preview",
        json=_csv_payload(content),
    )
    assert duplicate.status_code == 409
    attendees = client.get(f"/api/v1/engage/events/{event_id}/attendees?pageSize=100")
    assert attendees.status_code == 200, attendees.text
    return cast(list[dict[str, object]], attendees.json()["items"])


def _counts() -> tuple[int, int]:
    result = (0, 0)

    async def execute() -> None:
        nonlocal result
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            result = (
                int(await session.scalar(select(func.count()).select_from(Interaction)) or 0),
                int(await session.scalar(select(func.count()).select_from(Evidence)) or 0),
            )
        await engine.dispose()

    asyncio.run(execute())
    return result


def test_event_import_rejects_sensitive_mapping_and_formula_rows_are_never_executed() -> None:
    content = (
        b"First Name,Company,Business Email,Dietary Requirements\n"
        b"=2+2,Northstar Systems,person@gmail.com,Gluten free\n"
        b"Asha,Northstar Systems,asha@northstar.example,None\n"
    )
    preview = parse_event_csv("attendees.csv", content, {})
    assert len(preview.rows) == 2
    assert preview.rows[0].first_name == "=2+2"
    assert {item.code for item in preview.issues} >= {"formula_like_text", "personal_email"}
    assert any(item.source_column == "Dietary Requirements" for item in preview.ignored)
    try:
        parse_event_csv("attendees.csv", content, {"Dietary Requirements": "job_title"})
    except EventImportError as error:
        assert error.code == "sensitive_column_mapping"
    else:
        raise AssertionError("Sensitive registration data must not be mappable.")


def test_event_import_does_not_merge_people_who_share_a_generic_business_inbox() -> None:
    content = (
        b"First Name,Last Name,Company,Business Email\n"
        b"Asha,Nguyen,Northstar Systems,info@northstar.example\n"
        b"Morgan,Lee,Northstar Systems,info@northstar.example\n"
        b"Priya,Nair,Harbour Health,priya@harbour.example\n"
        b"Priya,Nair,Harbour Health,priya@harbour.example\n"
    )

    preview = parse_event_csv("attendees.csv", content, {})

    assert [(row.first_name, row.business_email) for row in preview.rows] == [
        ("Asha", "info@northstar.example"),
        ("Morgan", "info@northstar.example"),
        ("Priya", "priya@harbour.example"),
    ]
    assert next(item for item in preview.issues if item.code == "duplicate_strong_identity").count == 1


def test_event_import_parser_fails_closed_for_malformed_or_unbounded_input() -> None:
    with pytest.raises(EventImportError, match="UTF-8") as invalid_encoding:
        parse_event_csv("attendees.csv", b"First Name,Company\n\xff,Northstar\n", {})
    assert invalid_encoding.value.code == "invalid_file_encoding"

    oversized_rows = b"First Name,Company\n" + b"Asha,Northstar\n" * 501
    with pytest.raises(EventImportError, match="500 rows") as too_many_rows:
        parse_event_csv("attendees.csv", oversized_rows, {})
    assert too_many_rows.value.code == "too_many_rows"

    with pytest.raises(EventImportError) as duplicate_mapping:
        parse_event_csv(
            "attendees.csv",
            b"First Name,Preferred Name,Company\nAsha,Ash,Northstar\n",
            {"First Name": "first_name", "Preferred Name": "first_name"},
        )
    assert duplicate_mapping.value.code == "duplicate_field_mapping"

    with pytest.raises(EventImportError) as null_bytes:
        decode_csv("attendees.csv", base64.b64encode(b"First Name,Company\nAsha,Northstar\x00\n").decode())
    assert null_bytes.value.code == "invalid_csv"


def test_event_flow_preserves_truth_provenance_and_canonical_records(
    app: FastAPI,
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="revenueos.events")
    event = _create_event(client)
    event_id = str(event["id"])
    attendees = _import_attendees(client, event_id)
    asha = next(item for item in attendees if item["firstName"] == "Asha")
    morgan = next(item for item in attendees if item["firstName"] == "Morgan")
    attendee_id = str(asha["id"])
    assert asha["emailTrustState"] == "provider_supplied"
    assert asha["permissionStatus"] == "not_assessed"
    assert asha["priorityState"] in {"priority_to_meet", "worth_meeting"}
    assert asha["priorityReasons"]
    event_log = " ".join(str(record.__dict__) for record in caplog.records)
    assert "Asha" not in event_log
    assert "asha@northstar.example" not in event_log
    assert "Northstar Systems" not in event_log

    raw_outreach = client.post(
        f"/api/v1/engage/events/{event_id}/attendees/{attendee_id}/outreach",
        json={"stage": "pre_event"},
    )
    assert raw_outreach.status_code == 409

    before = _counts()
    met_only = client.post(
        f"/api/v1/engage/events/{event_id}/attendees/{attendee_id}/encounter",
        json={"state": "met", "createInteraction": False},
    )
    assert met_only.status_code == 200, met_only.text
    assert met_only.json()["interactionId"] is None
    assert _counts() == before

    captured = client.post(
        f"/api/v1/engage/events/{event_id}/attendees/{attendee_id}/encounter",
        json={"state": "met", "createInteraction": True, "interactionLifecycle": "completed"},
    )
    assert captured.status_code == 200, captured.text
    assert captured.json()["interactionId"] is not None
    assert _counts() == (before[0] + 1, before[1])

    promoted = client.post(
        f"/api/v1/engage/events/{event_id}/attendees/{attendee_id}/promote",
        json={"confirmed": True, "createCompany": True},
    )
    assert promoted.status_code == 200, promoted.text
    contact_id = promoted.json()["contactId"]
    _configure_policy(client)
    morgan_promoted = client.post(
        f"/api/v1/engage/events/{event_id}/attendees/{morgan['id']}/promote",
        json={"confirmed": True, "createCompany": True},
    )
    assert morgan_promoted.status_code == 200, morgan_promoted.text
    unconfirmed_follow_up = client.post(
        f"/api/v1/engage/events/{event_id}/attendees/{morgan['id']}/outreach",
        json={"stage": "post_event"},
    )
    assert unconfirmed_follow_up.status_code == 200, unconfirmed_follow_up.text
    unconfirmed_body = unconfirmed_follow_up.json()["outreach"]["version"]["body"]
    assert "Good meeting" not in unconfirmed_body
    assert "following Secure Infrastructure Summit" in unconfirmed_body
    outreach = client.post(
        f"/api/v1/engage/events/{event_id}/attendees/{attendee_id}/outreach",
        json={"stage": "post_event"},
    )
    assert outreach.status_code == 200, outreach.text
    body = outreach.json()["outreach"]
    assert "Good meeting you" in body["version"]["body"]
    assert {item["sourceType"] for item in body["version"]["sources"]} >= {
        "event_attendance",
        "event_encounter",
    }

    campaign_request = _campaign_request([contact_id], name="Summit follow-up")
    campaign_request["steps"][1]["delayDays"] = 3  # type: ignore[index]
    campaign_request.update(
        {
            "sourceType": "event_attendees",
            "eventId": event_id,
            "eventStage": "post_event",
        }
    )
    campaign = client.post("/api/v1/engage/campaigns", json=campaign_request)
    assert campaign.status_code == 201, campaign.text
    assert campaign.json()["eventId"] == event_id
    assert campaign.json()["sourceType"] == "event_attendees"

    deleted = client.request(
        "DELETE",
        f"/api/v1/engage/events/{event_id}",
        json={"confirmed": True},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {
        "deleted": True,
        "preservedContacts": 2,
        "preservedInteractions": 1,
        "preservedCampaigns": 1,
    }

    async def verify() -> None:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            assert await session.get(Contact, UUID(contact_id)) is not None
            assert int(await session.scalar(select(func.count()).select_from(ContactFieldSource)) or 0) >= 1
            interaction = await session.scalar(select(Interaction))
            assert interaction is not None and interaction.event_id is None
            assert int(await session.scalar(select(func.count()).select_from(EngageCampaign)) or 0) == 1
            assert int(await session.scalar(select(func.count()).select_from(SalesEvent)) or 0) == 0
        await engine.dispose()

    asyncio.run(verify())

    async def export_data() -> dict[str, object]:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            payload = await _export_payload(session, PRIMARY_ORGANISATION_ID, app.state.settings)
        await engine.dispose()
        return payload

    export = asyncio.run(export_data())
    assert export["exportVersion"] == EXPORT_VERSION == 25
    assert "eventAttendeeImports" in export


def test_event_crud_planning_updated_import_and_preview_expiry(client: TestClient) -> None:
    invalid_timezone = {**_event_payload(), "timezone": "Australia/Nowhere"}
    assert client.post("/api/v1/engage/events", json=invalid_timezone).status_code == 422
    excessive_duration = {
        **_event_payload(),
        "endAt": "2026-11-15T17:00:00+11:00",
    }
    assert client.post("/api/v1/engage/events", json=excessive_duration).status_code == 422

    event = _create_event(client)
    event_id = str(event["id"])
    assert client.patch(f"/api/v1/engage/events/{event_id}", json={}).status_code == 422
    updated = client.patch(
        f"/api/v1/engage/events/{event_id}",
        json={"name": "Secure Infrastructure Expo", "goalType": "meet_strategic_accounts"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Secure Infrastructure Expo"
    assert client.get("/api/v1/engage/events?search=Infrastructure").json()["total"] == 1

    first_csv = "First Name,Last Name,Company,Business Email\nAsha,Nguyen,Northstar,asha@northstar.example\n"
    first_preview = client.post(
        f"/api/v1/engage/events/{event_id}/attendee-imports/preview",
        json=_csv_payload(first_csv),
    ).json()
    first_confirm = client.post(
        f"/api/v1/engage/events/{event_id}/attendee-imports/{first_preview['id']}/confirm",
        json={"confirmed": True, "authorityAttested": True, "attestationVersion": 1},
    )
    assert first_confirm.status_code == 200, first_confirm.text

    updated_csv = (
        "First Name,Last Name,Company,Business Email\n"
        "Asha,Nguyen,Northstar,asha@northstar.example\n"
        "Priya,Nair,Harbour Health,priya@harbour.example\n"
    )
    second_preview = client.post(
        f"/api/v1/engage/events/{event_id}/attendee-imports/preview",
        json=_csv_payload(updated_csv),
    ).json()
    second_confirm = client.post(
        f"/api/v1/engage/events/{event_id}/attendee-imports/{second_preview['id']}/confirm",
        json={"confirmed": True, "authorityAttested": True, "attestationVersion": 1},
    )
    assert second_confirm.status_code == 200, second_confirm.text
    assert second_confirm.json()["importedCount"] == 1
    assert second_confirm.json()["duplicateCount"] == 1
    attendees = client.get(f"/api/v1/engage/events/{event_id}/attendees?pageSize=100").json()["items"]
    assert {item["firstName"] for item in attendees} == {"Asha", "Priya"}
    asha = next(item for item in attendees if item["firstName"] == "Asha")
    planned = client.put(
        f"/api/v1/engage/events/{event_id}/attendees/{asha['id']}/plan",
        json={"planState": "planned", "meetingArranged": True},
    )
    assert planned.status_code == 200, planned.text
    assert planned.json()["planState"] == "planned"
    assert planned.json()["meetingArranged"] is True
    filtered = client.get(f"/api/v1/engage/events/{event_id}/attendees?planState=planned&pageSize=100")
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1

    promoted = client.post(
        f"/api/v1/engage/events/{event_id}/attendees/{asha['id']}/promote",
        json={"confirmed": True, "createCompany": True},
    )
    assert promoted.status_code == 200, promoted.text
    assert client.delete(f"/api/v1/contacts/{promoted.json()['contactId']}").status_code == 204
    detached = client.get(f"/api/v1/engage/events/{event_id}/attendees/{asha['id']}")
    assert detached.status_code == 200
    assert detached.json()["contactId"] is None
    assert detached.json()["matchState"] == "matched_company"

    expiring_csv = "First Name,Company\nMorgan,Harbour Security\n"
    expiring_preview = client.post(
        f"/api/v1/engage/events/{event_id}/attendee-imports/preview",
        json=_csv_payload(expiring_csv),
    ).json()

    async def expire_preview() -> None:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            await session.execute(
                update(EventAttendeeImport)
                .where(EventAttendeeImport.id == UUID(expiring_preview["id"]))
                .values(expires_at=datetime(2020, 1, 1, tzinfo=UTC))
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(expire_preview())
    expired = client.post(
        f"/api/v1/engage/events/{event_id}/attendee-imports/{expiring_preview['id']}/confirm",
        json={"confirmed": True, "authorityAttested": True, "attestationVersion": 1},
    )
    assert expired.status_code == 410

    archived = client.patch(f"/api/v1/engage/events/{event_id}", json={"state": "archived"})
    assert archived.status_code == 200
    assert archived.json()["state"] == "archived"


def test_event_tenant_isolation_and_disabled_engage_history(app: FastAPI, client: TestClient) -> None:
    event_id = str(_create_event(client)["id"])
    app.state.settings.feature_engage_events_enabled = False
    try:
        unavailable = client.get("/api/v1/engage/events")
        assert unavailable.status_code == 503
        assert unavailable.json()["code"] == "events_unavailable"
    finally:
        app.state.settings.feature_engage_events_enabled = True

    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    try:
        assert client.get(f"/api/v1/engage/events/{event_id}").status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    async def disable() -> None:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            await session.execute(
                update(OrganisationModuleEntitlement)
                .where(
                    OrganisationModuleEntitlement.organisation_id == PRIMARY_ORGANISATION_ID,
                    OrganisationModuleEntitlement.module_key == "engage",
                )
                .values(enabled=False, disabled_at=datetime.now(UTC))
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(disable())
    history = client.get("/api/v1/engage/events")
    assert history.status_code == 200
    assert history.json()["readOnly"] is True
    assert history.json()["items"][0]["readOnly"] is True
    assert client.post("/api/v1/engage/events", json=_event_payload()).status_code == 403
