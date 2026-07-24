from __future__ import annotations

import asyncio
import logging
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.ai_contracts import (
    NextBestActionArtifactContent,
    NextBestActionSource,
)
from revenueos.ai_executors import ClaimedAIJob, NextBestActionComposer
from revenueos.ai_mock_provider import (
    MOCK_MODEL_IDENTIFIER,
    MOCK_PROVIDER_NAME,
    DeterministicMockAIProvider,
)
from revenueos.ai_next_best_action import (
    build_next_best_action_source,
    output_is_grounded,
)
from revenueos.ai_output_schema_registry import create_default_output_schema_registry
from revenueos.ai_prompt_contracts import PromptVariables
from revenueos.ai_prompt_registry import create_default_prompt_registry
from revenueos.ai_prompt_renderer import render_prompt
from revenueos.ai_provider_contracts import (
    NextBestActionProviderInput,
    ProviderRequest,
    ProviderResponse,
)
from revenueos.ai_provider_registry import AIProviderRegistry
from revenueos.ai_worker_repositories import AIWorkerRepository
from revenueos.ai_worker_services import AIWorkerService
from revenueos.auth import get_current_user
from revenueos.config import Settings
from revenueos.domain import AIJobType
from revenueos.models import AIArtifact, AIJob, MeetingAuditEvent

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


def _claim() -> ClaimedAIJob:
    return ClaimedAIJob(
        organisation_id=PRIMARY_ORGANISATION_ID,
        job_id=uuid.uuid4(),
        meeting_id=uuid.uuid4(),
        transcript_id=uuid.uuid4(),
        transcript_version=1,
        requested_by_user_id=PRIMARY_USER_ID,
        job_type=AIJobType.NEXT_BEST_ACTION.value,
        prompt_key="next_best_action",
        prompt_version=1,
        schema_version=1,
        attempt_count=1,
        max_attempts=3,
        worker_id="next-best-action-test-worker",
    )


def _source() -> NextBestActionSource:
    return build_next_best_action_source(
        executive_summary={
            "executive_summary": "The customer confirmed the pilot scope and implementation approach.",
            "meeting_type": "sales_discovery",
            "sentiment": "positive",
            "confidence": 0.91,
        },
        buying_signals={
            "signals": [
                {
                    "signal_type": "decision_maker_missing",
                    "polarity": "negative",
                    "strength": "moderate",
                    "confidence": 0.94,
                    "evidence": "The decision-maker was absent and no access path was established.",
                }
            ],
            "overall_momentum": "negative",
            "momentum_summary": "Momentum is negative because the decision maker is missing.",
            "confidence": 0.9,
        },
        objections={
            "objections": [],
            "competitors": [],
            "overall_objection_pressure": "none",
            "summary": "No objections or competitive signals were identified in this meeting.",
        },
        stakeholders={
            "stakeholders": [
                {
                    "name": "Jane Smith",
                    "organisation": "Customer",
                    "role": "champion",
                    "influence": "high",
                    "stance": "supportive",
                    "engagement": "active",
                    "confidence": 0.93,
                    "evidence": "Jane advocated for the pilot and offered to present it internally.",
                }
            ],
            "role_coverage": {
                "economic_buyer": "not_identified",
                "decision_maker": "not_identified",
                "champion": "identified",
                "technical_buyer": "not_discussed",
                "procurement": "not_discussed",
                "legal_security": "not_discussed",
            },
            "stakeholder_summary": ("Jane Smith is a likely champion, but the economic buyer was not identified."),
            "confidence": 0.89,
        },
        decisions={
            "decisions": [
                {
                    "decision": "Proceed with the proposed pilot in September.",
                    "owner": "Jane Smith",
                    "status": "confirmed",
                    "confidence": 0.94,
                    "evidence": "The customer agreed to begin the pilot in September.",
                }
            ]
        },
        action_items={
            "action_items": [
                {
                    "task": "Send the revised commercial proposal.",
                    "owner": "Kevin",
                    "due_date": "2026-08-01",
                    "priority": "high",
                    "status": "open",
                    "confidence": 0.94,
                    "evidence": "Kevin committed to send the proposal by 2026-08-01.",
                }
            ]
        },
        open_questions={
            "open_questions": [
                {
                    "question": "Who is the economic buyer for the pilot?",
                    "owner": None,
                    "importance": "high",
                    "confidence": 0.92,
                    "evidence": "No economic buyer was named in the meeting.",
                }
            ]
        },
        risks={
            "risks": [
                {
                    "risk": "Technical validation may delay the pilot.",
                    "category": "technical",
                    "severity": "high",
                    "owner": "Customer IT",
                    "confidence": 0.93,
                    "evidence": "The customer requested technical validation before approval.",
                }
            ]
        },
    )


def _valid_action() -> dict[str, object]:
    return {
        "action": "Identify the economic buyer.",
        "reason": ("Buying Signals: decision_maker_missing. Stakeholders: economic_buyer:not_identified."),
        "priority": "high",
        "confidence": 0.94,
        "depends_on": ["buying_signals", "stakeholders"],
    }


def _valid_result() -> dict[str, object]:
    return {
        "overall_recommendation": "Identify the economic buyer.",
        "priority": "high",
        "confidence": 0.94,
        "reasoning": [
            "Buying Signals: decision_maker_missing.",
            "Stakeholders: economic_buyer:not_identified.",
        ],
        "recommended_actions": [_valid_action()],
    }


def _run_worker_once() -> None:
    async def execute() -> None:
        engine = create_async_engine(TEST_DB_URL)
        service = AIWorkerService(
            async_sessionmaker(engine, expire_on_commit=False),
            _settings(),
        )
        claim = await service.claim_next_job(
            PRIMARY_ORGANISATION_ID,
            "next-best-action-test-worker",
        )
        assert claim is not None
        await service.execute_claimed_job(claim)
        await engine.dispose()

    asyncio.run(execute())


def test_schema_is_strict_bounded_immutable_and_rejects_operational_actions() -> None:
    content = NextBestActionArtifactContent.model_validate(_valid_result())

    assert content.as_json() == _valid_result()
    without_declared_dependency = NextBestActionArtifactContent.model_validate(
        _valid_result()
        | {
            "recommended_actions": [
                {
                    **_valid_action(),
                    "depends_on": [],
                }
            ]
        }
    )
    assert without_declared_dependency.recommended_actions[0].depends_on == ()
    with pytest.raises(ValidationError):
        content.priority = "low"
    for invalid in (
        _valid_result() | {"priority": "urgent"},
        _valid_result() | {"confidence": float("nan")},
        _valid_result() | {"recommended_actions": [_valid_action()] * 6},
        _valid_result()
        | {
            "recommended_actions": [
                {
                    **_valid_action(),
                    "action": "Create a CRM task.",
                }
            ]
        },
        _valid_result() | {"unexpected": True},
    ):
        with pytest.raises(ValidationError):
            NextBestActionArtifactContent.model_validate(invalid)


def test_grounding_requires_exact_validated_values_for_every_dependency() -> None:
    source = _source()
    valid = NextBestActionArtifactContent.model_validate(_valid_result())
    unsupported = NextBestActionArtifactContent.model_validate(
        _valid_result()
        | {
            "recommended_actions": [
                {
                    **_valid_action(),
                    "reason": "The account needs executive attention.",
                }
            ]
        }
    )

    assert output_is_grounded(valid, source) is True
    assert output_is_grounded(unsupported, source) is False
    with pytest.raises(ValidationError):
        build_next_best_action_source(
            **{
                **source.model_dump(mode="json"),
                "risks": {"risks": [{"risk": "Unvalidated"}]},
            }
        )


def test_prompt_and_composer_use_only_the_eight_validated_artefacts() -> None:
    schemas = create_default_output_schema_registry()
    prompt = create_default_prompt_registry(schemas).resolve(
        "next_best_action",
        1,
    )
    rendered = render_prompt(
        prompt,
        PromptVariables(
            values={
                key: "{}"
                for key in (
                    "executive_summary",
                    "buying_signals",
                    "objections",
                    "stakeholders",
                    "decisions",
                    "action_items",
                    "open_questions",
                    "risks",
                )
            }
        ),
    )
    captured: list[ProviderRequest] = []
    delegate = DeterministicMockAIProvider()

    class CapturingProvider:
        provider_name = MOCK_PROVIDER_NAME
        model_identifier = MOCK_MODEL_IDENTIFIER

        async def execute(self, request: ProviderRequest) -> ProviderResponse:
            captured.append(request)
            return await delegate.execute(request)

    async def load_source(job: ClaimedAIJob) -> NextBestActionSource:
        assert job.job_type == "next_best_action"
        return _source()

    result = asyncio.run(
        NextBestActionComposer(
            _settings(),
            AIProviderRegistry({MOCK_PROVIDER_NAME: CapturingProvider()}),
        ).execute(
            _claim(),
            next_best_action_source_loader=load_source,
        )
    )

    assert prompt.output_schema_key == "next_best_action"
    assert schemas.resolve("next_best_action", 1).validation_model is NextBestActionArtifactContent
    assert "transcript" not in rendered.messages[1].content.casefold()
    result_content = NextBestActionArtifactContent.model_validate(result.content)
    assert result_content.recommended_actions[0].model_dump(mode="json") == _valid_action()
    assert len(result_content.recommended_actions) == 3
    assert output_is_grounded(result_content, _source()) is True
    assert len(captured) == 1
    assert isinstance(captured[0].input_payload, NextBestActionProviderInput)
    provider_text = "\n".join(message.content for message in captured[0].input_payload.messages)
    assert "Untrusted transcript" not in provider_text
    assert "raw_text" not in provider_text
    assert "Follow-up Email" not in provider_text


def test_api_requires_all_sources_is_idempotent_and_tenant_isolated(
    client: TestClient,
    app: FastAPI,
) -> None:
    meeting = create_meeting(
        client,
        transcript={
            "rawText": "The customer confirmed the pilot and discussed its stakeholders.",
            "language": "en",
            "source": "manual",
        },
    )
    endpoint = f"/api/v1/meetings/{meeting['id']}/intelligence/next-best-action"

    assert client.get(endpoint).json()["generationAvailable"] is False
    unavailable = client.post(endpoint)
    assert unavailable.status_code == 422
    assert unavailable.json()["code"] == "next_best_action_sources_required"

    assert client.post(f"/api/v1/meetings/{meeting['id']}/intelligence/generate").status_code == 202
    for _ in range(8):
        _run_worker_once()

    first = client.post(endpoint)
    duplicate = client.post(endpoint)
    assert first.status_code == 202
    assert duplicate.status_code == 200
    assert duplicate.json()["jobId"] == first.json()["jobId"]

    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    try:
        assert client.get(endpoint).status_code == 404
        assert client.post(endpoint).status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user)


def test_worker_persists_traceable_metadata_without_reading_or_logging_transcript(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    transcript_marker = "PRIVATE-NEXT-BEST-ACTION-TRANSCRIPT"
    meeting = create_meeting(
        client,
        transcript={
            "rawText": (
                f"{transcript_marker}. The decision-maker was absent. "
                "The customer requested technical validation before approving the pilot."
            ),
            "language": "en-AU",
            "source": "manual",
        },
    )
    base = f"/api/v1/meetings/{meeting['id']}/intelligence"
    assert client.post(f"{base}/generate").status_code == 202
    for _ in range(8):
        _run_worker_once()

    requested = client.post(f"{base}/next-best-action")
    assert requested.status_code == 202

    async def forbid_transcript_source(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("The Next Best Action worker must not load a transcript.")

    monkeypatch.setattr(
        AIWorkerRepository,
        "get_executive_summary_source",
        forbid_transcript_source,
    )
    caplog.set_level(logging.INFO)
    _run_worker_once()

    response = client.get(f"{base}/next-best-action")
    body = response.json()
    assert body["state"] == "completed"
    assert body["nextBestAction"]["recommendedActions"]
    assert len(body["nextBestAction"]["recommendedActions"]) <= 5
    assert transcript_marker not in caplog.text
    assert body["nextBestAction"]["overallRecommendation"] not in caplog.text
    assert "overall_priority" not in caplog.text
    assert '"confidence"' not in caplog.text

    async def verify_traceability() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            job = await session.scalar(select(AIJob).where(AIJob.job_type == "next_best_action"))
            artifact = await session.scalar(select(AIArtifact).where(AIArtifact.artifact_type == "next_best_action"))
            events = list(await session.scalars(select(MeetingAuditEvent)))
            count = await session.scalar(
                select(func.count()).select_from(AIArtifact).where(AIArtifact.artifact_type == "next_best_action")
            )
            assert job is not None
            assert job.status == "completed"
            assert job.prompt_key == "next_best_action"
            assert job.prompt_version == 1
            assert job.schema_version == 1
            assert artifact is not None
            assert artifact.job_id == job.id
            assert count == 1
            assert NextBestActionArtifactContent.model_validate(artifact.content_json)
            audit_metadata = repr([event.metadata_json for event in events])
            assert transcript_marker not in audit_metadata
            assert body["nextBestAction"]["overallRecommendation"] not in audit_metadata
            assert "overall_priority" not in audit_metadata
        await engine.dispose()

    asyncio.run(verify_traceability())
