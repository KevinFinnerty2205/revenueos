from __future__ import annotations

import asyncio
import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.ai_contracts import (
    FollowUpEmailArtifactContent,
    FollowUpEmailSource,
)
from revenueos.ai_executors import (
    ClaimedAIJob,
    FollowUpEmailComposer,
)
from revenueos.ai_mock_provider import (
    MOCK_MODEL_IDENTIFIER,
    MOCK_PROVIDER_NAME,
    DeterministicMockAIProvider,
)
from revenueos.ai_output_schema_registry import create_default_output_schema_registry
from revenueos.ai_prompt_contracts import PromptVariables
from revenueos.ai_prompt_registry import create_default_prompt_registry
from revenueos.ai_prompt_renderer import render_prompt
from revenueos.ai_provider_contracts import (
    FollowUpEmailProviderInput,
    ProviderRequest,
    ProviderResponse,
)
from revenueos.ai_provider_registry import AIProviderRegistry
from revenueos.ai_worker_repositories import AIWorkerRepository
from revenueos.ai_worker_services import AIWorkerService
from revenueos.config import Settings
from revenueos.domain import AIJobType
from revenueos.models import AIArtifact, AIJob, MeetingAuditEvent

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, TEST_DB_URL
from .test_meeting_api import create_meeting


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


def _claim(tone: str = "professional") -> ClaimedAIJob:
    return ClaimedAIJob(
        organisation_id=PRIMARY_ORGANISATION_ID,
        job_id=uuid.uuid4(),
        meeting_id=uuid.uuid4(),
        transcript_id=uuid.uuid4(),
        transcript_version=1,
        requested_by_user_id=PRIMARY_USER_ID,
        job_type=AIJobType.FOLLOW_UP_EMAIL.value,
        prompt_key="follow_up_email",
        prompt_version=1,
        schema_version=1,
        attempt_count=1,
        max_attempts=3,
        worker_id="follow-up-email-test-worker",
        composition_tone=tone,
    )


def _source(tone: str = "professional") -> FollowUpEmailSource:
    return FollowUpEmailSource(
        executive_summary="The customer confirmed the pilot scope and implementation approach.",
        decisions=("Proceed with the pilot (Owner: Customer Team)",),
        action_items=("Send the implementation plan (Owner: Alex; Due: 2026-07-30)",),
        open_questions=("Which security reviewer will approve access?",),
        tone=tone,
    )


def _run_worker_once() -> None:
    async def execute() -> None:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        service = AIWorkerService(session_factory, _settings())
        claim = await service.claim_next_job(
            PRIMARY_ORGANISATION_ID,
            "follow-up-email-test-worker",
        )
        assert claim is not None
        await service.execute_claimed_job(claim)
        await engine.dispose()

    asyncio.run(execute())


def test_follow_up_email_schema_is_strict_immutable_and_supports_empty_sections() -> None:
    valid = {
        "subject": "Meeting follow-up",
        "greeting": "Hello,",
        "summary": "The customer confirmed the pilot scope and implementation approach.",
        "decisions": [],
        "action_items": [],
        "open_questions": [],
        "closing": "Kind regards,",
        "tone": "professional",
        "confidence": 0.95,
    }
    content = FollowUpEmailArtifactContent.model_validate(valid)

    assert content.as_json() == valid
    with pytest.raises(ValidationError):
        content.subject = "Changed"
    for invalid in (
        valid | {"tone": "casual"},
        valid | {"confidence": 1.01},
        valid | {"decisions": [1]},
        valid | {"body": "Unexpected"},
    ):
        with pytest.raises(ValidationError):
            FollowUpEmailArtifactContent.model_validate(invalid)


def test_prompt_uses_exactly_validated_intelligence_and_tone_variables() -> None:
    schemas = create_default_output_schema_registry()
    prompt = create_default_prompt_registry(schemas).resolve("follow_up_email", 1)
    rendered = render_prompt(
        prompt,
        PromptVariables(
            values={
                "executive_summary": '"Validated summary"',
                "decisions": "[]",
                "action_items": "[]",
                "open_questions": "[]",
                "tone": '"professional"',
            }
        ),
    )

    assert prompt.job_type == "follow_up_email"
    assert prompt.output_schema_key == "follow_up_email"
    assert schemas.resolve("follow_up_email", 1).validation_model is FollowUpEmailArtifactContent
    assert "copy the supplied executive summary exactly" in rendered.messages[0].content.lower()
    assert "risks, blockers" in rendered.messages[0].content
    assert "transcript" not in rendered.messages[1].content.lower()


@pytest.mark.parametrize(
    ("tone", "greeting", "closing"),
    (
        ("professional", "Hello,", "Kind regards,"),
        ("friendly", "Hi,", "Thanks,"),
        ("executive", "Hello,", "Regards,"),
    ),
)
def test_composer_mock_supports_three_tones_and_never_builds_a_transcript_request(
    tone: str,
    greeting: str,
    closing: str,
) -> None:
    captured: list[ProviderRequest] = []
    delegate = DeterministicMockAIProvider()

    class CapturingProvider:
        provider_name = MOCK_PROVIDER_NAME
        model_identifier = MOCK_MODEL_IDENTIFIER

        async def execute(self, request: ProviderRequest) -> ProviderResponse:
            captured.append(request)
            return await delegate.execute(request)

    async def load_source(job: ClaimedAIJob) -> FollowUpEmailSource:
        assert job.composition_tone == tone
        return _source(tone)

    composer = FollowUpEmailComposer(
        _settings(),
        AIProviderRegistry({MOCK_PROVIDER_NAME: CapturingProvider()}),
    )
    result = asyncio.run(
        composer.execute(
            _claim(tone),
            follow_up_email_source_loader=load_source,
        )
    )

    assert result.content["tone"] == tone
    assert result.content["greeting"] == greeting
    assert result.content["closing"] == closing
    assert result.content["summary"] == _source(tone).executive_summary
    assert result.content["decisions"] == list(_source(tone).decisions)
    assert len(captured) == 1
    assert isinstance(captured[0].input_payload, FollowUpEmailProviderInput)
    provider_text = "\n".join(message.content for message in captured[0].input_payload.messages)
    assert "Untrusted transcript" not in provider_text
    assert "raw_text" not in provider_text
    assert "risks" not in captured[0].input_payload.messages[1].content.lower()


def test_api_is_unavailable_until_all_required_artefacts_exist(
    client: TestClient,
) -> None:
    meeting = create_meeting(
        client,
        transcript={
            "rawText": "The customer confirmed a pilot discussion.",
            "language": "en",
            "source": "manual",
        },
    )
    endpoint = f"/api/v1/meetings/{meeting['id']}/intelligence/follow-up-email"

    state = client.get(endpoint)
    request = client.post(endpoint, json={})

    assert state.status_code == 200
    assert state.json()["state"] == "empty"
    assert state.json()["generationAvailable"] is False
    assert "Executive Summary" in state.json()["unavailableReason"]
    assert request.status_code == 422
    assert request.json()["code"] == "follow_up_email_sources_required"


def test_api_worker_composes_from_artefacts_regenerates_and_never_reads_transcript(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    transcript_text = (
        "The customer agreed to proceed with the pilot. "
        "Decision: the pilot is approved. "
        "Alex will send the implementation plan by 2026-07-30. "
        "Customer Security owns this question: Which security reviewer will approve access?"
    )
    meeting = create_meeting(
        client,
        title="Pilot follow-up",
        transcript={"rawText": transcript_text, "language": "en-AU", "source": "manual"},
    )
    base = f"/api/v1/meetings/{meeting['id']}/intelligence"
    for source_endpoint in (
        "executive-summary",
        "decisions",
        "action-items",
        "open-questions",
    ):
        assert client.post(f"{base}/{source_endpoint}").status_code == 202
    for _ in range(4):
        _run_worker_once()

    empty = client.get(f"{base}/follow-up-email")
    assert empty.json()["state"] == "empty"
    assert empty.json()["generationAvailable"] is True

    first = client.post(f"{base}/follow-up-email", json={"tone": "friendly"})
    duplicate = client.post(f"{base}/follow-up-email", json={"tone": "friendly"})
    assert first.status_code == 202
    assert first.json()["tone"] == "friendly"
    assert duplicate.status_code == 200
    assert duplicate.json()["jobId"] == first.json()["jobId"]

    async def forbid_transcript_source(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("The Follow-up Email worker must not load a transcript.")

    monkeypatch.setattr(
        AIWorkerRepository,
        "get_executive_summary_source",
        forbid_transcript_source,
    )
    caplog.set_level(logging.INFO)
    _run_worker_once()

    completed = client.get(f"{base}/follow-up-email")
    body = completed.json()
    assert body["state"] == "completed"
    assert body["generationAvailable"] is True
    assert body["tone"] == "friendly"
    assert body["followUpEmail"]["tone"] == "friendly"
    assert body["followUpEmail"]["greeting"] == "Hi,"
    assert body["followUpEmail"]["decisions"]
    assert body["followUpEmail"]["actionItems"]
    assert body["followUpEmail"]["openQuestions"]
    assert "risksBlockers" not in completed.text
    assert transcript_text not in caplog.text

    regenerated = client.post(
        f"{base}/follow-up-email",
        json={"tone": "friendly"},
    )
    assert regenerated.status_code == 202
    assert regenerated.json()["jobId"] != first.json()["jobId"]

    async def verify_traceability() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            composer_jobs = list(
                await session.scalars(
                    select(AIJob).where(AIJob.job_type == "follow_up_email").order_by(AIJob.created_at)
                )
            )
            artifact = await session.scalar(select(AIArtifact).where(AIArtifact.artifact_type == "follow_up_email"))
            events = list(await session.scalars(select(MeetingAuditEvent)))
            assert len(composer_jobs) == 2
            completed_job = composer_jobs[0]
            assert completed_job.status == "completed"
            assert completed_job.composition_tone == "friendly"
            assert completed_job.provider_key == "mock"
            assert completed_job.model_name == MOCK_MODEL_IDENTIFIER
            assert completed_job.prompt_version == 1
            assert completed_job.schema_version == 1
            assert completed_job.attempt_count == 1
            assert completed_job.input_token_count == 0
            assert completed_job.output_token_count == 0
            assert completed_job.estimated_cost_minor_units == 0
            assert completed_job.processing_duration_ms is not None
            assert artifact is not None
            assert artifact.job_id == completed_job.id
            assert artifact.artifact_version == 1
            assert FollowUpEmailArtifactContent.model_validate(artifact.content_json)
            audit_metadata = repr([event.metadata_json for event in events])
            assert transcript_text not in audit_metadata
            assert body["followUpEmail"]["summary"] not in audit_metadata
            assert "follow_up_email" in audit_metadata
        await engine.dispose()

    asyncio.run(verify_traceability())


def test_transcript_correction_makes_prior_intelligence_stale(
    client: TestClient,
) -> None:
    meeting = create_meeting(
        client,
        transcript={
            "rawText": "The customer approved the pilot and Alex will send the plan.",
            "language": "en",
            "source": "manual",
        },
    )
    base = f"/api/v1/meetings/{meeting['id']}/intelligence"
    for endpoint in (
        "executive-summary",
        "decisions",
        "action-items",
        "open-questions",
    ):
        assert client.post(f"{base}/{endpoint}").status_code == 202
    for _ in range(4):
        _run_worker_once()

    assert client.get(f"{base}/follow-up-email").json()["generationAvailable"] is True
    corrected = client.patch(
        f"/api/v1/meetings/{meeting['id']}/transcript",
        json={
            "rawText": "Corrected transcript content.",
            "language": "en-AU",
            "version": 1,
        },
    )
    assert corrected.status_code == 200
    assert corrected.json()["version"] == 2

    stale_state = client.get(f"{base}/follow-up-email")
    stale_request = client.post(
        f"{base}/follow-up-email",
        json={"tone": "professional"},
    )
    assert stale_state.status_code == 200
    assert stale_state.json()["state"] == "empty"
    assert stale_state.json()["generationAvailable"] is False
    assert "before drafting" in stale_state.json()["unavailableReason"]
    assert stale_request.status_code == 422
    assert stale_request.json()["code"] == "follow_up_email_sources_required"


def test_partial_intelligence_preserves_empty_sections(client: TestClient) -> None:
    meeting = create_meeting(
        client,
        transcript={
            "rawText": "The customer discussed the implementation approach and no commitments were made.",
            "language": "en",
            "source": "manual",
        },
    )
    base = f"/api/v1/meetings/{meeting['id']}/intelligence"
    for endpoint in (
        "executive-summary",
        "decisions",
        "action-items",
        "open-questions",
    ):
        assert client.post(f"{base}/{endpoint}").status_code == 202
    for _ in range(4):
        _run_worker_once()

    assert client.post(f"{base}/follow-up-email", json={"tone": "executive"}).status_code == 202
    _run_worker_once()
    content = client.get(f"{base}/follow-up-email").json()["followUpEmail"]
    assert content["tone"] == "executive"
    assert content["decisions"] == []
    assert content["actionItems"] == []
    assert content["openQuestions"] == []

    async def count_artifacts() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            count = await session.scalar(
                select(func.count()).select_from(AIArtifact).where(AIArtifact.artifact_type == "follow_up_email")
            )
            assert count == 1
        await engine.dispose()

    asyncio.run(count_artifacts())
