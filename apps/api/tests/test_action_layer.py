from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import get_current_user
from revenueos.models import (
    ActionAuditEvent,
    ActionProposal,
    ActionProposalVersion,
    Opportunity,
    PreInteractionBrief,
    Task,
)

from .conftest import TEST_DB_URL
from .test_business_api import create_company, create_opportunity
from .test_interaction_api import create_interaction
from .test_meeting_api import cast_auth_dependency, create_meeting, secondary_user
from .test_meeting_intelligence_workspace import _run_worker_once
from .test_opportunity_workspace import _associate


def _completed_intelligence_actions(client: TestClient) -> tuple[dict[str, object], dict[str, object]]:
    company = create_company(client, name="Action Layer account")
    opportunity = create_opportunity(client, str(company["id"]))
    meeting = create_meeting(
        client,
        title="Action Layer review",
        company_id=str(company["id"]),
        transcript={
            "rawText": (
                "The customer confirmed budget and asked for the security documentation. "
                "Jordan will send the security pack by 2026-08-20. "
                "We agreed to schedule a technical workshop. The final legal approver remains unknown."
            ),
            "language": "en-AU",
            "source": "manual",
        },
    )
    completed = client.patch(
        f"/api/v1/meetings/{meeting['id']}",
        json={"status": "completed"},
    )
    assert completed.status_code == 200, completed.text
    meeting.update(completed.json())
    _associate(client, meeting, str(opportunity["id"]))
    endpoint = f"/api/v1/meetings/{meeting['id']}/intelligence/generate"
    assert client.post(endpoint).status_code == 202
    for _ in range(8):
        _run_worker_once()
    assert client.post(endpoint).status_code == 202
    _run_worker_once()
    _run_worker_once()
    return opportunity, meeting


def _database_state(action_id: str) -> dict[str, object]:
    async def read() -> dict[str, object]:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            proposal = await session.scalar(select(ActionProposal).where(ActionProposal.id == UUID(action_id)))
            assert proposal is not None
            versions = await session.scalar(
                select(func.count())
                .select_from(ActionProposalVersion)
                .where(ActionProposalVersion.action_id == proposal.id)
            )
            events = await session.scalars(
                select(ActionAuditEvent.event_type)
                .where(ActionAuditEvent.action_id == proposal.id)
                .order_by(ActionAuditEvent.created_at, ActionAuditEvent.id)
            )
            tasks = await session.scalar(select(func.count()).select_from(Task))
            opportunity = await session.get(Opportunity, proposal.opportunity_id)
            result = {
                "status": proposal.status,
                "current_version": proposal.current_version,
                "versions": int(versions or 0),
                "events": list(events.all()),
                "task_count": int(tasks or 0),
                "opportunity_stage": opportunity.stage if opportunity else None,
            }
        await engine.dispose()
        return result

    return asyncio.run(read())


def test_generation_requires_final_validated_sources_and_is_idempotent(client: TestClient) -> None:
    opportunity = create_opportunity(client, str(create_company(client)["id"]))
    empty = client.post(f"/api/v1/opportunities/{opportunity['id']}/actions/generate")
    assert empty.status_code == 200, empty.text
    assert empty.json()["actions"] == []
    assert empty.json()["providerCompositionUsed"] is False
    assert empty.json()["externalActionsExecuted"] is False

    opportunity, _ = _completed_intelligence_actions(client)
    generated = client.post(f"/api/v1/opportunities/{opportunity['id']}/actions/generate")
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert 1 <= body["createdCount"] <= 8
    assert body["proposalLimit"] == 8
    assert any(item["actionType"] == "follow_up_email" for item in body["actions"])
    assert any(item["actionType"] == "create_task" for item in body["actions"])
    assert all(item["executionState"] == "not_executed" for item in body["actions"])
    assert "rawText" not in generated.text

    repeated = client.post(f"/api/v1/opportunities/{opportunity['id']}/actions/generate")
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["createdCount"] == 0
    assert repeated.json()["reusedCount"] == body["createdCount"]
    assert {item["id"] for item in repeated.json()["actions"]} == {item["id"] for item in body["actions"]}


def test_edit_approve_reject_and_manual_completion_preserve_review_boundary(client: TestClient) -> None:
    opportunity, _ = _completed_intelligence_actions(client)
    generated = client.post(f"/api/v1/opportunities/{opportunity['id']}/actions/generate").json()["actions"]
    email_action = next(item for item in generated if item["actionType"] == "follow_up_email")
    task_action = next(item for item in generated if item["actionType"] == "create_task")
    rejected_action = next(item for item in generated if item["id"] not in {email_action["id"], task_action["id"]})

    edited_payload = {**email_action["proposedPayload"], "subject": "Reviewed follow-up subject"}
    edited = client.patch(
        f"/api/v1/actions/{email_action['id']}",
        json={
            "expectedVersion": email_action["currentVersion"],
            "title": email_action["title"],
            "description": email_action["description"],
            "proposedDueAt": email_action["proposedDueAt"],
            "proposedPayload": edited_payload,
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["status"] == "edited"
    assert edited.json()["currentVersion"] == 2
    assert edited.json()["proposedPayload"]["subject"] == "Reviewed follow-up subject"

    approved_email = client.post(
        f"/api/v1/actions/{email_action['id']}/approve",
        json={"expectedVersion": 2},
    )
    assert approved_email.status_code == 200, approved_email.text
    assert approved_email.json()["status"] == "approved"
    assert approved_email.json()["executionState"] == "not_executed"
    assert approved_email.json()["sendReady"] is False

    approved_task = client.post(
        f"/api/v1/actions/{task_action['id']}/approve",
        json={"expectedVersion": task_action["currentVersion"]},
    )
    assert approved_task.status_code == 200, approved_task.text
    completed = client.post(
        f"/api/v1/actions/{task_action['id']}/complete",
        json={"expectedVersion": task_action["currentVersion"]},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed_manually"

    rejected = client.post(
        f"/api/v1/actions/{rejected_action['id']}/reject",
        json={"expectedVersion": rejected_action["currentVersion"], "reasonCode": "not_relevant"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["rejectionReasonCode"] == "not_relevant"

    email_state = _database_state(str(email_action["id"]))
    assert email_state["versions"] == 2
    assert email_state["events"] == ["proposed", "edited", "approved"]
    assert email_state["task_count"] == 0
    assert email_state["opportunity_stage"] == opportunity["stage"]
    assert (
        client.post(
            f"/api/v1/actions/{email_action['id']}/complete",
            json={"expectedVersion": 2},
        ).status_code
        == 409
    )


def test_stale_source_is_superseded_before_approval(client: TestClient) -> None:
    opportunity, meeting = _completed_intelligence_actions(client)
    actions = client.post(f"/api/v1/opportunities/{opportunity['id']}/actions/generate").json()["actions"]
    action = next(item for item in actions if item["actionType"] == "follow_up_email")
    transcript = client.get(f"/api/v1/meetings/{meeting['id']}/transcript").json()
    updated = client.patch(
        f"/api/v1/meetings/{meeting['id']}/transcript",
        json={
            "rawText": "A new final transcript invalidates the earlier Action proposal.",
            "language": "en-AU",
            "version": transcript["version"],
        },
    )
    assert updated.status_code == 200, updated.text

    approval = client.post(
        f"/api/v1/actions/{action['id']}/approve",
        json={"expectedVersion": action["currentVersion"]},
    )
    assert approval.status_code == 409
    assert approval.json()["code"] == "action_source_stale"
    assert client.get(f"/api/v1/actions/{action['id']}").json()["status"] == "superseded"


def test_actions_are_tenant_scoped_and_payloads_forbid_unknown_fields(
    app: FastAPI,
    client: TestClient,
) -> None:
    opportunity, _ = _completed_intelligence_actions(client)
    action = client.post(f"/api/v1/opportunities/{opportunity['id']}/actions/generate").json()["actions"][0]

    invalid = client.patch(
        f"/api/v1/actions/{action['id']}",
        json={
            "expectedVersion": action["currentVersion"],
            "title": action["title"],
            "description": action["description"],
            "proposedDueAt": action["proposedDueAt"],
            "proposedPayload": {**action["proposedPayload"], "executeNow": True},
        },
    )
    assert invalid.status_code == 422

    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    try:
        assert client.get(f"/api/v1/actions/{action['id']}").status_code == 404
        assert client.get(f"/api/v1/opportunities/{opportunity['id']}/actions").status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user)


def test_action_feature_flag_fails_closed(app: FastAPI, client: TestClient) -> None:
    app.state.settings.feature_action_layer_enabled = False
    opportunity = create_opportunity(client, str(create_company(client)["id"]))
    response = client.post(f"/api/v1/opportunities/{opportunity['id']}/actions/generate")
    assert response.status_code == 404
    assert response.json()["code"] == "feature_unavailable"


def test_pending_actions_feed_future_briefs_and_rejected_actions_are_excluded(client: TestClient) -> None:
    opportunity, _ = _completed_intelligence_actions(client)
    actions = client.post(f"/api/v1/opportunities/{opportunity['id']}/actions/generate").json()["actions"]
    email_action = next(item for item in actions if item["actionType"] == "follow_up_email")
    target = create_interaction(
        client,
        title="Prepare with pending Actions",
        interaction_type="phone_call",
        company_id=str(opportunity["companyId"]),
        opportunity_id=str(opportunity["id"]),
    )
    generated = client.post(f"/api/v1/interactions/{target['id']}/companion/brief")
    assert generated.status_code == 200, generated.text
    assert email_action["title"] in {item["commitment"] for item in generated.json()["brief"]["openCommitments"]}
    assert "Current pending or approved Actions" in generated.json()["sourceLabels"]

    rejected = client.post(
        f"/api/v1/actions/{email_action['id']}/reject",
        json={"expectedVersion": email_action["currentVersion"], "reasonCode": "not_relevant"},
    )
    assert rejected.status_code == 200, rejected.text
    next_target = create_interaction(
        client,
        title="Prepare after rejection",
        interaction_type="phone_call",
        company_id=str(opportunity["companyId"]),
        opportunity_id=str(opportunity["id"]),
    )
    regenerated = client.post(f"/api/v1/interactions/{next_target['id']}/companion/brief")
    assert regenerated.status_code == 200, regenerated.text
    assert email_action["title"] not in {item["commitment"] for item in regenerated.json()["brief"]["openCommitments"]}

    async def source_capabilities() -> set[str]:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            record = await session.scalar(
                select(PreInteractionBrief).where(PreInteractionBrief.interaction_id == UUID(str(next_target["id"])))
            )
            assert record is not None
            capabilities = {str(item["capability"]) for item in record.source_references_json}
        await engine.dispose()
        return capabilities

    assert "action_layer" in asyncio.run(source_capabilities())
