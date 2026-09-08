from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import AuthenticatedUser, get_current_user
from revenueos.beta_maintenance import EXPORT_VERSION, _export_payload
from revenueos.commercial_services import CommercialService
from revenueos.deal_room_services import PublicDealRoomRateLimiter
from revenueos.errors import PublicAPIError
from revenueos.models import (
    CreatePresentationVersion,
    DealRoomAccessLink,
    DealRoomAuditEvent,
    Opportunity,
    OrganisationMembership,
    User,
)

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, TEST_DB_URL
from .test_business_api import create_company, create_contact, create_opportunity
from .test_business_cases import _create_approved_model, _inputs
from .test_create_studio import _review_and_approve, _run_worker, _upload
from .test_meeting_api import cast_auth_dependency, secondary_user


def _draft_payload(room: dict[str, object], *, overview: str) -> dict[str, object]:
    return {
        "expectedDraftVersion": room["draftVersion"],
        "expectedLockVersion": room["lockVersion"],
        "content": {
            "overview": overview,
            "commercialSummary": "Approved scope: implementation support. Approved term: 12 months.",
            "stakeholders": [
                {
                    "id": str(uuid.uuid4()),
                    "name": "Jordan Lee",
                    "role": "Operations Director",
                    "company": "Synthetic Customer",
                    "party": "customer",
                },
                {
                    "id": str(uuid.uuid4()),
                    "name": "Alex Morgan",
                    "role": "Account lead",
                    "company": "Example Revenue Team",
                    "party": "seller",
                },
            ],
            "milestones": [
                {
                    "id": str(uuid.uuid4()),
                    "title": "Complete security review",
                    "ownerParty": "joint",
                    "targetDate": "2026-09-18",
                    "status": "in_progress",
                    "note": "Review the approved questionnaire together.",
                }
            ],
            "resources": [
                {
                    "id": str(uuid.uuid4()),
                    "kind": "external_link",
                    "title": "Implementation overview",
                    "externalUrl": "https://example.com/implementation",
                }
            ],
            "nextMeetingAt": "2026-09-12T03:00:00Z",
        },
    }


def _publish(
    client: TestClient,
    opportunity_id: object,
    room: dict[str, object],
    *,
    link_expires_at: str | None = None,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/opportunities/{opportunity_id}/deal-room/publish",
        json={
            "expectedDraftVersion": room["draftVersion"],
            "expectedLockVersion": room["lockVersion"],
            "confirmed": True,
            "linkExpiresAt": link_expires_at,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _resolve(client: TestClient, token: str) -> object:
    return client.post("/api/v1/deal-rooms/public/resolve", json={"token": token})


def test_public_rate_limit_is_scoped_to_source_and_bearer_authority() -> None:
    limiter = PublicDealRoomRateLimiter()
    for _ in range(2):
        limiter.check("198.51.100.10", "room-a-token", 2)
    with pytest.raises(PublicAPIError, match="Too many Deal Room requests"):
        limiter.check("198.51.100.10", "room-a-token", 2)

    limiter.check("198.51.100.10", "room-b-token", 2)
    limiter.check("198.51.100.11", "room-a-token", 2)


def test_deal_room_requires_the_existing_create_entitlement(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    company = create_company(client, name="Entitlement Customer")
    opportunity = create_opportunity(client, str(company["id"]), name="Entitlement rollout")

    async def no_create_access(
        self: CommercialService,
        organisation_id: uuid.UUID,
        module: str,
        *,
        lock_for_write: bool = False,
    ) -> str:
        del self, organisation_id, lock_for_write
        return "none" if module == "create" else "write"

    async def deny_create_write(self: CommercialService, organisation_id: uuid.UUID, module: str) -> None:
        del self, organisation_id, module
        raise PublicAPIError(
            "create_not_in_plan",
            "Create isn't included in your organisation's current plan.",
            403,
        )

    monkeypatch.setattr(CommercialService, "module_access", no_create_access)
    monkeypatch.setattr(CommercialService, "require_module_write", deny_create_write)

    unavailable = client.get(f"/api/v1/opportunities/{opportunity['id']}/deal-room")
    assert unavailable.status_code == 403
    assert unavailable.json()["code"] == "create_not_in_plan"
    denied_create = client.post(f"/api/v1/opportunities/{opportunity['id']}/deal-room")
    assert denied_create.status_code == 403
    assert denied_create.json()["code"] == "create_not_in_plan"


def test_deal_room_explicit_publication_snapshot_link_lifecycle_and_safe_projection(
    client: TestClient,
    app: FastAPI,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO")
    company = create_company(client, name="Synthetic Customer")
    opportunity = create_opportunity(client, str(company["id"]), name="Synthetic secure rollout")

    workspace = client.get(f"/api/v1/opportunities/{opportunity['id']}/deal-room")
    assert workspace.status_code == 200, workspace.text
    assert workspace.json()["room"] is None
    assert workspace.json()["entitlement"] == "create"
    assert workspace.json()["creditsRequired"] is False

    created = client.post(f"/api/v1/opportunities/{opportunity['id']}/deal-room")
    assert created.status_code == 201, created.text
    room = created.json()["workspace"]["room"]
    assert room["status"] == "draft"
    duplicate = client.post(f"/api/v1/opportunities/{opportunity['id']}/deal-room")
    assert duplicate.status_code == 409

    forbidden = _draft_payload(room, overview="Safe objective")
    forbidden["content"]["forecastProbability"] = 0.9  # type: ignore[index]
    rejected = client.put(
        f"/api/v1/opportunities/{opportunity['id']}/deal-room/draft",
        json=forbidden,
    )
    assert rejected.status_code == 422

    unsafe_url = _draft_payload(room, overview="Safe objective")
    unsafe_url["content"]["resources"][0]["externalUrl"] = "javascript:alert(1)"  # type: ignore[index]
    rejected_url = client.put(
        f"/api/v1/opportunities/{opportunity['id']}/deal-room/draft",
        json=unsafe_url,
    )
    assert rejected_url.status_code == 422
    for rejected_resource_url in (
        "data:text/plain,secret",
        "file:///etc/passwd",
        "vbscript:msgbox(1)",
        "https:///missing-host",
        "https://buyer:secret@example.com/resource",
    ):
        unsafe_resource = _draft_payload(room, overview="Safe objective")
        unsafe_resource["content"]["resources"][0]["externalUrl"] = rejected_resource_url  # type: ignore[index]
        unsafe_response = client.put(
            f"/api/v1/opportunities/{opportunity['id']}/deal-room/draft",
            json=unsafe_resource,
        )
        assert unsafe_response.status_code == 422

    original_overview = "<script>alert('not executable')</script> Align the approved implementation objective."
    saved = client.put(
        f"/api/v1/opportunities/{opportunity['id']}/deal-room/draft",
        json=_draft_payload(room, overview=original_overview),
    )
    assert saved.status_code == 200, saved.text
    room = saved.json()["workspace"]["room"]
    published = _publish(client, opportunity["id"], room)
    token = published["shareToken"]
    room = published["workspace"]["room"]
    assert isinstance(token, str) and len(token) >= 40
    assert room["status"] == "published"
    assert room["publishedRevision"] == 1

    public = _resolve(client, token)
    assert public.status_code == 200, public.text
    assert public.headers["cache-control"] == "no-store"
    assert public.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in public.headers["content-security-policy"]
    projection = public.json()["room"]
    assert set(projection) == {
        "schemaVersion",
        "revision",
        "publishedAt",
        "sellerCompanyName",
        "customerCompanyName",
        "opportunityName",
        "overview",
        "businessCase",
        "commercialSummary",
        "stakeholders",
        "milestones",
        "resources",
        "nextMeetingAt",
    }
    assert projection["overview"] == original_overview
    internal_opportunity_edit = client.patch(
        f"/api/v1/opportunities/{opportunity['id']}",
        json={"name": "Internal renamed opportunity"},
    )
    assert internal_opportunity_edit.status_code == 200, internal_opportunity_edit.text
    assert _resolve(client, token).json()["room"]["opportunityName"] == "Synthetic secure rollout"
    invalid_token = "short-malformed-token"
    invalid = _resolve(client, invalid_token)
    assert invalid.status_code == 404
    assert invalid.json()["message"] == "This Deal Room is no longer available."
    assert invalid_token not in invalid.text
    serialised = json.dumps(projection)
    for forbidden_text in (
        "forecastProbability",
        "meddic",
        "manager coaching",
        "economic buyer",
        "Customer expansion programme.",
    ):
        assert forbidden_text.casefold() not in serialised.casefold()

    next_draft = _draft_payload(room, overview="Republished customer-approved objective.")
    edited = client.put(
        f"/api/v1/opportunities/{opportunity['id']}/deal-room/draft",
        json=next_draft,
    )
    assert edited.status_code == 200, edited.text
    edited_room = edited.json()["workspace"]["room"]
    assert _resolve(client, token).json()["room"]["overview"] == original_overview
    extended_expiry = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    republished = _publish(
        client,
        opportunity["id"],
        edited_room,
        link_expires_at=extended_expiry,
    )
    assert republished["shareToken"] is None
    room = republished["workspace"]["room"]
    assert room["publishedRevision"] == 2
    assert datetime.fromisoformat(room["link"]["expiresAt"].replace("Z", "+00:00")) == datetime.fromisoformat(
        extended_expiry
    )
    assert _resolve(client, token).json()["room"]["overview"] == "Republished customer-approved objective."

    stale_publish = client.post(
        f"/api/v1/opportunities/{opportunity['id']}/deal-room/publish",
        json={
            "expectedDraftVersion": room["draftVersion"],
            "expectedLockVersion": room["lockVersion"] - 1,
            "confirmed": True,
        },
    )
    assert stale_publish.status_code == 409

    paused = client.post(
        f"/api/v1/opportunities/{opportunity['id']}/deal-room/pause",
        json={"confirmed": True, "expectedLockVersion": room["lockVersion"]},
    )
    assert paused.status_code == 200, paused.text
    room = paused.json()["workspace"]["room"]
    unavailable = _resolve(client, token)
    assert unavailable.status_code == 404
    assert unavailable.json()["message"] == "This Deal Room is no longer available."

    resumed = _publish(client, opportunity["id"], room)
    room = resumed["workspace"]["room"]
    assert _resolve(client, token).status_code == 200
    rotated = client.post(
        f"/api/v1/opportunities/{opportunity['id']}/deal-room/rotate-link",
        json={"expectedLockVersion": room["lockVersion"], "expiresAt": None},
    )
    assert rotated.status_code == 200, rotated.text
    rotated_token = rotated.json()["shareToken"]
    room = rotated.json()["workspace"]["room"]
    assert _resolve(client, token).status_code == 404
    assert _resolve(client, rotated_token).status_code == 200

    revoked = client.post(
        f"/api/v1/opportunities/{opportunity['id']}/deal-room/revoke",
        json={"confirmed": True, "expectedLockVersion": room["lockVersion"] - 1},
    )
    assert revoked.status_code == 200, revoked.text
    assert _resolve(client, rotated_token).status_code == 404

    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    cross_tenant_requests = (
        client.get(f"/api/v1/opportunities/{opportunity['id']}/deal-room"),
        client.post(f"/api/v1/opportunities/{opportunity['id']}/deal-room"),
        client.put(
            f"/api/v1/opportunities/{opportunity['id']}/deal-room/draft",
            json=_draft_payload(room, overview="Cross-tenant write must fail."),
        ),
        client.post(
            f"/api/v1/opportunities/{opportunity['id']}/deal-room/publish",
            json={
                "expectedDraftVersion": room["draftVersion"],
                "expectedLockVersion": room["lockVersion"],
                "confirmed": True,
            },
        ),
        client.post(
            f"/api/v1/opportunities/{opportunity['id']}/deal-room/pause",
            json={"expectedLockVersion": room["lockVersion"], "confirmed": True},
        ),
        client.post(
            f"/api/v1/opportunities/{opportunity['id']}/deal-room/revoke",
            json={"expectedLockVersion": room["lockVersion"], "confirmed": True},
        ),
        client.post(
            f"/api/v1/opportunities/{opportunity['id']}/deal-room/rotate-link",
            json={"expectedLockVersion": room["lockVersion"], "expiresAt": None},
        ),
    )
    assert all(response.status_code == 404 for response in cross_tenant_requests)
    assert all(response.json()["code"] == "opportunity_not_found" for response in cross_tenant_requests)
    app.dependency_overrides.pop(get_current_user, None)

    async def assert_secrets_and_audits() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                links = list((await session.scalars(select(DealRoomAccessLink))).all())
                audits = list((await session.scalars(select(DealRoomAuditEvent))).all())
                assert links
                assert all(len(link.token_hash) == 64 for link in links)
                assert all(link.token_hash not in {token, rotated_token} for link in links)
                assert token not in json.dumps([item.metadata_json for item in audits])
                assert rotated_token not in json.dumps([item.metadata_json for item in audits])
                assert {item.action for item in audits} >= {
                    "created",
                    "draft_updated",
                    "published",
                    "republished",
                    "paused",
                    "link_rotated",
                    "revoked",
                }
                exported = await _export_payload(session, PRIMARY_ORGANISATION_ID, app.state.settings)
                assert exported["exportVersion"] == EXPORT_VERSION == 37
                deal_room_export = exported["dealRooms"]
                assert deal_room_export["rooms"][0]["status"] == "revoked"  # type: ignore[index]
                assert len(deal_room_export["revisions"]) == 3  # type: ignore[arg-type,index]
                exported_text = json.dumps(deal_room_export, default=str)
                assert token not in exported_text
                assert rotated_token not in exported_text
                assert all(link.token_hash not in exported_text for link in links)
        finally:
            await engine.dispose()

    asyncio.run(assert_secrets_and_audits())
    assert token not in caplog.text
    assert rotated_token not in caplog.text

    peer_id = uuid.uuid4()

    async def add_peer() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                session.add(
                    User(
                        id=peer_id,
                        external_auth_id=f"peer-{peer_id}",
                        email=f"{peer_id}@example.test",
                        display_name="Unrelated seller",
                    )
                )
                session.add(
                    OrganisationMembership(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=peer_id,
                        role="member",
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(add_peer())
    peer = AuthenticatedUser(
        user_id=peer_id,
        external_auth_id=f"peer-{peer_id}",
        display_name="Unrelated seller",
        email=f"{peer_id}@example.test",
        organisation_id=PRIMARY_ORGANISATION_ID,
        organisation_name="Example Revenue Team",
        organisation_slug="example-revenue-team",
        role="member",
        auth_mode="mock",
    )
    app.dependency_overrides[get_current_user] = cast_auth_dependency(peer)
    denied = client.get(f"/api/v1/opportunities/{opportunity['id']}/deal-room")
    assert denied.status_code == 403
    app.dependency_overrides.pop(get_current_user, None)

    async def remove_peer() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await session.execute(
                    delete(OrganisationMembership).where(
                        OrganisationMembership.organisation_id == PRIMARY_ORGANISATION_ID,
                        OrganisationMembership.user_id == peer_id,
                    )
                )
                await session.execute(delete(User).where(User.id == peer_id))
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(remove_peer())


def test_deal_room_pins_approved_business_case_and_create_presentation_revision(
    client: TestClient,
    app: FastAPI,
) -> None:
    company = create_company(client, name="Deal Room Sources")
    opportunity = create_opportunity(client, str(company["id"]), name="Approved source rollout")
    contact = create_contact(client, str(company["id"]), first_name="Taylor")
    model = _create_approved_model(client)
    created_case = client.post(
        "/api/v1/create/business-cases",
        json={
            "accountId": company["id"],
            "opportunityId": opportunity["id"],
            "modelVersionId": model["latestVersion"]["id"],
            "currency": "AUD",
            "idempotencyKey": "deal-room-case",
        },
    )
    assert created_case.status_code == 201, created_case.text
    case_id = created_case.json()["id"]
    calculated = client.post(
        f"/api/v1/create/business-cases/{case_id}/calculate",
        json={"inputs": _inputs(), "idempotencyKey": "deal-room-case-v1"},
    )
    assert calculated.status_code == 200, calculated.text
    approved_case = client.post(
        f"/api/v1/create/business-cases/{case_id}/approve",
        json={"confirmed": True},
    )
    assert approved_case.status_code == 200, approved_case.text
    business_case_version = approved_case.json()["currentVersion"]

    uploaded = _upload(client)
    assert _run_worker(app)
    template = client.get(f"/api/v1/create/templates/{uploaded['id']}").json()
    template = _review_and_approve(client, template)
    created_presentation = client.post(
        "/api/v1/create/presentations",
        json={
            "accountId": company["id"],
            "opportunityId": opportunity["id"],
            "objective": "solution_overview",
            "audience": [{"contactId": contact["id"], "audienceType": "executive"}],
            "templateVersionId": template["latestVersion"]["id"],
            "idempotencyKey": "deal-room-presentation",
        },
    )
    assert created_presentation.status_code == 201, created_presentation.text
    presentation_id = created_presentation.json()["id"]
    generated = client.post(
        f"/api/v1/create/presentations/{presentation_id}/generate",
        json={"idempotencyKey": "deal-room-presentation-v1"},
    )
    assert generated.status_code == 200, generated.text
    assert _run_worker(app)
    approved_presentation = client.post(
        f"/api/v1/create/presentations/{presentation_id}/approve",
        json={"confirmed": True},
    )
    assert approved_presentation.status_code == 200, approved_presentation.text
    presentation_version = approved_presentation.json()["currentVersion"]

    created = client.post(f"/api/v1/opportunities/{opportunity['id']}/deal-room")
    room = created.json()["workspace"]["room"]
    resource_id = str(uuid.uuid4())
    saved = client.put(
        f"/api/v1/opportunities/{opportunity['id']}/deal-room/draft",
        json={
            "expectedDraftVersion": room["draftVersion"],
            "expectedLockVersion": room["lockVersion"],
            "content": {
                "overview": "Approved source material for buyer review.",
                "businessCaseVersionId": business_case_version["id"],
                "stakeholders": [],
                "milestones": [],
                "resources": [
                    {
                        "id": resource_id,
                        "kind": "presentation",
                        "title": "Approved solution presentation",
                        "presentationVersionId": presentation_version["id"],
                    }
                ],
            },
        },
    )
    assert saved.status_code == 200, saved.text
    published = _publish(client, opportunity["id"], saved.json()["workspace"]["room"])
    token = published["shareToken"]
    projection = _resolve(client, token).json()["room"]
    assert projection["businessCase"]["version"] == 1
    assert projection["businessCase"]["scenarios"]
    assert "caseId" not in projection["businessCase"]
    assert "versionId" not in projection["businessCase"]
    assert "formula" not in json.dumps(projection["businessCase"]).casefold()
    assert projection["resources"] == [
        {
            "id": resource_id,
            "kind": "presentation",
            "title": "Approved solution presentation",
            "url": None,
            "downloadAvailable": True,
        }
    ]
    assert "presentationVersionId" not in projection["resources"][0]
    downloaded = client.post(
        f"/api/v1/deal-rooms/public/resources/{resource_id}/download",
        json={"token": token},
    )
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content.startswith(b"PK")
    assert downloaded.headers["cache-control"] == "private, no-store, max-age=0"
    assert downloaded.headers["referrer-policy"] == "no-referrer"

    recalculated = client.post(
        f"/api/v1/create/business-cases/{case_id}/calculate",
        json={"inputs": _inputs(rekey_cost="0"), "idempotencyKey": "deal-room-case-v2"},
    )
    assert recalculated.status_code == 200, recalculated.text
    approved_v2 = client.post(
        f"/api/v1/create/business-cases/{case_id}/approve",
        json={"confirmed": True},
    )
    assert approved_v2.status_code == 200, approved_v2.text
    assert approved_v2.json()["currentVersion"]["version"] == 2
    assert _resolve(client, token).json()["room"]["businessCase"]["version"] == 1

    regenerated_presentation = client.post(
        f"/api/v1/create/presentations/{presentation_id}/generate",
        json={
            "idempotencyKey": "deal-room-presentation-v2",
            "explicitRegenerate": True,
        },
    )
    assert regenerated_presentation.status_code == 200, regenerated_presentation.text
    assert _run_worker(app)
    approved_presentation_v2 = client.post(
        f"/api/v1/create/presentations/{presentation_id}/approve",
        json={"confirmed": True},
    )
    assert approved_presentation_v2.status_code == 200, approved_presentation_v2.text
    assert approved_presentation_v2.json()["currentVersion"]["version"] == 2
    assert approved_presentation_v2.json()["currentVersion"]["id"] != presentation_version["id"]
    pinned_download = client.post(
        f"/api/v1/deal-rooms/public/resources/{resource_id}/download",
        json={"token": token},
    )
    assert pinned_download.status_code == 200, pinned_download.text

    room = published["workspace"]["room"]
    cross_asset = client.put(
        f"/api/v1/opportunities/{opportunity['id']}/deal-room/draft",
        json={
            "expectedDraftVersion": room["draftVersion"],
            "expectedLockVersion": room["lockVersion"],
            "content": {
                "stakeholders": [],
                "milestones": [],
                "resources": [
                    {
                        "id": str(uuid.uuid4()),
                        "kind": "presentation",
                        "title": "Unowned asset",
                        "presentationVersionId": str(uuid.uuid4()),
                    }
                ],
            },
        },
    )
    assert cross_asset.status_code == 422
    assert cross_asset.json()["code"] == "deal_room_presentation_invalid"

    async def retire_asset_and_close_opportunity() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await session.execute(
                    update(CreatePresentationVersion)
                    .where(CreatePresentationVersion.id == uuid.UUID(presentation_version["id"]))
                    .values(storage_status="deleted")
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(retire_asset_and_close_opportunity())
    unavailable_download = client.post(
        f"/api/v1/deal-rooms/public/resources/{resource_id}/download",
        json={"token": token},
    )
    assert unavailable_download.status_code == 404


def test_expired_and_closed_opportunity_links_fail_with_the_same_safe_response(client: TestClient) -> None:
    company = create_company(client, name="Lifecycle Customer")
    opportunity = create_opportunity(client, str(company["id"]), name="Lifecycle rollout")
    created = client.post(f"/api/v1/opportunities/{opportunity['id']}/deal-room").json()
    saved = client.put(
        f"/api/v1/opportunities/{opportunity['id']}/deal-room/draft",
        json=_draft_payload(created["workspace"]["room"], overview="Lifecycle-safe objective."),
    ).json()
    published = _publish(client, opportunity["id"], saved["workspace"]["room"])
    token = published["shareToken"]

    async def expire_link() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                link = await session.scalar(select(DealRoomAccessLink).where(DealRoomAccessLink.revoked_at.is_(None)))
                assert link is not None
                link.created_at = datetime.now(UTC) - timedelta(days=2)
                link.expires_at = datetime.now(UTC) - timedelta(days=1)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(expire_link())
    expired = _resolve(client, token)
    assert expired.status_code == 404
    safe_body = expired.json()

    room = client.get(f"/api/v1/opportunities/{opportunity['id']}/deal-room").json()["room"]
    rotated = client.post(
        f"/api/v1/opportunities/{opportunity['id']}/deal-room/rotate-link",
        json={"expectedLockVersion": room["lockVersion"], "expiresAt": None},
    )
    assert rotated.status_code == 200, rotated.text
    current_token = rotated.json()["shareToken"]

    async def close_opportunity() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await session.execute(update(User).where(User.id == PRIMARY_USER_ID).values(status="active"))
                await session.execute(
                    update(Opportunity)
                    .where(Opportunity.id == uuid.UUID(str(opportunity["id"])))
                    .values(status="lost", stage="closed_lost")
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(close_opportunity())
    closed = _resolve(client, current_token)
    assert closed.status_code == 404
    assert closed.json()["code"] == safe_body["code"]
    assert closed.json()["message"] == safe_body["message"]
