from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import AuthenticatedUser, get_current_user
from revenueos.beta_maintenance import EXPORT_VERSION, _export_payload
from revenueos.database import set_tenant_database_context
from revenueos.models import IntegrationConnection, OrganisationCRMSetting

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, TEST_DB_URL
from .test_business_api import create_company, create_opportunity
from .test_meeting_api import cast_auth_dependency, secondary_user


def configure_native(client: TestClient) -> None:
    response = client.put("/api/v1/crm/settings", json={"mode": "native", "confirmed": True})
    assert response.status_code == 200, response.text


def test_board_keeps_currencies_separate_and_stage_transition_is_immutable_and_idempotent(
    client: TestClient,
) -> None:
    configure_native(client)
    company = create_company(client, name="Pipeline board account")
    first = create_opportunity(client, str(company["id"]), name="AUD opportunity")
    second = client.post(
        "/api/v1/opportunities",
        json={
            "companyId": company["id"],
            "name": "USD opportunity",
            "stage": "evaluation",
            "status": "open",
            "estimatedValue": "50000",
            "currency": "USD",
            "expectedCloseDate": "2026-09-20",
        },
    )
    assert second.status_code == 201, second.text

    board = client.get("/api/v1/pipeline")
    assert board.status_code == 200, board.text
    body = board.json()
    assert {item["currency"]: item["amount"] for item in body["summary"]["values"]} == {
        "AUD": "125000.50",
        "USD": "50000.00",
    }
    assert "weighted" not in board.text.lower()
    assert "probability" not in board.text.lower()

    pipeline = client.get(f"/api/v1/opportunities/{first['id']}/pipeline").json()
    current_stage_id = pipeline["stage"]["id"]
    negotiation = next(stage for stage in pipeline["pipeline"]["stages"] if stage["key"] == "negotiation")
    methodology_before = client.get(f"/api/v1/opportunities/{first['id']}/methodology").json()
    request = {
        "targetStageId": negotiation["id"],
        "expectedCurrentStageId": current_stage_id,
        "idempotencyKey": "pipeline-idempotent-move",
    }
    moved = client.post(f"/api/v1/opportunities/{first['id']}/stage", json=request)
    assert moved.status_code == 200, moved.text
    assert moved.json()["stage"]["name"] == "Negotiation"
    assert moved.json()["daysInStage"] == 0
    repeated = client.post(f"/api/v1/opportunities/{first['id']}/stage", json=request)
    assert repeated.status_code == 200, repeated.text
    assert len(repeated.json()["history"]) == 2
    no_op = client.post(
        f"/api/v1/opportunities/{first['id']}/stage",
        json={
            "targetStageId": negotiation["id"],
            "expectedCurrentStageId": negotiation["id"],
            "idempotencyKey": "pipeline-same-stage-no-op",
        },
    )
    assert no_op.status_code == 200, no_op.text
    assert len(no_op.json()["history"]) == 2
    assert client.get(f"/api/v1/opportunities/{first['id']}/methodology").json() == methodology_before

    stale = client.post(
        f"/api/v1/opportunities/{first['id']}/stage",
        json={
            "targetStageId": pipeline["pipeline"]["stages"][0]["id"],
            "expectedCurrentStageId": current_stage_id,
            "idempotencyKey": "pipeline-stale-second-move",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_pipeline_state"


def test_close_won_records_final_value_without_changing_methodology(client: TestClient) -> None:
    configure_native(client)
    company = create_company(client, name="Won outcome account")
    opportunity = create_opportunity(client, str(company["id"]), name="Won opportunity")
    pipeline = client.get(f"/api/v1/opportunities/{opportunity['id']}/pipeline").json()
    methodology_before = client.get(f"/api/v1/opportunities/{opportunity['id']}/methodology").json()

    closed = client.post(
        f"/api/v1/opportunities/{opportunity['id']}/close-won",
        json={
            "expectedCurrentStageId": pipeline["stage"]["id"],
            "actualCloseDate": datetime.now(UTC).date().isoformat(),
            "finalAmount": "130000.00",
            "outcomeReason": "solution_fit",
            "outcomeNote": "Seller reported a strong solution fit.",
            "idempotencyKey": "pipeline-close-won",
        },
    )

    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "won"
    assert closed.json()["stage"]["stageType"] == "won"
    closure_event = next(event for event in closed.json()["history"] if event["outcomeReason"] == "solution_fit")
    assert closure_event["finalAmount"] == "130000.00"
    assert closure_event["finalCurrency"] == "AUD"
    assert client.get(f"/api/v1/opportunities/{opportunity['id']}/methodology").json() == methodology_before


def test_close_lost_and_reopen_preserve_seller_reported_history(app: FastAPI, client: TestClient) -> None:
    configure_native(client)
    company = create_company(client, name="Outcome account")
    opportunity = create_opportunity(client, str(company["id"]), name="Outcome opportunity")
    pipeline = client.get(f"/api/v1/opportunities/{opportunity['id']}/pipeline").json()
    closed = client.post(
        f"/api/v1/opportunities/{opportunity['id']}/close-lost",
        json={
            "expectedCurrentStageId": pipeline["stage"]["id"],
            "actualCloseDate": datetime.now(UTC).date().isoformat(),
            "outcomeReason": "timing",
            "outcomeNote": "Seller reported timing changed.",
            "idempotencyKey": "pipeline-close-lost",
        },
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "lost"
    assert closed.json()["outcomeReason"] == "timing"
    assert closed.json()["outcomeProvenance"] == "seller_reported"
    record = client.get(f"/api/v1/crm/records/opportunity/{opportunity['id']}")
    assert record.status_code == 200, record.text
    assert {item["fieldKey"] for item in record.json()["history"]} >= {
        "status",
        "actual_close_date",
        "outcome_reason",
        "outcome_note",
        "outcome_provenance",
    }
    assert client.get("/api/v1/pipeline").json()["cards"] == []
    assert client.get("/api/v1/pipeline", params={"view": "closed"}).json()["cards"][0]["outcomeReason"] == "timing"

    discovery = next(stage for stage in closed.json()["availablePipelines"][0]["stages"] if stage["key"] == "discovery")
    reopened = client.post(
        f"/api/v1/opportunities/{opportunity['id']}/reopen",
        json={
            "targetStageId": discovery["id"],
            "expectedCurrentStageId": closed.json()["stage"]["id"],
            "idempotencyKey": "pipeline-reopen-lost",
        },
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "open"
    assert reopened.json()["outcomeReason"] is None
    closure_event = next(event for event in reopened.json()["history"] if event["outcomeReason"] == "timing")
    assert closure_event["actualCloseDate"] == datetime.now(UTC).date().isoformat()
    assert closure_event["finalAmount"] == "125000.50"
    assert closure_event["finalCurrency"] == "AUD"

    async def export_payload() -> dict[str, object]:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            payload = await _export_payload(session, PRIMARY_ORGANISATION_ID, app.state.settings)
        await engine.dispose()
        return payload

    exported = asyncio.run(export_payload())
    assert exported["exportVersion"] == EXPORT_VERSION == 29
    assert len(exported["salesPipelines"]) == 1  # type: ignore[arg-type]
    assert len(exported["salesPipelineStages"]) == 9  # type: ignore[arg-type]
    events = exported["opportunityStageEvents"]
    assert isinstance(events, list)
    exported_closure = next(item for item in events if item["outcome_reason"] == "timing")
    assert exported_closure["actual_close_date"] == datetime.now(UTC).date()


def test_admin_pipeline_limits_archive_guard_and_external_authority(app: FastAPI, client: TestClient) -> None:
    configure_native(client)
    company = create_company(client, name="Pipeline administration account")
    opportunity = create_opportunity(client, str(company["id"]), name="Administration opportunity")
    created = client.post(
        "/api/v1/pipelines",
        json={
            "name": "Enterprise sales",
            "stages": [
                {"name": "Explore", "stageType": "open"},
                {"name": "Validate", "stageType": "open"},
                {"name": "Won", "stageType": "won"},
                {"name": "Lost", "stageType": "lost"},
            ],
        },
    )
    assert created.status_code == 201, created.text
    enterprise = created.json()
    added = client.post(
        f"/api/v1/pipelines/{enterprise['id']}/stages",
        json={"name": "Legal review", "position": 2},
    )
    assert added.status_code == 201, added.text
    legal = next(stage for stage in added.json()["stages"] if stage["name"] == "Legal review")
    renamed = client.patch(
        f"/api/v1/pipelines/{enterprise['id']}/stages/{legal['id']}",
        json={"name": "Contract review", "position": 1},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["stages"][1]["name"] == "Contract review"
    semantic_change = client.patch(
        f"/api/v1/pipelines/{enterprise['id']}/stages/{legal['id']}",
        json={"stageType": "won"},
    )
    assert semantic_change.status_code == 422
    archived_empty = client.post(f"/api/v1/pipelines/{enterprise['id']}/stages/{legal['id']}/archive")
    assert archived_empty.status_code == 200, archived_empty.text

    made_default = client.patch(f"/api/v1/pipelines/{enterprise['id']}", json={"isDefault": True})
    assert made_default.status_code == 200, made_default.text
    assert made_default.json()["isDefault"] is True
    original_pipeline = next(item for item in client.get("/api/v1/pipelines").json() if item["id"] != enterprise["id"])
    used_stage = next(stage for stage in original_pipeline["stages"] if stage["key"] == "proposal")
    blocked_archive = client.post(f"/api/v1/pipelines/{original_pipeline['id']}/stages/{used_stage['id']}/archive")
    assert blocked_archive.status_code == 409
    assert blocked_archive.json()["code"] == "pipeline_stage_in_use"

    client.patch(f"/api/v1/pipelines/{original_pipeline['id']}", json={"isDefault": True})
    assert client.post(f"/api/v1/pipelines/{enterprise['id']}/archive").status_code == 200
    for index in range(4):
        response = client.post(
            "/api/v1/pipelines",
            json={
                "name": f"Bounded pipeline {index}",
                "stages": [
                    {"name": "Open", "stageType": "open"},
                    {"name": "Won", "stageType": "won"},
                    {"name": "Lost", "stageType": "lost"},
                ],
                "isDefault": index == 0,
            },
        )
        assert response.status_code == 201, response.text
        if index == 0:
            assert response.json()["isDefault"] is True
    limit = client.post(
        "/api/v1/pipelines",
        json={
            "name": "One pipeline too many",
            "stages": [
                {"name": "Open", "stageType": "open"},
                {"name": "Won", "stageType": "won"},
                {"name": "Lost", "stageType": "lost"},
            ],
        },
    )
    assert limit.status_code == 409
    assert limit.json()["code"] == "pipeline_limit_reached"

    member = AuthenticatedUser(
        user_id=PRIMARY_USER_ID,
        external_auth_id="user_dev_001",
        display_name="Alex Morgan",
        email="alex@example.test",
        organisation_id=PRIMARY_ORGANISATION_ID,
        organisation_name="Example Revenue Team",
        organisation_slug="example-revenue-team",
        role="member",
        auth_mode="mock",
    )
    app.dependency_overrides[get_current_user] = cast_auth_dependency(member)
    try:
        denied_admin = client.post(
            "/api/v1/pipelines",
            json={
                "name": "Member pipeline",
                "stages": [
                    {"name": "Open", "stageType": "open"},
                    {"name": "Won", "stageType": "won"},
                    {"name": "Lost", "stageType": "lost"},
                ],
            },
        )
        assert denied_admin.status_code == 403
        assert denied_admin.json()["code"] == "admin_required"
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    async def make_external() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            await session.execute(
                update(OrganisationCRMSetting)
                .where(OrganisationCRMSetting.organisation_id == PRIMARY_ORGANISATION_ID)
                .values(mode="external", external_provider="hubspot")
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(make_external())
    state = client.get(f"/api/v1/opportunities/{opportunity['id']}/pipeline").json()
    target = next(stage for stage in state["pipeline"]["stages"] if stage["key"] == "negotiation")
    blocked_move = client.post(
        f"/api/v1/opportunities/{opportunity['id']}/stage",
        json={
            "targetStageId": target["id"],
            "expectedCurrentStageId": state["stage"]["id"],
            "idempotencyKey": "external-authority-move",
        },
    )
    assert blocked_move.status_code == 409
    assert blocked_move.json()["code"] == "external_stage_authority"

    async def make_legacy_external() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            await session.execute(
                delete(OrganisationCRMSetting).where(OrganisationCRMSetting.organisation_id == PRIMARY_ORGANISATION_ID)
            )
            session.add(
                IntegrationConnection(
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    connector_key="hubspot",
                    connection_status="active",
                    created_by_user_id=PRIMARY_USER_ID,
                )
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(make_legacy_external())
    legacy_blocked = client.post(
        f"/api/v1/opportunities/{opportunity['id']}/stage",
        json={
            "targetStageId": target["id"],
            "expectedCurrentStageId": state["stage"]["id"],
            "idempotencyKey": "legacy-external-authority-move",
        },
    )
    assert legacy_blocked.status_code == 409
    assert legacy_blocked.json()["code"] == "external_stage_authority"


def test_cross_tenant_stage_identifier_is_not_resolved(app: FastAPI, client: TestClient) -> None:
    configure_native(client)
    company = create_company(client, name="Tenant-safe pipeline account")
    opportunity = create_opportunity(client, str(company["id"]), name="Tenant-safe opportunity")
    current = client.get(f"/api/v1/opportunities/{opportunity['id']}/pipeline").json()

    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    try:
        other_stage_id = client.get("/api/v1/pipelines").json()[0]["stages"][0]["id"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    denied = client.post(
        f"/api/v1/opportunities/{opportunity['id']}/stage",
        json={
            "targetStageId": other_stage_id,
            "expectedCurrentStageId": current["stage"]["id"],
            "idempotencyKey": "cross-tenant-stage-move",
        },
    )
    assert denied.status_code == 404
    assert denied.json()["code"] == "pipeline_stage_not_found"
