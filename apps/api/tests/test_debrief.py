from __future__ import annotations

import asyncio
import base64

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.ai_mock_provider import DeterministicMockAIProvider
from revenueos.ai_output_schema_registry import (
    AI_DEBRIEF_EVIDENCE_SCHEMA_KEY,
    AI_DEBRIEF_QUESTION_SCHEMA_KEY,
    create_default_output_schema_registry,
)
from revenueos.ai_prompt_registry import (
    AI_DEBRIEF_EVIDENCE_PROMPT_KEY,
    AI_DEBRIEF_QUESTION_PROMPT_KEY,
    create_default_prompt_registry,
)
from revenueos.auth import get_current_user
from revenueos.config import Settings
from revenueos.debrief_ai import StructuredDebriefReasoning
from revenueos.debrief_reasoning import DeterministicDebriefReasoning
from revenueos.main import create_app
from revenueos.models import (
    BetaSystemEvent,
    CandidateEvidence,
    DebriefSession,
    DebriefTurn,
    Evidence,
    EvidenceFragment,
    InteractionIntelligenceSnapshot,
    RevenueBrainInteractionSnapshot,
)

from .conftest import PRIMARY_ORGANISATION_ID, TEST_DB_URL
from .test_business_api import create_company, create_opportunity
from .test_interaction_api import create_interaction
from .test_meeting_api import cast_auth_dependency, secondary_user


def test_recording_gap_fill_suppresses_supported_questions_and_prioritises_markers() -> None:
    reasoning = DeterministicDebriefReasoning()
    opening = reasoning.opening_question(gap_fill=True)
    assert opening.question == "What important outcome might the recording have missed?"
    question = reasoning.next_question(
        interaction_type="face_to_face_meeting",
        capture_type="ai_debrief",
        answers=("The recording covered the discussion, but one detail may be missing.",),
        asked_targets=("other",),
        question_count=1,
        max_questions=6,
        brief_questions=(),
        direct_supported_targets=("next_step", "stakeholder", "decision", "timeline", "commercial_intent"),
        marker_targets=("objection",),
    )
    assert question.target == "objection"
    assert question.question == "Did the customer raise or resolve an important concern?"


def _completed_interaction(
    client: TestClient,
    *,
    interaction_type: str = "phone_call",
) -> tuple[str, str]:
    company_id = str(create_company(client, name=f"{interaction_type} debrief account")["id"])
    opportunity_id = str(create_opportunity(client, company_id, name=f"{interaction_type} debrief opportunity")["id"])
    interaction = create_interaction(
        client,
        title=f"Completed {interaction_type}",
        interaction_type=interaction_type,
        company_id=company_id,
        opportunity_id=opportunity_id,
    )
    interaction_id = str(interaction["id"])
    completed = client.post(f"/api/v1/interactions/{interaction_id}/complete", json={})
    assert completed.status_code == 200, completed.text
    return interaction_id, opportunity_id


def _start(
    client: TestClient,
    interaction_id: str,
    *,
    capture_type: str = "ai_debrief",
    acknowledged: bool = False,
    key: str = "start-1",
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/interactions/{interaction_id}/debrief",
        json={
            "captureType": capture_type,
            "safetyConfirmed": True,
            "voiceProcessingAcknowledged": acknowledged,
            "idempotencyKey": key,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_ai_debrief_is_bounded_idempotent_reviewed_and_source_aware(client: TestClient) -> None:
    interaction_id, opportunity_id = _completed_interaction(client)
    started = _start(client, interaction_id)
    session_id = str(started["id"])
    assert started["lifecycleStatus"] == "collecting"
    assert started["currentQuestion"]["question"] == "How did it go?"  # type: ignore[index]
    assert started["turns"] == []

    repeated_start = _start(client, interaction_id)
    assert repeated_start["id"] == session_id

    answer_text = (
        "Jordan joined as the economic buyer. The budget is approved and they want to move forward. "
        "I will send the proposal tomorrow."
    )
    response_url = f"/api/v1/interactions/{interaction_id}/debrief/{session_id}/response"
    answered = client.post(
        response_url,
        json={"answerText": answer_text, "idempotencyKey": "answer-1"},
    )
    assert answered.status_code == 200, answered.text
    assert len(answered.json()["turns"]) == 1
    assert answered.json()["canFinish"] is True
    assert answered.json()["questionCount"] <= answered.json()["maxQuestions"]
    assert answered.json()["currentQuestion"]["target"] == "timeline"

    repeated_answer = client.post(
        response_url,
        json={"answerText": "This replacement must be ignored.", "idempotencyKey": "answer-1"},
    )
    assert repeated_answer.status_code == 200
    assert [turn["answerText"] for turn in repeated_answer.json()["turns"]] == [answer_text]

    restored = client.get(f"/api/v1/interactions/{interaction_id}/debrief/{session_id}")
    assert restored.status_code == 200
    assert restored.json()["turns"][0]["answerText"] == answer_text

    finished = client.post(
        f"/api/v1/interactions/{interaction_id}/debrief/{session_id}/finish",
        json={"idempotencyKey": "finish-1", "finishEarly": True},
    )
    assert finished.status_code == 200, finished.text
    candidates = finished.json()["candidates"]
    assert finished.json()["lifecycleStatus"] == "review"
    assert candidates
    assert {candidate["origin"] for candidate in candidates} == {"salesperson_reported"}
    assert {candidate["supportClassification"] for candidate in candidates} == {"reported"}
    assert {candidate["validationState"] for candidate in candidates} == {"unreviewed"}
    assert all(candidate["sourceLabel"] == "Reported by you" for candidate in candidates)

    decisions = []
    for index, candidate in enumerate(candidates):
        decisions.append(
            {
                "candidateId": candidate["id"],
                "decision": "accept" if index == 0 else "reject",
                **({"statement": "Jordan is the confirmed economic buyer."} if index == 0 else {}),
            }
        )
    reviewed = client.post(
        f"/api/v1/interactions/{interaction_id}/debrief/{session_id}/review",
        json={"decisions": decisions, "idempotencyKey": "review-1"},
    )
    assert reviewed.status_code == 200, reviewed.text
    body = reviewed.json()
    assert body["lifecycleStatus"] == "completed"
    assert body["acceptedCount"] == 1
    assert body["rejectedCount"] == len(candidates) - 1
    assert body["interactionUpdated"] is True
    assert body["revenueBrainUpdated"] is True
    assert body["interactionIntelligenceId"] is not None
    assert body["revenueBrainSnapshotId"] is not None
    accepted = next(candidate for candidate in body["candidates"] if candidate["userReviewState"] == "accepted")
    assert accepted["statement"] == "Jordan is the confirmed economic buyer."
    assert accepted["edited"] is True
    assert accepted["validationState"] == "verified"
    assert accepted["acceptedEvidenceId"] is not None

    repeated_review = client.post(
        f"/api/v1/interactions/{interaction_id}/debrief/{session_id}/review",
        json={"decisions": decisions, "idempotencyKey": "review-2"},
    )
    assert repeated_review.status_code == 200
    assert repeated_review.json()["interactionIntelligenceId"] == body["interactionIntelligenceId"]

    workspace = client.get(f"/api/v1/opportunities/{opportunity_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    reported = workspace.json()["reportedIntelligence"]
    assert reported["sourceLabel"] == "Reported by you"
    assert reported["items"][0]["statement"] == "Jordan is the confirmed economic buyer."
    assert reported["items"][0]["validationState"] == "verified"
    assert "probability" not in workspace.text.lower()

    async def verify_persistence() -> tuple[int, int, int, int, list[dict[str, object]]]:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            counts = []
            for model in (
                DebriefSession,
                DebriefTurn,
                EvidenceFragment,
                InteractionIntelligenceSnapshot,
            ):
                counts.append(
                    int(
                        await session.scalar(
                            select(func.count())
                            .select_from(model)
                            .where(model.organisation_id == PRIMARY_ORGANISATION_ID)
                        )
                        or 0
                    )
                )
            events = list(
                await session.scalars(
                    select(BetaSystemEvent).where(BetaSystemEvent.organisation_id == PRIMARY_ORGANISATION_ID)
                )
            )
            metadata = [event.metadata_json for event in events]
        await engine.dispose()
        return counts[0], counts[1], counts[2], counts[3], metadata

    session_count, turn_count, fragment_count, snapshot_count, event_metadata = asyncio.run(verify_persistence())
    assert (session_count, turn_count, fragment_count, snapshot_count) == (1, 1, 1, 1)
    assert all(answer_text not in str(metadata) for metadata in event_metadata)
    assert not {"audio", "audio_bytes", "audio_blob", "recording"} & set(DebriefTurn.__table__.columns)
    assert not {"audio", "audio_bytes", "audio_blob", "recording"} & set(EvidenceFragment.__table__.columns)


def test_presentation_debrief_prioritises_customer_reaction_and_filters_seller_deck_claims(
    client: TestClient,
) -> None:
    interaction_id, _ = _completed_interaction(client, interaction_type="presentation")
    started = _start(client, interaction_id, key="presentation-start")
    session_id = str(started["id"])
    answered = client.post(
        f"/api/v1/interactions/{interaction_id}/debrief/{session_id}/response",
        json={
            "answerText": (
                "Our deck says the customer will purchase this quarter. "
                "The customer asked for a security workshop and challenged the rollout plan."
            ),
            "idempotencyKey": "presentation-answer",
        },
    )
    assert answered.status_code == 200, answered.text
    question = answered.json()["currentQuestion"]
    assert question["target"] in {
        "other",
        "open_question",
        "objection",
        "action_item",
        "decision",
        "commitment",
    }

    finished = client.post(
        f"/api/v1/interactions/{interaction_id}/debrief/{session_id}/finish",
        json={"idempotencyKey": "presentation-finish", "finishEarly": True},
    )
    assert finished.status_code == 200, finished.text
    statements = [item["statement"].casefold() for item in finished.json()["candidates"]]
    assert statements
    assert not any("our deck says" in statement for statement in statements)
    assert any("customer asked" in statement or "challenged" in statement for statement in statements)


def test_voice_journal_uses_ephemeral_audio_and_has_typed_fallbacks(client: TestClient) -> None:
    interaction_id, _ = _completed_interaction(client, interaction_type="conference_interaction")
    without_ack = _start(client, interaction_id, capture_type="voice_journal", key="voice-no-ack")
    voice_url = f"/api/v1/interactions/{interaction_id}/debrief/{without_ack['id']}/voice-response"
    rejected = client.post(
        voice_url,
        json={
            "audioBase64": base64.b64encode(b"MOCK_TRANSCRIPT:Met Priya, the procurement owner.").decode(),
            "mimeType": "audio/webm;codecs=opus",
            "durationSeconds": 4,
            "idempotencyKey": "voice-1",
        },
    )
    assert rejected.status_code == 428
    assert rejected.json()["code"] == "voice_processing_acknowledgement_required"

    second_interaction_id, _ = _completed_interaction(client, interaction_type="trade_show_interaction")
    started = _start(
        client,
        second_interaction_id,
        capture_type="voice_journal",
        acknowledged=True,
        key="voice-start",
    )
    session_id = str(started["id"])
    assert started["maxQuestions"] == 2
    voice_url = f"/api/v1/interactions/{second_interaction_id}/debrief/{session_id}/voice-response"
    transcript = "Met Priya, the procurement owner. She requested a security document."
    submitted = client.post(
        voice_url,
        json={
            "audioBase64": base64.b64encode(f"MOCK_TRANSCRIPT:{transcript}".encode()).decode(),
            "mimeType": "audio/webm;codecs=opus",
            "durationSeconds": 7,
            "language": "en-AU",
            "idempotencyKey": "voice-2",
        },
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["turns"][0]["answerText"] == transcript
    assert submitted.json()["turns"][0]["inputMode"] == "voice"

    unsupported = client.post(
        voice_url,
        json={
            "audioBase64": base64.b64encode(b"not-stored").decode(),
            "mimeType": "audio/wav",
            "durationSeconds": 2,
            "idempotencyKey": "voice-unsupported",
        },
    )
    assert unsupported.status_code == 422
    typed = client.post(
        f"/api/v1/interactions/{second_interaction_id}/debrief/{session_id}/response",
        json={"answerText": "Nothing else.", "idempotencyKey": "typed-fallback"},
    )
    assert typed.status_code == 200
    assert typed.json()["currentQuestion"]["status"] == "complete"


def test_debrief_structured_output_types_are_versioned_allowlisted_and_retryable() -> None:
    schemas = create_default_output_schema_registry()
    prompts = create_default_prompt_registry(schemas)
    assert schemas.resolve(AI_DEBRIEF_QUESTION_SCHEMA_KEY, 1).job_type == "ai_debrief_question"
    assert schemas.resolve(AI_DEBRIEF_EVIDENCE_SCHEMA_KEY, 1).job_type == "ai_debrief_evidence"
    assert prompts.resolve(AI_DEBRIEF_QUESTION_PROMPT_KEY, 1).job_type == "ai_debrief_question"
    assert prompts.resolve(AI_DEBRIEF_EVIDENCE_PROMPT_KEY, 1).job_type == "ai_debrief_evidence"

    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=TEST_DB_URL,
        ai_structured_output_max_attempts=2,
    )
    reasoning = StructuredDebriefReasoning(
        settings,
        PRIMARY_ORGANISATION_ID,
        DeterministicMockAIProvider(output_sequence=("schema_invalid", "valid_mapping")),
    )
    result = asyncio.run(
        reasoning.next_question(
            request_id=PRIMARY_ORGANISATION_ID,
            session_id=PRIMARY_ORGANISATION_ID,
            interaction_type="presentation",
            capture_type="ai_debrief",
            context={"preInteractionBrief": {"questionsToAsk": []}},
            answers=("The customer asked several security questions.",),
            asked_targets=(),
            question_count=0,
            max_questions=6,
            context_questions=(),
        )
    )
    assert result.status == "ask"
    assert result.target == "other"


def test_debrief_fails_closed_for_lifecycle_feature_and_tenant(
    app: FastAPI,
    client: TestClient,
) -> None:
    planned = create_interaction(client, interaction_type="site_visit")
    lifecycle = client.post(
        f"/api/v1/interactions/{planned['id']}/debrief",
        json={
            "captureType": "ai_debrief",
            "safetyConfirmed": True,
            "idempotencyKey": "planned",
        },
    )
    assert lifecycle.status_code == 409
    assert lifecycle.json()["code"] == "interaction_not_completed"

    interaction_id, _ = _completed_interaction(client, interaction_type="presentation")
    started = _start(client, interaction_id, key="tenant-start")
    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    assert client.get(f"/api/v1/interactions/{interaction_id}/debrief/{started['id']}").status_code == 404
    app.dependency_overrides.pop(get_current_user)

    disabled = Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url=TEST_DB_URL,
        feature_ai_debrief_enabled=False,
    )
    with TestClient(create_app(disabled)) as disabled_client:
        response = disabled_client.post(
            f"/api/v1/interactions/{interaction_id}/debrief",
            json={
                "captureType": "ai_debrief",
                "safetyConfirmed": True,
                "idempotencyKey": "disabled",
            },
        )
    assert response.status_code == 404
    assert response.json()["code"] == "feature_unavailable"


def test_review_requires_every_candidate_and_rejected_reports_do_not_update_brain(
    client: TestClient,
) -> None:
    interaction_id, _ = _completed_interaction(client, interaction_type="site_visit")
    started = _start(client, interaction_id, key="reject-start")
    session_id = str(started["id"])
    answered = client.post(
        f"/api/v1/interactions/{interaction_id}/debrief/{session_id}/response",
        json={
            "answerText": "There is a security risk and an implementation constraint.",
            "idempotencyKey": "reject-answer",
        },
    )
    assert answered.status_code == 200
    finished = client.post(
        f"/api/v1/interactions/{interaction_id}/debrief/{session_id}/finish",
        json={"idempotencyKey": "reject-finish"},
    )
    candidates = finished.json()["candidates"]
    assert len(candidates) >= 2
    incomplete = client.post(
        f"/api/v1/interactions/{interaction_id}/debrief/{session_id}/review",
        json={
            "decisions": [{"candidateId": candidates[0]["id"], "decision": "reject"}],
            "idempotencyKey": "incomplete",
        },
    )
    assert incomplete.status_code == 422
    assert incomplete.json()["code"] == "incomplete_review"
    completed = client.post(
        f"/api/v1/interactions/{interaction_id}/debrief/{session_id}/review",
        json={
            "decisions": [{"candidateId": candidate["id"], "decision": "reject"} for candidate in candidates],
            "idempotencyKey": "reject-all",
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["interactionUpdated"] is False
    assert completed.json()["revenueBrainUpdated"] is False

    async def verify() -> tuple[int, int, int]:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            candidates_count = int(await session.scalar(select(func.count()).select_from(CandidateEvidence)) or 0)
            evidence_count = int(
                await session.scalar(
                    select(func.count()).select_from(Evidence).where(Evidence.validation_state == "verified")
                )
                or 0
            )
            brain_count = int(
                await session.scalar(select(func.count()).select_from(RevenueBrainInteractionSnapshot)) or 0
            )
        await engine.dispose()
        return candidates_count, evidence_count, brain_count

    assert asyncio.run(verify()) == (len(candidates), 0, 0)
