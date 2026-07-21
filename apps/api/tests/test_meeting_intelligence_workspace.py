from __future__ import annotations

import asyncio
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.ai_mock_provider import MOCK_MODEL_IDENTIFIER, MOCK_PROVIDER_NAME
from revenueos.ai_worker_services import AIWorkerService
from revenueos.auth import get_current_user
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.intelligence_workspace import MeetingIntelligenceService
from revenueos.main import create_app
from revenueos.models import AIJob
from revenueos.tenant import TenantContext

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, TEST_DB_URL
from .test_meeting_api import (
    cast_auth_dependency,
    create_meeting,
    secondary_user,
)


def _settings() -> Settings:
    return Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url=TEST_DB_URL,
        ai_provider_name=MOCK_PROVIDER_NAME,
        ai_provider_model_identifier=MOCK_MODEL_IDENTIFIER,
        worker_heartbeat_interval_seconds=1,
        worker_lease_duration_seconds=10,
    )


def _run_worker_once() -> None:
    async def execute() -> None:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        service = AIWorkerService(session_factory, _settings())
        claim = await service.claim_next_job(
            PRIMARY_ORGANISATION_ID,
            "meeting-intelligence-test-worker",
        )
        assert claim is not None
        await service.execute_claimed_job(claim)
        await engine.dispose()

    asyncio.run(execute())


def _count_jobs() -> int:
    async def count() -> int:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            value = await session.scalar(select(func.count()).select_from(AIJob))
        await engine.dispose()
        return int(value or 0)

    return asyncio.run(count())


@pytest.mark.parametrize(
    (
        "transcript_usable",
        "ready",
        "queued",
        "processing",
        "failed",
        "empty_result",
        "expected",
    ),
    (
        (False, 0, 0, 0, 0, False, "unavailable"),
        (True, 0, 0, 0, 0, False, "not_started"),
        (True, 2, 0, 0, 0, False, "partially_generated"),
        (True, 0, 2, 0, 0, False, "queued"),
        (True, 1, 1, 1, 1, False, "processing"),
        (True, 2, 0, 0, 1, False, "partially_failed"),
        (True, 0, 0, 0, 1, False, "failed"),
        (True, 7, 0, 0, 0, False, "completed"),
        (True, 7, 0, 0, 0, True, "completed_with_empty_results"),
    ),
)
def test_overall_state_precedence_is_deterministic(
    transcript_usable: bool,
    ready: int,
    queued: int,
    processing: int,
    failed: int,
    empty_result: bool,
    expected: str,
) -> None:
    assert (
        MeetingIntelligenceService._overall_state(
            transcript_usable=transcript_usable,
            ready=ready,
            queued=queued,
            processing=processing,
            failed=failed,
            any_empty_result=empty_result,
        )
        == expected
    )


def test_aggregate_read_is_product_safe_and_unavailable_without_transcript(
    client: TestClient,
) -> None:
    meeting = create_meeting(client)
    endpoint = f"/api/v1/meetings/{meeting['id']}/intelligence"

    response = client.get(endpoint)

    assert response.status_code == 200
    body = response.json()
    assert body["overallState"] == "unavailable"
    assert body["generationAvailable"] is False
    assert body["progress"] == {
        "ready": 0,
        "queued": 0,
        "processing": 0,
        "failed": 0,
        "notGenerated": 7,
        "total": 7,
        "summary": "0 of 7 ready",
    }
    assert body["executiveSummary"]["state"] == "unavailable"
    assert body["buyingSignals"]["state"] == "unavailable"
    assert body["followUpEmail"]["state"] == "unavailable"
    for internal_field in (
        "jobId",
        "artifactId",
        "provider",
        "model",
        "promptVersion",
        "schemaVersion",
        "rawText",
        "lastErrorCode",
        "lease",
    ):
        assert internal_field not in response.text
    assert client.get("/api/v1/meetings/00000000-0000-4000-8000-000000000099/intelligence").status_code == 404


def test_aggregate_read_remains_bounded_to_four_queries(client: TestClient) -> None:
    meeting = create_meeting(
        client,
        transcript={
            "rawText": "The customer confirmed the pilot budget and next meeting.",
            "language": "en",
            "source": "manual",
        },
    )
    assert client.post(f"/api/v1/meetings/{meeting['id']}/intelligence/generate").status_code == 202

    async def read_workspace() -> tuple[int, int]:
        engine = create_async_engine(TEST_DB_URL)
        select_statements: list[str] = []

        def record_statement(
            connection: object,
            cursor: object,
            statement: str,
            parameters: object,
            context: object,
            executemany: bool,
        ) -> None:
            del connection, cursor, parameters, context, executemany
            if statement.lstrip().upper().startswith("SELECT"):
                select_statements.append(statement)

        event.listen(engine.sync_engine, "before_cursor_execute", record_statement)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                response = await MeetingIntelligenceService(
                    session,
                    TenantContext(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=PRIMARY_USER_ID,
                        role="admin",
                    ),
                ).get_workspace(uuid.UUID(meeting["id"]))
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", record_statement)
            await engine.dispose()
        return len(select_statements), response.progress.total

    query_count, total = asyncio.run(read_workspace())
    assert query_count == 4
    assert total == 7


def test_aggregate_read_emits_metadata_only_polling_and_transition_telemetry(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    transcript_marker = "PRIVATE-TRANSCRIPT-MARKER"
    meeting = create_meeting(
        client,
        transcript={
            "rawText": transcript_marker,
            "language": "en",
            "source": "manual",
        },
    )
    endpoint = f"/api/v1/meetings/{meeting['id']}/intelligence"

    with caplog.at_level(logging.INFO, logger="revenueos.intelligence_workspace"):
        response = client.get(
            endpoint,
            params={
                "previousOverallState": "queued",
                "pollingEvent": "started",
            },
        )

    assert response.status_code == 200
    assert response.json()["overallState"] == "not_started"
    messages = {record.message for record in caplog.records}
    assert "meeting_intelligence_capability_state_count" in messages
    assert "meeting_intelligence_overall_state_transition" in messages
    assert "unified_intelligence_polling_started" in messages
    assert "unified_intelligence_polling_stopped" in messages
    assert transcript_marker not in caplog.text


def test_aggregate_read_rejects_unauthenticated_requests() -> None:
    app = create_app(
        Settings(
            environment="test",
            auth_mode="clerk",
            mock_auth_enabled=False,
            database_url=TEST_DB_URL,
            clerk_jwks_url="https://clerk.example.test/.well-known/jwks.json",
            clerk_issuer="https://clerk.example.test",
            clerk_audience="revenueos-api",
            log_level="WARNING",
        )
    )

    with TestClient(app) as unauthenticated:
        response = unauthenticated.get("/api/v1/meetings/00000000-0000-4000-8000-000000000099/intelligence")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_generation_orchestrates_missing_work_and_composer_dependencies(
    client: TestClient,
) -> None:
    meeting = create_meeting(
        client,
        title="Pilot readiness review",
        transcript={
            "rawText": (
                "The customer confirmed the pilot scope and approved the implementation plan. "
                "Alex will send the plan by 2026-07-30. The security reviewer is still unknown."
            ),
            "language": "en-AU",
            "source": "manual",
        },
    )
    base = f"/api/v1/meetings/{meeting['id']}/intelligence"

    first = client.post(f"{base}/generate")
    assert first.status_code == 202, first.text
    assert first.json()["createdCapabilities"] == [
        "executive_summary",
        "buying_signals",
        "decisions",
        "action_items",
        "risks_blockers",
        "open_questions",
    ]
    assert first.json()["followUpEmail"]["state"] == "unavailable"
    assert _count_jobs() == 6

    repeated = client.post(f"{base}/generate")
    assert repeated.status_code == 200
    assert repeated.json()["createdCapabilities"] == []
    assert len(repeated.json()["reusedCapabilities"]) == 6
    assert _count_jobs() == 6

    for _ in range(6):
        _run_worker_once()
    prerequisites_ready = client.get(base)
    assert prerequisites_ready.json()["overallState"] == "partially_generated"
    assert prerequisites_ready.json()["progress"]["ready"] == 6
    assert prerequisites_ready.json()["followUpEmail"]["state"] == "not_generated"

    composer = client.post(f"{base}/generate")
    assert composer.status_code == 202
    assert composer.json()["createdCapabilities"] == ["follow_up_email"]
    assert composer.json()["followUpEmail"]["state"] == "queued"
    assert _count_jobs() == 7

    _run_worker_once()
    completed = client.get(base)
    body = completed.json()
    assert body["overallState"] in {"completed", "completed_with_empty_results"}
    assert body["progress"]["ready"] == 7
    assert body["buyingSignals"]["state"] == "completed"
    assert body["followUpEmail"]["content"]["summary"] == body["executiveSummary"]["content"]["executiveSummary"]
    assert "risksBlockers" not in body["followUpEmail"]["content"]
    assert "rawText" not in completed.text

    final_repeat = client.post(f"{base}/generate")
    assert final_repeat.status_code == 200
    assert final_repeat.json()["createdCapabilities"] == []
    assert _count_jobs() == 7


def test_concurrent_generate_requests_do_not_duplicate_equivalent_jobs(
    client: TestClient,
) -> None:
    meeting = create_meeting(
        client,
        transcript={
            "rawText": "The customer confirmed the requirements and next steps for the pilot.",
            "language": "en",
            "source": "manual",
        },
    )
    endpoint = f"/api/v1/meetings/{meeting['id']}/intelligence/generate"

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: client.post(endpoint), range(2)))

    assert {response.status_code for response in responses} <= {200, 202}
    assert _count_jobs() == 6

    for _ in range(6):
        _run_worker_once()
    with ThreadPoolExecutor(max_workers=2) as executor:
        composer_responses = list(executor.map(lambda _: client.post(endpoint), range(2)))

    assert {response.status_code for response in composer_responses} <= {200, 202}
    assert _count_jobs() == 7


def test_transcript_version_change_queues_new_extraction_jobs(client: TestClient) -> None:
    meeting = create_meeting(
        client,
        transcript={
            "rawText": "The customer discussed the first pilot scope and delivery plan.",
            "language": "en",
            "source": "manual",
        },
    )
    base = f"/api/v1/meetings/{meeting['id']}"
    assert client.post(f"{base}/intelligence/generate").status_code == 202
    assert _count_jobs() == 6

    update = client.patch(
        f"{base}/transcript",
        json={
            "rawText": "The updated pilot scope includes security review and a new delivery date.",
            "version": 1,
        },
    )
    assert update.status_code == 200
    second = client.post(f"{base}/intelligence/generate")
    assert second.status_code == 202
    assert len(second.json()["createdCapabilities"]) == 6
    assert _count_jobs() == 12


def test_cancelled_capability_is_not_ready_and_uses_failure_precedence(
    client: TestClient,
) -> None:
    meeting = create_meeting(
        client,
        transcript={
            "rawText": "The customer discussed a pilot requirement and next steps.",
            "language": "en",
            "source": "manual",
        },
    )
    base = f"/api/v1/meetings/{meeting['id']}/intelligence"
    assert client.post(f"{base}/generate").status_code == 202

    async def cancel_one() -> None:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            job = await session.scalar(select(AIJob).where(AIJob.job_type == "risks_blockers"))
            assert job is not None
            job.status = "cancelled"
            job.cancelled_at = datetime.now(UTC)
            await session.commit()
        await engine.dispose()

    asyncio.run(cancel_one())
    response = client.get(base)

    assert response.json()["risksBlockers"]["state"] == "cancelled"
    assert response.json()["progress"]["ready"] == 0
    assert response.json()["progress"]["failed"] == 1
    assert response.json()["overallState"] == "failed"

    retry = client.post(f"{base}/generate")
    assert retry.status_code == 202
    assert retry.json()["createdCapabilities"] == ["risks_blockers"]
    assert _count_jobs() == 7


def test_valid_empty_sections_count_as_ready_and_complete_with_empty_results(
    client: TestClient,
) -> None:
    meeting = create_meeting(
        client,
        title="General catch-up",
        transcript={
            "rawText": "The participants discussed the weather and ended the call.",
            "language": "en",
            "source": "manual",
        },
    )
    base = f"/api/v1/meetings/{meeting['id']}/intelligence"
    assert client.post(f"{base}/generate").status_code == 202
    for _ in range(6):
        _run_worker_once()
    assert client.post(f"{base}/generate").status_code == 202
    _run_worker_once()

    response = client.get(base)
    body = response.json()
    assert body["overallState"] == "completed_with_empty_results"
    assert body["progress"]["ready"] == 7
    assert body["decisions"]["emptyResult"] is True
    assert body["actionItems"]["emptyResult"] is True
    assert body["risksBlockers"]["emptyResult"] is True
    assert body["openQuestions"]["emptyResult"] is True
    assert body["buyingSignals"]["emptyResult"] is True


def test_aggregate_and_generation_are_tenant_scoped(
    app: FastAPI,
    client: TestClient,
) -> None:
    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    foreign = create_meeting(
        client,
        transcript={
            "rawText": "Foreign tenant confidential meeting transcript.",
            "language": "en",
            "source": "manual",
        },
    )
    app.dependency_overrides.pop(get_current_user)
    base = f"/api/v1/meetings/{foreign['id']}/intelligence"

    assert client.get(base).status_code == 404
    assert client.post(f"{base}/generate").status_code == 404
