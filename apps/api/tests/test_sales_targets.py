from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.auth import AuthenticatedUser, get_current_user
from revenueos.database import set_tenant_database_context
from revenueos.models import (
    Company,
    Interaction,
    Opportunity,
    Organisation,
    OrganisationMembership,
    SalesTarget,
    SalesTargetRevision,
    User,
)
from revenueos.pipeline_repositories import ensure_default_pipeline
from revenueos.sales_metric_registry import SALES_METRIC_REGISTRY
from revenueos.sales_target_policy import SALES_TARGET_METRIC_POLICY

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID

PEER_USER_ID = UUID("00000000-0000-4000-8000-000000000021")


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
        external_auth_id="user_peer_001",
        display_name="Priya Seller",
        email="priya@example.test",
        role="member",
    )


def current_anchor() -> str:
    return datetime.now(UTC).date().isoformat()


def target_payload(
    *,
    metric_id: str = "won_value",
    goal_value: str = "20000",
    currency: str | None = "AUD",
    scope: str = "personal",
    origin: str = "self_set",
    owner_user_id: UUID | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "metricId": metric_id,
        "metricDefinitionVersion": "1",
        "scope": scope,
        "origin": origin,
        "periodType": "month",
        "periodAnchor": current_anchor(),
        "goalValue": goal_value,
    }
    if currency is not None:
        payload["currency"] = currency
    if owner_user_id is not None:
        payload["ownerUserId"] = str(owner_user_id)
    return payload


async def seed_target_actuals(session_factory: async_sessionmaker[AsyncSession]) -> None:
    now = datetime.now(UTC)
    async with session_factory() as session, session.begin():
        await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
        peer = await session.get(User, PEER_USER_ID)
        if peer is None:
            session.add(
                User(
                    id=PEER_USER_ID,
                    external_auth_id="user_peer_001",
                    email="priya@example.test",
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
        won_stage = next(stage for stage in stages if stage.stage_type == "won")
        company = Company(
            id=uuid4(),
            organisation_id=PRIMARY_ORGANISATION_ID,
            name="Target actuals account",
            status="active",
            owner_user_id=PRIMARY_USER_ID,
        )
        session.add(company)
        await session.flush()
        for label, amount, currency in (
            ("AUD won", Decimal("14500.00"), "AUD"),
            ("USD won", Decimal("7000.00"), "USD"),
            ("Unvalued won", None, None),
        ):
            session.add(
                Opportunity(
                    id=uuid4(),
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    company_id=company.id,
                    name=label,
                    stage="closed_won",
                    status="won",
                    estimated_value=amount,
                    currency=currency,
                    owner_user_id=PRIMARY_USER_ID,
                    pipeline_id=pipeline.id,
                    pipeline_stage_id=won_stage.id,
                    actual_close_date=now.date(),
                    outcome_reason="solution_fit",
                    outcome_provenance="seller_reported",
                    created_at=now - timedelta(days=1),
                    updated_at=now,
                )
            )
        for interaction_type in ("phone_call", "online_meeting"):
            session.add(
                Interaction(
                    id=uuid4(),
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    company_id=company.id,
                    interaction_type=interaction_type,
                    lifecycle_status="completed",
                    title=f"Target {interaction_type}",
                    actual_start_at=now - timedelta(hours=1),
                    actual_end_at=now - timedelta(minutes=30),
                    timezone="UTC",
                    creation_origin="manual",
                    call_direction="outbound" if interaction_type == "phone_call" else None,
                    call_outcome="connected" if interaction_type == "phone_call" else None,
                    created_by_user_id=PRIMARY_USER_ID,
                )
            )


def seed(app: FastAPI) -> None:
    session_factory = app.state.session_factory
    assert isinstance(session_factory, async_sessionmaker)
    asyncio.run(seed_target_actuals(session_factory))


def test_targetable_policy_is_small_higher_is_better_and_excludes_rates_and_outreach(client: TestClient) -> None:
    response = client.get("/api/v1/targets/metadata")
    assert response.status_code == 200, response.text
    metadata = response.json()
    assert [metric["metricId"] for metric in metadata["metrics"]] == [
        "won_value",
        "opportunities_closed_won_count",
        "opportunities_created_count",
        "meetings_completed_count",
        "phone_calls_completed_count",
    ]
    assert metadata["metrics"][0]["category"] == "outcome"
    assert metadata["metrics"][-1]["category"] == "activity"
    assert set(SALES_TARGET_METRIC_POLICY) == {metric["metricId"] for metric in metadata["metrics"]}
    assert {metric_id for metric_id, definition in SALES_METRIC_REGISTRY.items() if definition.targetable} == set(
        SALES_TARGET_METRIC_POLICY
    )
    rendered = response.text.lower()
    assert "live_outreach_sent_count" not in rendered
    assert "followed_by" not in rendered


def test_personal_won_value_progress_reuses_canonical_metric_and_keeps_currency_separate(
    app: FastAPI,
    client: TestClient,
) -> None:
    seed(app)
    created_response = client.post("/api/v1/targets", json=target_payload())
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()
    assert created["origin"] == "self_set"
    assert created["ownerUserId"] == str(PRIMARY_USER_ID)
    assert created["progress"] == {
        **created["progress"],
        "state": "available",
        "actualValue": "14500.00",
        "targetValue": "20000.00",
        "remainingValue": "5500.00",
        "aboveTargetValue": "0",
        "percentageComplete": "72.5",
        "targetReached": False,
    }
    assert "other currencies are not converted" in " ".join(created["progress"]["disclosures"]).lower()

    metric = client.get(
        "/api/v1/insights/sales/metrics/won_value",
        params={
            "startDate": created["periodStart"],
            "endDate": created["progress"]["calculatedThrough"],
            "timezone": created["timezone"],
            "ownerUserId": str(PRIMARY_USER_ID),
            "currency": "AUD",
        },
    )
    assert metric.status_code == 200, metric.text
    assert metric.json()["value"] == created["progress"]["actualValue"]

    usd = client.post("/api/v1/targets", json={**target_payload(), "currency": "USD"})
    assert usd.status_code == 201, usd.text
    assert usd.json()["progress"]["actualValue"] == "7000.00"


def test_revision_history_preserves_old_goal_and_progress_can_exceed_one_hundred(
    app: FastAPI,
    client: TestClient,
) -> None:
    seed(app)
    target = client.post("/api/v1/targets", json=target_payload()).json()
    revised_response = client.post(
        f"/api/v1/targets/{target['id']}/revisions",
        json={"goalValue": "10000", "expectedRevisionNumber": 1},
    )
    assert revised_response.status_code == 200, revised_response.text
    revised = revised_response.json()
    assert revised["latestRevision"]["revisionNumber"] == 2
    assert [item["goalValue"] for item in revised["revisions"]] == ["10000.00", "20000.00"]
    assert revised["progress"]["percentageComplete"] == "145.0"
    assert revised["progress"]["remainingValue"] == "0"
    assert revised["progress"]["aboveTargetValue"] == "4500.00"
    stale = client.post(
        f"/api/v1/targets/{target['id']}/revisions",
        json={"goalValue": "12000", "expectedRevisionNumber": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "target_revision_conflict"


def test_canonical_correction_and_reopen_change_progress_without_a_target_counter(
    app: FastAPI,
    client: TestClient,
) -> None:
    seed(app)
    target = client.post("/api/v1/targets", json=target_payload()).json()

    async def correct(*, status: str, amount: Decimal | None) -> None:
        session_factory = app.state.session_factory
        assert isinstance(session_factory, async_sessionmaker)
        async with session_factory() as session, session.begin():
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            opportunity = await session.scalar(
                select(Opportunity).where(
                    Opportunity.organisation_id == PRIMARY_ORGANISATION_ID,
                    Opportunity.name == "AUD won",
                )
            )
            assert opportunity is not None
            opportunity.status = status
            opportunity.estimated_value = amount
            opportunity.actual_close_date = datetime.now(UTC).date() if status == "won" else None

    asyncio.run(correct(status="open", amount=Decimal("14500.00")))
    reopened = client.get(f"/api/v1/targets/{target['id']}")
    assert reopened.status_code == 200
    assert reopened.json()["progress"]["actualValue"] == "0"

    asyncio.run(correct(status="won", amount=Decimal("16000.00")))
    corrected = client.get(f"/api/v1/targets/{target['id']}")
    assert corrected.status_code == 200
    assert corrected.json()["progress"]["actualValue"] == "16000.00"


def test_self_and_assigned_targets_can_coexist_but_duplicates_are_blocked(app: FastAPI, client: TestClient) -> None:
    seed(app)
    self_target = client.post("/api/v1/targets", json=target_payload())
    assert self_target.status_code == 201
    duplicate = client.post("/api/v1/targets", json=target_payload())
    assert duplicate.status_code == 409
    assigned = client.post(
        "/api/v1/targets",
        json=target_payload(origin="admin_assigned", owner_user_id=PRIMARY_USER_ID),
    )
    assert assigned.status_code == 201, assigned.text
    assert assigned.json()["progress"]["actualValue"] == self_target.json()["progress"]["actualValue"]


def test_personal_visibility_and_mutation_authority_are_enforced_within_one_tenant(
    app: FastAPI,
    client: TestClient,
) -> None:
    seed(app)
    personal = client.post("/api/v1/targets", json=target_payload()).json()
    organisation = client.post(
        "/api/v1/targets",
        json=target_payload(scope="organisation", origin="admin_assigned", owner_user_id=None),
    )
    assert organisation.status_code == 201, organisation.text

    app.dependency_overrides[get_current_user] = lambda: peer_user()
    try:
        assert client.get(f"/api/v1/targets/{personal['id']}").status_code == 404
        assert client.get(f"/api/v1/targets/{organisation.json()['id']}").status_code == 200
        member_list = client.get("/api/v1/targets", params={"view": "current"}).json()["items"]
        assert {item["id"] for item in member_list} == {organisation.json()["id"]}
        forbidden = client.post(
            "/api/v1/targets",
            json=target_payload(scope="organisation", origin="admin_assigned", owner_user_id=None),
        )
        assert forbidden.status_code == 403
        peer_goal = client.post("/api/v1/targets", json=target_payload(goal_value="25000"))
        assert peer_goal.status_code == 201, peer_goal.text
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    admin_edit = client.post(
        f"/api/v1/targets/{peer_goal.json()['id']}/revisions",
        json={"goalValue": "30000", "expectedRevisionNumber": 1},
    )
    assert admin_edit.status_code == 403


def test_admin_assignment_is_read_only_for_owner_and_count_activity_is_secondary(
    app: FastAPI,
    client: TestClient,
) -> None:
    seed(app)
    assigned = client.post(
        "/api/v1/targets",
        json=target_payload(
            metric_id="phone_calls_completed_count",
            goal_value="1",
            currency=None,
            origin="admin_assigned",
            owner_user_id=PEER_USER_ID,
        ),
    )
    assert assigned.status_code == 201, assigned.text
    assert assigned.json()["metric"]["category"] == "activity"
    app.dependency_overrides[get_current_user] = lambda: peer_user()
    try:
        visible = client.get(f"/api/v1/targets/{assigned.json()['id']}")
        assert visible.status_code == 200
        assert visible.json()["canRevise"] is False
        edit = client.post(
            f"/api/v1/targets/{assigned.json()['id']}/revisions",
            json={"goalValue": "2", "expectedRevisionNumber": 1},
        )
        assert edit.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_requests_fail_closed_for_non_targetable_metrics_values_periods_and_client_actuals(client: TestClient) -> None:
    rate = client.post(
        "/api/v1/targets",
        json=target_payload(metric_id="closed_win_rate", goal_value="50", currency=None),
    )
    assert rate.status_code == 422
    assert rate.json()["code"] == "metric_not_targetable"
    fractional_count = client.post(
        "/api/v1/targets",
        json=target_payload(metric_id="meetings_completed_count", goal_value="1.5", currency=None),
    )
    assert fractional_count.status_code == 422
    zero = client.post("/api/v1/targets", json=target_payload(goal_value="0"))
    assert zero.status_code == 422
    past_anchor = datetime.now(UTC).date().replace(year=datetime.now(UTC).year - 1)
    past = client.post(
        "/api/v1/targets",
        json={**target_payload(), "periodAnchor": past_anchor.isoformat()},
    )
    assert past.status_code == 422
    forged = client.post(
        "/api/v1/targets",
        json={**target_payload(), "actual": "20000", "progress": "100"},
    )
    assert forged.status_code == 422


def test_pipeline_binding_is_limited_to_opportunity_metrics(app: FastAPI, client: TestClient) -> None:
    seed(app)
    pipeline_id = client.get("/api/v1/targets/metadata").json()["pipelines"][0]["id"]
    activity = client.post(
        "/api/v1/targets",
        json={
            **target_payload(
                metric_id="meetings_completed_count",
                goal_value="8",
                currency=None,
            ),
            "pipelineId": pipeline_id,
        },
    )
    assert activity.status_code == 422
    assert activity.json()["code"] == "pipeline_not_supported"

    opportunity = client.post(
        "/api/v1/targets",
        json={**target_payload(), "pipelineId": pipeline_id},
    )
    assert opportunity.status_code == 201, opportunity.text
    assert opportunity.json()["pipelineId"] == pipeline_id


def test_calendar_periods_use_an_immutable_organisation_timezone_snapshot_and_future_has_no_fake_actual(
    app: FastAPI,
    client: TestClient,
) -> None:
    async def set_timezone(value: str) -> None:
        session_factory = app.state.session_factory
        assert isinstance(session_factory, async_sessionmaker)
        async with session_factory() as session, session.begin():
            organisation = await session.get(Organisation, PRIMARY_ORGANISATION_ID)
            assert organisation is not None
            organisation.timezone = value

    asyncio.run(set_timezone("Australia/Sydney"))
    now = datetime.now(UTC).date()
    quarter_start_month = ((now.month - 1) // 3) * 3 + 1
    quarter = client.post(
        "/api/v1/targets",
        json={
            **target_payload(
                metric_id="opportunities_created_count",
                goal_value="10",
                currency=None,
            ),
            "periodType": "quarter",
        },
    )
    assert quarter.status_code == 201, quarter.text
    assert quarter.json()["periodStart"] == f"{now.year}-{quarter_start_month:02d}-01"
    assert quarter.json()["timezone"] == "Australia/Sydney"

    asyncio.run(set_timezone("Pacific/Auckland"))
    unchanged = client.get(f"/api/v1/targets/{quarter.json()['id']}")
    assert unchanged.json()["timezone"] == "Australia/Sydney"

    future = client.post(
        "/api/v1/targets",
        json={
            **target_payload(
                metric_id="meetings_completed_count",
                goal_value="12",
                currency=None,
            ),
            "periodType": "year",
            "periodAnchor": f"{now.year + 1}-01-01",
        },
    )
    assert future.status_code == 201, future.text
    assert future.json()["periodStart"] == f"{now.year + 1}-01-01"
    assert future.json()["periodEnd"] == f"{now.year + 1}-12-31"
    assert future.json()["progress"]["state"] == "upcoming"
    assert future.json()["progress"]["actualValue"] is None
    assert future.json()["progress"]["percentageComplete"] is None


def test_past_target_is_locked_and_archiving_preserves_revision_history(app: FastAPI, client: TestClient) -> None:
    seed(app)
    current = client.post("/api/v1/targets", json=target_payload()).json()
    archived = client.post(f"/api/v1/targets/{current['id']}/archive", json={"confirmed": True})
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert archived.json()["revisions"][0]["goalValue"] == "20000.00"
    assert client.get("/api/v1/targets", params={"view": "archived"}).json()["items"][0]["id"] == current["id"]

    async def add_past() -> UUID:
        session_factory = app.state.session_factory
        assert isinstance(session_factory, async_sessionmaker)
        now = datetime.now(UTC)
        async with session_factory() as session, session.begin():
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            target_id = uuid4()
            target = SalesTarget(
                id=target_id,
                organisation_id=PRIMARY_ORGANISATION_ID,
                metric_id="opportunities_closed_won_count",
                metric_definition_version="1",
                scope="personal",
                origin="self_set",
                owner_user_id=PRIMARY_USER_ID,
                period_type="month",
                period_start=(now.date().replace(day=1) - timedelta(days=40)).replace(day=1),
                period_end=now.date().replace(day=1) - timedelta(days=1),
                timezone="UTC",
                created_by_user_id=PRIMARY_USER_ID,
            )
            session.add(target)
            session.add(
                SalesTargetRevision(
                    id=uuid4(),
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    target_id=target_id,
                    revision_number=1,
                    goal_value=Decimal("5"),
                    created_by_user_id=PRIMARY_USER_ID,
                )
            )
            return target_id

    past_id = asyncio.run(add_past())
    locked = client.post(
        f"/api/v1/targets/{past_id}/revisions",
        json={"goalValue": "6", "expectedRevisionNumber": 1},
    )
    assert locked.status_code == 409
    assert locked.json()["code"] == "past_target_locked"


def test_disabling_member_archives_their_current_targets_but_keeps_history(
    app: FastAPI,
    client: TestClient,
) -> None:
    seed(app)
    assigned = client.post(
        "/api/v1/targets",
        json=target_payload(
            metric_id="meetings_completed_count",
            goal_value="12",
            currency=None,
            origin="admin_assigned",
            owner_user_id=PEER_USER_ID,
        ),
    )
    assert assigned.status_code == 201, assigned.text

    disabled = client.patch(
        f"/api/v1/beta/admin/members/{PEER_USER_ID}",
        json={"status": "disabled"},
    )
    assert disabled.status_code == 200, disabled.text
    archived = client.get(f"/api/v1/targets/{assigned.json()['id']}")
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert archived.json()["revisions"][0]["goalValue"] == "12.00"


def test_target_feature_flag_fails_closed(app: FastAPI, client: TestClient) -> None:
    assert client.get("/api/v1/beta/capabilities").json()["featureFlags"]["salesTargets"] is True
    app.state.settings.feature_sales_targets_enabled = False
    try:
        assert client.get("/api/v1/beta/capabilities").json()["featureFlags"]["salesTargets"] is False
        response = client.get("/api/v1/targets/metadata")
        assert response.status_code == 404
        assert response.json()["code"] == "feature_unavailable"
    finally:
        app.state.settings.feature_sales_targets_enabled = True
