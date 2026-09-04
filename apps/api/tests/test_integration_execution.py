from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import AuthenticatedUser, get_current_user
from revenueos.beta_maintenance import _export_payload
from revenueos.config import Settings
from revenueos.integration_executors import (
    ActionExecutorRegistry,
    ApprovedActionInput,
    ExecutorResult,
    MockEmailExecutor,
    RetryableExecutionFailure,
    UnknownExternalStateFailure,
)
from revenueos.integration_worker import ActionExecutionWorkerService
from revenueos.models import (
    ActionExecution,
    ActionProposal,
    ActionProposalVersion,
    MockConnectorObject,
    Opportunity,
    OrganisationMembership,
)

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, TEST_DB_URL, set_test_commercial_plan
from .test_business_api import create_company, create_contact, create_opportunity
from .test_meeting_api import cast_auth_dependency, secondary_user


def _enable_execution(app: FastAPI) -> Settings:
    settings = app.state.settings
    settings.feature_integrations_enabled = True
    settings.feature_action_execution_enabled = True
    settings.feature_mock_connectors_enabled = True
    return settings


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _seed_approved_action(
    *,
    opportunity_id: str,
    action_type: str,
    risk_class: str,
    target_entity_type: str | None,
    target_entity_id: str | None,
    payload: dict[str, object],
    title: str,
    status: Literal["proposed", "approved"] = "approved",
) -> str:
    action_id = uuid.uuid4()
    now = datetime.now(UTC)

    async def seed() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add(
                ActionProposal(
                    id=action_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    opportunity_id=UUID(opportunity_id),
                    interaction_id=None,
                    action_type=action_type,
                    status=status,
                    priority="normal",
                    audience="customer_facing" if risk_class == "external_customer_facing" else "internal",
                    risk_class=risk_class,
                    current_version=1,
                    approved_version=1 if status == "approved" else None,
                    source_fingerprint=_fingerprint(f"source:{action_id}"),
                    semantic_key=_fingerprint(f"semantic:{action_id}"),
                    created_by_user_id=PRIMARY_USER_ID,
                    generated_at=now,
                    reviewed_by_user_id=PRIMARY_USER_ID if status == "approved" else None,
                    reviewed_at=now if status == "approved" else None,
                    approved_at=now if status == "approved" else None,
                )
            )
            session.add(
                ActionProposalVersion(
                    id=uuid.uuid4(),
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    action_id=action_id,
                    version=1,
                    title=title,
                    description="Approved simulation test Action.",
                    proposed_due_at=None,
                    target_entity_type=target_entity_type,
                    target_entity_id=UUID(target_entity_id) if target_entity_id else None,
                    payload_json=payload,
                    source_refs_json=[],
                    provenance_summary="Synthetic test provenance.",
                    content_fingerprint=_fingerprint(f"content:{action_id}"),
                    created_by_user_id=PRIMARY_USER_ID,
                    created_at=now,
                )
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(seed())
    return str(action_id)


def _run_execution_worker(
    app: FastAPI,
    executors: ActionExecutorRegistry | None = None,
) -> None:
    async def run() -> None:
        worker = ActionExecutionWorkerService(
            app.state.session_factory,
            app.state.settings,
            executors=executors,
        )
        await worker.run_once("execution-test-worker")

    asyncio.run(run())


class _FlakyEmailExecutor(MockEmailExecutor):
    def __init__(self) -> None:
        self.calls = 0

    async def execute(
        self,
        action: ApprovedActionInput,
        *,
        idempotency_key: str,
        current_external_state: object | None,
    ) -> ExecutorResult:
        self.calls += 1
        if self.calls == 1:
            raise RetryableExecutionFailure(
                "mock_transient_failure",
                "The simulation connector is temporarily unavailable.",
            )
        return await super().execute(
            action,
            idempotency_key=idempotency_key,
            current_external_state=current_external_state,
        )


class _UnknownEmailExecutor(MockEmailExecutor):
    async def execute(
        self,
        action: ApprovedActionInput,
        *,
        idempotency_key: str,
        current_external_state: object | None,
    ) -> ExecutorResult:
        del action, idempotency_key, current_external_state
        raise UnknownExternalStateFailure(
            "mock_outcome_unknown",
            "The simulation outcome could not be reconciled safely.",
        )


class _UnavailableEmailExecutor(MockEmailExecutor):
    async def execute(
        self,
        action: ApprovedActionInput,
        *,
        idempotency_key: str,
        current_external_state: object | None,
    ) -> ExecutorResult:
        del action, idempotency_key, current_external_state
        raise RetryableExecutionFailure(
            "mock_transient_failure",
            "The simulation connector is temporarily unavailable.",
        )


def test_connection_registry_is_server_authoritative_and_admin_controlled(
    app: FastAPI,
    client: TestClient,
) -> None:
    _enable_execution(app)
    catalog = client.get("/api/v1/integrations")
    assert catalog.status_code == 200, catalog.text
    assert {item["connectorKey"] for item in catalog.json()["connectors"]} == {
        "mock_email",
        "mock_calendar",
        "mock_crm",
        "mock_task",
    }
    assert catalog.json()["executionMode"] == "simulation"
    assert catalog.json()["externalActionsEnabled"] is False

    created = client.post(
        "/api/v1/integrations/connections",
        json={"connectorKey": "mock_email"},
    )
    assert created.status_code == 201, created.text
    connection = created.json()
    assert connection["displayName"] == "Mock Email"
    assert connection["simulationOnly"] is True
    assert connection["capabilityState"] == ["send_email"]
    assert "credential" not in created.text.casefold()

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
    app.dependency_overrides[get_current_user] = lambda: member
    try:
        assert client.get("/api/v1/integrations/connections").status_code == 200
        assert (
            client.post(
                "/api/v1/integrations/connections",
                json={"connectorKey": "mock_task"},
            ).status_code
            == 403
        )
        assert client.delete(f"/api/v1/integrations/connections/{connection['id']}").status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user)

    tested = client.post(f"/api/v1/integrations/connections/{connection['id']}/test")
    assert tested.status_code == 200
    assert tested.json()["safeMessage"] == "Simulation connection verified. No external request was made."


def test_email_preview_confirmation_and_worker_are_explicit_and_idempotent(
    app: FastAPI,
    client: TestClient,
) -> None:
    _enable_execution(app)
    company = create_company(client)
    contact = create_contact(client, str(company["id"]))
    opportunity = create_opportunity(client, str(company["id"]))
    action_id = _seed_approved_action(
        opportunity_id=str(opportunity["id"]),
        action_type="follow_up_email",
        risk_class="external_customer_facing",
        target_entity_type="contact",
        target_entity_id=str(contact["id"]),
        payload={
            "kind": "follow_up_email",
            "draftArtifactId": str(uuid.uuid4()),
            "recipientContactId": str(contact["id"]),
            "recipientEmail": contact["email"],
            "recipientConfirmed": True,
            "subject": "Security documentation",
            "body": "Hello Jordan,\n\nHere is the approved security follow-up.",
        },
        title="Send approved security follow-up",
    )
    connection = client.post(
        "/api/v1/integrations/connections",
        json={"connectorKey": "mock_email"},
    ).json()
    options = client.get(f"/api/v1/actions/{action_id}/execution-options")
    assert options.status_code == 200, options.text
    assert options.json()["items"] == [
        {
            "connectionId": connection["id"],
            "connectorKey": "mock_email",
            "connectorDisplayName": "Mock Email",
            "capability": "send_email",
            "riskClass": "external_customer_facing",
            "executionMode": "simulation",
            "simulationOnly": True,
        }
    ]
    preview = client.post(
        f"/api/v1/actions/{action_id}/execution-preview",
        json={"connectionId": connection["id"]},
    )
    assert preview.status_code == 200, preview.text
    preview_body = preview.json()
    assert preview_body["confirmationLabel"] == "Send email"
    assert preview_body["executionMode"] == "simulation"
    assert preview_body["content"] == {
        "kind": "email",
        "recipient": contact["email"],
        "subject": "Security documentation",
        "body": "Hello Jordan,\n\nHere is the approved security follow-up.",
        "action": "send_email",
    }

    injected = client.post(
        f"/api/v1/actions/{action_id}/execute",
        json={
            "previewId": preview_body["id"],
            "connectionId": connection["id"],
            "confirmed": True,
            "recipient": "attacker@example.test",
        },
    )
    assert injected.status_code == 422
    assert (
        client.post(
            f"/api/v1/actions/{action_id}/execute",
            json={
                "previewId": preview_body["id"],
                "connectionId": connection["id"],
                "confirmed": False,
            },
        ).status_code
        == 422
    )

    confirmed = client.post(
        f"/api/v1/actions/{action_id}/execute",
        json={
            "previewId": preview_body["id"],
            "connectionId": connection["id"],
            "confirmed": True,
        },
    )
    assert confirmed.status_code == 202, confirmed.text
    assert confirmed.json()["executionStatus"] == "queued"
    duplicate = client.post(
        f"/api/v1/actions/{action_id}/execute",
        json={
            "previewId": preview_body["id"],
            "connectionId": connection["id"],
            "confirmed": True,
        },
    )
    assert duplicate.status_code == 202
    assert duplicate.json()["id"] == confirmed.json()["id"]

    _run_execution_worker(app)
    execution = client.get(f"/api/v1/executions/{confirmed.json()['id']}")
    assert execution.status_code == 200, execution.text
    result = execution.json()
    assert result["executionStatus"] == "simulated_success"
    assert result["simulationOnly"] is True
    assert result["externalResultId"].startswith("mock_email_")
    assert result["attempts"][0]["status"] == "simulated_success"

    app.state.settings.private_beta_max_email_executions_per_day = 1
    limited_action_id = _seed_approved_action(
        opportunity_id=str(opportunity["id"]),
        action_type="follow_up_email",
        risk_class="external_customer_facing",
        target_entity_type="contact",
        target_entity_id=str(contact["id"]),
        payload={
            "kind": "follow_up_email",
            "draftArtifactId": str(uuid.uuid4()),
            "recipientContactId": str(contact["id"]),
            "recipientEmail": contact["email"],
            "recipientConfirmed": True,
            "subject": "Second approved follow-up",
            "body": "This simulation should be stopped by the daily guardrail.",
        },
        title="Second approved follow-up",
    )
    limited_preview = client.post(
        f"/api/v1/actions/{limited_action_id}/execution-preview",
        json={"connectionId": connection["id"]},
    ).json()
    limited = client.post(
        f"/api/v1/actions/{limited_action_id}/execute",
        json={
            "previewId": limited_preview["id"],
            "connectionId": connection["id"],
            "confirmed": True,
        },
    )
    assert limited.status_code == 429
    assert limited.json()["code"] == "execution_rate_limit_exceeded"

    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    try:
        assert client.get(f"/api/v1/integrations/connections/{connection['id']}").status_code == 404
        assert client.get(f"/api/v1/executions/{confirmed.json()['id']}").status_code == 404
        assert client.get(f"/api/v1/actions/{action_id}/executions").status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user)

    async def counts() -> tuple[int, int]:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            executions = await session.scalar(select(func.count()).select_from(ActionExecution))
            objects = await session.scalar(select(func.count()).select_from(MockConnectorObject))
        await engine.dispose()
        return int(executions or 0), int(objects or 0)

    assert asyncio.run(counts()) == (1, 1)

    async def exported_metadata() -> dict[str, object]:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            payload = await _export_payload(
                session,
                PRIMARY_ORGANISATION_ID,
                app.state.settings,
            )
        await engine.dispose()
        return payload

    exported = asyncio.run(exported_metadata())
    connections = exported["integrationConnections"]
    executions = exported["actionExecutions"]
    attempts = exported["actionExecutionAttempts"]
    audits = exported["integrationAuditEvents"]
    assert isinstance(connections, list) and len(connections) == 1
    assert isinstance(executions, list) and len(executions) == 1
    assert isinstance(attempts, list) and len(attempts) == 1
    assert isinstance(audits, list) and audits
    exported_text = str(exported)
    assert "credential_reference" not in exported_text
    assert "idempotency_key" not in str(executions)
    assert "preview_fingerprint" not in str(executions)
    assert "mockConnectorObjects" not in exported


def test_worker_fails_closed_when_engage_is_removed_after_confirmation(
    app: FastAPI,
    client: TestClient,
) -> None:
    _enable_execution(app)
    company = create_company(client)
    contact = create_contact(client, str(company["id"]))
    opportunity = create_opportunity(client, str(company["id"]))
    action_id = _seed_approved_action(
        opportunity_id=str(opportunity["id"]),
        action_type="follow_up_email",
        risk_class="external_customer_facing",
        target_entity_type="contact",
        target_entity_id=str(contact["id"]),
        payload={
            "kind": "follow_up_email",
            "draftArtifactId": str(uuid.uuid4()),
            "recipientContactId": str(contact["id"]),
            "recipientEmail": contact["email"],
            "recipientConfirmed": True,
            "subject": "Do not execute after downgrade",
            "body": "This synthetic message must remain unsent.",
        },
        title="Confirm before downgrade",
    )
    connection = client.post(
        "/api/v1/integrations/connections",
        json={"connectorKey": "mock_email"},
    ).json()
    preview = client.post(
        f"/api/v1/actions/{action_id}/execution-preview",
        json={"connectionId": connection["id"]},
    ).json()
    queued = client.post(
        f"/api/v1/actions/{action_id}/execute",
        json={
            "previewId": preview["id"],
            "connectionId": connection["id"],
            "confirmed": True,
        },
    )
    assert queued.status_code == 202, queued.text

    set_test_commercial_plan("core")
    try:
        _run_execution_worker(app)
        result = client.get(f"/api/v1/executions/{queued.json()['id']}")
        assert result.status_code == 200, result.text
        assert result.json()["executionStatus"] == "failed_permanent"
        assert result.json()["safeFailureCode"] == "engage_not_in_plan"
        assert result.json()["externalResultId"] is None
    finally:
        set_test_commercial_plan("complete")


def test_revocation_invalidates_preview_and_crm_stale_state_fails_without_mutation(
    app: FastAPI,
    client: TestClient,
) -> None:
    _enable_execution(app)
    company = create_company(client)
    opportunity = create_opportunity(client, str(company["id"]))
    initial_stage = opportunity["stage"]
    action_id = _seed_approved_action(
        opportunity_id=str(opportunity["id"]),
        action_type="update_opportunity",
        risk_class="data_mutation",
        target_entity_type="opportunity",
        target_entity_id=str(opportunity["id"]),
        payload={
            "kind": "update_opportunity",
            "field": "stage",
            "currentValue": initial_stage,
            "proposedValue": "negotiation",
            "reason": "The customer requested commercial review.",
        },
        title="Update opportunity stage",
    )
    connection = client.post(
        "/api/v1/integrations/connections",
        json={"connectorKey": "mock_crm"},
    ).json()
    preview = client.post(
        f"/api/v1/actions/{action_id}/execution-preview",
        json={"connectionId": connection["id"]},
    ).json()
    confirmed = client.post(
        f"/api/v1/actions/{action_id}/execute",
        json={
            "previewId": preview["id"],
            "connectionId": connection["id"],
            "confirmed": True,
        },
    )
    assert confirmed.status_code == 202, confirmed.text

    async def create_changed_external_state() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            execution = await session.get(ActionExecution, UUID(confirmed.json()["id"]))
            assert execution is not None
            session.add(
                MockConnectorObject(
                    id=uuid.uuid4(),
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    connection_id=UUID(connection["id"]),
                    last_execution_id=execution.id,
                    connector_key="mock_crm",
                    object_type="crm_record_field",
                    object_key=f"opportunity:{opportunity['id']}:stage",
                    last_idempotency_key="0" * 64,
                    external_result_id="mock_existing_state",
                    state_json={"field": "stage", "current_value": "closed_won", "simulation": True},
                )
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(create_changed_external_state())
    _run_execution_worker(app)
    failed = client.get(f"/api/v1/executions/{confirmed.json()['id']}")
    assert failed.status_code == 200
    assert failed.json()["executionStatus"] == "failed_permanent"
    assert failed.json()["safeFailureCode"] == "stale_external_state"

    async def canonical_stage() -> str:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            record = await session.get(Opportunity, UUID(str(opportunity["id"])))
            assert record is not None
            stage = record.stage
        await engine.dispose()
        return stage

    assert asyncio.run(canonical_stage()) == initial_stage

    next_action_id = _seed_approved_action(
        opportunity_id=str(opportunity["id"]),
        action_type="update_opportunity",
        risk_class="data_mutation",
        target_entity_type="opportunity",
        target_entity_id=str(opportunity["id"]),
        payload={
            "kind": "update_opportunity",
            "field": "status",
            "currentValue": "open",
            "proposedValue": "on_hold",
            "reason": "Awaiting executive review.",
        },
        title="Update opportunity status",
    )
    next_preview = client.post(
        f"/api/v1/actions/{next_action_id}/execution-preview",
        json={"connectionId": connection["id"]},
    ).json()
    queued = client.post(
        f"/api/v1/actions/{next_action_id}/execute",
        json={
            "previewId": next_preview["id"],
            "connectionId": connection["id"],
            "confirmed": True,
        },
    )
    assert queued.status_code == 202

    unconfirmed_action_id = _seed_approved_action(
        opportunity_id=str(opportunity["id"]),
        action_type="update_opportunity",
        risk_class="data_mutation",
        target_entity_type="opportunity",
        target_entity_id=str(opportunity["id"]),
        payload={
            "kind": "update_opportunity",
            "field": "expected_close_date",
            "currentValue": opportunity["expectedCloseDate"],
            "proposedValue": "2026-10-15",
            "reason": "The customer requested a revised implementation plan.",
        },
        title="Update opportunity close date",
    )
    unconfirmed_preview = client.post(
        f"/api/v1/actions/{unconfirmed_action_id}/execution-preview",
        json={"connectionId": connection["id"]},
    ).json()
    revoked = client.delete(f"/api/v1/integrations/connections/{connection['id']}")
    assert revoked.status_code == 200
    cancelled = client.get(f"/api/v1/executions/{queued.json()['id']}")
    assert cancelled.status_code == 200
    assert cancelled.json()["executionStatus"] == "cancelled"
    assert cancelled.json()["safeFailureCode"] == "connection_revoked"
    denied = client.post(
        f"/api/v1/actions/{unconfirmed_action_id}/execute",
        json={
            "previewId": unconfirmed_preview["id"],
            "connectionId": connection["id"],
            "confirmed": True,
        },
    )
    assert denied.status_code == 409
    assert denied.json()["code"] == "execution_preview_expired"


def test_preview_rejects_disabled_unapproved_unsupported_and_incomplete_actions(
    app: FastAPI,
    client: TestClient,
) -> None:
    settings = _enable_execution(app)
    settings.feature_integrations_enabled = False
    assert client.get("/api/v1/integrations").status_code == 404
    settings.feature_integrations_enabled = True
    settings.feature_mock_connectors_enabled = False
    assert client.get("/api/v1/integrations").json()["connectors"] == []
    assert client.get("/api/v1/integrations/connections").json()["items"] == []
    settings.feature_mock_connectors_enabled = True

    company = create_company(client)
    contact = create_contact(client, str(company["id"]))
    opportunity = create_opportunity(client, str(company["id"]))
    email_connection = client.post(
        "/api/v1/integrations/connections",
        json={"connectorKey": "mock_email"},
    ).json()
    task_connection = client.post(
        "/api/v1/integrations/connections",
        json={"connectorKey": "mock_task"},
    ).json()

    proposed_id = _seed_approved_action(
        opportunity_id=str(opportunity["id"]),
        action_type="follow_up_email",
        risk_class="external_customer_facing",
        target_entity_type="contact",
        target_entity_id=str(contact["id"]),
        payload={
            "kind": "follow_up_email",
            "draftArtifactId": str(uuid.uuid4()),
            "recipientContactId": str(contact["id"]),
            "recipientEmail": contact["email"],
            "recipientConfirmed": True,
            "subject": "Proposed only",
            "body": "This Action has not been approved.",
        },
        title="Proposed email",
        status="proposed",
    )
    unapproved = client.post(
        f"/api/v1/actions/{proposed_id}/execution-preview",
        json={"connectionId": email_connection["id"]},
    )
    assert unapproved.status_code == 409
    assert unapproved.json()["code"] == "action_not_approved"

    wrong_connection_id = _seed_approved_action(
        opportunity_id=str(opportunity["id"]),
        action_type="follow_up_email",
        risk_class="external_customer_facing",
        target_entity_type="contact",
        target_entity_id=str(contact["id"]),
        payload={
            "kind": "follow_up_email",
            "draftArtifactId": str(uuid.uuid4()),
            "recipientContactId": str(contact["id"]),
            "recipientEmail": contact["email"],
            "recipientConfirmed": True,
            "subject": "Wrong connection",
            "body": "The task connector must not accept this email.",
        },
        title="Wrong connector email",
    )
    wrong_connection = client.post(
        f"/api/v1/actions/{wrong_connection_id}/execution-preview",
        json={"connectionId": task_connection["id"]},
    )
    assert wrong_connection.status_code == 409
    assert wrong_connection.json()["code"] == "capability_unavailable"

    wrong_risk_id = _seed_approved_action(
        opportunity_id=str(opportunity["id"]),
        action_type="follow_up_email",
        risk_class="internal_low_risk",
        target_entity_type="contact",
        target_entity_id=str(contact["id"]),
        payload={
            "kind": "follow_up_email",
            "draftArtifactId": str(uuid.uuid4()),
            "recipientContactId": str(contact["id"]),
            "recipientEmail": contact["email"],
            "recipientConfirmed": True,
            "subject": "Incorrect risk",
            "body": "Customer-facing content cannot use the internal risk class.",
        },
        title="Incorrectly classified email",
    )
    wrong_risk = client.post(
        f"/api/v1/actions/{wrong_risk_id}/execution-preview",
        json={"connectionId": email_connection["id"]},
    )
    assert wrong_risk.status_code == 409
    assert wrong_risk.json()["code"] == "action_risk_mismatch"

    unsupported_id = _seed_approved_action(
        opportunity_id=str(opportunity["id"]),
        action_type="notify_internal",
        risk_class="internal_low_risk",
        target_entity_type=None,
        target_entity_id=None,
        payload={
            "kind": "notify_internal",
            "recipientUserId": None,
            "reason": "Internal review required.",
            "severity": "normal",
        },
        title="Unsupported internal notification",
    )
    unsupported = client.post(
        f"/api/v1/actions/{unsupported_id}/execution-preview",
        json={"connectionId": task_connection["id"]},
    )
    assert unsupported.status_code == 409
    assert unsupported.json()["code"] == "action_not_executable"

    incomplete_email_id = _seed_approved_action(
        opportunity_id=str(opportunity["id"]),
        action_type="follow_up_email",
        risk_class="external_customer_facing",
        target_entity_type="contact",
        target_entity_id=str(contact["id"]),
        payload={
            "kind": "follow_up_email",
            "draftArtifactId": str(uuid.uuid4()),
            "recipientContactId": None,
            "recipientEmail": None,
            "recipientConfirmed": False,
            "subject": "Recipient required",
            "body": "No recipient has been validated.",
        },
        title="Incomplete email",
    )
    incomplete = client.post(
        f"/api/v1/actions/{incomplete_email_id}/execution-preview",
        json={"connectionId": email_connection["id"]},
    )
    assert incomplete.status_code == 409
    assert incomplete.json()["code"] == "recipient_not_confirmed"

    calendar_connection = client.post(
        "/api/v1/integrations/connections",
        json={"connectorKey": "mock_calendar"},
    ).json()
    calendar_id = _seed_approved_action(
        opportunity_id=str(opportunity["id"]),
        action_type="schedule_interaction",
        risk_class="external_customer_facing",
        target_entity_type="opportunity",
        target_entity_id=str(opportunity["id"]),
        payload={
            "kind": "schedule_interaction",
            "interactionType": "online_meeting",
            "timeframe": None,
            "participantContactIds": [str(contact["id"])],
            "purpose": "Review implementation readiness.",
            "objective": "Agree next steps.",
        },
        title="Schedule implementation review",
    )
    incomplete_calendar = client.post(
        f"/api/v1/actions/{calendar_id}/execution-preview",
        json={"connectionId": calendar_connection["id"]},
    )
    assert incomplete_calendar.status_code == 409
    assert incomplete_calendar.json()["code"] == "calendar_time_not_exact"


def test_task_preview_preserves_null_owner_and_due_date_and_simulates_success(
    app: FastAPI,
    client: TestClient,
) -> None:
    _enable_execution(app)
    company = create_company(client)
    opportunity = create_opportunity(client, str(company["id"]))
    action_id = _seed_approved_action(
        opportunity_id=str(opportunity["id"]),
        action_type="create_task",
        risk_class="internal_low_risk",
        target_entity_type="opportunity",
        target_entity_id=str(opportunity["id"]),
        payload={
            "kind": "create_task",
            "title": "Prepare reviewed security pack",
            "ownerName": None,
            "ownerUserId": None,
            "dueAt": "2026-08-20T09:00:00+10:00",
            "context": "The approved Action deliberately leaves ownership unassigned.",
            "linkedOpportunityId": str(opportunity["id"]),
            "linkedInteractionId": None,
        },
        title="Prepare security pack",
    )
    connection = client.post(
        "/api/v1/integrations/connections",
        json={"connectorKey": "mock_task"},
    ).json()
    preview = client.post(
        f"/api/v1/actions/{action_id}/execution-preview",
        json={"connectionId": connection["id"]},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["content"]["ownerUserId"] is None
    assert preview.json()["content"]["dueAt"] == "2026-08-20T09:00:00+10:00"
    execution = client.post(
        f"/api/v1/actions/{action_id}/execute",
        json={
            "previewId": preview.json()["id"],
            "connectionId": connection["id"],
            "confirmed": True,
        },
    )
    assert execution.status_code == 202
    _run_execution_worker(app)
    completed = client.get(f"/api/v1/executions/{execution.json()['id']}").json()
    assert completed["executionStatus"] == "simulated_success"
    assert completed["externalResultId"].startswith("mock_task_")


def test_calendar_preview_preserves_exact_time_participants_and_is_idempotent(
    app: FastAPI,
    client: TestClient,
) -> None:
    _enable_execution(app)
    company = create_company(client)
    contact = create_contact(client, str(company["id"]))
    opportunity = create_opportunity(client, str(company["id"]))
    action_id = _seed_approved_action(
        opportunity_id=str(opportunity["id"]),
        action_type="schedule_interaction",
        risk_class="external_customer_facing",
        target_entity_type="opportunity",
        target_entity_id=str(opportunity["id"]),
        payload={
            "kind": "schedule_interaction",
            "interactionType": "online_meeting",
            "timeframe": "2026-08-21T14:00:00+10:00",
            "participantContactIds": [str(contact["id"])],
            "purpose": "Review implementation readiness.",
            "objective": "Agree next steps.",
        },
        title="Schedule implementation review",
    )
    connection = client.post(
        "/api/v1/integrations/connections",
        json={"connectorKey": "mock_calendar"},
    ).json()
    preview = client.post(
        f"/api/v1/actions/{action_id}/execution-preview",
        json={"connectionId": connection["id"]},
    )
    assert preview.status_code == 200, preview.text
    content = preview.json()["content"]
    assert content["scheduledAt"] == "2026-08-21T14:00:00+10:00"
    assert content["timezone"] == "UTC+10:00"
    assert content["participantContactIds"] == [contact["id"]]
    assert content["participants"] == [
        {
            "contactId": contact["id"],
            "displayName": f"{contact['firstName']} {contact['lastName']}",
            "email": contact["email"],
        }
    ]
    request = {
        "previewId": preview.json()["id"],
        "connectionId": connection["id"],
        "confirmed": True,
    }
    first = client.post(f"/api/v1/actions/{action_id}/execute", json=request)
    duplicate = client.post(f"/api/v1/actions/{action_id}/execute", json=request)
    assert first.status_code == 202, first.text
    assert duplicate.status_code == 202, duplicate.text
    assert duplicate.json()["id"] == first.json()["id"]
    _run_execution_worker(app)
    completed = client.get(f"/api/v1/executions/{first.json()['id']}").json()
    assert completed["executionStatus"] == "simulated_success"
    assert completed["externalResultId"].startswith("mock_event_")


def test_worker_retries_transient_failure_and_never_retries_unknown_state(
    app: FastAPI,
    client: TestClient,
) -> None:
    settings = _enable_execution(app)
    settings.worker_base_retry_delay_seconds = 0
    company = create_company(client)
    contact = create_contact(client, str(company["id"]))
    opportunity = create_opportunity(client, str(company["id"]))
    connection = client.post(
        "/api/v1/integrations/connections",
        json={"connectorKey": "mock_email"},
    ).json()

    def confirm_email(subject: str) -> dict[str, object]:
        action_id = _seed_approved_action(
            opportunity_id=str(opportunity["id"]),
            action_type="follow_up_email",
            risk_class="external_customer_facing",
            target_entity_type="contact",
            target_entity_id=str(contact["id"]),
            payload={
                "kind": "follow_up_email",
                "draftArtifactId": str(uuid.uuid4()),
                "recipientContactId": str(contact["id"]),
                "recipientEmail": contact["email"],
                "recipientConfirmed": True,
                "subject": subject,
                "body": "This is a deterministic simulation.",
            },
            title=subject,
        )
        preview = client.post(
            f"/api/v1/actions/{action_id}/execution-preview",
            json={"connectionId": connection["id"]},
        ).json()
        response = client.post(
            f"/api/v1/actions/{action_id}/execute",
            json={
                "previewId": preview["id"],
                "connectionId": connection["id"],
                "confirmed": True,
            },
        )
        assert response.status_code == 202, response.text
        return response.json()

    retrying = confirm_email("Retry safely")
    flaky = _FlakyEmailExecutor()
    retry_registry = ActionExecutorRegistry((flaky,))
    _run_execution_worker(app, retry_registry)
    first_attempt = client.get(f"/api/v1/executions/{retrying['id']}").json()
    assert first_attempt["executionStatus"] == "failed_retryable"
    assert first_attempt["safeFailureCode"] == "mock_transient_failure"
    assert first_attempt["attemptCount"] == 1
    _run_execution_worker(app, retry_registry)
    retried = client.get(f"/api/v1/executions/{retrying['id']}").json()
    assert retried["executionStatus"] == "simulated_success"
    assert retried["attemptCount"] == 2
    assert [item["status"] for item in retried["attempts"]] == [
        "failed_retryable",
        "simulated_success",
    ]

    unknown = confirm_email("Do not retry unknown state")
    unknown_registry = ActionExecutorRegistry((_UnknownEmailExecutor(),))
    _run_execution_worker(app, unknown_registry)
    unresolved = client.get(f"/api/v1/executions/{unknown['id']}").json()
    assert unresolved["executionStatus"] == "unknown_external_state"
    assert unresolved["safeFailureCode"] == "mock_outcome_unknown"
    assert unresolved["retryable"] is False
    _run_execution_worker(app, unknown_registry)
    unchanged = client.get(f"/api/v1/executions/{unknown['id']}").json()
    assert unchanged["attemptCount"] == 1

    exhausted = confirm_email("Stop at the maximum attempt count")
    unavailable_registry = ActionExecutorRegistry((_UnavailableEmailExecutor(),))
    for _ in range(settings.worker_default_max_attempts + 1):
        _run_execution_worker(app, unavailable_registry)
    stopped = client.get(f"/api/v1/executions/{exhausted['id']}").json()
    assert stopped["executionStatus"] == "failed_permanent"
    assert stopped["attemptCount"] == settings.worker_default_max_attempts
    assert len(stopped["attempts"]) == settings.worker_default_max_attempts

    disabled = confirm_email("Recheck membership immediately before execution")

    async def disable_after_claim() -> tuple[str, int]:
        worker = ActionExecutionWorkerService(
            app.state.session_factory,
            app.state.settings,
        )
        claim = await worker.claim_next(PRIMARY_ORGANISATION_ID, "membership-check-worker")
        assert claim is not None and str(claim.execution_id) == disabled["id"]
        async with app.state.session_factory() as session, session.begin():
            membership = await session.get(
                OrganisationMembership,
                (PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID),
            )
            assert membership is not None
            membership.status = "disabled"
        await worker.execute_claimed(claim)
        async with app.state.session_factory() as session:
            execution = await session.get(ActionExecution, claim.execution_id)
            assert execution is not None
            return execution.execution_status, execution.attempt_count

    assert asyncio.run(disable_after_claim()) == ("failed_permanent", 1)


def test_mock_connectors_are_rejected_in_production_configuration() -> None:
    with pytest.raises(ValidationError, match="Mock connectors are prohibited in production"):
        Settings(
            environment="production",
            auth_mode="clerk",
            mock_auth_enabled=False,
            clerk_jwks_url="https://identity.example.test/jwks",
            clerk_issuer="https://identity.example.test",
            clerk_audience="revenueos",
            database_url="postgresql+asyncpg://example.invalid/revenueos",
            cors_origins="https://app.example.test",
            feature_mock_connectors_enabled=True,
            visual_storage_backend="s3_compatible",
            visual_storage_signing_secret="deployment-specific-signing-secret",
            visual_s3_endpoint="https://storage.example.test",
            visual_s3_bucket="private",
            visual_s3_region="ap-southeast-2",
            visual_s3_access_key_id="placeholder-access-key",
            visual_s3_secret_access_key="placeholder-secret-key",
        )
