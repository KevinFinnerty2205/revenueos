from __future__ import annotations

import asyncio
import calendar
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.auth import AuthenticatedUser, get_current_user
from revenueos.database import set_tenant_database_context
from revenueos.models import (
    Company,
    Opportunity,
    OpportunityStageEvent,
    OrganisationMembership,
    SalesForecastJudgment,
    SalesForecastJudgmentRevision,
    SalesForecastPeriod,
    SalesForecastReviewerJudgment,
    SalesForecastReviewerRevision,
    SalesTarget,
    SalesTargetRevision,
    User,
)
from revenueos.pipeline_repositories import ensure_default_pipeline

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, SECONDARY_ORGANISATION_ID

PEER_USER_ID = UUID("00000000-0000-4000-8000-000000000031")


def fixture_id(label: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"revenueos-wo-038-{label}")


def primary_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=PRIMARY_USER_ID,
        external_auth_id="user_dev_001",
        display_name="Alex Morgan",
        email="alex@example.test",
        organisation_id=PRIMARY_ORGANISATION_ID,
        organisation_name="Example Revenue Team",
        organisation_slug="example-revenue-team",
        role="admin",
        auth_mode="mock",
    )


def peer_user() -> AuthenticatedUser:
    return replace(
        primary_user(),
        user_id=PEER_USER_ID,
        external_auth_id="user_forecast_peer",
        display_name="Priya Seller",
        email="priya-forecast@example.test",
        role="member",
    )


def quarter_bounds(value: date) -> tuple[date, date]:
    start_month = ((value.month - 1) // 3) * 3 + 1
    start = date(value.year, start_month, 1)
    end_month = start_month + 2
    return start, date(value.year, end_month, calendar.monthrange(value.year, end_month)[1])


async def seed_forecast_data(session_factory: async_sessionmaker[AsyncSession]) -> None:
    now = datetime.now(UTC)
    async with session_factory() as session, session.begin():
        await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
        if await session.get(Company, fixture_id("company")) is not None:
            return
        if await session.get(User, PEER_USER_ID) is None:
            session.add(
                User(
                    id=PEER_USER_ID,
                    external_auth_id="user_forecast_peer",
                    email="priya-forecast@example.test",
                    display_name="Priya Seller",
                )
            )
            session.add(
                OrganisationMembership(
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    user_id=PEER_USER_ID,
                    role="member",
                    status="active",
                )
            )
            await session.flush()
        pipeline, stages = await ensure_default_pipeline(session, PRIMARY_ORGANISATION_ID)
        negotiation = next(stage for stage in stages if stage.stage_key == "negotiation")
        discovery = next(stage for stage in stages if stage.stage_key == "discovery")
        won_stage = next(stage for stage in stages if stage.stage_type == "won")
        lost_stage = next(stage for stage in stages if stage.stage_type == "lost")
        company = Company(
            id=fixture_id("company"),
            organisation_id=PRIMARY_ORGANISATION_ID,
            name="Forecast fixture account",
            status="active",
            owner_user_id=PRIMARY_USER_ID,
        )
        session.add(company)
        await session.flush()
        historical_close = (now - timedelta(days=120)).date()
        for index in range(12):
            won = index < 8
            opportunity = Opportunity(
                id=fixture_id(f"historical-{index}"),
                organisation_id=PRIMARY_ORGANISATION_ID,
                company_id=company.id,
                name=f"Historical negotiation {index}",
                stage="closed_won" if won else "closed_lost",
                status="won" if won else "lost",
                estimated_value=Decimal("10000.00"),
                currency="AUD",
                expected_close_date=historical_close,
                owner_user_id=PRIMARY_USER_ID,
                pipeline_id=pipeline.id,
                pipeline_stage_id=won_stage.id if won else lost_stage.id,
                stage_tracking_started_at=now - timedelta(days=180),
                actual_close_date=historical_close,
                outcome_reason="solution_fit" if won else "timing",
                outcome_provenance="seller_reported",
                created_at=now - timedelta(days=200),
                updated_at=now - timedelta(days=120),
            )
            session.add(opportunity)
            session.add(
                OpportunityStageEvent(
                    id=fixture_id(f"historical-event-{index}"),
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    opportunity_id=opportunity.id,
                    to_pipeline_id=pipeline.id,
                    to_stage_id=negotiation.id,
                    to_stage_name=negotiation.name,
                    to_stage_type="open",
                    changed_by_user_id=PRIMARY_USER_ID,
                    changed_at=now - timedelta(days=150),
                    source="manual",
                    is_baseline=False,
                )
            )
        current_values = (
            ("northstar", "Northstar", Decimal("180000.00"), "AUD", negotiation.id, "negotiation"),
            ("bluepeak", "BluePeak", Decimal("100000.00"), "AUD", negotiation.id, "negotiation"),
            ("atlas", "Atlas", Decimal("80000.00"), "AUD", negotiation.id, "negotiation"),
            ("harbour", "Harbour", Decimal("50000.00"), "AUD", negotiation.id, "negotiation"),
            ("unvalued", "Unvalued commit", None, None, negotiation.id, "negotiation"),
            ("sparse", "Sparse stage", Decimal("25000.00"), "AUD", discovery.id, "discovery"),
            ("usd", "USD expansion", Decimal("70000.00"), "USD", negotiation.id, "negotiation"),
        )
        for key, name, amount, currency, stage_id, legacy_stage in current_values:
            session.add(
                Opportunity(
                    id=fixture_id(key),
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    company_id=company.id,
                    name=name,
                    stage=legacy_stage,
                    status="open",
                    estimated_value=amount,
                    currency=currency,
                    expected_close_date=now.date(),
                    owner_user_id=PRIMARY_USER_ID,
                    pipeline_id=pipeline.id,
                    pipeline_stage_id=stage_id,
                    stage_entered_at=now - timedelta(days=12),
                    stage_tracking_started_at=now - timedelta(days=60),
                    created_at=now - timedelta(days=90),
                    updated_at=now,
                )
            )
        session.add(
            Opportunity(
                id=fixture_id("missing-close"),
                organisation_id=PRIMARY_ORGANISATION_ID,
                company_id=company.id,
                name="Missing close date",
                stage="negotiation",
                status="open",
                estimated_value=Decimal("30000.00"),
                currency="AUD",
                owner_user_id=PRIMARY_USER_ID,
                pipeline_id=pipeline.id,
                pipeline_stage_id=negotiation.id,
                created_at=now - timedelta(days=30),
                updated_at=now,
            )
        )
        session.add(
            Opportunity(
                id=fixture_id("actual-won"),
                organisation_id=PRIMARY_ORGANISATION_ID,
                company_id=company.id,
                name="Actual won this period",
                stage="closed_won",
                status="won",
                estimated_value=Decimal("54000.00"),
                currency="AUD",
                expected_close_date=now.date(),
                owner_user_id=PRIMARY_USER_ID,
                pipeline_id=pipeline.id,
                pipeline_stage_id=won_stage.id,
                actual_close_date=now.date(),
                outcome_reason="solution_fit",
                outcome_provenance="seller_reported",
                created_at=now - timedelta(days=45),
                updated_at=now,
            )
        )
        period_start, period_end = quarter_bounds(now.date())
        target = SalesTarget(
            id=fixture_id("target"),
            organisation_id=PRIMARY_ORGANISATION_ID,
            metric_id="won_value",
            metric_definition_version="1",
            scope="organisation",
            origin="admin_assigned",
            period_type="quarter",
            period_start=period_start,
            period_end=period_end,
            timezone="UTC",
            currency="AUD",
            created_by_user_id=PRIMARY_USER_ID,
        )
        session.add(target)
        session.add(
            SalesTargetRevision(
                id=fixture_id("target-revision"),
                organisation_id=PRIMARY_ORGANISATION_ID,
                target_id=target.id,
                revision_number=1,
                goal_value=Decimal("150000.00"),
                created_by_user_id=PRIMARY_USER_ID,
            )
        )
        previous_month_end = period_start - timedelta(days=1)
        previous_month_start = previous_month_end.replace(day=1)
        past_period = SalesForecastPeriod(
            id=fixture_id("past-period"),
            organisation_id=PRIMARY_ORGANISATION_ID,
            period_type="month",
            period_start=previous_month_start,
            period_end=previous_month_end,
            timezone="UTC",
            created_by_user_id=PRIMARY_USER_ID,
            created_at=datetime.combine(previous_month_start, datetime.min.time(), UTC),
        )
        session.add(past_period)
        await session.flush()
        for index, (category, won) in enumerate((("commit", True), ("likely", True), ("possible", False))):
            opportunity = Opportunity(
                id=fixture_id(f"calibration-{index}"),
                organisation_id=PRIMARY_ORGANISATION_ID,
                company_id=company.id,
                name=f"Calibration {category}",
                stage="closed_won" if won else "closed_lost",
                status="won" if won else "lost",
                estimated_value=Decimal("10000.00"),
                currency="AUD",
                expected_close_date=previous_month_end,
                owner_user_id=PRIMARY_USER_ID,
                pipeline_id=pipeline.id,
                pipeline_stage_id=won_stage.id if won else lost_stage.id,
                actual_close_date=previous_month_end if won else previous_month_end,
                outcome_reason="solution_fit" if won else "timing",
                outcome_provenance="seller_reported",
                created_at=datetime.combine(previous_month_start, datetime.min.time(), UTC),
                updated_at=datetime.combine(previous_month_end, datetime.min.time(), UTC),
            )
            judgment = SalesForecastJudgment(
                id=fixture_id(f"calibration-judgment-{index}"),
                organisation_id=PRIMARY_ORGANISATION_ID,
                period_id=past_period.id,
                opportunity_id=opportunity.id,
                created_at=datetime.combine(previous_month_start, datetime.min.time(), UTC),
            )
            session.add(opportunity)
            await session.flush()
            session.add(judgment)
            await session.flush()
            session.add(
                SalesForecastJudgmentRevision(
                    id=fixture_id(f"calibration-revision-{index}"),
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    judgment_id=judgment.id,
                    revision_number=1,
                    category=category,
                    created_by_user_id=PRIMARY_USER_ID,
                    owner_user_id_snapshot=PRIMARY_USER_ID,
                    amount_snapshot=Decimal("10000.00"),
                    currency_snapshot="AUD",
                    expected_close_date_snapshot=previous_month_end,
                    pipeline_id_snapshot=pipeline.id,
                    pipeline_name_snapshot=pipeline.name,
                    stage_id_snapshot=negotiation.id,
                    stage_name_snapshot=negotiation.name,
                    opportunity_status_snapshot="open",
                    model_version="forecast_historical_stage_outcome_v1",
                    model_status="insufficient_sample",
                    model_won_count=0,
                    model_lost_count=0,
                    model_minimum_sample=10,
                    model_lookback_start=previous_month_end - timedelta(days=730),
                    model_lookback_end=previous_month_start,
                    created_at=datetime.combine(previous_month_start, datetime.min.time(), UTC),
                )
            )
            if index == 0:
                session.add(
                    SalesForecastJudgmentRevision(
                        id=fixture_id("calibration-revision-after-period"),
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        judgment_id=judgment.id,
                        revision_number=2,
                        category="possible",
                        created_by_user_id=PRIMARY_USER_ID,
                        owner_user_id_snapshot=PRIMARY_USER_ID,
                        amount_snapshot=Decimal("10000.00"),
                        currency_snapshot="AUD",
                        expected_close_date_snapshot=previous_month_end,
                        pipeline_id_snapshot=pipeline.id,
                        pipeline_name_snapshot=pipeline.name,
                        stage_id_snapshot=negotiation.id,
                        stage_name_snapshot=negotiation.name,
                        opportunity_status_snapshot="open",
                        model_version="forecast_historical_stage_outcome_v1",
                        model_status="insufficient_sample",
                        model_won_count=0,
                        model_lost_count=0,
                        model_minimum_sample=10,
                        model_lookback_start=previous_month_end - timedelta(days=730),
                        model_lookback_end=previous_month_end,
                        created_at=datetime.combine(
                            previous_month_end + timedelta(days=2),
                            datetime.min.time(),
                            UTC,
                        ),
                    )
                )


def seed(app: FastAPI) -> None:
    session_factory = app.state.session_factory
    assert isinstance(session_factory, async_sessionmaker)
    asyncio.run(seed_forecast_data(session_factory))


def current_quarter_params(currency: str = "AUD") -> dict[str, str]:
    return {
        "periodType": "quarter",
        "periodAnchor": datetime.now(UTC).date().isoformat(),
        "currency": currency,
    }


def review(client: TestClient, opportunity_id: UUID, category: str) -> dict[str, object]:
    forecast = client.get("/api/v1/forecast", params=current_quarter_params()).json()
    item = next(item for item in forecast["opportunities"] if item["opportunityId"] == str(opportunity_id))
    expected = item["judgment"]["revisionNumber"] if item["judgment"] is not None else 0
    response = client.post(
        f"/api/v1/forecast/opportunities/{opportunity_id}/judgments",
        json={
            "periodType": "quarter",
            "periodAnchor": datetime.now(UTC).date().isoformat(),
            "category": category,
            "expectedRevisionNumber": expected,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_forecast_metadata_declares_the_transparent_model_and_no_probability(client: TestClient, app: FastAPI) -> None:
    seed(app)
    response = client.get("/api/v1/forecast/metadata")
    assert response.status_code == 200, response.text
    metadata = response.json()
    assert metadata["modelVersion"] == "forecast_historical_stage_outcome_v1"
    assert metadata["modelLookbackDays"] == 730
    assert metadata["modelMinimumSample"] == 10
    assert metadata["categories"] == ["commit", "likely", "possible", "not_this_period"]
    assert metadata["supportedPeriodTypes"] == ["month", "quarter"]
    assert "probability" not in response.text.lower()
    assert client.get("/api/v1/beta/capabilities").json()["featureFlags"]["salesForecasting"] is True


def test_seller_range_actual_target_and_historical_baseline_remain_separate(
    client: TestClient,
    app: FastAPI,
) -> None:
    seed(app)
    review(client, fixture_id("bluepeak"), "commit")
    review(client, fixture_id("northstar"), "likely")
    review(client, fixture_id("atlas"), "possible")
    review(client, fixture_id("unvalued"), "commit")
    response = client.get("/api/v1/forecast", params=current_quarter_params())
    assert response.status_code == 200, response.text
    forecast = response.json()
    assert forecast["actual"]["amount"] == "54000.00"
    assert forecast["actual"]["metricId"] == "won_value"
    assert forecast["targets"] == [
        {
            "id": str(fixture_id("target")),
            "label": "Organisation target",
            "scope": "organisation",
            "origin": "admin_assigned",
            "targetValue": "150000.00",
        }
    ]
    seller = forecast["sellerForecast"]
    assert seller["commit"] == {"amount": "100000.00", "opportunityCount": 2, "unvaluedCount": 1}
    assert seller["likely"]["amount"] == "280000.00"
    assert seller["possible"]["amount"] == "360000.00"
    assert seller["unreviewedCount"] == 2
    baseline = forecast["revenueosBaseline"]
    assert baseline["expectedContribution"] == "273333.33"
    assert baseline["coveredOpportunityCount"] == 4
    assert baseline["uncoveredOpportunityCount"] == 1
    assert baseline["unvaluedOpportunityCount"] == 1
    northstar = next(item for item in forecast["opportunities"] if item["opportunityName"] == "Northstar")
    assert northstar["historicalBaseline"]["wonCount"] == 8
    assert northstar["historicalBaseline"]["sampleSize"] == 12
    assert northstar["historicalBaseline"]["observedWinRate"] == "66.7"
    assert northstar["historicalBaseline"]["expectedContribution"] == "120000.00"
    assert "have no fixed probability weights" in response.text.lower()


def test_sparse_history_missing_close_and_currency_are_honest(client: TestClient, app: FastAPI) -> None:
    seed(app)
    aud = client.get("/api/v1/forecast", params=current_quarter_params()).json()
    sparse = next(item for item in aud["opportunities"] if item["opportunityName"] == "Sparse stage")
    assert sparse["historicalBaseline"]["status"] == "insufficient_sample"
    assert sparse["historicalBaseline"]["expectedContribution"] is None
    assert "no fallback rate" in sparse["historicalBaseline"]["explanation"].lower()
    assert aud["inputQuality"]["missingExpectedCloseCount"] == 1
    assert all(item["opportunityName"] != "Missing close date" for item in aud["opportunities"])
    usd = client.get("/api/v1/forecast", params=current_quarter_params("USD")).json()
    assert usd["currency"] == "USD"
    assert usd["totalOpportunities"] == 2  # USD-valued plus the explicitly unvalued Opportunity.
    assert all(item["currency"] in {"USD", None} for item in usd["opportunities"])
    assert "convert" not in usd["sellerForecast"]["disclosure"].lower()


def test_owner_only_versioning_stale_review_and_client_forgery_denial(
    client: TestClient,
    app: FastAPI,
) -> None:
    seed(app)
    first = review(client, fixture_id("northstar"), "likely")
    first_revision = first["revisions"][0]
    second = review(client, fixture_id("northstar"), "commit")
    assert [item["category"] for item in second["revisions"][:2]] == ["commit", "likely"]
    assert second["revisions"][1]["id"] == first_revision["id"]

    forged = client.post(
        f"/api/v1/forecast/opportunities/{fixture_id('atlas')}/judgments",
        json={
            "periodType": "quarter",
            "periodAnchor": datetime.now(UTC).date().isoformat(),
            "category": "likely",
            "expectedRevisionNumber": 0,
            "probability": 73,
            "amount": "999999",
            "historicalRate": "99.0",
        },
    )
    assert forged.status_code == 422

    async def change_amount(value: Decimal) -> None:
        session_factory = app.state.session_factory
        assert isinstance(session_factory, async_sessionmaker)
        async with session_factory() as session, session.begin():
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            opportunity = await session.get(Opportunity, fixture_id("northstar"))
            assert opportunity is not None
            opportunity.estimated_value = value

    asyncio.run(change_amount(Decimal("181000.00")))
    changed = client.get("/api/v1/forecast", params=current_quarter_params()).json()
    northstar = next(item for item in changed["opportunities"] if item["opportunityName"] == "Northstar")
    assert northstar["judgment"]["category"] == "commit"
    assert northstar["judgment"]["staleReasons"] == ["amount_changed"]
    review(client, fixture_id("northstar"), "commit")

    app.dependency_overrides[get_current_user] = lambda: peer_user()
    try:
        denied = client.post(
            f"/api/v1/forecast/opportunities/{fixture_id('northstar')}/judgments",
            json={
                "periodType": "quarter",
                "periodAnchor": datetime.now(UTC).date().isoformat(),
                "category": "possible",
                "expectedRevisionNumber": 3,
            },
        )
        assert denied.status_code == 403
        own = client.get("/api/v1/forecast", params=current_quarter_params())
        assert own.status_code == 200
        assert own.json()["ownerUserId"] == str(PEER_USER_ID)
        other = client.get(
            "/api/v1/forecast",
            params={**current_quarter_params(), "ownerUserId": str(PRIMARY_USER_ID)},
        )
        assert other.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_closed_won_leaves_remaining_forecast_and_actual_reuses_sales_metric(
    client: TestClient,
    app: FastAPI,
) -> None:
    seed(app)
    review(client, fixture_id("bluepeak"), "commit")
    manager_review = client.post(
        f"/api/v1/forecast/opportunities/{fixture_id('bluepeak')}/manager-judgments",
        json={
            "periodType": "quarter",
            "periodAnchor": datetime.now(UTC).date().isoformat(),
            "category": "commit",
            "expectedRevisionNumber": 0,
        },
    )
    assert manager_review.status_code == 200, manager_review.text
    before = client.get("/api/v1/forecast", params=current_quarter_params()).json()
    before_actual = Decimal(before["actual"]["amount"])

    async def set_state(status: str) -> None:
        session_factory = app.state.session_factory
        assert isinstance(session_factory, async_sessionmaker)
        async with session_factory() as session, session.begin():
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            opportunity = await session.get(Opportunity, fixture_id("bluepeak"))
            assert opportunity is not None
            _, stages = await ensure_default_pipeline(session, PRIMARY_ORGANISATION_ID)
            if status == "won":
                won_stage = next(stage for stage in stages if stage.stage_type == "won")
                opportunity.status = "won"
                opportunity.stage = "closed_won"
                opportunity.pipeline_stage_id = won_stage.id
                opportunity.actual_close_date = datetime.now(UTC).date()
            else:
                negotiation = next(stage for stage in stages if stage.stage_key == "negotiation")
                opportunity.status = "open"
                opportunity.stage = "negotiation"
                opportunity.pipeline_stage_id = negotiation.id
                opportunity.actual_close_date = None

    asyncio.run(set_state("won"))
    after = client.get("/api/v1/forecast", params=current_quarter_params()).json()
    assert all(item["opportunityName"] != "BluePeak" for item in after["opportunities"])
    assert Decimal(after["managerForecast"]["commit"]["amount"]) == Decimal(
        before["managerForecast"]["commit"]["amount"]
    ) - Decimal("100000.00")
    assert Decimal(after["actual"]["amount"]) == before_actual + Decimal("100000.00")
    metric = client.get(
        "/api/v1/insights/sales/metrics/won_value",
        params={
            "startDate": after["period"]["periodStart"],
            "endDate": after["actual"]["calculatedThrough"],
            "timezone": after["period"]["timezone"],
            "currency": "AUD",
        },
    )
    assert metric.status_code == 200
    assert metric.json()["value"] == after["actual"]["amount"]
    history = client.get(
        f"/api/v1/forecast/opportunities/{fixture_id('bluepeak')}/history",
        params={"periodType": "quarter", "periodAnchor": datetime.now(UTC).date().isoformat()},
    )
    assert history.status_code == 200
    assert history.json()["revisions"]
    closed_attention = client.get("/api/v1/manager/deal-attention", params={"pageSize": 50}).json()
    assert all(item["opportunityName"] != "BluePeak" for item in closed_attention["items"])
    asyncio.run(set_state("open"))
    reopened_attention = client.get("/api/v1/manager/deal-attention", params={"pageSize": 50}).json()
    assert any(item["opportunityName"] == "BluePeak" for item in reopened_attention["items"])


def test_past_period_is_locked_and_calibration_is_descriptive(client: TestClient, app: FastAPI) -> None:
    seed(app)
    past_anchor = datetime.now(UTC).date().replace(day=1) - timedelta(days=1)
    blocked = client.post(
        f"/api/v1/forecast/opportunities/{fixture_id('northstar')}/judgments",
        json={
            "periodType": "month",
            "periodAnchor": past_anchor.isoformat(),
            "category": "commit",
            "expectedRevisionNumber": 0,
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "past_forecast_locked"
    manager_blocked = client.post(
        f"/api/v1/forecast/opportunities/{fixture_id('northstar')}/manager-judgments",
        json={
            "periodType": "month",
            "periodAnchor": past_anchor.isoformat(),
            "category": "likely",
            "expectedRevisionNumber": 0,
        },
    )
    assert manager_blocked.status_code == 409
    assert manager_blocked.json()["code"] == "past_forecast_locked"
    calibration = client.get("/api/v1/forecast/calibration", params={"periodType": "month"})
    assert calibration.status_code == 200, calibration.text
    body = calibration.json()
    assert body["periodsIncluded"] == 1
    assert [(item["category"], item["assessedCount"], item["realisedWonCount"]) for item in body["categories"]] == [
        ("commit", 1, 1),
        ("likely", 1, 1),
        ("possible", 1, 0),
    ]
    assert all(item["realisationRate"] is None for item in body["categories"])
    rendered = calibration.text.lower()
    assert "rep score" in rendered
    assert "accuracy score" not in rendered


def test_forecast_feature_flag_fails_closed(app: FastAPI, client: TestClient) -> None:
    app.state.settings.feature_sales_forecasting_enabled = False
    try:
        assert client.get("/api/v1/beta/capabilities").json()["featureFlags"]["salesForecasting"] is False
        response = client.get("/api/v1/forecast/metadata")
        assert response.status_code == 404
        assert response.json()["code"] == "feature_unavailable"
    finally:
        app.state.settings.feature_sales_forecasting_enabled = True


def test_cross_tenant_forecast_opportunity_is_not_disclosed(client: TestClient, app: FastAPI) -> None:
    seed(app)
    response = client.get(
        f"/api/v1/forecast/opportunities/{SECONDARY_ORGANISATION_ID}/history",
        params={"periodType": "quarter", "periodAnchor": datetime.now(UTC).date().isoformat()},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "opportunity_not_found"


def test_manager_forecast_is_separate_immutable_and_visible_to_the_owner(
    client: TestClient,
    app: FastAPI,
) -> None:
    seed(app)
    review(client, fixture_id("atlas"), "commit")
    response = client.post(
        f"/api/v1/forecast/opportunities/{fixture_id('atlas')}/manager-judgments",
        json={
            "periodType": "quarter",
            "periodAnchor": datetime.now(UTC).date().isoformat(),
            "category": "possible",
            "expectedRevisionNumber": 0,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["revisions"][0]["category"] == "possible"
    concurrent = client.post(
        f"/api/v1/forecast/opportunities/{fixture_id('atlas')}/manager-judgments",
        json={
            "periodType": "quarter",
            "periodAnchor": datetime.now(UTC).date().isoformat(),
            "category": "likely",
            "expectedRevisionNumber": 0,
        },
    )
    assert concurrent.status_code == 409
    assert concurrent.json()["code"] == "forecast_revision_conflict"
    forged = client.post(
        f"/api/v1/forecast/opportunities/{fixture_id('atlas')}/manager-judgments",
        json={
            "periodType": "quarter",
            "periodAnchor": datetime.now(UTC).date().isoformat(),
            "category": "likely",
            "expectedRevisionNumber": 1,
            "amount": "999999.00",
            "probability": 80,
        },
    )
    assert forged.status_code == 422
    history = client.get(
        f"/api/v1/forecast/opportunities/{fixture_id('atlas')}/manager-history",
        params={"periodType": "quarter", "periodAnchor": datetime.now(UTC).date().isoformat()},
    )
    assert history.status_code == 200
    assert history.json()["revisions"][0]["category"] == "possible"
    forecast = client.get("/api/v1/forecast", params=current_quarter_params()).json()
    atlas = next(item for item in forecast["opportunities"] if item["opportunityName"] == "Atlas")
    assert atlas["judgment"]["category"] == "commit"
    assert atlas["managerJudgment"]["category"] == "possible"
    assert forecast["managerForecast"]["possible"]["amount"] == "80000.00"
    assert "blend" in forecast["managerForecast"]["disclosure"].lower()

    app.dependency_overrides[get_current_user] = lambda: peer_user()
    try:
        peer_history = client.get(
            f"/api/v1/forecast/opportunities/{fixture_id('atlas')}/manager-history",
            params={"periodType": "quarter", "periodAnchor": datetime.now(UTC).date().isoformat()},
        )
        assert peer_history.status_code == 403
        assert peer_history.json()["code"] == "forbidden"
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    async def assert_rows_and_assign_owner() -> None:
        session_factory = app.state.session_factory
        assert isinstance(session_factory, async_sessionmaker)
        async with session_factory() as session, session.begin():
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            identities = list(
                (
                    await session.scalars(
                        select(SalesForecastReviewerJudgment).where(
                            SalesForecastReviewerJudgment.organisation_id == PRIMARY_ORGANISATION_ID,
                            SalesForecastReviewerJudgment.opportunity_id == fixture_id("atlas"),
                        )
                    )
                ).all()
            )
            assert len(identities) == 1
            revisions = list(
                (
                    await session.scalars(
                        select(SalesForecastReviewerRevision).where(
                            SalesForecastReviewerRevision.organisation_id == PRIMARY_ORGANISATION_ID,
                            SalesForecastReviewerRevision.reviewer_judgment_id == identities[0].id,
                        )
                    )
                ).all()
            )
            assert len(revisions) == 1
            opportunity = await session.get(Opportunity, fixture_id("atlas"))
            assert opportunity is not None
            opportunity.owner_user_id = PEER_USER_ID

    asyncio.run(assert_rows_and_assign_owner())
    app.dependency_overrides[get_current_user] = lambda: peer_user()
    try:
        own = client.get("/api/v1/forecast", params=current_quarter_params()).json()
        atlas = next(item for item in own["opportunities"] if item["opportunityName"] == "Atlas")
        assert atlas["managerJudgment"]["category"] == "possible"
        assert atlas["managerJudgment"]["canReview"] is False
        assert atlas["managerJudgment"]["staleReasons"] == ["owner_changed"]
        assert own["managerForecast"] is None
        own_history = client.get(
            f"/api/v1/forecast/opportunities/{fixture_id('atlas')}/manager-history",
            params={"periodType": "quarter", "periodAnchor": datetime.now(UTC).date().isoformat()},
        )
        assert own_history.status_code == 200
        assert own_history.json()["revisions"][0]["category"] == "possible"
        denied = client.post(
            f"/api/v1/forecast/opportunities/{fixture_id('atlas')}/manager-judgments",
            json={
                "periodType": "quarter",
                "periodAnchor": datetime.now(UTC).date().isoformat(),
                "category": "likely",
                "expectedRevisionNumber": 1,
            },
        )
        assert denied.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    app.state.settings.feature_manager_intelligence_enabled = False
    try:
        assert client.get("/api/v1/beta/capabilities").json()["featureFlags"]["managerIntelligence"] is False
        unavailable = client.get("/api/v1/manager/deal-attention")
        assert unavailable.status_code == 404
        assert unavailable.json()["code"] == "feature_unavailable"
    finally:
        app.state.settings.feature_manager_intelligence_enabled = True


def test_manager_attention_and_review_are_deal_centric_explainable_and_admin_only(
    client: TestClient,
    app: FastAPI,
) -> None:
    seed(app)

    async def make_close_date_passed() -> None:
        session_factory = app.state.session_factory
        assert isinstance(session_factory, async_sessionmaker)
        async with session_factory() as session, session.begin():
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            opportunity = await session.get(Opportunity, fixture_id("bluepeak"))
            assert opportunity is not None
            opportunity.expected_close_date = datetime.now(UTC).date() - timedelta(days=1)

    asyncio.run(make_close_date_passed())
    attention = client.get("/api/v1/manager/deal-attention", params={"pageSize": 5})
    assert attention.status_code == 200, attention.text
    body = attention.json()
    assert body["total"] >= 1
    bluepeak = next(item for item in body["items"] if item["opportunityName"] == "BluePeak")
    reason_codes = [reason["code"] for reason in bluepeak["reasons"]]
    assert reason_codes[0] == "close_date_passed"
    assert len(reason_codes) == len(set(reason_codes))
    assert "forecast_not_reviewed" in reason_codes
    assert "no_next_action" in reason_codes
    assert all(reason["sources"] for reason in bluepeak["reasons"])
    assert all(reason["detectedAt"].endswith("Z") for reason in bluepeak["reasons"])
    assert all(key not in attention.text.lower() for key in ("leaderboard", "screen_time", "talk_ratio"))
    assert '"score"' not in attention.text.lower()

    detail = client.get(f"/api/v1/manager/opportunities/{fixture_id('bluepeak')}")
    assert detail.status_code == 200, detail.text
    review_body = detail.json()
    assert 1 <= len(review_body["questions"]) <= 5
    assert all(question["sourceReasonIds"] and question["sources"] for question in review_body["questions"])
    assert "transcript" not in detail.text.lower()

    summary = client.get(
        "/api/v1/manager/summary",
        params={"periodAnchor": datetime.now(UTC).date().isoformat(), "currency": "AUD"},
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["actual"]["metricId"] == "won_value"
    assert all(target["scope"] == "organisation" for target in summary.json()["organisationTargets"])
    assert summary.json()["sellerForecast"] != summary.json()["managerForecast"]

    app.dependency_overrides[get_current_user] = lambda: peer_user()
    try:
        denied = client.get("/api/v1/manager/deal-attention")
        assert denied.status_code == 403
        assert (
            client.get(
                "/api/v1/manager/summary",
                params={
                    "periodAnchor": datetime.now(UTC).date().isoformat(),
                    "currency": "AUD",
                },
            ).status_code
            == 403
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
