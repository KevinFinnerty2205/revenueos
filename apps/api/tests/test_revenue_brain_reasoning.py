from __future__ import annotations

import asyncio
import copy
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from revenueos.auth import get_current_user
from revenueos.models import (
    AIArtifact,
    Meeting,
    MeetingAuditEvent,
    RevenueBrainInsight,
    RevenueBrainSnapshot,
)
from revenueos.revenue_brain_comparison import (
    RevenueBrainArtifactPayloads,
    RevenueBrainComparisonEngine,
    RevenueBrainSnapshotBundle,
)
from revenueos.revenue_brain_reasoning_contracts import RevenueBrainInsightContent

from .conftest import PRIMARY_ORGANISATION_ID, TEST_DB_URL
from .test_meeting_api import cast_auth_dependency, secondary_user
from .test_revenue_brain import (
    NOW,
    SeededMeeting,
    _artifact_content,
    _create_snapshot,
    _seed_ready_meeting,
)


def _contents() -> dict[str, dict[str, object]]:
    return {
        artifact_type: copy.deepcopy(_artifact_content(artifact_type))
        for artifact_type in (
            "executive_summary",
            "buying_signals",
            "objections_competitive_signals",
            "stakeholder_intelligence",
            "decisions",
            "action_items",
            "risks_blockers",
            "open_questions",
            "next_best_action",
        )
    }


def _bundle(
    suffix: int,
    meeting_date: datetime,
    contents: dict[str, dict[str, object]],
) -> RevenueBrainSnapshotBundle:
    identifiers = {name: uuid.uuid5(uuid.NAMESPACE_URL, f"reasoning-test:{suffix}:{name}") for name in contents}
    snapshot = RevenueBrainSnapshot(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"reasoning-test:{suffix}:snapshot"),
        organisation_id=PRIMARY_ORGANISATION_ID,
        company_id=uuid.uuid5(uuid.NAMESPACE_URL, "reasoning-test:company"),
        opportunity_id=uuid.uuid5(uuid.NAMESPACE_URL, "reasoning-test:opportunity"),
        meeting_id=uuid.uuid5(uuid.NAMESPACE_URL, f"reasoning-test:{suffix}:meeting"),
        transcript_version_id=uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"reasoning-test:{suffix}:transcript-version",
        ),
        summary_reference=identifiers["executive_summary"],
        buying_signals_reference=identifiers["buying_signals"],
        objections_reference=identifiers["objections_competitive_signals"],
        stakeholders_reference=identifiers["stakeholder_intelligence"],
        decisions_reference=identifiers["decisions"],
        actions_reference=identifiers["action_items"],
        risks_reference=identifiers["risks_blockers"],
        questions_reference=identifiers["open_questions"],
        next_best_action_reference=identifiers["next_best_action"],
        version=1,
    )
    from revenueos.ai_contracts import (
        ActionItemsArtifactContent,
        BuyingSignalsArtifactContent,
        DecisionsArtifactContent,
        ExecutiveSummaryArtifactContent,
        NextBestActionArtifactContent,
        ObjectionsCompetitiveSignalsArtifactContent,
        OpenQuestionsArtifactContent,
        RisksBlockersArtifactContent,
        StakeholderIntelligenceArtifactContent,
    )

    return RevenueBrainSnapshotBundle(
        snapshot=snapshot,
        meeting_date=meeting_date,
        payloads=RevenueBrainArtifactPayloads(
            executive_summary=ExecutiveSummaryArtifactContent.model_validate(contents["executive_summary"]),
            buying_signals=BuyingSignalsArtifactContent.model_validate(contents["buying_signals"]),
            objections_competitive_signals=(
                ObjectionsCompetitiveSignalsArtifactContent.model_validate(contents["objections_competitive_signals"])
            ),
            stakeholder_intelligence=(
                StakeholderIntelligenceArtifactContent.model_validate(contents["stakeholder_intelligence"])
            ),
            decisions=DecisionsArtifactContent.model_validate(contents["decisions"]),
            action_items=ActionItemsArtifactContent.model_validate(contents["action_items"]),
            risks_blockers=RisksBlockersArtifactContent.model_validate(contents["risks_blockers"]),
            open_questions=OpenQuestionsArtifactContent.model_validate(contents["open_questions"]),
            next_best_action=NextBestActionArtifactContent.model_validate(contents["next_best_action"]),
        ),
        artifact_ids={
            "executive_summary": identifiers["executive_summary"],
            "buying_signals": identifiers["buying_signals"],
            "objections_competitive_signals": identifiers["objections_competitive_signals"],
            "stakeholder_intelligence": identifiers["stakeholder_intelligence"],
            "decisions": identifiers["decisions"],
            "action_items": identifiers["action_items"],
            "risks_blockers": identifiers["risks_blockers"],
            "open_questions": identifiers["open_questions"],
            "next_best_action": identifiers["next_best_action"],
        },
    )


def _material_comparison() -> tuple[RevenueBrainSnapshotBundle, RevenueBrainSnapshotBundle]:
    before = _contents()
    after = _contents()
    before["buying_signals"] = {
        "signals": [
            {
                "signal_type": "budget_unconfirmed",
                "polarity": "neutral",
                "strength": "moderate",
                "confidence": 0.8,
                "evidence": "Budget approval was explicitly unconfirmed.",
            },
            {
                "signal_type": "next_step_weak",
                "polarity": "negative",
                "strength": "moderate",
                "confidence": 0.8,
                "evidence": "The proposed next step lacked commitment.",
            },
            {
                "signal_type": "security_or_legal_blocker",
                "polarity": "negative",
                "strength": "strong",
                "confidence": 0.9,
                "evidence": "Security review was explicitly blocked.",
            },
        ],
        "overall_momentum": "negative",
        "momentum_summary": ("Budget, the next step and security evidence remained explicitly uncertain."),
        "confidence": 0.84,
    }
    after["buying_signals"] = {
        "signals": [
            {
                "signal_type": "budget_confirmed",
                "polarity": "positive",
                "strength": "strong",
                "confidence": 0.94,
                "evidence": "Budget approval was explicitly confirmed.",
            },
            {
                "signal_type": "next_step_committed",
                "polarity": "positive",
                "strength": "strong",
                "confidence": 0.9,
                "evidence": "The customer committed to the next step.",
            },
            {
                "signal_type": "security_or_legal_progress",
                "polarity": "positive",
                "strength": "moderate",
                "confidence": 0.88,
                "evidence": "Security review explicitly progressed.",
            },
        ],
        "overall_momentum": "strong_positive",
        "momentum_summary": ("Budget, the next step and security evidence all showed supported progress."),
        "confidence": 0.91,
    }
    before["objections_competitive_signals"] = {
        "objections": [
            {
                "objection": "Security review timing may delay approval.",
                "category": "security",
                "status": "unresolved",
                "strength": "moderate",
                "owner": None,
                "confidence": 0.86,
                "evidence": "Security timing remained unresolved.",
            }
        ],
        "competitors": [],
        "overall_objection_pressure": "medium",
        "summary": "A supported security objection created meaningful pressure.",
    }
    after["objections_competitive_signals"] = {
        "objections": [
            {
                "objection": "Security review timing may delay approval.",
                "category": "security",
                "status": "resolved",
                "strength": "weak",
                "owner": None,
                "confidence": 0.9,
                "evidence": "Security timing was explicitly resolved.",
            }
        ],
        "competitors": [
            {
                "name": "Competitor X",
                "position": "present",
                "confidence": 0.75,
                "evidence": "Competitor X was named as an alternative.",
            }
        ],
        "overall_objection_pressure": "low",
        "summary": ("The security objection was resolved, while competition was newly present."),
    }
    before["stakeholder_intelligence"] = {
        "stakeholders": [
            {
                "name": "Jordan Lee",
                "organisation": "Acme",
                "role": "champion",
                "influence": "medium",
                "stance": "supportive",
                "engagement": "active",
                "confidence": 0.86,
                "evidence": "Jordan advocated for the evaluation.",
            }
        ],
        "role_coverage": {
            "economic_buyer": "not_identified",
            "decision_maker": "unclear",
            "champion": "identified",
            "technical_buyer": "not_discussed",
            "procurement": "not_discussed",
            "legal_security": "not_discussed",
        },
        "stakeholder_summary": ("Champion coverage was identified, while other buying roles remained unclear."),
        "confidence": 0.85,
    }
    after["stakeholder_intelligence"] = {
        "stakeholders": [
            {
                "name": "Jordan Lee",
                "organisation": "Acme",
                "role": "champion",
                "influence": "high",
                "stance": "supportive",
                "engagement": "active",
                "confidence": 0.94,
                "evidence": "Jordan actively advocated for approval.",
            },
            {
                "name": "Economic Buyer",
                "organisation": "Acme",
                "role": "economic_buyer",
                "influence": "high",
                "stance": "neutral",
                "engagement": "active",
                "confidence": 0.82,
                "evidence": "The economic buyer joined the process.",
            },
        ],
        "role_coverage": {
            "economic_buyer": "identified",
            "decision_maker": "unclear",
            "champion": "identified",
            "technical_buyer": "not_discussed",
            "procurement": "not_discussed",
            "legal_security": "not_discussed",
        },
        "stakeholder_summary": ("Champion and economic buyer coverage were identified in the current meeting."),
        "confidence": 0.92,
    }
    before["risks_blockers"] = {
        "risks": [
            {
                "risk": "Implementation capacity may delay rollout.",
                "category": "implementation",
                "severity": "medium",
                "owner": None,
                "confidence": 0.8,
                "evidence": "Implementation capacity remained limited.",
            }
        ]
    }
    after["risks_blockers"] = {
        "risks": [
            {
                "risk": "Implementation capacity may delay rollout.",
                "category": "implementation",
                "severity": "high",
                "owner": None,
                "confidence": 0.87,
                "evidence": "Implementation capacity became a high-severity risk.",
            }
        ]
    }
    for collection in (before, after):
        collection["open_questions"] = {
            "open_questions": [
                {
                    "question": "Who approves the implementation plan?",
                    "owner": None,
                    "importance": "high",
                    "confidence": 0.82,
                    "evidence": "The approver was not identified.",
                }
            ]
        }
        collection["action_items"] = {
            "action_items": [
                {
                    "task": "Send the implementation plan.",
                    "owner": "Alex" if collection is before else "Jordan",
                    "due_date": ("2026-08-10" if collection is before else "2026-08-12"),
                    "priority": "high",
                    "status": "open",
                    "confidence": 0.9,
                    "evidence": "The plan remains an explicit action.",
                }
            ]
        }
    before["decisions"] = {
        "decisions": [
            {
                "decision": "Proceed to implementation planning.",
                "owner": None,
                "status": "tentative",
                "confidence": 0.8,
                "evidence": "Planning was tentatively supported.",
            }
        ]
    }
    after["decisions"] = {
        "decisions": [
            {
                "decision": "Proceed to implementation planning.",
                "owner": None,
                "status": "confirmed",
                "confidence": 0.92,
                "evidence": "Planning was explicitly confirmed.",
            }
        ]
    }
    after["next_best_action"] = {
        "overall_recommendation": "Schedule the implementation planning review.",
        "priority": "medium",
        "confidence": 0.88,
        "reasoning": ["Action items: implementation planning is now confirmed."],
        "recommended_actions": [
            {
                "action": "Schedule the implementation planning review.",
                "reason": "Action items: implementation planning is now confirmed.",
                "priority": "medium",
                "confidence": 0.88,
                "depends_on": ["action_items"],
            }
        ],
    }
    return (
        _bundle(1, NOW - timedelta(days=14), before),
        _bundle(2, NOW, after),
    )


def test_engine_produces_grounded_changes_across_supported_capabilities() -> None:
    before, after = _material_comparison()
    content = RevenueBrainComparisonEngine().compare(
        "opportunity",
        before,
        after,
    )

    change_types = {item.change_type for item in content.changes}
    assert {
        "budget_confirmed",
        "next_step_strengthened",
        "security_or_legal_progressed",
        "objection_resolved",
        "competitor_introduced",
        "champion_strengthened",
        "economic_buyer_identified",
        "risk_severity_increased",
        "open_question_persisted",
        "decision_changed",
        "action_item_owner_changed",
        "action_item_due_date_changed",
        "next_best_action_changed",
        "next_best_action_priority_decreased",
    }.issubset(change_types)
    assert content.from_meeting_date < content.to_meeting_date
    assert content.changes[0].title in content.summary
    assert all(
        evidence.snapshot_id in {before.snapshot.id, after.snapshot.id}
        for change in content.changes
        for evidence in change.evidence
    )
    assert all("Jordan Lee" not in evidence.entity_key for change in content.changes for evidence in change.evidence)
    serialised = content.model_dump_json()
    for prohibited in (
        "transcript",
        "provider",
        "prompt",
        "forecast",
        "probability",
        "score",
    ):
        assert prohibited not in serialised.casefold()


def test_silence_does_not_resolve_remove_complete_or_deteriorate_entities() -> None:
    before, after = _material_comparison()
    later_contents = _contents()
    later_contents["stakeholder_intelligence"] = {
        "stakeholders": [],
        "role_coverage": {
            "economic_buyer": "not_discussed",
            "decision_maker": "not_discussed",
            "champion": "not_discussed",
            "technical_buyer": "not_discussed",
            "procurement": "not_discussed",
            "legal_security": "not_discussed",
        },
        "stakeholder_summary": ("There was not enough evidence to identify stakeholder roles reliably."),
        "confidence": 0.3,
    }
    silent_after = _bundle(3, NOW, later_contents)

    content = RevenueBrainComparisonEngine().compare(
        "opportunity",
        before,
        silent_after,
    )
    prohibited = {
        "objection_resolved",
        "competitor_removed",
        "champion_disappeared",
        "stakeholder_removed",
        "risk_resolved",
        "open_question_answered",
        "action_item_completed",
        "action_item_removed",
    }
    assert prohibited.isdisjoint(item.change_type for item in content.changes)
    assert after.snapshot.id != silent_after.snapshot.id


def test_identical_empty_snapshots_return_the_documented_no_change_state() -> None:
    baseline = _contents()
    content = RevenueBrainComparisonEngine().compare(
        "account",
        _bundle(10, NOW - timedelta(days=1), baseline),
        _bundle(11, NOW, baseline),
    )

    assert content.changes == ()
    assert content.summary == ("No material supported changes were identified between the latest eligible meetings.")


def test_insight_contract_rejects_unknown_fields_invalid_dates_and_confidence() -> None:
    before, after = _material_comparison()
    valid = RevenueBrainComparisonEngine().compare("account", before, after)
    payload = valid.model_dump(mode="json")
    payload["unknown"] = True
    with pytest.raises(ValidationError):
        RevenueBrainInsightContent.model_validate(payload)

    payload = valid.model_dump(mode="json")
    payload["to_meeting_date"] = "2020-01-01"
    with pytest.raises(ValidationError):
        RevenueBrainInsightContent.model_validate(payload)

    payload = valid.model_dump(mode="json")
    payload["confidence"] = 1.1
    with pytest.raises(ValidationError):
        RevenueBrainInsightContent.model_validate(payload)


async def _persist_snapshot(
    session: AsyncSession,
    *,
    company_id: uuid.UUID | None,
    opportunity_id: uuid.UUID | None,
    meeting_date: datetime,
    contents: dict[str, dict[str, object]],
) -> SeededMeeting:
    seeded = await _seed_ready_meeting(
        session,
        company_id=company_id,
        meeting_date=meeting_date,
        link_opportunity=company_id is None,
    )
    resolved_opportunity_id = opportunity_id or seeded.opportunity_id
    meeting = await session.get(Meeting, seeded.meeting_id)
    assert meeting is not None
    meeting.opportunity_id = resolved_opportunity_id
    for artifact_type, artifact_id in seeded.artifacts.items():
        artifact = await session.get(AIArtifact, artifact_id)
        assert artifact is not None
        artifact.content_json = contents[artifact_type]
    snapshot = await _create_snapshot(session, seeded)
    assert snapshot is not None
    assert resolved_opportunity_id is not None
    return SeededMeeting(
        company_id=seeded.company_id,
        opportunity_id=resolved_opportunity_id,
        meeting_id=seeded.meeting_id,
        transcript_id=seeded.transcript_id,
        artifacts=seeded.artifacts,
    )


def test_reasoning_api_is_transcript_free_idempotent_and_scope_isolated(
    app: FastAPI,
    client: TestClient,
) -> None:
    async def seed() -> tuple[uuid.UUID, uuid.UUID]:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        before_bundle, after_bundle = _material_comparison()
        first_contents = {source: copy.deepcopy(content) for source, content in _contents().items()}
        second_contents = _contents()
        first_contents["buying_signals"] = before_bundle.payloads.buying_signals.model_dump(mode="json")
        first_contents["stakeholder_intelligence"] = before_bundle.payloads.stakeholder_intelligence.model_dump(
            mode="json"
        )
        second_contents["buying_signals"] = after_bundle.payloads.buying_signals.model_dump(mode="json")
        second_contents["stakeholder_intelligence"] = after_bundle.payloads.stakeholder_intelligence.model_dump(
            mode="json"
        )
        async with session_factory() as session, session.begin():
            first = await _persist_snapshot(
                session,
                company_id=None,
                opportunity_id=None,
                meeting_date=NOW - timedelta(days=14),
                contents=first_contents,
            )
            assert first.opportunity_id is not None
            await _persist_snapshot(
                session,
                company_id=first.company_id,
                opportunity_id=first.opportunity_id,
                meeting_date=NOW - timedelta(days=7),
                contents=second_contents,
            )
            await _persist_snapshot(
                session,
                company_id=first.company_id,
                opportunity_id=first.opportunity_id,
                meeting_date=NOW,
                contents=first_contents,
            )
        await engine.dispose()
        return first.company_id, first.opportunity_id

    company_id, opportunity_id = asyncio.run(seed())
    selected_statements: list[str] = []

    def capture_selects(
        connection: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        del connection, cursor, parameters, context, executemany
        if statement.lstrip().upper().startswith("SELECT"):
            selected_statements.append(statement.casefold())

    event.listen(
        app.state.engine.sync_engine,
        "before_cursor_execute",
        capture_selects,
    )
    try:
        created = client.post(f"/api/v1/opportunities/{opportunity_id}/brain/reasoning?mode=recent_history")
    finally:
        event.remove(
            app.state.engine.sync_engine,
            "before_cursor_execute",
            capture_selects,
        )

    assert created.status_code == 200, created.text
    body = created.json()
    assert body["state"] == "completed"
    assert body["created"] is True
    assert len(body["history"]) == 2
    assert body["latest"]["content"]["toMeetingDate"] == NOW.date().isoformat()
    assert all("transcripts" not in statement for statement in selected_statements)
    assert all("raw_text" not in statement for statement in selected_statements)
    for prohibited in (
        "rawText",
        "providerKey",
        "modelName",
        "promptVersion",
        "schemaVersion",
        "workerId",
        "forecast",
        "probability",
        "score",
    ):
        assert prohibited not in created.text

    reused = client.post(f"/api/v1/opportunities/{opportunity_id}/brain/reasoning?mode=recent_history")
    assert reused.status_code == 200
    assert reused.json()["created"] is False
    assert [item["id"] for item in reused.json()["history"]] == [item["id"] for item in body["history"]]

    account = client.post(f"/api/v1/accounts/{company_id}/brain/reasoning?mode=recent_history")
    assert account.status_code == 200
    assert account.json()["latest"]["content"]["scope"] == "account"
    assert account.json()["latest"]["id"] != body["latest"]["id"]

    workspace = client.get(f"/api/v1/opportunities/{opportunity_id}/workspace")
    assert workspace.status_code == 200
    assert workspace.json()["reasoning"]["latest"]["id"] == body["latest"]["id"]
    assert "rawText" not in workspace.text

    async def add_newer_snapshot() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session, session.begin():
            await _persist_snapshot(
                session,
                company_id=company_id,
                opportunity_id=opportunity_id,
                meeting_date=NOW + timedelta(days=7),
                contents=_contents(),
            )
        await engine.dispose()

    asyncio.run(add_newer_snapshot())
    stale = client.get(f"/api/v1/opportunities/{opportunity_id}/brain/reasoning")
    assert stale.status_code == 200
    assert stale.json()["state"] == "not_generated"
    assert stale.json()["latest"] is None
    assert len(stale.json()["history"]) == 2

    new_comparison = client.post(f"/api/v1/opportunities/{opportunity_id}/brain/reasoning")
    assert new_comparison.status_code == 200
    assert new_comparison.json()["created"] is True
    assert len(new_comparison.json()["history"]) == 3

    async def inspect() -> tuple[int, list[dict[str, object]]]:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            insight_count = int(await session.scalar(select(func.count()).select_from(RevenueBrainInsight)) or 0)
            audit_metadata = [
                item.metadata_json
                for item in await session.scalars(
                    select(MeetingAuditEvent).where(MeetingAuditEvent.changed_fields == ["revenue_brain_reasoning"])
                )
            ]
        await engine.dispose()
        return insight_count, audit_metadata

    insight_count, audit_metadata = asyncio.run(inspect())
    assert insight_count == 5
    assert {item["event"] for item in audit_metadata} >= {
        "revenue_brain_reasoning_requested",
        "revenue_brain_insight_created",
    }
    assert all("summary" not in item and "description" not in item for item in audit_metadata)

    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    cross_tenant = client.get(f"/api/v1/opportunities/{opportunity_id}/brain/reasoning")
    assert cross_tenant.status_code == 404
    assert str(opportunity_id) not in cross_tenant.text


def test_reasoning_api_reports_safe_history_states(client: TestClient) -> None:
    missing = client.get(f"/api/v1/opportunities/{uuid.uuid4()}/brain/reasoning")
    assert missing.status_code == 404
    assert missing.json()["code"] == "opportunity_not_found"


def test_reasoning_excludes_malformed_snapshot_identity_and_references(
    client: TestClient,
) -> None:
    async def seed() -> uuid.UUID:
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session, session.begin():
            first = await _persist_snapshot(
                session,
                company_id=None,
                opportunity_id=None,
                meeting_date=NOW - timedelta(days=14),
                contents=_contents(),
            )
            assert first.opportunity_id is not None
            second = await _persist_snapshot(
                session,
                company_id=first.company_id,
                opportunity_id=first.opportunity_id,
                meeting_date=NOW - timedelta(days=7),
                contents=_contents(),
            )
            third = await _persist_snapshot(
                session,
                company_id=first.company_id,
                opportunity_id=first.opportunity_id,
                meeting_date=NOW,
                contents=_contents(),
            )
            second_snapshot = await session.scalar(
                select(RevenueBrainSnapshot).where(
                    RevenueBrainSnapshot.meeting_id == second.meeting_id,
                )
            )
            third_snapshot = await session.scalar(
                select(RevenueBrainSnapshot).where(
                    RevenueBrainSnapshot.meeting_id == third.meeting_id,
                )
            )
            assert second_snapshot is not None
            assert third_snapshot is not None
            second_snapshot.transcript_version_id = uuid.uuid4()
            third_snapshot.summary_reference = first.artifacts["executive_summary"]
        await engine.dispose()
        return first.opportunity_id

    opportunity_id = asyncio.run(seed())
    response = client.post(
        f"/api/v1/opportunities/{opportunity_id}/brain/reasoning",
    )

    assert response.status_code == 200
    assert response.json()["state"] == "insufficient_history"
    assert response.json()["created"] is False
