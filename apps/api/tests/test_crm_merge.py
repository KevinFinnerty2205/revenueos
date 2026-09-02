from __future__ import annotations

import asyncio
import hashlib
import hmac
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import get_current_user
from revenueos.beta_maintenance import _export_payload
from revenueos.database import set_tenant_database_context
from revenueos.models import (
    Contact,
    ContactSuppression,
    CRMRecordChange,
    CRMRecordMerge,
    Opportunity,
    Task,
)
from tests.conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, TEST_DB_URL
from tests.test_business_api import create_company, create_contact, create_opportunity, create_task
from tests.test_native_crm import primary_user


def configure_native_crm(client: TestClient) -> None:
    response = client.put("/api/v1/crm/settings", json={"mode": "native", "confirmed": True})
    assert response.status_code == 200, response.text


def selections(preview: dict[str, object], source_fields: set[str] | None = None) -> dict[str, str]:
    source_fields = source_fields or set()
    conflicts = preview["conflicts"]
    assert isinstance(conflicts, list)
    return {
        str(conflict["fieldKey"]): "source" if conflict["fieldKey"] in source_fields else "survivor"
        for conflict in conflicts
        if isinstance(conflict, dict)
    }


def test_account_merge_moves_relationships_is_idempotent_and_leaves_tombstone(app: FastAPI, client: TestClient) -> None:
    configure_native_crm(client)
    suffix = uuid4().hex[:10]
    source = create_company(client, name=f"Merge Source {suffix}")
    survivor = create_company(client, name=f"Merge Survivor {suffix}")
    source_contact = create_contact(client, str(source["id"]), first_name=f"Source{suffix}")
    opportunity = create_opportunity(client, str(source["id"]), name=f"Merge Deal {suffix}")
    task = create_task(
        client,
        company_id=str(source["id"]),
        contact_id=str(source_contact["id"]),
        opportunity_id=str(opportunity["id"]),
    )
    request = {
        "entityType": "account",
        "sourceEntityId": source["id"],
        "survivorEntityId": survivor["id"],
    }
    preview = client.post("/api/v1/crm/merges/preview", json=request)
    assert preview.status_code == 200, preview.text
    assert preview.json()["blockedReasons"] == []
    confirm_request = {
        **request,
        "previewFingerprint": preview.json()["previewFingerprint"],
        "fieldSelection": selections(preview.json(), {"name"}),
        "idempotencyKey": f"account-merge-{suffix}",
    }
    confirmed = client.post("/api/v1/crm/merges/confirm", json=confirm_request)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["alreadyApplied"] is False
    retried = client.post("/api/v1/crm/merges/confirm", json=confirm_request)
    assert retried.status_code == 200
    assert retried.json()["mergeId"] == confirmed.json()["mergeId"]
    assert retried.json()["alreadyApplied"] is True

    tombstone = client.get(f"/api/v1/crm/records/account/{source['id']}")
    assert tombstone.status_code == 200, tombstone.text
    assert tombstone.json()["mergedIntoEntityId"] == survivor["id"]
    assert tombstone.json()["mergeId"] == confirmed.json()["mergeId"]
    restore = client.post(f"/api/v1/crm/records/account/{source['id']}/restore")
    assert restore.status_code == 409
    assert restore.json()["code"] == "record_merged"

    async def assert_graph() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            moved_opportunity = await session.get(Opportunity, UUID(str(opportunity["id"])))
            moved_task = await session.get(Task, UUID(str(task["id"])))
            moved_contact = await session.get(Contact, UUID(str(source_contact["id"])))
            merge = await session.get(CRMRecordMerge, UUID(confirmed.json()["mergeId"]))
            changes = list(
                await session.scalars(
                    select(CRMRecordChange).where(
                        CRMRecordChange.organisation_id == PRIMARY_ORGANISATION_ID,
                        CRMRecordChange.entity_id == UUID(str(survivor["id"])),
                        CRMRecordChange.source == "record_merge",
                    )
                )
            )
            assert moved_opportunity is not None and moved_opportunity.company_id == UUID(str(survivor["id"]))
            assert moved_task is not None and moved_task.company_id == UUID(str(survivor["id"]))
            assert moved_contact is not None and moved_contact.company_id == UUID(str(survivor["id"]))
            assert merge is not None and merge.merged_by_user_id == PRIMARY_USER_ID
            assert {change.field_key for change in changes} == {"name"}
            exported = await _export_payload(session, PRIMARY_ORGANISATION_ID, app.state.settings)
            assert len(exported["crmRecordMerges"]) == 1  # type: ignore[arg-type]
            assert "account-merge" not in str(exported["crmRecordMerges"])
        await engine.dispose()

    asyncio.run(assert_graph())


def test_contact_merge_preserves_most_restrictive_suppression_and_custom_value(client: TestClient) -> None:
    configure_native_crm(client)
    suffix = uuid4().hex[:10]
    company = create_company(client, name=f"Merge Contacts {suffix}")
    source = create_contact(client, str(company["id"]), first_name=f"Suppressed{suffix}")
    survivor = create_contact(client, str(company["id"]), first_name=f"Survivor{suffix}")
    definition = client.post(
        "/api/v1/crm/custom-fields",
        json={
            "entityType": "contact",
            "fieldKey": f"merge_note_{suffix}",
            "label": "Merge note",
            "fieldType": "short_text",
        },
    )
    assert definition.status_code == 201, definition.text
    custom_value = client.put(
        f"/api/v1/crm/records/contact/{source['id']}/custom-fields/{definition.json()['id']}",
        json={"value": "Preserve provenance"},
    )
    assert custom_value.status_code == 200, custom_value.text

    async def seed_suppression() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            source_email = str(source["email"])
            session.add(
                ContactSuppression(
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    contact_id=UUID(str(source["id"])),
                    email_fingerprint=hmac.new(
                        b"local-development-outreach-suppression-key",
                        source_email.casefold().encode(),
                        hashlib.sha256,
                    ).hexdigest(),
                    reason="complaint",
                    source="recipient",
                    active=True,
                    created_at=datetime.now(UTC),
                )
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(seed_suppression())
    request = {
        "entityType": "contact",
        "sourceEntityId": source["id"],
        "survivorEntityId": survivor["id"],
    }
    preview = client.post("/api/v1/crm/merges/preview", json=request)
    assert preview.status_code == 200, preview.text
    assert preview.json()["blockedReasons"] == []
    custom_key = f"custom:{definition.json()['id']}"
    response = client.post(
        "/api/v1/crm/merges/confirm",
        json={
            **request,
            "previewFingerprint": preview.json()["previewFingerprint"],
            "fieldSelection": selections(preview.json(), {custom_key}),
            "idempotencyKey": f"contact-merge-{suffix}",
        },
    )
    assert response.status_code == 200, response.text
    survivor_record = client.get(f"/api/v1/crm/records/contact/{survivor['id']}")
    assert survivor_record.status_code == 200
    custom = next(
        item for item in survivor_record.json()["customFields"] if item["definition"]["id"] == definition.json()["id"]
    )
    assert custom["value"] == "Preserve provenance"
    assert custom["source"] == "record_merge"

    async def assert_suppression() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            active = list(
                await session.scalars(
                    select(ContactSuppression).where(
                        ContactSuppression.organisation_id == PRIMARY_ORGANISATION_ID,
                        ContactSuppression.contact_id == UUID(str(survivor["id"])),
                        ContactSuppression.active.is_(True),
                    )
                )
            )
            assert len(active) == 1
            assert active[0].reason == "complaint"
            assert active[0].source == "recipient"
        await engine.dispose()

    asyncio.run(assert_suppression())


def test_merge_rejects_stale_cross_tenant_and_member_requests(app: FastAPI, client: TestClient) -> None:
    configure_native_crm(client)
    suffix = uuid4().hex[:10]
    source = create_company(client, name=f"Stale Source {suffix}")
    survivor = create_company(client, name=f"Stale Survivor {suffix}")
    request = {
        "entityType": "account",
        "sourceEntityId": source["id"],
        "survivorEntityId": survivor["id"],
    }
    preview = client.post("/api/v1/crm/merges/preview", json=request)
    assert preview.status_code == 200
    changed = client.patch(f"/api/v1/companies/{source['id']}", json={"location": "Hobart"})
    assert changed.status_code == 200
    stale = client.post(
        "/api/v1/crm/merges/confirm",
        json={
            **request,
            "previewFingerprint": preview.json()["previewFingerprint"],
            "fieldSelection": selections(preview.json()),
            "idempotencyKey": f"stale-merge-{suffix}",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "merge_preview_stale"

    cross_tenant = client.post(
        "/api/v1/crm/merges/preview",
        json={**request, "sourceEntityId": "00000000-0000-4000-8000-000000000099"},
    )
    assert cross_tenant.status_code == 404
    member = replace(primary_user(), role="member")
    app.dependency_overrides[get_current_user] = lambda: member
    try:
        forbidden = client.post("/api/v1/crm/merges/preview", json=request)
        assert forbidden.status_code == 403
        assert forbidden.json()["code"] == "forbidden"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
