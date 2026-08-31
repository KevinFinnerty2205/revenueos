from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid5

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.database import set_tenant_database_context
from revenueos.models import (
    Company,
    Contact,
    Interaction,
    Meeting,
    MeetingParticipant,
    Opportunity,
    OpportunityStageEvent,
)
from revenueos.pipeline_repositories import ensure_default_pipeline
from revenueos.sales_analytics_services import SalesAnalyticsService
from revenueos.sales_metric_registry import SALES_METRIC_DEFINITIONS, SALES_METRIC_REGISTRY
from revenueos.tenant import TenantContext

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, SECONDARY_USER_ID

NAMESPACE = UUID("0870261c-0458-4d70-ae23-bbd36546bbbe")


def fixture_id(label: str) -> UUID:
    return uuid5(NAMESPACE, label)


async def seed_sales_analytics(session_factory: async_sessionmaker[AsyncSession]) -> UUID:
    async with session_factory() as session, session.begin():
        await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
        pipeline, stages = await ensure_default_pipeline(session, PRIMARY_ORGANISATION_ID)
        by_key = {stage.stage_key: stage for stage in stages}
        company_id = fixture_id("company")
        second_company_id = fixture_id("company-two")
        contact_id = fixture_id("contact")
        session.add_all(
            (
                Company(
                    id=company_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    name="Analytics account",
                    status="prospect",
                    owner_user_id=PRIMARY_USER_ID,
                ),
                Company(
                    id=second_company_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    name="Unrelated account",
                    status="prospect",
                    owner_user_id=PRIMARY_USER_ID,
                ),
                Contact(
                    id=contact_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    company_id=company_id,
                    first_name="Casey",
                    last_name="Ng",
                    email="casey@example.test",
                    owner_user_id=PRIMARY_USER_ID,
                ),
            )
        )
        await session.flush()

        opportunity_specs = (
            ("won-aud", "won", "closed_won", date(2026, 2, 1), "solution_fit", Decimal("100.00"), "AUD"),
            ("lost", "lost", "closed_lost", date(2026, 2, 20), "timing", Decimal("80.00"), "AUD"),
            ("open", "open", "proposal", None, None, Decimal("70.00"), "AUD"),
            ("baseline", "open", "evaluation", None, None, Decimal("50.00"), "AUD"),
            ("reopened", "open", "discovery", None, None, Decimal("60.00"), "AUD"),
            ("won-usd", "won", "closed_won", date(2026, 3, 1), "commercial", Decimal("200.00"), "USD"),
        )
        created_dates = {
            "won-aud": datetime(2026, 1, 1, 1, tzinfo=UTC),
            "lost": datetime(2026, 1, 5, 1, tzinfo=UTC),
            "open": datetime(2026, 1, 10, 1, tzinfo=UTC),
            "baseline": datetime(2025, 1, 1, 1, tzinfo=UTC),
            "reopened": datetime(2026, 1, 2, 1, tzinfo=UTC),
            "won-usd": datetime(2026, 2, 1, 1, tzinfo=UTC),
        }
        opportunities: dict[str, Opportunity] = {}
        for label, status, stage_key, closed_at, reason, amount, currency in opportunity_specs:
            stage = by_key[stage_key]
            opportunity = Opportunity(
                id=fixture_id(f"opportunity-{label}"),
                organisation_id=PRIMARY_ORGANISATION_ID,
                company_id=company_id,
                name=f"Analytics {label}",
                stage=stage_key,
                status=status,
                estimated_value=amount,
                currency=currency,
                owner_user_id=PRIMARY_USER_ID,
                pipeline_id=pipeline.id,
                pipeline_stage_id=stage.id,
                stage_entered_at=None if label == "baseline" else created_dates[label],
                stage_tracking_started_at=(
                    datetime(2026, 1, 15, tzinfo=UTC) if label == "baseline" else created_dates[label]
                ),
                actual_close_date=closed_at,
                outcome_reason=reason,
                outcome_note="This sensitive seller note must never enter Insights." if closed_at else None,
                outcome_provenance="seller_reported" if closed_at else None,
                created_at=created_dates[label],
                updated_at=created_dates[label],
            )
            session.add(opportunity)
            opportunities[label] = opportunity
        await session.flush()

        def stage_event(
            label: str,
            event_label: str,
            to_key: str,
            changed_at: datetime,
            *,
            from_key: str | None = None,
            previous_entered_at: datetime | None = None,
            baseline: bool = False,
            reason: str | None = None,
            actual_close: date | None = None,
        ) -> OpportunityStageEvent:
            to_stage = by_key[to_key]
            from_stage = by_key[from_key] if from_key is not None else None
            return OpportunityStageEvent(
                id=fixture_id(f"event-{label}-{event_label}"),
                organisation_id=PRIMARY_ORGANISATION_ID,
                opportunity_id=opportunities[label].id,
                from_pipeline_id=pipeline.id if from_stage is not None else None,
                to_pipeline_id=pipeline.id,
                from_stage_id=from_stage.id if from_stage is not None else None,
                to_stage_id=to_stage.id,
                from_stage_name=from_stage.name if from_stage is not None else None,
                to_stage_name=to_stage.name,
                from_stage_type=from_stage.stage_type if from_stage is not None else None,
                to_stage_type=to_stage.stage_type,
                changed_by_user_id=PRIMARY_USER_ID,
                changed_at=changed_at,
                source="migration_baseline" if baseline else "system_initial" if from_stage is None else "manual",
                is_baseline=baseline,
                previous_stage_entered_at=previous_entered_at,
                outcome_reason=reason,
                outcome_note="Sensitive closure note" if reason else None,
                outcome_provenance="seller_reported" if reason else None,
                actual_close_date=actual_close,
                final_amount=opportunities[label].estimated_value if actual_close else None,
                final_currency=opportunities[label].currency if actual_close else None,
            )

        events = (
            stage_event("won-aud", "discovery", "discovery", datetime(2026, 1, 1, 1, tzinfo=UTC)),
            stage_event(
                "won-aud",
                "evaluation",
                "evaluation",
                datetime(2026, 1, 10, 1, tzinfo=UTC),
                from_key="discovery",
                previous_entered_at=datetime(2026, 1, 1, 1, tzinfo=UTC),
            ),
            stage_event(
                "won-aud",
                "proposal",
                "proposal",
                datetime(2026, 1, 20, 1, tzinfo=UTC),
                from_key="evaluation",
                previous_entered_at=datetime(2026, 1, 10, 1, tzinfo=UTC),
            ),
            stage_event(
                "won-aud",
                "won",
                "closed_won",
                datetime(2026, 2, 1, 1, tzinfo=UTC),
                from_key="proposal",
                previous_entered_at=datetime(2026, 1, 20, 1, tzinfo=UTC),
                reason="solution_fit",
                actual_close=date(2026, 2, 1),
            ),
            stage_event("lost", "discovery", "discovery", datetime(2026, 1, 5, 1, tzinfo=UTC)),
            stage_event(
                "lost",
                "qualification",
                "qualification",
                datetime(2026, 1, 10, 1, tzinfo=UTC),
                from_key="discovery",
                previous_entered_at=datetime(2026, 1, 5, 1, tzinfo=UTC),
            ),
            stage_event(
                "lost",
                "lost",
                "closed_lost",
                datetime(2026, 2, 20, 1, tzinfo=UTC),
                from_key="qualification",
                previous_entered_at=datetime(2026, 1, 10, 1, tzinfo=UTC),
                reason="timing",
                actual_close=date(2026, 2, 20),
            ),
            stage_event("open", "discovery", "discovery", datetime(2026, 1, 10, 1, tzinfo=UTC)),
            stage_event(
                "open",
                "proposal",
                "proposal",
                datetime(2026, 2, 1, 1, tzinfo=UTC),
                from_key="discovery",
                previous_entered_at=datetime(2026, 1, 10, 1, tzinfo=UTC),
            ),
            stage_event(
                "baseline",
                "baseline",
                "evaluation",
                datetime(2026, 1, 15, 1, tzinfo=UTC),
                baseline=True,
            ),
            stage_event("reopened", "discovery", "discovery", datetime(2026, 1, 2, 1, tzinfo=UTC)),
            stage_event(
                "reopened",
                "lost",
                "closed_lost",
                datetime(2026, 2, 1, 1, tzinfo=UTC),
                from_key="discovery",
                previous_entered_at=datetime(2026, 1, 2, 1, tzinfo=UTC),
                reason="budget",
                actual_close=date(2026, 2, 1),
            ),
            stage_event(
                "reopened",
                "again",
                "discovery",
                datetime(2026, 2, 10, 1, tzinfo=UTC),
                from_key="closed_lost",
                previous_entered_at=datetime(2026, 2, 1, 1, tzinfo=UTC),
            ),
            stage_event("won-usd", "discovery", "discovery", datetime(2026, 2, 1, 1, tzinfo=UTC)),
            stage_event(
                "won-usd",
                "won",
                "closed_won",
                datetime(2026, 3, 1, 1, tzinfo=UTC),
                from_key="discovery",
                previous_entered_at=datetime(2026, 2, 1, 1, tzinfo=UTC),
                reason="commercial",
                actual_close=date(2026, 3, 1),
            ),
        )
        session.add_all(events)

        interaction_specs = (
            ("call-one", "phone_call", datetime(2026, 1, 5, 2, tzinfo=UTC), company_id, contact_id, None),
            ("call-unassociated", "phone_call", datetime(2026, 1, 6, 2, tzinfo=UTC), None, None, None),
            ("call-immature", "phone_call", datetime(2026, 8, 5, 2, tzinfo=UTC), company_id, contact_id, None),
            (
                "meeting-progressed",
                "online_meeting",
                datetime(2026, 1, 15, 2, tzinfo=UTC),
                company_id,
                None,
                opportunities["won-aud"].id,
            ),
            (
                "meeting-no-progress",
                "face_to_face_meeting",
                datetime(2026, 1, 25, 2, tzinfo=UTC),
                company_id,
                None,
                opportunities["lost"].id,
            ),
            (
                "meeting-immature",
                "online_meeting",
                datetime(2026, 8, 10, 2, tzinfo=UTC),
                company_id,
                None,
                opportunities["open"].id,
            ),
        )
        interactions: dict[str, Interaction] = {}
        for (
            label,
            interaction_type,
            ended_at,
            related_company_id,
            related_contact_id,
            opportunity_id,
        ) in interaction_specs:
            interaction = Interaction(
                id=fixture_id(f"interaction-{label}"),
                organisation_id=PRIMARY_ORGANISATION_ID,
                company_id=related_company_id,
                contact_id=related_contact_id,
                opportunity_id=opportunity_id,
                interaction_type=interaction_type,
                lifecycle_status="completed",
                title=f"Analytics {label}",
                actual_start_at=ended_at - timedelta(minutes=20),
                actual_end_at=ended_at,
                timezone="Australia/Sydney",
                creation_origin="manual",
                call_direction="outbound" if interaction_type == "phone_call" else None,
                call_outcome="connected" if interaction_type == "phone_call" else None,
                created_by_user_id=PRIMARY_USER_ID,
                created_at=ended_at - timedelta(minutes=20),
                updated_at=ended_at,
            )
            session.add(interaction)
            interactions[label] = interaction
        await session.flush()
        for label in ("meeting-progressed", "meeting-no-progress", "meeting-immature"):
            interaction = interactions[label]
            meeting_id = fixture_id(f"meeting-{label}")
            session.add(
                Meeting(
                    id=meeting_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    interaction_id=interaction.id,
                    title=interaction.title,
                    meeting_date=interaction.actual_end_at,
                    meeting_type="remote",
                    status="completed",
                    company_id=interaction.company_id,
                    opportunity_id=interaction.opportunity_id,
                    owner_user_id=PRIMARY_USER_ID,
                    created_by=PRIMARY_USER_ID,
                    updated_by=PRIMARY_USER_ID,
                )
            )
            await session.flush()
            if label in {"meeting-progressed", "meeting-immature"}:
                session.add(
                    MeetingParticipant(
                        id=fixture_id(f"participant-{label}"),
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        meeting_id=meeting_id,
                        contact_id=contact_id,
                        attendance_status="attended",
                        role="attendee",
                    )
                )
        return pipeline.id


def seed(app: FastAPI) -> UUID:
    session_factory = app.state.session_factory
    assert isinstance(session_factory, async_sessionmaker)
    return asyncio.run(seed_sales_analytics(session_factory))


def params(pipeline_id: UUID | None = None) -> dict[str, str]:
    values = {
        "startDate": "2026-01-01",
        "endDate": "2026-08-30",
        "timezone": "Australia/Sydney",
    }
    if pipeline_id is not None:
        values["pipelineId"] = str(pipeline_id)
    return values


def test_metric_registry_is_unique_versioned_and_contains_no_surveillance_or_forecast_terms() -> None:
    assert len(SALES_METRIC_DEFINITIONS) == len(SALES_METRIC_REGISTRY)
    assert all(definition.definition_version == "1" for definition in SALES_METRIC_DEFINITIONS)
    rendered = " ".join(
        f"{definition.id} {definition.label} {definition.description}" for definition in SALES_METRIC_DEFINITIONS
    ).lower()
    for forbidden in ("login count", "screen time", "leaderboard", "rep score", "weighted pipeline", "predicted close"):
        assert forbidden not in rendered


def test_date_range_uses_local_dst_boundaries(app: FastAPI) -> None:
    async def boundaries() -> timedelta:
        session_factory = app.state.session_factory
        assert isinstance(session_factory, async_sessionmaker)
        async with session_factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            service = SalesAnalyticsService(
                session,
                TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin"),
                app.state.settings,
            )
            filters = await service.filters(
                start_date=date(2026, 10, 4),
                end_date=date(2026, 10, 4),
                timezone_name="Australia/Sydney",
                pipeline_id=None,
                owner_user_id=None,
                now=datetime(2026, 10, 5, tzinfo=UTC),
            )
            return filters.end_at - filters.start_at

    assert asyncio.run(boundaries()) == timedelta(hours=23)


def test_overview_funnel_activity_and_win_loss_reconcile_exactly(app: FastAPI, client: TestClient) -> None:
    pipeline_id = seed(app)

    overview_response = client.get("/api/v1/insights/sales/overview", params=params())
    assert overview_response.status_code == 200, overview_response.text
    overview = overview_response.json()
    assert overview["openOpportunityCount"] == 3
    assert overview["opportunitiesCreatedCount"] == 5
    assert overview["wonCount"] == 2
    assert overview["lostCount"] == 1
    assert overview["closedCount"] == 3
    assert overview["winRate"] == "66.7"
    assert overview["medianSalesCycleDays"] == "31.0"
    assert {item["currency"]: item["amount"] for item in overview["wonValues"]} == {
        "AUD": "100.00",
        "USD": "200.00",
    }

    funnel_response = client.get("/api/v1/insights/sales/funnel", params=params(pipeline_id))
    assert funnel_response.status_code == 200, funnel_response.text
    funnel = funnel_response.json()
    assert funnel["cohortCount"] == 5
    assert funnel["currentWonCount"] == 2
    assert funnel["currentLostCount"] == 1
    assert funnel["coverage"]["baselineOnlyOpportunityCount"] == 1
    discovery = next(stage for stage in funnel["stages"] if stage["stageName"] == "Discovery")
    assert discovery == {
        **discovery,
        "enteredCount": 5,
        "advancedCount": 4,
        "stillOpenCount": 1,
        "closedLostCount": 0,
    }
    evaluation = next(stage for stage in funnel["stages"] if stage["stageName"] == "Evaluation")
    assert evaluation["enteredCount"] == 1
    evaluation_duration = next(stage for stage in funnel["stageDurations"] if stage["stageName"] == "Evaluation")
    assert evaluation_duration["completedIntervalCount"] == 1
    qualification = next(stage for stage in funnel["stages"] if stage["stageName"] == "Qualification")
    assert "baseline" in funnel["coverage"]["disclosure"].lower()

    activity_response = client.get("/api/v1/insights/sales/activity", params=params())
    assert activity_response.status_code == 200, activity_response.text
    activity = activity_response.json()
    assert activity["phoneCallsCompletedCount"] == 3
    assert activity["meetingsCompletedCount"] == 3
    assert activity["callsFollowedByMeeting"] == {
        "cohortCount": 3,
        "eligibleMatureCount": 1,
        "followedByOutcomeCount": 1,
        "rate": "100.0",
        "immatureCount": 1,
        "excludedUnassociatedCount": 1,
        "excludedUntrackedCount": 0,
        "windowDays": 30,
    }
    assert activity["meetingsFollowedByProgression"]["eligibleMatureCount"] == 2
    assert activity["meetingsFollowedByProgression"]["followedByOutcomeCount"] == 1
    assert activity["meetingsFollowedByProgression"]["rate"] == "50.0"
    assert "causation" in activity["associationDisclosure"].lower()
    assert activity["liveOutreachSentCount"] == 0

    win_loss_response = client.get("/api/v1/insights/sales/win-loss", params=params())
    assert win_loss_response.status_code == 200, win_loss_response.text
    win_loss = win_loss_response.json()
    assert win_loss["reasonProvenance"] == "seller_reported"
    assert win_loss["notesAggregated"] is False
    assert "sensitive" not in win_loss_response.text.lower()
    assert {item["reason"]: item["count"] for item in win_loss["wonReasons"]} == {
        "commercial": 1,
        "solution_fit": 1,
    }
    assert win_loss["lostReasons"] == [{"reason": "timing", "label": "Timing", "count": 1, "percentage": "100.0"}]
    assert win_loss["lossStages"] == [
        {
            "stageId": qualification["stageId"],
            "stageName": "Qualification",
            "count": 1,
        }
    ]
    assert {(item["outcome"], item["currency"]) for item in win_loss["values"]} == {
        ("won", "AUD"),
        ("won", "USD"),
        ("lost", "AUD"),
    }
    for forbidden in ("probability", "weighted", "forecast", "leaderboard", "click", "screen time"):
        assert forbidden not in win_loss_response.text.lower()


def test_metric_observation_requires_currency_and_filters_fail_closed(app: FastAPI, client: TestClient) -> None:
    seed(app)
    missing_currency = client.get("/api/v1/insights/sales/metrics/won_value", params=params())
    assert missing_currency.status_code == 422
    observation = client.get(
        "/api/v1/insights/sales/metrics/won_value",
        params={**params(), "currency": "usd"},
    )
    assert observation.status_code == 200, observation.text
    assert observation.json()["value"] == "200.00"
    assert observation.json()["definitionVersion"] == "1"

    wrong_tenant_pipeline = client.get(
        "/api/v1/insights/sales/overview",
        params={**params(), "pipelineId": "00000000-0000-4000-8000-000000000099"},
    )
    assert wrong_tenant_pipeline.status_code == 404
    future = client.get(
        "/api/v1/insights/sales/overview",
        params={**params(), "endDate": "2099-12-31"},
    )
    assert future.status_code == 422

    other_tenant_owner = client.get(
        "/api/v1/insights/sales/overview",
        params={**params(), "ownerUserId": str(SECONDARY_USER_ID)},
    )
    assert other_tenant_owner.status_code == 404

    no_closed = client.get(
        "/api/v1/insights/sales/overview",
        params={
            "startDate": "2026-04-01",
            "endDate": "2026-04-30",
            "timezone": "Australia/Sydney",
        },
    )
    assert no_closed.status_code == 200
    assert no_closed.json()["winRate"] is None


def test_sales_insights_feature_flag_fails_closed(app: FastAPI, client: TestClient) -> None:
    app.state.settings.feature_sales_analytics_enabled = False
    response = client.get("/api/v1/insights/sales/metadata")
    assert response.status_code == 404
    assert response.json()["code"] == "feature_unavailable"
