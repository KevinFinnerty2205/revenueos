from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.config import get_settings
from revenueos.daily_contracts import (
    DailyAction,
    DailyDealAttention,
    DailyDealReason,
    DailyInteraction,
    DailyRecommendation,
)
from revenueos.daily_repositories import DailyRecommendationRecord, DailyRepository
from revenueos.daily_services import RevenueOSDailyService
from revenueos.methodology_contracts import (
    MethodologyProjectionContent,
    MethodologyProjectionItem,
    MethodologyStateCounts,
)
from revenueos.models import (
    ActionProposal,
    ActionProposalVersion,
    Company,
    Interaction,
    MethodologyProjection,
    Opportunity,
    OrganisationMembership,
    OrganisationMethodologySetting,
    PreInteractionBrief,
    RevenueBrainInsight,
    User,
)

from .conftest import (
    PRIMARY_ORGANISATION_ID,
    PRIMARY_USER_ID,
    SECONDARY_ORGANISATION_ID,
    SECONDARY_USER_ID,
    TEST_DB_URL,
)


def _local_day_bounds() -> tuple[datetime, datetime]:
    timezone = ZoneInfo("Australia/Sydney")
    now = datetime.now(UTC).astimezone(timezone)
    start = datetime.combine(now.date(), time.min, timezone)
    return start, start + timedelta(days=1)


def _seed_daily_scenario(*, include_second_currency: bool = False) -> dict[str, str]:
    async def seed() -> dict[str, str]:
        engine = create_async_engine(TEST_DB_URL)
        start, end = _local_day_bounds()
        now = datetime.now(UTC)
        start_utc = start.astimezone(UTC)
        remaining_today = end.astimezone(UTC) - now
        next_interaction_at = now + min(timedelta(hours=2), remaining_today / 3)
        prepared_interaction_at = now + min(timedelta(hours=5), remaining_today * 2 / 3)
        prepared_interaction_end = min(
            prepared_interaction_at + timedelta(hours=1),
            end.astimezone(UTC) - remaining_today / 10,
        )
        company_id = uuid.uuid4()
        opportunity_id = uuid.uuid4()
        next_interaction_id = uuid.uuid4()
        prepared_interaction_id = uuid.uuid4()
        tomorrow_interaction_id = uuid.uuid4()
        yesterday_interaction_id = uuid.uuid4()
        action_id = uuid.uuid4()
        approved_action_id = uuid.uuid4()
        rejected_action_id = uuid.uuid4()
        completed_action_id = uuid.uuid4()
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add(
                Company(
                    id=company_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    name="Qantas",
                    status="active",
                    owner_user_id=PRIMARY_USER_ID,
                )
            )
            session.add(
                Opportunity(
                    id=opportunity_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    company_id=company_id,
                    name="Network modernisation",
                    stage="evaluation",
                    status="open",
                    estimated_value=Decimal("420000.00"),
                    currency="AUD",
                    expected_close_date=(start + timedelta(days=8)).date(),
                    owner_user_id=PRIMARY_USER_ID,
                )
            )
            if include_second_currency:
                session.add(
                    Opportunity(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        company_id=company_id,
                        name="US expansion",
                        stage="discovery",
                        status="open",
                        estimated_value=Decimal("90000.00"),
                        currency="USD",
                        expected_close_date=(start + timedelta(days=9)).date(),
                        owner_user_id=PRIMARY_USER_ID,
                    )
                )
            session.add(
                Opportunity(
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    company_id=company_id,
                    name="Closed historical win",
                    stage="closed_won",
                    status="won",
                    estimated_value=Decimal("9999999.00"),
                    currency="EUR",
                    expected_close_date=start.date(),
                    owner_user_id=PRIMARY_USER_ID,
                )
            )
            await session.flush()
            interactions = (
                Interaction(
                    id=next_interaction_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    company_id=company_id,
                    opportunity_id=opportunity_id,
                    interaction_type="workshop",
                    lifecycle_status="planned",
                    title="Technical review",
                    scheduled_start_at=next_interaction_at,
                    scheduled_end_at=next_interaction_at + timedelta(hours=1),
                    timezone="Australia/Sydney",
                    creation_origin="manual",
                    created_by_user_id=PRIMARY_USER_ID,
                ),
                Interaction(
                    id=prepared_interaction_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    company_id=company_id,
                    opportunity_id=opportunity_id,
                    interaction_type="phone_call",
                    lifecycle_status="planned",
                    title="Commercial follow-up",
                    scheduled_start_at=prepared_interaction_at,
                    scheduled_end_at=prepared_interaction_end,
                    timezone="Australia/Sydney",
                    creation_origin="manual",
                    call_direction="outbound",
                    created_by_user_id=PRIMARY_USER_ID,
                ),
                Interaction(
                    id=tomorrow_interaction_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    company_id=company_id,
                    opportunity_id=opportunity_id,
                    interaction_type="presentation",
                    lifecycle_status="planned",
                    title="Tomorrow presentation",
                    scheduled_start_at=end.astimezone(UTC) + timedelta(hours=2),
                    timezone="Australia/Sydney",
                    creation_origin="manual",
                    created_by_user_id=PRIMARY_USER_ID,
                ),
                Interaction(
                    id=yesterday_interaction_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    company_id=company_id,
                    opportunity_id=opportunity_id,
                    interaction_type="site_visit",
                    lifecycle_status="planned",
                    title="Yesterday site visit",
                    scheduled_start_at=start.astimezone(UTC) - timedelta(hours=1),
                    timezone="Australia/Sydney",
                    creation_origin="manual",
                    created_by_user_id=PRIMARY_USER_ID,
                ),
            )
            session.add_all(interactions)
            await session.flush()
            session.add_all(
                [
                    PreInteractionBrief(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_id=prepared_interaction_id,
                        company_id=company_id,
                        opportunity_id=opportunity_id,
                        source_context_fingerprint=hashlib.sha256(b"daily-test-brief").hexdigest(),
                        brief_version=1,
                        schema_version=1,
                        status="completed",
                        content_json={"test": "bounded"},
                        source_references_json=[],
                        created_by_user_id=PRIMARY_USER_ID,
                    ),
                    PreInteractionBrief(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_id=tomorrow_interaction_id,
                        company_id=company_id,
                        opportunity_id=opportunity_id,
                        source_context_fingerprint=hashlib.sha256(b"daily-test-tomorrow-brief").hexdigest(),
                        brief_version=1,
                        schema_version=1,
                        status="completed",
                        content_json={"test": "bounded"},
                        source_references_json=[],
                        created_by_user_id=PRIMARY_USER_ID,
                    ),
                ]
            )
            source_fingerprint = hashlib.sha256(b"daily-action-source").hexdigest()
            session.add(
                ActionProposal(
                    id=action_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    opportunity_id=opportunity_id,
                    action_type="create_task",
                    status="proposed",
                    priority="high",
                    audience="internal",
                    risk_class="internal_low_risk",
                    current_version=1,
                    source_fingerprint=source_fingerprint,
                    semantic_key=hashlib.sha256(b"daily-action-semantic").hexdigest(),
                    created_by_user_id=PRIMARY_USER_ID,
                    generated_at=now - timedelta(days=1),
                )
            )
            session.add(
                ActionProposalVersion(
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    action_id=action_id,
                    version=1,
                    title="Send security documentation",
                    description="Review the customer commitment.",
                    proposed_due_at=max(now - timedelta(hours=3), start_utc),
                    payload_json={"kind": "create_task", "title": "Send security documentation"},
                    source_refs_json=[],
                    provenance_summary="Final validated customer evidence.",
                    content_fingerprint=hashlib.sha256(b"daily-action-content").hexdigest(),
                    created_by_user_id=PRIMARY_USER_ID,
                )
            )
            for proposal_id, status, label, due_at in (
                (
                    approved_action_id,
                    "approved",
                    "Confirm approved pilot scope",
                    min(now + timedelta(hours=1), end.astimezone(UTC) - timedelta(minutes=5)),
                ),
                (rejected_action_id, "rejected", "Rejected historical action", now - timedelta(days=2)),
                (
                    completed_action_id,
                    "completed_manually",
                    "Completed historical action",
                    now - timedelta(days=2),
                ),
            ):
                encoded_id = str(proposal_id).encode()
                is_approved = status == "approved"
                session.add_all(
                    (
                        ActionProposal(
                            id=proposal_id,
                            organisation_id=PRIMARY_ORGANISATION_ID,
                            opportunity_id=opportunity_id,
                            action_type="create_task",
                            status=status,
                            priority="normal",
                            audience="internal",
                            risk_class="internal_low_risk",
                            current_version=1,
                            approved_version=1 if is_approved else None,
                            source_fingerprint=hashlib.sha256(b"source:" + encoded_id).hexdigest(),
                            semantic_key=hashlib.sha256(b"semantic:" + encoded_id).hexdigest(),
                            created_by_user_id=PRIMARY_USER_ID,
                            generated_at=now - timedelta(hours=2),
                            reviewed_by_user_id=PRIMARY_USER_ID if is_approved else None,
                            reviewed_at=now - timedelta(hours=1) if is_approved else None,
                            approved_at=now - timedelta(hours=1) if is_approved else None,
                            completed_by_user_id=(PRIMARY_USER_ID if status == "completed_manually" else None),
                            completed_at=(now - timedelta(hours=1) if status == "completed_manually" else None),
                        ),
                        ActionProposalVersion(
                            organisation_id=PRIMARY_ORGANISATION_ID,
                            action_id=proposal_id,
                            version=1,
                            title=label,
                            description="Daily status-boundary regression fixture.",
                            proposed_due_at=due_at,
                            payload_json={"kind": "create_task", "title": label},
                            source_refs_json=[],
                            provenance_summary="Final validated test evidence.",
                            content_fingerprint=hashlib.sha256(b"content:" + encoded_id).hexdigest(),
                            created_by_user_id=PRIMARY_USER_ID,
                        ),
                    )
                )
            session.add(
                OrganisationMethodologySetting(
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    selection="meddpicc",
                    custom_definition_id=None,
                    updated_by_user_id=PRIMARY_USER_ID,
                )
            )
            projection_content = MethodologyProjectionContent(
                opportunity_id=opportunity_id,
                methodology_key="meddpicc",
                methodology_name="MEDDPICC",
                definition_version=1,
                projection_version=1,
                engine_version=1,
                state_counts=MethodologyStateCounts(
                    confirmed=0,
                    partially_supported=0,
                    unknown=1,
                    conflicting=0,
                    stale=0,
                ),
                items=(
                    MethodologyProjectionItem(
                        field_key="economic_buyer",
                        display_name="Economic Buyer",
                        explanation="The person who owns the final commercial decision.",
                        required=True,
                        state="unknown",
                        conclusion=None,
                        sources=(),
                        conflicts=(),
                        last_supported_at=None,
                        freshness="not_applicable",
                        suggested_question="Who owns the final commercial decision?",
                        stage_expectation="evaluation",
                        reviews=(),
                    ),
                ),
                generated_at=now,
            )
            session.add(
                MethodologyProjection(
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    opportunity_id=opportunity_id,
                    methodology_kind="standard",
                    definition_key="meddpicc",
                    definition_id=None,
                    definition_version=1,
                    projection_version=1,
                    engine_version=1,
                    schema_version=1,
                    source_fingerprint=hashlib.sha256(b"daily-methodology").hexdigest(),
                    content_json=projection_content.as_json(),
                    generated_by_user_id=PRIMARY_USER_ID,
                    generated_at=now,
                )
            )
            await session.commit()
        await engine.dispose()
        return {
            "opportunity_id": str(opportunity_id),
            "interaction_id": str(next_interaction_id),
            "tomorrow_interaction_id": str(tomorrow_interaction_id),
            "yesterday_interaction_id": str(yesterday_interaction_id),
            "action_id": str(action_id),
            "approved_action_id": str(approved_action_id),
            "rejected_action_id": str(rejected_action_id),
            "completed_action_id": str(completed_action_id),
        }

    return asyncio.run(seed())


def test_daily_empty_state_is_bounded_and_does_not_invent_forecast(client: TestClient) -> None:
    response = client.get("/api/v1/daily", params={"timezone": "Australia/Sydney"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["timezone"] == "Australia/Sydney"
    assert body["userDisplayName"] == "Alex Morgan"
    assert body["topPriority"] is None
    assert body["todayInteractions"] == []
    assert body["actions"]["items"] == []
    assert body["dealAttention"]["items"] == []
    assert body["pipeline"]["state"] == "empty"
    assert body["hasOpportunities"] is False
    assert body["caughtUp"] is True
    assert body["availability"]["targets"] is False
    assert body["availability"]["forecast"] is False
    assert "forecastValue" not in response.text
    assert "evidence" not in response.text.casefold()
    assert "transcript" not in response.text.casefold()
    assert "provider" not in response.text.casefold()


def test_daily_open_telemetry_contains_metadata_only(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    _seed_daily_scenario()
    caplog.set_level(logging.INFO, logger="revenueos.daily")

    response = client.get("/api/v1/daily", params={"timezone": "Australia/Sydney"})

    assert response.status_code == 200, response.text
    records = [record for record in caplog.records if record.name == "revenueos.daily"]
    opened = next(record for record in records if record.getMessage() == "daily_opened")
    assert opened.organisation_id == str(PRIMARY_ORGANISATION_ID)
    assert opened.user_id == str(PRIMARY_USER_ID)
    assert opened.timezone == "Australia/Sydney"
    assert opened.top_priority_type == "interaction"
    logged = " ".join(str(record.__dict__) for record in records)
    assert "Qantas" not in logged
    assert "Technical review" not in logged
    assert "Economic Buyer" not in logged
    assert "Send security documentation" not in logged


def test_daily_prioritises_near_term_unprepared_interaction_and_deduplicates_action_reason(
    client: TestClient,
) -> None:
    identifiers = _seed_daily_scenario()

    response = client.get("/api/v1/daily", params={"timezone": "Australia/Sydney"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["topPriority"]["reasonCode"] == "interaction_needs_preparation"
    assert body["topPriority"]["sourceId"] == identifiers["interaction_id"]
    assert body["topPriority"]["ctaLabel"] == "Prepare for meeting"
    assert body["nextInteraction"]["id"] == identifiers["interaction_id"]
    assert [item["title"] for item in body["todayInteractions"]][:2] == [
        "Technical review",
        "Commercial follow-up",
    ]
    assert identifiers["tomorrow_interaction_id"] not in {item["id"] for item in body["todayInteractions"]}
    assert identifiers["yesterday_interaction_id"] not in {item["id"] for item in body["todayInteractions"]}
    assert body["actions"]["overdueCount"] == 1
    assert body["actions"]["dueTodayCount"] == 2
    assert body["actions"]["pendingReviewCount"] == 1
    assert body["actions"]["approvedOpenCount"] == 1
    assert body["actions"]["items"][0]["stateLabel"] == "Needs review"
    assert body["actions"]["items"][0]["ctaLabel"] == "Review"
    assert body["actions"]["items"][1]["stateLabel"] == "Approved — not complete"
    assert body["actions"]["items"][1]["ctaLabel"] == "Complete"
    visible_action_ids = {item["id"] for item in body["actions"]["items"]}
    assert identifiers["rejected_action_id"] not in visible_action_ids
    assert identifiers["completed_action_id"] not in visible_action_ids
    deal = body["dealAttention"]["items"][0]
    assert deal["opportunityId"] == identifiers["opportunity_id"]
    assert any(reason["text"] == "Economic Buyer is still unknown." for reason in deal["reasons"])
    assert not any(reason["code"] == "overdue_action" for reason in deal["reasons"])
    assert body["pipeline"]["state"] == "single_currency"
    assert body["pipeline"]["currencies"][0]["openValue"] == "420000.00"


def test_daily_never_combines_multiple_currencies(client: TestClient) -> None:
    _seed_daily_scenario(include_second_currency=True)

    response = client.get("/api/v1/daily", params={"timezone": "Australia/Sydney"})

    assert response.status_code == 200, response.text
    pipeline = response.json()["pipeline"]
    assert pipeline["state"] == "multiple_currencies"
    assert pipeline["currencyCount"] == 2
    assert [(item["currency"], item["openValue"]) for item in pipeline["currencies"]] == [
        ("AUD", "420000.00"),
        ("USD", "90000.00"),
    ]
    assert "separately by currency" in pipeline["safeMessage"]


def test_daily_keeps_unvalued_opportunities_out_of_monetary_currency_groups(client: TestClient) -> None:
    identifiers = _seed_daily_scenario()

    async def seed_unvalued() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            source = await session.get(Opportunity, uuid.UUID(identifiers["opportunity_id"]))
            assert source is not None
            session.add(
                Opportunity(
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    company_id=source.company_id,
                    name="Unvalued international opportunity",
                    stage="discovery",
                    status="open",
                    estimated_value=None,
                    currency=None,
                    owner_user_id=PRIMARY_USER_ID,
                )
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(seed_unvalued())
    response = client.get("/api/v1/daily", params={"timezone": "Australia/Sydney"})

    assert response.status_code == 200, response.text
    pipeline = response.json()["pipeline"]
    assert pipeline["state"] == "single_currency"
    assert pipeline["currencyCount"] == 1
    assert pipeline["unvaluedOpportunityCount"] == 1
    assert [item["currency"] for item in pipeline["currencies"]] == ["AUD"]


def test_daily_rejects_invalid_timezone(client: TestClient) -> None:
    response = client.get("/api/v1/daily", params={"timezone": "Sydney/Not-A-Timezone"})

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_timezone"


def test_daily_fails_closed_for_disabled_membership(client: TestClient) -> None:
    async def disable() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await session.execute(
                update(OrganisationMembership)
                .where(
                    OrganisationMembership.organisation_id == PRIMARY_ORGANISATION_ID,
                    OrganisationMembership.user_id == PRIMARY_USER_ID,
                )
                .values(status="disabled")
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(disable())
    response = client.get("/api/v1/daily", params={"timezone": "Australia/Sydney"})

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_daily_is_available_to_active_member_role(client: TestClient) -> None:
    async def set_role(role: str) -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await session.execute(
                update(OrganisationMembership)
                .where(
                    OrganisationMembership.organisation_id == PRIMARY_ORGANISATION_ID,
                    OrganisationMembership.user_id == PRIMARY_USER_ID,
                )
                .values(role=role)
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(set_role("member"))
    try:
        response = client.get("/api/v1/daily", params={"timezone": "Australia/Sydney"})
    finally:
        asyncio.run(set_role("admin"))

    assert response.status_code == 200, response.text


def test_daily_isolates_other_tenant_owned_work(client: TestClient) -> None:
    async def seed_other() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            company = Company(
                organisation_id=SECONDARY_ORGANISATION_ID,
                name="Other tenant account",
                status="active",
                owner_user_id=SECONDARY_USER_ID,
            )
            session.add(company)
            await session.flush()
            session.add(
                Opportunity(
                    organisation_id=SECONDARY_ORGANISATION_ID,
                    company_id=company.id,
                    name="Other tenant secret opportunity",
                    stage="proposal",
                    status="open",
                    estimated_value=Decimal("999999.00"),
                    currency="AUD",
                    owner_user_id=SECONDARY_USER_ID,
                )
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(seed_other())
    response = client.get("/api/v1/daily", params={"timezone": "Australia/Sydney"})

    assert response.status_code == 200, response.text
    assert "Other tenant" not in response.text
    assert response.json()["hasOpportunities"] is False


def test_existing_next_best_action_is_bounded_to_product_safe_recommendation() -> None:
    opportunity_id = uuid.uuid4()
    artifact_id = uuid.uuid4()
    rows = [
        DailyRecommendationRecord(
            artifact_id=artifact_id,
            opportunity_id=opportunity_id,
            opportunity_name="Qantas renewal",
            content_json={
                "overall_recommendation": "Confirm access to the economic buyer.",
                "priority": "high",
                "confidence": 0.9,
                "reasoning": ["Stakeholders: economic_buyer:not_identified."],
                "recommended_actions": [
                    {
                        "action": "Confirm access to the economic buyer.",
                        "reason": "Stakeholders: economic_buyer:not_identified.",
                        "priority": "high",
                        "confidence": 0.9,
                        "depends_on": ["stakeholders"],
                    }
                ],
            },
        )
    ]

    recommendations = RevenueOSDailyService._recommendations(rows)

    assert len(recommendations) == 1
    assert recommendations[0].source_id == artifact_id
    assert recommendations[0].recommendation == "Confirm access to the economic buyer."
    dumped = recommendations[0].model_dump(mode="json")
    assert "reasoning" not in dumped
    assert "confidence" not in dumped
    assert "provider" not in dumped


def test_daily_maps_revenue_brain_risk_and_conflict_to_controlled_text() -> None:
    def insight(change_type: str, opportunity_id: uuid.UUID) -> RevenueBrainInsight:
        from_snapshot_id = uuid.uuid4()
        to_snapshot_id = uuid.uuid4()
        capability = "risks_blockers" if change_type == "risk_introduced" else "executive_summary"
        return RevenueBrainInsight(
            organisation_id=PRIMARY_ORGANISATION_ID,
            company_id=uuid.uuid4(),
            opportunity_id=opportunity_id,
            scope="opportunity",
            scope_target_id=opportunity_id,
            from_snapshot_id=from_snapshot_id,
            to_snapshot_id=to_snapshot_id,
            reasoning_version=1,
            status="completed",
            content_json={
                "scope": "opportunity",
                "from_snapshot_id": str(from_snapshot_id),
                "to_snapshot_id": str(to_snapshot_id),
                "from_meeting_id": str(uuid.uuid4()),
                "to_meeting_id": str(uuid.uuid4()),
                "from_meeting_date": "2026-08-15",
                "to_meeting_date": "2026-08-16",
                "changes": [
                    {
                        "change_type": change_type,
                        "direction": "introduced" if change_type == "risk_introduced" else "unclear",
                        "importance": "high",
                        "title": "Raw customer-specific title",
                        "description": "Raw customer-specific explanation must not reach Daily.",
                        "confidence": 0.9,
                        "source_capabilities": [capability],
                        "evidence": [
                            {
                                "snapshot_id": str(to_snapshot_id),
                                "artefact_id": str(uuid.uuid4()),
                                "artefact_type": capability,
                                "entity_key": "risk:security",
                                "field": "severity",
                                "value": "high",
                            }
                        ],
                    }
                ],
                "summary": "A material supported change was identified.",
                "confidence": 0.9,
            },
        )

    risk_opportunity_id = uuid.uuid4()
    conflict_opportunity_id = uuid.uuid4()
    reasons = RevenueOSDailyService._brain_reasons(
        [
            insight("risk_introduced", risk_opportunity_id),
            insight("timeline_became_unclear", conflict_opportunity_id),
        ]
    )

    assert reasons[risk_opportunity_id].code == "unresolved_risk"
    assert reasons[risk_opportunity_id].text == "A material risk was identified."
    assert reasons[conflict_opportunity_id].code == "conflicting_evidence"
    assert reasons[conflict_opportunity_id].text == "Timeline needs clarification."
    assert "customer-specific" not in " ".join(reason.text for reason in reasons.values())


def test_daily_top_priority_hierarchy_is_deterministic() -> None:
    now = datetime.now(UTC)
    opportunity_id = uuid.uuid4()

    def interaction(
        state: Literal["active", "not_prepared", "capture_needed", "prepared"],
        *,
        starts_at: datetime,
    ) -> DailyInteraction:
        labels = {
            "active": ("Open Companion", "/companion"),
            "not_prepared": ("Prepare for meeting", "/preparation"),
            "capture_needed": ("Capture what happened", "/debrief"),
            "prepared": ("Prepare", "/preparation"),
        }
        label, href = labels[state]
        return DailyInteraction(
            id=uuid.uuid4(),
            title=f"{state} interaction",
            company_id=None,
            company_name="Qantas",
            opportunity_id=opportunity_id,
            opportunity_name="Network modernisation",
            interaction_type="workshop",
            lifecycle_status="in_progress" if state == "active" else "planned",
            starts_at=starts_at,
            preparation_state=state,
            context="Customer context",
            cta_label=label,
            href=href,
        )

    def action(
        *,
        timing: Literal["overdue", "upcoming"] = "upcoming",
        priority: Literal["high", "normal", "low"] = "high",
    ) -> DailyAction:
        return DailyAction(
            id=uuid.uuid4(),
            title="Review commitment",
            opportunity_id=opportunity_id,
            opportunity_name="Network modernisation",
            company_name="Qantas",
            priority=priority,
            review_status="proposed",
            timing=timing,
            due_at=now - timedelta(hours=1) if timing == "overdue" else now + timedelta(hours=5),
            state="needs_review",
            state_label="Needs review",
            cta_label="Review",
            href="/actions",
        )

    urgent_deal = DailyDealAttention(
        opportunity_id=opportunity_id,
        opportunity_name="Network modernisation",
        company_name="Qantas",
        estimated_value=Decimal("420000.00"),
        currency="AUD",
        expected_close_date=now.date() + timedelta(days=5),
        priority="urgent",
        reasons=[
            DailyDealReason(
                code="upcoming_close_with_blocker",
                text="Close date approaching with an unresolved gap.",
            )
        ],
        href="/opportunity",
    )
    recommendation = DailyRecommendation(
        source_id=uuid.uuid4(),
        opportunity_id=opportunity_id,
        opportunity_name="Network modernisation",
        recommendation="Confirm the economic buyer.",
        priority="high",
        reason="Existing Next Best Action from final validated intelligence.",
        href="/recommendation",
    )
    active = interaction("active", starts_at=now - timedelta(minutes=5))
    needs_prep = interaction("not_prepared", starts_at=now + timedelta(hours=2))
    capture = interaction("capture_needed", starts_at=now - timedelta(hours=1))
    upcoming = interaction("prepared", starts_at=now + timedelta(days=1))
    overdue = action(timing="overdue")
    high_action = action()

    def reason(
        interactions: list[DailyInteraction],
        actions: list[DailyAction],
        deals: list[DailyDealAttention],
        recommendations: list[DailyRecommendation],
    ) -> str:
        result = RevenueOSDailyService._top_priority(
            interactions,
            actions,
            deals,
            recommendations,
            now,
        )
        assert result is not None
        return result.reason_code

    assert (
        reason([active, needs_prep, capture, upcoming], [overdue], [urgent_deal], [recommendation])
        == "active_interaction"
    )
    assert (
        reason([needs_prep, capture, upcoming], [overdue], [urgent_deal], [recommendation])
        == "interaction_needs_preparation"
    )
    assert reason([capture, upcoming], [overdue], [urgent_deal], [recommendation]) == "overdue_high_priority_action"
    assert reason([capture, upcoming], [], [urgent_deal], [recommendation]) == "interaction_needs_capture"
    assert reason([upcoming], [], [urgent_deal], [recommendation]) == "time_sensitive_deal_blocker"
    assert reason([upcoming], [high_action], [], [recommendation]) == "high_priority_action"
    assert reason([upcoming], [], [], [recommendation]) == "next_best_action"
    assert reason([upcoming], [], [], []) == "next_upcoming_interaction"


def test_daily_maps_active_and_capture_needed_interactions_to_plain_ctas(client: TestClient) -> None:
    identifiers = _seed_daily_scenario()
    interaction_id = uuid.UUID(identifiers["interaction_id"])

    async def set_state(state: str) -> None:
        engine = create_async_engine(TEST_DB_URL)
        now = datetime.now(UTC)
        start, _ = _local_day_bounds()
        actual_start_at = max(now - timedelta(minutes=30), start.astimezone(UTC))
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await session.execute(
                update(ActionProposal)
                .where(ActionProposal.organisation_id == PRIMARY_ORGANISATION_ID)
                .values(status="rejected", rejected_at=now)
            )
            values: dict[str, object] = {
                "lifecycle_status": state,
                "actual_start_at": actual_start_at,
                "actual_end_at": max(now - timedelta(minutes=5), actual_start_at) if state == "completed" else None,
            }
            await session.execute(update(Interaction).where(Interaction.id == interaction_id).values(**values))
            await session.commit()
        await engine.dispose()

    asyncio.run(set_state("in_progress"))
    active = client.get("/api/v1/daily", params={"timezone": "Australia/Sydney"}).json()
    assert active["topPriority"]["reasonCode"] == "active_interaction"
    assert active["topPriority"]["ctaLabel"] == "Open Companion"

    asyncio.run(set_state("completed"))
    capture = client.get("/api/v1/daily", params={"timezone": "Australia/Sydney"}).json()
    assert capture["topPriority"]["reasonCode"] == "interaction_needs_capture"
    assert capture["topPriority"]["ctaLabel"] == "Capture what happened"


def test_daily_bounds_lists_and_query_count_does_not_scale_per_item(client: TestClient) -> None:
    identifiers = _seed_daily_scenario()
    opportunity_id = uuid.UUID(identifiers["opportunity_id"])

    async def seed_more() -> None:
        engine = create_async_engine(TEST_DB_URL)
        start, _ = _local_day_bounds()
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            for index in range(7):
                interaction_id = uuid.uuid4()
                action_id = uuid.uuid4()
                session.add_all(
                    (
                        Interaction(
                            id=interaction_id,
                            organisation_id=PRIMARY_ORGANISATION_ID,
                            opportunity_id=opportunity_id,
                            interaction_type="manual_interaction",
                            lifecycle_status="planned",
                            title=f"Bounded interaction {index}",
                            scheduled_start_at=start.astimezone(UTC) + timedelta(hours=12, minutes=index),
                            timezone="Australia/Sydney",
                            creation_origin="manual",
                            created_by_user_id=PRIMARY_USER_ID,
                        ),
                        ActionProposal(
                            id=action_id,
                            organisation_id=PRIMARY_ORGANISATION_ID,
                            opportunity_id=opportunity_id,
                            action_type="create_task",
                            status="proposed",
                            priority="normal",
                            audience="internal",
                            risk_class="internal_low_risk",
                            current_version=1,
                            source_fingerprint=hashlib.sha256(f"bound-source-{index}".encode()).hexdigest(),
                            semantic_key=hashlib.sha256(f"bound-semantic-{index}".encode()).hexdigest(),
                            created_by_user_id=PRIMARY_USER_ID,
                        ),
                        ActionProposalVersion(
                            organisation_id=PRIMARY_ORGANISATION_ID,
                            action_id=action_id,
                            version=1,
                            title=f"Bounded action {index}",
                            description="Bounded Daily regression fixture.",
                            proposed_due_at=None,
                            payload_json={"kind": "create_task", "title": f"Bounded action {index}"},
                            source_refs_json=[],
                            provenance_summary="Final validated test evidence.",
                            content_fingerprint=hashlib.sha256(f"bound-content-{index}".encode()).hexdigest(),
                            created_by_user_id=PRIMARY_USER_ID,
                        ),
                    )
                )
            await session.commit()
        await engine.dispose()

    asyncio.run(seed_more())
    select_count = 0

    def count_selects(*args: object) -> None:
        nonlocal select_count
        statement = str(args[2])
        if statement.lstrip().upper().startswith("SELECT"):
            select_count += 1

    engine = client.app.state.engine.sync_engine
    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        response = client.get("/api/v1/daily", params={"timezone": "Australia/Sydney"})
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["todayInteractions"]) == 5
    assert len(body["actions"]["items"]) == 5
    assert body["actions"]["truncated"] is True
    assert select_count <= 15


def test_daily_degrades_one_source_failure_without_exposing_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_daily_scenario()

    async def fail_actions(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise OperationalError("SELECT action_proposals", {}, RuntimeError("synthetic failure"))

    monkeypatch.setattr(DailyRepository, "actions", fail_actions)
    response = client.get("/api/v1/daily", params={"timezone": "Australia/Sydney"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["availability"]["actions"] is False
    assert body["availability"]["interactions"] is True
    assert body["actions"]["items"] == []
    assert "synthetic failure" not in response.text


def test_daily_does_not_show_new_user_state_when_opportunities_are_temporarily_unavailable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_daily_scenario()

    async def fail_opportunities(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise OperationalError("SELECT opportunities", {}, RuntimeError("synthetic failure"))

    monkeypatch.setattr(DailyRepository, "opportunities", fail_opportunities)
    response = client.get("/api/v1/daily", params={"timezone": "Australia/Sydney"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["availability"]["dealAttention"] is False
    assert body["hasOpportunities"] is True
    assert body["caughtUp"] is False
    assert body["todayInteractions"]
    assert "synthetic failure" not in response.text


def test_daily_respects_current_feature_availability(client: TestClient) -> None:
    _seed_daily_scenario()
    original_override = client.app.dependency_overrides[get_settings]
    disabled_settings = client.app.state.settings.model_copy(
        update={
            "feature_action_layer_enabled": False,
            "feature_revenue_brain_enabled": False,
            "feature_sales_methodology_enabled": False,
        }
    )
    client.app.dependency_overrides[get_settings] = lambda: disabled_settings
    try:
        response = client.get("/api/v1/daily", params={"timezone": "Australia/Sydney"})
    finally:
        client.app.dependency_overrides[get_settings] = original_override

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["actions"]["items"] == []
    assert body["recommendations"] == []
    assert body["availability"]["actions"] is False
    assert body["availability"]["recommendations"] is False
    assert body["availability"]["methodology"] is False
    assert body["availability"]["revenueBrain"] is False


def test_daily_hides_same_tenant_work_assigned_to_another_user(client: TestClient) -> None:
    async def seed_other_user() -> None:
        engine = create_async_engine(TEST_DB_URL)
        user_id = uuid.uuid4()
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add_all(
                (
                    User(
                        id=user_id,
                        external_auth_id=f"same-org-{user_id}",
                        email=f"same-org-{user_id}@example.test",
                        display_name="Another salesperson",
                    ),
                    OrganisationMembership(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=user_id,
                        role="member",
                    ),
                )
            )
            await session.flush()
            company = Company(
                organisation_id=PRIMARY_ORGANISATION_ID,
                name="Private assigned account",
                status="active",
                owner_user_id=user_id,
            )
            session.add(company)
            await session.flush()
            opportunity = Opportunity(
                organisation_id=PRIMARY_ORGANISATION_ID,
                company_id=company.id,
                name="Private assigned opportunity",
                stage="proposal",
                status="open",
                estimated_value=Decimal("777777.00"),
                currency="AUD",
                owner_user_id=user_id,
            )
            session.add(opportunity)
            await session.flush()
            session.add(
                Interaction(
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    company_id=company.id,
                    opportunity_id=opportunity.id,
                    interaction_type="phone_call",
                    lifecycle_status="planned",
                    title="Private assigned interaction",
                    scheduled_start_at=datetime.now(UTC) + timedelta(hours=1),
                    timezone="Australia/Sydney",
                    creation_origin="manual",
                    call_direction="outbound",
                    created_by_user_id=user_id,
                )
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(seed_other_user())
    response = client.get("/api/v1/daily", params={"timezone": "Australia/Sydney"})

    assert response.status_code == 200, response.text
    assert "Private assigned" not in response.text
    assert "777777" not in response.text
