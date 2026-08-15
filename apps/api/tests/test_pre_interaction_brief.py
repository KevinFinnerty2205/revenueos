from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import get_current_user
from revenueos.config import Settings
from revenueos.main import create_app
from revenueos.models import AIUsageCounter, PreInteractionBrief
from revenueos.pre_interaction_contracts import PreInteractionBriefContent
from revenueos.pre_interaction_repositories import PreInteractionBriefRepository
from revenueos.revenue_brain_reasoning_repositories import RevenueBrainReasoningRepository

from .conftest import (
    PRIMARY_ORGANISATION_ID,
    SECONDARY_ORGANISATION_ID,
    TEST_DB_URL,
)
from .test_business_api import create_company, create_contact, create_opportunity
from .test_interaction_api import create_interaction
from .test_meeting_api import cast_auth_dependency, create_meeting, secondary_user
from .test_meeting_intelligence_workspace import _run_worker_once
from .test_opportunity_workspace import _associate


def _brief_url(interaction_id: str) -> str:
    return f"/api/v1/interactions/{interaction_id}/companion/brief"


def _valid_content() -> dict[str, object]:
    return {
        "interaction_id": "00000000-0000-4000-8000-000000000099",
        "interaction_type": "phone_call",
        "brief_version": 1,
        "headline": "Agree a concrete next step.",
        "account_context": "The opportunity is in evaluation with limited validated intelligence.",
        "recent_changes": [],
        "objectives": [
            {
                "objective": "Agree a concrete next step.",
                "priority": "high",
                "reason": "A short call should close with clear ownership.",
            }
        ],
        "questions_to_ask": [
            {
                "question": "What is the most useful next step?",
                "purpose": "Close the call clearly.",
                "priority": "high",
            }
        ],
        "stakeholder_focus": [],
        "open_commitments": [],
        "risks_to_watch": [],
        "success_criteria": ["A clear next step is agreed."],
        "interaction_guidance": "Keep the call concise and close with ownership.",
        "confidence": 0.5,
    }


def test_brief_schema_is_strict_bounded_and_non_predictive() -> None:
    content = PreInteractionBriefContent.model_validate_json(json.dumps(_valid_content()))
    assert content.interaction_type == "phone_call"
    with pytest.raises(ValidationError):
        PreInteractionBriefContent.model_validate_json(json.dumps({**_valid_content(), "close_probability": 0.8}))
    with pytest.raises(ValidationError):
        PreInteractionBriefContent.model_validate_json(json.dumps({**_valid_content(), "confidence": float("nan")}))
    with pytest.raises(ValidationError):
        PreInteractionBriefContent.model_validate_json(
            json.dumps(
                {
                    **_valid_content(),
                    "questions_to_ask": [
                        {
                            "question": f"Question {index}?",
                            "purpose": "Test the documented maximum.",
                            "priority": "low",
                        }
                        for index in range(9)
                    ],
                }
            )
        )
    with pytest.raises(ValidationError):
        PreInteractionBriefContent.model_validate_json(
            json.dumps(
                {
                    **_valid_content(),
                    "questions_to_ask": [
                        {
                            "question": "This is not a question",
                            "purpose": "Validate question form.",
                            "priority": "low",
                        }
                    ],
                }
            )
        )
    with pytest.raises(ValidationError):
        content.headline = "Mutation is prohibited."  # type: ignore[misc]
    for invalid in (
        {"interaction_type": "video_call"},
        {"objectives": _valid_content()["objectives"] * 6},
        {"success_criteria": [f"Criterion {index}" for index in range(6)]},
        {
            "objectives": [
                {
                    "objective": "Invalid priority.",
                    "priority": "urgent",
                    "reason": "Priorities are intentionally bounded.",
                }
            ]
        },
        {"automation_action": "send_email"},
    ):
        with pytest.raises(ValidationError):
            PreInteractionBriefContent.model_validate_json(json.dumps({**_valid_content(), **invalid}))


def test_opportunity_context_does_not_fall_back_to_account_reasoning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def list_insights(
        _repository: RevenueBrainReasoningRepository,
        _organisation_id: UUID,
        *,
        scope: str,
        scope_target_id: UUID,
        reasoning_version: int,
        limit: int,
    ) -> list[object]:
        del scope_target_id, reasoning_version, limit
        calls.append(scope)
        return []

    monkeypatch.setattr(RevenueBrainReasoningRepository, "list_insights", list_insights)
    repository = PreInteractionBriefRepository(object())  # type: ignore[arg-type]
    result = asyncio.run(
        repository._latest_revenue_brain_insight(  # noqa: SLF001
            PRIMARY_ORGANISATION_ID,
            opportunity_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
        )
    )

    assert result is None
    assert calls == ["opportunity"]


@pytest.mark.parametrize(
    "interaction_type",
    (
        "online_meeting",
        "face_to_face_meeting",
        "presentation",
        "workshop",
        "site_visit",
        "executive_lunch",
        "phone_call",
        "conference_interaction",
        "trade_show_interaction",
        "manual_interaction",
    ),
)
def test_deterministic_brief_supports_every_interaction_type(
    client: TestClient,
    interaction_type: str,
) -> None:
    company_id = str(create_company(client, name=f"{interaction_type} account")["id"])
    opportunity_id = str(create_opportunity(client, company_id, name=f"{interaction_type} opportunity")["id"])
    interaction = create_interaction(
        client,
        title=f"Prepare {interaction_type}",
        interaction_type=interaction_type,
        company_id=company_id,
        opportunity_id=opportunity_id,
    )
    response = client.post(_brief_url(str(interaction["id"])))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "completed"
    assert body["created"] is True
    assert body["brief"]["interactionType"] == interaction_type
    assert body["brief"]["objectives"]
    assert body["brief"]["questionsToAsk"]
    assert body["brief"]["successCriteria"]
    assert 0 <= body["brief"]["confidence"] <= 1
    for prohibited in (
        "rawText",
        "transcript",
        "providerKey",
        "promptKey",
        "schemaVersion",
        "workerId",
        "closeProbability",
        "forecast",
        "recording",
    ):
        assert prohibited not in response.text
    if interaction_type == "phone_call":
        assert len(body["brief"]["questionsToAsk"]) <= 5
        assert "concise" in body["brief"]["interactionGuidance"].lower()
    if interaction_type == "presentation":
        assert "seller-prepared material" in body["brief"]["interactionGuidance"]


def test_phone_brief_prioritises_the_explicit_linked_contact_and_role(client: TestClient) -> None:
    company_id = str(create_company(client, name="Phone brief account")["id"])
    contact = create_contact(
        client,
        company_id,
        first_name="Jordan",
    )
    interaction = create_interaction(
        client,
        title="Commercial alignment call",
        interaction_type="phone_call",
        company_id=company_id,
        contact_id=str(contact["id"]),
        call_direction="outbound",
    )

    generated = client.post(_brief_url(str(interaction["id"])))

    assert generated.status_code == 200, generated.text
    stakeholder = generated.json()["brief"]["stakeholderFocus"][0]
    assert stakeholder == {
        "name": "Jordan Lee",
        "role": "Revenue Director",
        "focus": "Confirm Jordan Lee's priorities and role in this interaction.",
    }
    assert "+61 400 000 000" not in generated.text


def test_generation_is_versioned_idempotent_reviewable_and_visible_in_list(
    client: TestClient,
) -> None:
    company_id = str(create_company(client)["id"])
    opportunity_id = str(create_opportunity(client, company_id)["id"])
    interaction = create_interaction(
        client,
        interaction_type="phone_call",
        company_id=company_id,
        opportunity_id=opportunity_id,
    )
    interaction_id = str(interaction["id"])
    first = client.post(_brief_url(interaction_id))
    assert first.status_code == 200
    assert first.json()["brief"]["briefVersion"] == 1

    repeated = client.post(_brief_url(interaction_id))
    assert repeated.status_code == 200
    assert repeated.json()["created"] is False
    assert repeated.json()["brief"]["briefVersion"] == 1

    reviewed = client.post(f"{_brief_url(interaction_id)}/review")
    assert reviewed.status_code == 200
    assert reviewed.json()["reviewed"] is True
    reviewed_at = reviewed.json()["reviewedAt"]
    repeated_review = client.post(f"{_brief_url(interaction_id)}/review")
    assert repeated_review.status_code == 200
    assert repeated_review.json()["reviewedAt"] == reviewed_at

    updated = client.patch(
        f"/api/v1/interactions/{interaction_id}",
        json={"title": "Updated preparation context"},
    )
    assert updated.status_code == 200
    second = client.post(_brief_url(interaction_id))
    assert second.status_code == 200
    assert second.json()["created"] is True
    assert second.json()["brief"]["briefVersion"] == 2
    assert second.json()["priorVersions"][0]["briefVersion"] == 1
    assert second.json()["priorVersions"][0]["reviewed"] is True

    listed = client.get("/api/v1/interactions", params={"search": "Updated preparation context"})
    assert listed.status_code == 200
    assert listed.json()["items"][0]["briefState"] == "completed"
    assert listed.json()["items"][0]["briefGeneratedAt"] is not None

    async def verify() -> tuple[int, int]:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            brief_count = await session.scalar(
                select(func.count())
                .select_from(PreInteractionBrief)
                .where(PreInteractionBrief.interaction_id == UUID(interaction_id))
            )
            usage = await session.get(AIUsageCounter, (PRIMARY_ORGANISATION_ID, datetime.now(UTC).date()))
        await engine.dispose()
        return int(brief_count or 0), usage.generation_count if usage is not None else 0

    assert asyncio.run(verify()) == (2, 2)


def test_unavailable_notice_feature_and_tenant_fail_closed(
    app: FastAPI,
    client: TestClient,
) -> None:
    no_context = create_interaction(client, interaction_type="manual_interaction")
    unavailable = client.get(_brief_url(str(no_context["id"])))
    assert unavailable.status_code == 200
    assert unavailable.json()["state"] == "unavailable"
    assert unavailable.json()["generationAvailable"] is False

    company_id = str(create_company(client)["id"])
    opportunity_id = str(create_opportunity(client, company_id)["id"])
    interaction = create_interaction(client, company_id=company_id, opportunity_id=opportunity_id)

    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    assert client.get(_brief_url(str(interaction["id"]))).status_code == 404
    app.dependency_overrides.pop(get_current_user)

    settings = Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url=TEST_DB_URL,
        private_beta_data_notice_version=2,
    )
    with TestClient(create_app(settings)) as notice_client:
        required = notice_client.post(_brief_url(str(interaction["id"])))
        assert required.status_code == 428
        assert required.json()["code"] == "data_notice_acknowledgement_required"

    disabled_settings = Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url=TEST_DB_URL,
        feature_ai_companion_enabled=False,
    )
    with TestClient(create_app(disabled_settings)) as disabled_client:
        disabled = disabled_client.get(_brief_url(str(interaction["id"])))
        assert disabled.status_code == 404
        assert disabled.json()["code"] == "feature_unavailable"


def test_context_selection_never_queries_the_transcript_table(
    app: FastAPI,
    client: TestClient,
) -> None:
    company_id = str(create_company(client)["id"])
    opportunity_id = str(create_opportunity(client, company_id)["id"])
    source_meeting = create_meeting(
        client,
        company_id=company_id,
        transcript={
            "rawText": "Synthetic prior customer context that the brief service must never read.",
            "language": "en-AU",
            "source": "manual",
        },
    )
    associated = _associate(client, source_meeting, opportunity_id)
    completed = client.patch(
        f"/api/v1/meetings/{associated['id']}",
        json={"status": "completed"},
    )
    assert completed.status_code == 200
    target = create_interaction(
        client,
        interaction_type="face_to_face_meeting",
        company_id=company_id,
        opportunity_id=opportunity_id,
    )

    statements: list[str] = []

    def capture_statement(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        statements.append(statement)

    event.listen(app.state.engine.sync_engine, "before_cursor_execute", capture_statement)
    try:
        response = client.post(_brief_url(str(target["id"])))
    finally:
        event.remove(app.state.engine.sync_engine, "before_cursor_execute", capture_statement)
    assert response.status_code == 200, response.text
    assert all("transcripts" not in statement.lower() for statement in statements)
    assert "Synthetic prior customer context" not in response.text
    assert str(SECONDARY_ORGANISATION_ID) not in response.text


def test_full_validated_intelligence_is_grounded_and_stale_versions_are_excluded(
    client: TestClient,
) -> None:
    company_id = str(create_company(client, name="Grounded context account")["id"])
    opportunity_id = str(create_opportunity(client, company_id, name="Grounded context opportunity")["id"])
    source_meeting = create_meeting(
        client,
        title="Prior validated pilot review",
        company_id=company_id,
        participants=[
            {
                "displayName": "Alex Morgan",
                "attendanceStatus": "attended",
                "role": "attendee",
            }
        ],
        transcript={
            "rawText": (
                "Alex confirmed the limited pilot budget and asked for the security plan. "
                "Implementation capacity remains a risk. Alex will send the technical requirements by Friday. "
                "The procurement owner is still unknown and the next step is a technical workshop."
            ),
            "language": "en-AU",
            "source": "manual",
        },
    )
    associated = _associate(client, source_meeting, opportunity_id)
    assert client.patch(f"/api/v1/meetings/{associated['id']}", json={"status": "completed"}).status_code == 200
    base = f"/api/v1/meetings/{associated['id']}/intelligence"
    assert client.post(f"{base}/generate").status_code == 202
    for _ in range(8):
        _run_worker_once()
    assert client.post(f"{base}/generate").status_code == 202
    _run_worker_once()
    _run_worker_once()

    target = create_interaction(
        client,
        title="Grounded upcoming workshop",
        interaction_type="workshop",
        company_id=company_id,
        opportunity_id=opportunity_id,
    )
    response = client.post(_brief_url(str(target["id"])))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "completed"
    assert "Prior validated Meeting Intelligence" in body["sourceLabels"]
    assert body["brief"]["objectives"]
    assert body["brief"]["questionsToAsk"]
    assert "rawText" not in response.text
    assert "provider" not in response.text.lower()

    async def source_capabilities(interaction_id: str) -> set[str]:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            record = await session.scalar(
                select(PreInteractionBrief).where(
                    PreInteractionBrief.organisation_id == PRIMARY_ORGANISATION_ID,
                    PreInteractionBrief.interaction_id == UUID(interaction_id),
                )
            )
            assert record is not None
            capabilities = {str(item["capability"]) for item in record.source_references_json}
        await engine.dispose()
        return capabilities

    grounded_capabilities = asyncio.run(source_capabilities(str(target["id"])))
    assert {
        "executive_summary",
        "buying_signals",
        "objections_competitive_signals",
        "stakeholder_intelligence",
        "decisions",
        "action_items",
        "risks_blockers",
        "open_questions",
        "next_best_action",
    }.issubset(grounded_capabilities)

    transcript = client.get(f"/api/v1/meetings/{associated['id']}/transcript").json()
    assert (
        client.patch(
            f"/api/v1/meetings/{associated['id']}/transcript",
            json={
                "rawText": "A corrected synthetic transcript version invalidates all earlier artefacts.",
                "language": "en-AU",
                "version": transcript["version"],
            },
        ).status_code
        == 200
    )
    stale_target = create_interaction(
        client,
        title="Stale artefacts excluded",
        interaction_type="phone_call",
        company_id=company_id,
        opportunity_id=opportunity_id,
    )
    stale_response = client.post(_brief_url(str(stale_target["id"])))
    assert stale_response.status_code == 200
    assert "Prior validated Meeting Intelligence" not in stale_response.json()["sourceLabels"]
    assert grounded_capabilities - {
        "interaction_metadata",
        "company_metadata",
        "opportunity_metadata",
    }
    assert asyncio.run(source_capabilities(str(stale_target["id"]))).isdisjoint(
        {
            "executive_summary",
            "buying_signals",
            "objections_competitive_signals",
            "stakeholder_intelligence",
            "decisions",
            "action_items",
            "risks_blockers",
            "open_questions",
            "next_best_action",
        }
    )


def test_company_only_partial_context_and_terminal_states_are_product_safe(client: TestClient) -> None:
    company_id = str(create_company(client, name="Company-only context")["id"])
    partial = create_interaction(client, interaction_type="executive_lunch", company_id=company_id)
    generated = client.post(_brief_url(str(partial["id"])))
    assert generated.status_code == 200
    assert "No linked opportunity" in generated.json()["brief"]["accountContext"]
    assert generated.json()["brief"]["stakeholderFocus"] == []
    assert generated.json()["brief"]["risksToWatch"] == []

    failed_interaction = create_interaction(client, interaction_type="phone_call", company_id=company_id)
    cancelled_interaction = create_interaction(client, interaction_type="presentation", company_id=company_id)

    async def insert_terminal_records() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session, session.begin():
            for version, (interaction, status) in enumerate(
                ((failed_interaction, "failed"), (cancelled_interaction, "cancelled")),
                start=1,
            ):
                session.add(
                    PreInteractionBrief(
                        id=uuid.uuid4(),
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_id=UUID(str(interaction["id"])),
                        company_id=UUID(company_id),
                        source_context_fingerprint=str(version) * 64,
                        brief_version=1,
                        schema_version=1,
                        status=status,
                        content_json={"safe": "terminal fixture"},
                        source_references_json=[],
                        created_by_user_id=UUID("00000000-0000-4000-8000-000000000001"),
                    )
                )
        await engine.dispose()

    asyncio.run(insert_terminal_records())
    failed = client.get(_brief_url(str(failed_interaction["id"])))
    cancelled = client.get(_brief_url(str(cancelled_interaction["id"])))
    assert failed.json()["state"] == "failed"
    assert cancelled.json()["state"] == "cancelled"
    for response in (failed, cancelled):
        assert response.json()["brief"] is None
        assert "terminal fixture" not in response.text


def test_quota_exhaustion_is_safe_and_equivalent_reuse_is_free(client: TestClient) -> None:
    company_id = str(create_company(client, name="Quota context")["id"])
    first = create_interaction(client, title="First quota brief", company_id=company_id)
    second = create_interaction(client, title="Second quota brief", company_id=company_id)
    settings = Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url=TEST_DB_URL,
        private_beta_max_generations_per_day=1,
    )
    with TestClient(create_app(settings)) as quota_client:
        generated = quota_client.post(_brief_url(str(first["id"])))
        assert generated.status_code == 200
        assert quota_client.post(_brief_url(str(first["id"]))).json()["created"] is False
        exhausted = quota_client.post(_brief_url(str(second["id"])))
        assert exhausted.status_code == 429
        assert exhausted.json()["code"] == "daily_generation_limit_exceeded"
