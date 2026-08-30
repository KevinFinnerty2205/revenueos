from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import get_current_user
from revenueos.beta_maintenance import EXPORT_VERSION, _export_payload
from revenueos.campaign_worker import CampaignWorkerService
from revenueos.integration_worker import ActionExecutionWorkerService
from revenueos.models import (
    ActionAuditEvent,
    ActionExecution,
    EngageCampaignAudience,
    EngageCampaignVersion,
    EngageEnrollmentStep,
    Evidence,
    OutreachMessage,
)

from .conftest import PRIMARY_ORGANISATION_ID, TEST_DB_URL
from .test_integration_execution import _enable_execution
from .test_meeting_api import cast_auth_dependency, secondary_user
from .test_outreach import _configure_policy, _promote_jane


def _campaign_request(
    contact_ids: list[str],
    *,
    approval_mode: str = "review_each_send",
    name: str = "Australian Multi-Site CIO Outreach",
) -> dict[str, object]:
    return {
        "name": name,
        "purpose": "Book respectful introductory meetings",
        "approvalMode": approval_mode,
        "sourceType": "manual_contacts",
        "senderTimezone": "Australia/Sydney",
        "sendDays": [1, 2, 3, 4, 5, 6, 7],
        "sendWindowStartMinutes": 0,
        "sendWindowEndMinutes": 1439,
        "stopOnActiveOpportunity": True,
        "contactIds": contact_ids,
        "steps": [
            {
                "delayDays": 0,
                "objective": "introduction",
                "contentStrategy": "source_backed_value",
                "enabled": True,
            },
            {
                "delayDays": 1,
                "objective": "follow_up",
                "contentStrategy": "truthful_follow_up",
                "enabled": True,
            },
        ],
    }


def _run_campaign_worker(app: FastAPI, *, times: int = 1) -> None:
    async def execute() -> None:
        worker = CampaignWorkerService(app.state.session_factory, app.state.settings)
        for index in range(times):
            assert await worker.run_once(f"campaign-test-worker-{index}") is True

    asyncio.run(execute())


def _run_execution_worker(app: FastAPI) -> None:
    async def execute() -> None:
        worker = ActionExecutionWorkerService(app.state.session_factory, app.state.settings)
        assert await worker.run_once("campaign-execution-test-worker") is True

    asyncio.run(execute())


def _evidence_count() -> int:
    result = 0

    async def execute() -> None:
        nonlocal result
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            result = int(await session.scalar(select(Evidence.id).limit(1)) is not None)
        await engine.dispose()

    asyncio.run(execute())
    return result


def _make_current_step_due() -> None:
    async def execute() -> None:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            await session.execute(
                update(EngageEnrollmentStep)
                .where(EngageEnrollmentStep.state.in_(("pending", "prepared", "deferred")))
                .values(prepare_at=datetime.now(UTC), scheduled_at=datetime.now(UTC))
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(execute())


def _mark_campaign_execution_unknown() -> None:
    async def execute() -> None:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            execution = await session.scalar(
                select(ActionExecution).order_by(ActionExecution.created_at.desc()).limit(1)
            )
            assert execution is not None
            execution.execution_status = "unknown_external_state"
            execution.safe_failure_code = "mock_outcome_unknown"
            execution.retryable = False
            await session.commit()
        await engine.dispose()

    asyncio.run(execute())


def _approval_audit_for_outreach(outreach_id: str) -> dict[str, object]:
    result: dict[str, object] = {}

    async def execute() -> None:
        nonlocal result
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            event = await session.scalar(
                select(ActionAuditEvent)
                .join(OutreachMessage, OutreachMessage.action_id == ActionAuditEvent.action_id)
                .where(
                    OutreachMessage.id == UUID(outreach_id),
                    ActionAuditEvent.event_type == "approved",
                )
            )
            assert event is not None
            result = event.metadata_json
        await engine.dispose()

    asyncio.run(execute())
    return result


def test_review_each_send_campaign_reuses_exact_outreach_and_manual_outcome(app: FastAPI, client: TestClient) -> None:
    _enable_execution(app)
    contact_id = _promote_jane(client)
    _configure_policy(client, cooldown_hours=0)
    connection = client.post("/api/v1/integrations/connections", json={"connectorKey": "mock_email"})
    assert connection.status_code == 201, connection.text

    created = client.post("/api/v1/engage/campaigns", json=_campaign_request([contact_id]))
    assert created.status_code == 201, created.text
    campaign = created.json()
    assert campaign["eligibleCount"] == 1
    assert campaign["blockedCount"] == 0
    assert len(campaign["steps"]) == 2

    launched = client.post(
        f"/api/v1/engage/campaigns/{campaign['id']}/launch",
        json={"expectedVersion": 1, "confirmed": True, "autoSendConfirmed": False},
    )
    assert launched.status_code == 200, launched.text
    assert launched.json()["state"] == "active"
    assert launched.json()["policyVersion"] == 1

    immutable = client.patch(
        f"/api/v1/engage/campaigns/{campaign['id']}",
        json={**_campaign_request([contact_id]), "expectedVersion": 1},
    )
    assert immutable.status_code == 409, immutable.text
    assert immutable.json()["code"] == "campaign_immutable"

    _run_campaign_worker(app)
    enrollments = client.get(f"/api/v1/engage/campaigns/{campaign['id']}/enrollments")
    assert enrollments.status_code == 200, enrollments.text
    enrollment = enrollments.json()["items"][0]
    outreach = enrollment["currentOutreach"]
    assert outreach["state"] == "draft"
    assert outreach["version"]["personalizationUsed"] is True
    assert "technology consolidation" in outreach["version"]["body"]
    assert enrollment["steps"][0]["state"] == "ready_for_review"

    approved = client.post(f"/api/v1/engage/outreach/{outreach['id']}/approve", json={"expectedVersion": 1})
    assert approved.status_code == 200, approved.text
    preview = client.post(
        f"/api/v1/engage/outreach/{outreach['id']}/execution-preview",
        json={"connectionId": connection.json()["id"]},
    )
    assert preview.status_code == 200, preview.text
    sent = client.post(
        f"/api/v1/engage/outreach/{outreach['id']}/send",
        json={
            "connectionId": connection.json()["id"],
            "previewId": preview.json()["id"],
            "confirmed": True,
        },
    )
    assert sent.status_code == 202, sent.text
    before_evidence = _evidence_count()
    _run_execution_worker(app)
    _run_campaign_worker(app)

    progressed = client.get(f"/api/v1/engage/enrollments/{enrollment['id']}")
    assert progressed.status_code == 200, progressed.text
    assert progressed.json()["currentStepOrder"] == 2
    assert progressed.json()["steps"][0]["state"] == "sent"
    assert progressed.json()["steps"][1]["state"] == "pending"
    assert _evidence_count() == before_evidence

    outcome = client.post(f"/api/v1/engage/enrollments/{enrollment['id']}/outcome", json={"outcome": "replied"})
    assert outcome.status_code == 200, outcome.text
    assert outcome.json()["state"] == "stopped"
    assert outcome.json()["outcomeProvenance"] == "seller_reported"
    assert outcome.json()["steps"][1]["state"] == "cancelled"
    assert _evidence_count() == before_evidence


def test_campaign_contract_rejects_unbounded_or_ambiguous_configuration(client: TestClient) -> None:
    too_many_recipients = client.post(
        "/api/v1/engage/campaigns",
        json=_campaign_request([str(uuid4()) for _ in range(51)]),
    )
    assert too_many_recipients.status_code == 422, too_many_recipients.text

    duplicate_contact = str(uuid4())
    duplicates = client.post(
        "/api/v1/engage/campaigns",
        json=_campaign_request([duplicate_contact, duplicate_contact]),
    )
    assert duplicates.status_code == 422, duplicates.text

    scripted = _campaign_request([str(uuid4())])
    scripted["steps"] = [
        {
            "delayDays": 0,
            "objective": "introduction",
            "contentStrategy": "execute_arbitrary_script",
            "enabled": True,
        }
    ]
    unsupported_strategy = client.post("/api/v1/engage/campaigns", json=scripted)
    assert unsupported_strategy.status_code == 422, unsupported_strategy.text


def test_auto_send_requires_org_permission_and_explicit_launch_confirmation(app: FastAPI, client: TestClient) -> None:
    _enable_execution(app)
    contact_id = _promote_jane(client)
    _configure_policy(client, cooldown_hours=0)
    client.post("/api/v1/integrations/connections", json={"connectorKey": "mock_email"})
    campaign = client.post(
        "/api/v1/engage/campaigns",
        json=_campaign_request([contact_id], approval_mode="approved_campaign_auto_send"),
    ).json()

    blocked = client.post(
        f"/api/v1/engage/campaigns/{campaign['id']}/launch",
        json={"expectedVersion": 1, "confirmed": True, "autoSendConfirmed": True},
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "campaign_auto_send_not_allowed"

    _configure_policy(client, cooldown_hours=0, campaign_auto_send_allowed=True)
    unconfirmed = client.post(
        f"/api/v1/engage/campaigns/{campaign['id']}/launch",
        json={"expectedVersion": 1, "confirmed": True, "autoSendConfirmed": False},
    )
    assert unconfirmed.status_code == 409, unconfirmed.text
    assert unconfirmed.json()["code"] == "campaign_auto_send_confirmation_required"

    launched = client.post(
        f"/api/v1/engage/campaigns/{campaign['id']}/launch",
        json={"expectedVersion": 1, "confirmed": True, "autoSendConfirmed": True},
    )
    assert launched.status_code == 200, launched.text
    assert "automatically" in launched.json()["launchWarning"]
    _run_campaign_worker(app, times=2)
    _run_execution_worker(app)
    _run_campaign_worker(app)

    enrollment = client.get(f"/api/v1/engage/campaigns/{campaign['id']}/enrollments").json()["items"][0]
    assert enrollment["steps"][0]["state"] == "sent"
    assert enrollment["currentStepOrder"] == 2
    sent_outreach = client.get(f"/api/v1/engage/outreach/{enrollment['steps'][0]['outreachMessageId']}").json()
    assert sent_outreach["version"]["composerVersion"] == "outreach_campaign_deterministic_v1"
    approval_audit = _approval_audit_for_outreach(enrollment["steps"][0]["outreachMessageId"])
    assert approval_audit["approval_basis"] == "campaign_launch"
    assert approval_audit["campaign_step_instance_id"] == enrollment["steps"][0]["id"]

    _make_current_step_due()
    _run_campaign_worker(app)
    suppression = client.post(
        f"/api/v1/engage/contacts/{contact_id}/suppression", json={"reason": "manual_do_not_contact"}
    )
    assert suppression.status_code == 201, suppression.text
    _run_campaign_worker(app)
    stopped = client.get(f"/api/v1/engage/enrollments/{enrollment['id']}").json()
    assert stopped["state"] == "stopped"
    assert stopped["stopReason"] == "suppressed"
    assert stopped["steps"][1]["state"] == "blocked"


def test_active_opportunity_and_campaign_collision_block_cold_follow_up(app: FastAPI, client: TestClient) -> None:
    _enable_execution(app)
    contact_id = _promote_jane(client)
    _configure_policy(client, cooldown_hours=0)
    client.post("/api/v1/integrations/connections", json={"connectorKey": "mock_email"})
    first = client.post("/api/v1/engage/campaigns", json=_campaign_request([contact_id])).json()
    launch = client.post(
        f"/api/v1/engage/campaigns/{first['id']}/launch",
        json={"expectedVersion": 1, "confirmed": True, "autoSendConfirmed": False},
    )
    assert launch.status_code == 200, launch.text

    collision = client.post(
        "/api/v1/engage/campaigns",
        json=_campaign_request([contact_id], name="Second prospecting campaign"),
    )
    assert collision.status_code == 201, collision.text
    assert collision.json()["eligibleCount"] == 0
    assert collision.json()["audience"][0]["eligibilityCode"] == "active_campaign_collision"

    company_id = launch.json()["audience"][0]["companyId"]
    opportunity = client.post(
        "/api/v1/opportunities",
        json={
            "companyId": company_id,
            "name": "Northstar active opportunity",
            "stage": "evaluation",
            "status": "open",
            "estimatedValue": "120000",
            "currency": "AUD",
        },
    )
    assert opportunity.status_code == 201, opportunity.text
    _run_campaign_worker(app)
    enrollment = client.get(f"/api/v1/engage/campaigns/{first['id']}/enrollments").json()["items"][0]
    assert enrollment["state"] == "stopped"
    assert enrollment["stopReason"] == "active_opportunity"


def test_campaign_pause_resume_stop_and_cross_tenant_access(app: FastAPI, client: TestClient) -> None:
    _enable_execution(app)
    contact_id = _promote_jane(client)
    _configure_policy(client, cooldown_hours=0)
    client.post("/api/v1/integrations/connections", json={"connectorKey": "mock_email"})
    campaign = client.post("/api/v1/engage/campaigns", json=_campaign_request([contact_id])).json()
    client.post(
        f"/api/v1/engage/campaigns/{campaign['id']}/launch",
        json={"expectedVersion": 1, "confirmed": True, "autoSendConfirmed": False},
    )
    paused = client.post(f"/api/v1/engage/campaigns/{campaign['id']}/pause", json={"confirmed": True})
    assert paused.status_code == 200, paused.text
    assert paused.json()["state"] == "paused"
    resumed = client.post(f"/api/v1/engage/campaigns/{campaign['id']}/resume", json={"confirmed": True})
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["state"] == "active"

    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    try:
        assert client.get(f"/api/v1/engage/campaigns/{campaign['id']}").status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    stopped = client.post(f"/api/v1/engage/campaigns/{campaign['id']}/stop", json={"confirmed": True})
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["state"] == "stopped"
    enrollment = client.get(f"/api/v1/engage/campaigns/{campaign['id']}/enrollments").json()["items"][0]
    assert enrollment["state"] == "stopped"
    assert enrollment["stopReason"] == "campaign_stopped"


def test_published_campaign_version_carries_launch_fingerprint(app: FastAPI, client: TestClient) -> None:
    _enable_execution(app)
    contact_id = _promote_jane(client)
    _configure_policy(client, cooldown_hours=0)
    client.post("/api/v1/integrations/connections", json={"connectorKey": "mock_email"})
    campaign = client.post("/api/v1/engage/campaigns", json=_campaign_request([contact_id])).json()
    client.post(
        f"/api/v1/engage/campaigns/{campaign['id']}/launch",
        json={"expectedVersion": 1, "confirmed": True, "autoSendConfirmed": False},
    )

    async def assert_snapshot() -> None:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            version = await session.scalar(
                select(EngageCampaignVersion).where(EngageCampaignVersion.campaign_id == UUID(campaign["id"]))
            )
            assert version is not None
            assert version.status == "published"
            assert version.policy_fingerprint is not None and len(version.policy_fingerprint) == 64
            assert version.launch_fingerprint is not None and len(version.launch_fingerprint) == 64
            assert version.approved_by_user_id is not None
            export = await _export_payload(session, PRIMARY_ORGANISATION_ID, app.state.settings)
            assert export["exportVersion"] == EXPORT_VERSION == 27
            assert len(export["engageCampaigns"]) == 1  # type: ignore[arg-type]
            assert len(export["engageCampaignVersions"]) == 1  # type: ignore[arg-type]
            assert len(export["engageSequenceSteps"]) == 2  # type: ignore[arg-type]
            assert len(export["engageCampaignAudience"]) == 1  # type: ignore[arg-type]
            assert len(export["engageCampaignEnrollments"]) == 1  # type: ignore[arg-type]
            assert len(export["engageEnrollmentSteps"]) == 1  # type: ignore[arg-type]
            assert "worker_id" not in export["engageEnrollmentSteps"][0]  # type: ignore[index]
            assert "launch_fingerprint" not in export["engageCampaignVersions"][0]  # type: ignore[index]
        await engine.dispose()

    asyncio.run(assert_snapshot())


def test_contact_deletion_stops_future_campaign_work_and_preserves_history(app: FastAPI, client: TestClient) -> None:
    _enable_execution(app)
    contact_id = _promote_jane(client)
    _configure_policy(client, cooldown_hours=0)
    client.post("/api/v1/integrations/connections", json={"connectorKey": "mock_email"})
    campaign = client.post("/api/v1/engage/campaigns", json=_campaign_request([contact_id])).json()
    launched = client.post(
        f"/api/v1/engage/campaigns/{campaign['id']}/launch",
        json={"expectedVersion": 1, "confirmed": True, "autoSendConfirmed": False},
    )
    assert launched.status_code == 200, launched.text

    deleted = client.delete(f"/api/v1/contacts/{contact_id}")
    assert deleted.status_code == 204, deleted.text
    enrollment = client.get(f"/api/v1/engage/campaigns/{campaign['id']}/enrollments").json()["items"][0]
    assert enrollment["contactId"] is None
    assert enrollment["recipientName"] == "Jane Smith"
    assert enrollment["state"] == "stopped"
    assert enrollment["stopReason"] == "contact_deleted"
    assert enrollment["steps"][0]["state"] == "cancelled"

    async def assert_audience_reference_removed() -> None:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            audience = await session.scalar(select(EngageCampaignAudience))
            assert audience is not None
            assert audience.contact_id is None
            assert audience.recipient_name == "Jane Smith"
        await engine.dispose()

    asyncio.run(assert_audience_reference_removed())


def test_material_policy_change_halts_active_campaign_immediately(app: FastAPI, client: TestClient) -> None:
    _enable_execution(app)
    contact_id = _promote_jane(client)
    _configure_policy(client, cooldown_hours=0)
    client.post("/api/v1/integrations/connections", json={"connectorKey": "mock_email"})
    campaign = client.post("/api/v1/engage/campaigns", json=_campaign_request([contact_id])).json()
    client.post(
        f"/api/v1/engage/campaigns/{campaign['id']}/launch",
        json={"expectedVersion": 1, "confirmed": True, "autoSendConfirmed": False},
    )

    _configure_policy(client, cooldown_hours=24)
    halted = client.get(f"/api/v1/engage/campaigns/{campaign['id']}")
    assert halted.status_code == 200, halted.text
    assert halted.json()["state"] == "needs_attention"
    assert halted.json()["needsAttentionReason"] == "campaign_policy_changed"
    enrollment = client.get(f"/api/v1/engage/campaigns/{campaign['id']}/enrollments").json()["items"][0]
    assert enrollment["state"] == "needs_attention"
    assert enrollment["steps"][0]["state"] == "blocked"


def test_unknown_delivery_halts_sequence_without_advancing(app: FastAPI, client: TestClient) -> None:
    _enable_execution(app)
    contact_id = _promote_jane(client)
    _configure_policy(client, cooldown_hours=0, campaign_auto_send_allowed=True)
    client.post("/api/v1/integrations/connections", json={"connectorKey": "mock_email"})
    campaign = client.post(
        "/api/v1/engage/campaigns",
        json=_campaign_request([contact_id], approval_mode="approved_campaign_auto_send"),
    ).json()
    launched = client.post(
        f"/api/v1/engage/campaigns/{campaign['id']}/launch",
        json={"expectedVersion": 1, "confirmed": True, "autoSendConfirmed": True},
    )
    assert launched.status_code == 200, launched.text

    _run_campaign_worker(app, times=2)
    _mark_campaign_execution_unknown()
    _run_campaign_worker(app)

    enrollment = client.get(f"/api/v1/engage/campaigns/{campaign['id']}/enrollments").json()["items"][0]
    assert enrollment["state"] == "needs_attention"
    assert enrollment["stopReason"] == "unknown_delivery_state"
    assert enrollment["nextScheduledAt"] is None
    assert enrollment["currentStepOrder"] == 1
    assert len(enrollment["steps"]) == 1
    assert enrollment["steps"][0]["state"] == "unknown_delivery_state"
    halted = client.get(f"/api/v1/engage/campaigns/{campaign['id']}").json()
    assert halted["state"] == "needs_attention"
    assert halted["needsAttentionReason"] == "unknown_delivery_state"


def test_disabling_engage_halts_campaign_and_future_steps(app: FastAPI, client: TestClient) -> None:
    _enable_execution(app)
    contact_id = _promote_jane(client)
    _configure_policy(client, cooldown_hours=0)
    client.post("/api/v1/integrations/connections", json={"connectorKey": "mock_email"})
    campaign = client.post("/api/v1/engage/campaigns", json=_campaign_request([contact_id])).json()
    launched = client.post(
        f"/api/v1/engage/campaigns/{campaign['id']}/launch",
        json={"expectedVersion": 1, "confirmed": True, "autoSendConfirmed": False},
    )
    assert launched.status_code == 200, launched.text

    disabled = client.patch("/api/v1/engage/admin/entitlement", json={"enabled": False})
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["enabled"] is False
    halted = client.get(f"/api/v1/engage/campaigns/{campaign['id']}")
    assert halted.status_code == 200, halted.text
    assert halted.json()["state"] == "needs_attention"
    assert halted.json()["needsAttentionReason"] == "engage_unavailable"
    enrollment = client.get(f"/api/v1/engage/campaigns/{campaign['id']}/enrollments").json()["items"][0]
    assert enrollment["state"] == "needs_attention"
    assert enrollment["steps"][0]["state"] == "blocked"
