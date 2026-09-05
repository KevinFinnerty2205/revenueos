from __future__ import annotations

import asyncio
import base64
import csv
import io
import json
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import get_current_user
from revenueos.beta_maintenance import _export_payload, run_retention
from revenueos.crm_import import (
    MAX_CRM_IMPORT_BYTES,
    CRMImportError,
    decode_crm_csv,
    parse_crm_csv,
)
from revenueos.database import set_tenant_database_context
from revenueos.models import (
    ContactSuppression,
    CRMImportBatch,
    CRMImportRow,
    CRMRecordChange,
    Opportunity,
    OpportunityStageEvent,
)
from tests.conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, TEST_DB_URL
from tests.test_native_crm import primary_user


def csv_base64(headers: list[str], rows: list[list[str]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return base64.b64encode(stream.getvalue().encode()).decode()


def enable_native_crm(client: TestClient) -> None:
    settings = client.put("/api/v1/crm/settings", json={"mode": "native", "confirmed": True})
    assert settings.status_code == 200, settings.text


def test_csv_parser_is_bounded_strict_and_keeps_formula_like_values_as_text() -> None:
    parsed = parse_crm_csv(
        b'\xef\xbb\xbfName,Phone,Notes\r\n"=literal","+61 400 000 000","quoted, value"\r\n',
        {"Name": "name", "Phone": "phone", "Notes": None},
    )
    assert parsed.rows[0].values == {"name": "=literal", "phone": "+61 400 000 000"}
    assert parsed.rows[0].formula_like is True

    with pytest.raises(CRMImportError, match="UTF-8"):
        parse_crm_csv(b"Name\r\n\xff", {"Name": "name"})
    with pytest.raises(CRMImportError, match="headers must be unique"):
        parse_crm_csv(b"Name,name\r\nOne,Two\r\n", {"Name": "name", "name": "website"})
    with pytest.raises(CRMImportError, match="5,000 rows"):
        parse_crm_csv(b"Name\r\n" + b"Example\r\n" * 5_001, {"Name": "name"})

    headers = [f"Column {index}" for index in range(101)]
    with pytest.raises(CRMImportError, match="100 columns"):
        parse_crm_csv(
            (",".join(headers) + "\r\n" + ",".join("x" for _ in headers) + "\r\n").encode(),
            {header: f"field_{index}" for index, header in enumerate(headers)},
        )
    oversized = base64.b64encode(b"x" * (MAX_CRM_IMPORT_BYTES + 1)).decode()
    with pytest.raises(CRMImportError, match="at most 5 MB"):
        decode_crm_csv("oversized.csv", oversized)


def test_import_requires_native_crm_entitlement_and_administrator(app: FastAPI, client: TestClient) -> None:
    request = {
        "entityType": "account",
        "fileName": "accounts.csv",
        "contentBase64": csv_base64(["Name"], [["Synthetic Account"]]),
        "columnMapping": {"Name": "name"},
        "defaultOwnerUserId": str(PRIMARY_USER_ID),
        "ownerValueMapping": {},
        "stageValueMapping": {},
    }
    unavailable = client.post("/api/v1/crm/imports/preview", json=request)
    assert unavailable.status_code == 409
    assert unavailable.json()["code"] == "native_crm_required"

    enable_native_crm(client)
    app.dependency_overrides[get_current_user] = lambda: replace(primary_user(), role="member")
    try:
        forbidden = client.post("/api/v1/crm/imports/preview", json=request)
        assert forbidden.status_code == 403
        assert forbidden.json()["code"] == "forbidden"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_account_csv_preview_confirm_is_conservative_idempotent_and_content_free(
    app: FastAPI, client: TestClient
) -> None:
    enable_native_crm(client)
    suffix = uuid.uuid4().hex[:10]
    existing = client.post(
        "/api/v1/companies",
        json={"name": f"Existing {suffix}", "website": f"https://existing-{suffix}.example.com"},
    )
    assert existing.status_code == 201, existing.text
    headers = ["Name", "Website", "Owner", "Ignored Notes"]
    content = csv_base64(
        headers,
        [
            [f"Exact domain {suffix}", f"existing-{suffix}.example.com", "Admin", "not retained"],
            [f"Existing {suffix}", "", "Admin", "not retained"],
            [f"Imported {suffix}", f"imported-{suffix}.example.com", "Admin", "not retained"],
            ["", "", "Admin", "not retained"],
        ],
    )
    preview_request = {
        "entityType": "account",
        "fileName": f"accounts-{suffix}.csv",
        "contentBase64": content,
        "columnMapping": {"Name": "name", "Website": "website", "Owner": "owner", "Ignored Notes": None},
        "defaultOwnerUserId": str(PRIMARY_USER_ID),
        "ownerValueMapping": {"Admin": str(PRIMARY_USER_ID)},
        "stageValueMapping": {},
    }
    preview = client.post("/api/v1/crm/imports/preview", json=preview_request)
    assert preview.status_code == 200, preview.text
    payload = preview.json()
    assert payload["rowCount"] == 4
    assert payload["actionableRowCount"] == 1
    assert payload["permissionToContactInferred"] is False
    assert payload["rawFileRetained"] is False
    assert [row["disposition"] for row in payload["rows"]] == [
        "matches_existing",
        "possible_duplicate",
        "new",
        "invalid",
    ]
    before = client.get(f"/api/v1/companies?search=Imported%20{suffix}")
    assert before.status_code == 200
    assert before.json()["total"] == 0

    async def assert_content_free() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            batch = await session.get(CRMImportBatch, UUID(payload["batchId"]))
            rows = list(
                await session.scalars(select(CRMImportRow).where(CRMImportRow.batch_id == UUID(payload["batchId"])))
            )
            assert batch is not None and len(rows) == 4
            persisted = json.dumps(
                {
                    "batch": {key: value for key, value in batch.__dict__.items() if not key.startswith("_sa_")},
                    "rows": [
                        {key: value for key, value in row.__dict__.items() if not key.startswith("_sa_")}
                        for row in rows
                    ],
                },
                default=str,
            )
            assert "not retained" not in persisted
            assert f"Imported {suffix}" not in persisted
            assert f"imported-{suffix}.example.com" not in persisted
        await engine.dispose()

    asyncio.run(assert_content_free())
    confirm_request = {**preview_request, "batchId": payload["batchId"]}
    confirmed = client.post("/api/v1/crm/imports/confirm", json=confirm_request)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["importedRowCount"] == 1
    assert [row["disposition"] for row in confirmed.json()["rows"]] == [
        "skipped",
        "skipped",
        "imported",
        "skipped",
    ]
    retried = client.post("/api/v1/crm/imports/confirm", json=confirm_request)
    assert retried.status_code == 200
    assert retried.json() == confirmed.json()
    after = client.get(f"/api/v1/companies?search=Imported%20{suffix}")
    assert after.status_code == 200
    assert after.json()["total"] == 1

    async def export_metadata() -> dict[str, object]:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            export = await _export_payload(session, PRIMARY_ORGANISATION_ID, app.state.settings)
        await engine.dispose()
        return export

    exported = asyncio.run(export_metadata())
    assert exported["exportVersion"] == 31
    assert len(exported["crmImportBatches"]) == 1  # type: ignore[arg-type]
    assert len(exported["crmImportRows"]) == 4  # type: ignore[arg-type]
    assert "not retained" not in json.dumps(exported, default=str)


def test_contact_import_can_only_add_restrictive_suppression(client: TestClient) -> None:
    enable_native_crm(client)
    suffix = uuid.uuid4().hex[:10]
    account = client.post(
        "/api/v1/companies",
        json={"name": f"Contact Account {suffix}", "website": f"https://contact-{suffix}.example.com"},
    )
    assert account.status_code == 201
    headers = ["First", "Last", "Email", "Account", "Owner", "DNC"]
    request = {
        "entityType": "contact",
        "fileName": "contacts.csv",
        "contentBase64": csv_base64(
            headers,
            [["Casey", "Ng", f"casey-{suffix}@example.com", f"contact-{suffix}.example.com", "Admin", "yes"]],
        ),
        "columnMapping": {
            "First": "first_name",
            "Last": "last_name",
            "Email": "email",
            "Account": "account_domain",
            "Owner": "owner",
            "DNC": "do_not_contact",
        },
        "defaultOwnerUserId": str(PRIMARY_USER_ID),
        "ownerValueMapping": {"Admin": str(PRIMARY_USER_ID)},
        "stageValueMapping": {},
    }
    preview = client.post("/api/v1/crm/imports/preview", json=request)
    assert preview.status_code == 200, preview.text
    confirmed = client.post(
        "/api/v1/crm/imports/confirm",
        json={**request, "batchId": preview.json()["batchId"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    contact_id = confirmed.json()["rows"][0]["canonicalEntityId"]

    async def assert_suppression() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            suppression = await session.scalar(
                select(ContactSuppression).where(
                    ContactSuppression.organisation_id == PRIMARY_ORGANISATION_ID,
                    ContactSuppression.contact_id == UUID(contact_id),
                )
            )
            assert suppression is not None
            assert suppression.active is True
            assert suppression.reason == "manual_do_not_contact"
            assert suppression.source == "user"
            assert f"casey-{suffix}@example.com" not in suppression.email_fingerprint
        await engine.dispose()

    asyncio.run(assert_suppression())


def test_import_confirmation_revalidates_new_duplicate_state(client: TestClient) -> None:
    enable_native_crm(client)
    suffix = uuid.uuid4().hex[:10]
    domain = f"stale-import-{suffix}.example.com"
    request = {
        "entityType": "account",
        "fileName": "stale-accounts.csv",
        "contentBase64": csv_base64(
            ["Name", "Website"],
            [[f"Stale import {suffix}", domain]],
        ),
        "columnMapping": {"Name": "name", "Website": "website"},
        "defaultOwnerUserId": str(PRIMARY_USER_ID),
        "ownerValueMapping": {},
        "stageValueMapping": {},
    }
    preview = client.post("/api/v1/crm/imports/preview", json=request)
    assert preview.status_code == 200, preview.text
    assert preview.json()["rows"][0]["disposition"] == "new"

    concurrent = client.post(
        "/api/v1/companies",
        json={"name": f"Created after preview {suffix}", "website": f"https://{domain}"},
    )
    assert concurrent.status_code == 201, concurrent.text
    confirmed = client.post(
        "/api/v1/crm/imports/confirm",
        json={**request, "batchId": preview.json()["batchId"]},
    )
    assert confirmed.status_code == 409
    assert confirmed.json()["code"] == "crm_import_stale"

    matching = client.get(f"/api/v1/companies?search=Stale%20import%20{suffix}")
    assert matching.status_code == 200
    assert matching.json()["total"] == 0


def test_open_opportunity_import_uses_explicit_stage_baseline_without_fabricated_duration(client: TestClient) -> None:
    enable_native_crm(client)
    suffix = uuid.uuid4().hex[:10]
    account = client.post(
        "/api/v1/companies",
        json={"name": f"Opportunity Account {suffix}", "website": f"https://opportunity-{suffix}.example.com"},
    )
    assert account.status_code == 201
    pipelines = client.get("/api/v1/pipelines")
    assert pipelines.status_code == 200, pipelines.text
    pipeline = next(item for item in pipelines.json() if item["isDefault"])
    stage = next(item for item in pipeline["stages"] if item["stageType"] == "open")
    headers = ["Name", "Account", "Stage", "Value", "Currency", "Owner"]
    request = {
        "entityType": "opportunity",
        "fileName": "opportunities.csv",
        "contentBase64": csv_base64(
            headers,
            [
                [
                    f"Imported Opportunity {suffix}",
                    f"opportunity-{suffix}.example.com",
                    "Discovery",
                    "12000",
                    "AUD",
                    "Admin",
                ]
            ],
        ),
        "columnMapping": {
            "Name": "name",
            "Account": "account_domain",
            "Stage": "stage",
            "Value": "estimated_value",
            "Currency": "currency",
            "Owner": "owner",
        },
        "defaultOwnerUserId": str(PRIMARY_USER_ID),
        "ownerValueMapping": {"Admin": str(PRIMARY_USER_ID)},
        "pipelineId": pipeline["id"],
        "stageValueMapping": {"Discovery": stage["id"]},
    }
    preview = client.post("/api/v1/crm/imports/preview", json=request)
    assert preview.status_code == 200, preview.text
    confirmed = client.post(
        "/api/v1/crm/imports/confirm",
        json={**request, "batchId": preview.json()["batchId"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    opportunity_id = UUID(confirmed.json()["rows"][0]["canonicalEntityId"])

    async def assert_baseline() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            opportunity = await session.get(Opportunity, opportunity_id)
            event = await session.scalar(
                select(OpportunityStageEvent).where(
                    OpportunityStageEvent.organisation_id == PRIMARY_ORGANISATION_ID,
                    OpportunityStageEvent.opportunity_id == opportunity_id,
                )
            )
            changes = list(
                await session.scalars(
                    select(CRMRecordChange).where(
                        CRMRecordChange.organisation_id == PRIMARY_ORGANISATION_ID,
                        CRMRecordChange.entity_id == opportunity_id,
                    )
                )
            )
            assert opportunity is not None
            assert opportunity.status == "open"
            assert opportunity.stage_entered_at is None
            assert opportunity.stage_tracking_started_at is None
            assert event is not None and event.source == "import_baseline" and event.is_baseline is True
            assert {change.source for change in changes} == {"crm_import"}
        await engine.dispose()

    asyncio.run(assert_baseline())


def test_expired_unconfirmed_import_preview_is_closed_by_retention(app: FastAPI, client: TestClient) -> None:
    enable_native_crm(client)
    suffix = uuid.uuid4().hex[:10]
    request = {
        "entityType": "account",
        "fileName": "expired-preview.csv",
        "contentBase64": csv_base64(["Name"], [[f"Expired Preview {suffix}"]]),
        "columnMapping": {"Name": "name"},
        "defaultOwnerUserId": str(PRIMARY_USER_ID),
        "ownerValueMapping": {},
        "stageValueMapping": {},
    }
    preview = client.post("/api/v1/crm/imports/preview", json=request)
    assert preview.status_code == 200, preview.text
    batch_id = UUID(preview.json()["batchId"])

    async def expire_and_retain() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            batch = await session.get(CRMImportBatch, batch_id)
            assert batch is not None
            batch.expires_at = datetime.now(UTC) - timedelta(minutes=1)
            await session.commit()
        dry_run = await run_retention(
            factory,
            app.state.settings,
            PRIMARY_ORGANISATION_ID,
            dry_run=True,
            batch_size=100,
        )
        assert dry_run.removed["expired_crm_import_batches"] == 1
        applied = await run_retention(
            factory,
            app.state.settings,
            PRIMARY_ORGANISATION_ID,
            dry_run=False,
            batch_size=100,
        )
        assert applied.removed["expired_crm_import_batches"] == 1
        async with factory() as session:
            batch = await session.get(CRMImportBatch, batch_id)
            assert batch is not None and batch.state == "expired"
        await engine.dispose()

    asyncio.run(expire_and_retain())
    confirm = client.post(
        "/api/v1/crm/imports/confirm",
        json={**request, "batchId": str(batch_id)},
    )
    assert confirm.status_code == 410
    assert confirm.json()["code"] == "crm_import_expired"
