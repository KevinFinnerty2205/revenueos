from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import AuthenticatedUser, get_current_user
from revenueos.create_repositories import CreateRepository
from revenueos.models import Evidence

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, TEST_DB_URL
from .test_business_api import create_company, create_opportunity
from .test_meeting_api import cast_auth_dependency, secondary_user


def _definition() -> dict[str, object]:
    def input_definition(
        key: str,
        label: str,
        value_type: str,
        unit: str,
        order: int,
        *,
        minimum: str = "0",
        maximum: str = "1000000000",
        precision: int = 2,
        default: str | None = None,
        sensitive: bool = False,
        material: bool = False,
    ) -> dict[str, object]:
        value: dict[str, object] = {
            "key": key,
            "label": label,
            "description": f"Approved input for {label.lower()}.",
            "valueType": value_type,
            "unit": unit,
            "required": True,
            "minimum": minimum,
            "maximum": maximum,
            "decimalPrecision": precision,
            "sourcePolicy": "reviewed_manual" if default is None else "approved_org_only",
            "assumptionLocked": default is not None,
            "customerFacing": True,
            "material": material,
            "sensitivityEligible": sensitive,
            "displayOrder": order,
        }
        if default is not None:
            value.update(
                {
                    "defaultValue": default,
                    "defaultOrigin": "organisation_assumption",
                    "defaultSourceReference": "Approved synthetic Summit commercial assumption.",
                }
            )
        return value

    return {
        "inputs": [
            input_definition(
                "access_changes_per_month",
                "Access changes per month",
                "count",
                "count",
                1,
                maximum="1000000",
                precision=0,
                material=True,
            ),
            input_definition("minutes_current", "Current minutes per change", "minutes", "minutes", 2),
            input_definition(
                "minutes_future",
                "Future minutes per change",
                "minutes",
                "minutes",
                3,
                sensitive=True,
                material=True,
            ),
            input_definition(
                "labour_cost_per_hour",
                "Loaded labour cost",
                "currency",
                "currency_per_hour",
                4,
                default="55",
                material=True,
            ),
            input_definition("annual_rekey_cost", "Annual rekey cost", "currency", "currency_per_year", 5),
            input_definition(
                "annual_subscription_cost",
                "Annual subscription cost",
                "currency",
                "currency_per_year",
                6,
                default="36000",
                material=True,
            ),
            input_definition(
                "implementation_cost",
                "Implementation cost",
                "currency",
                "currency",
                7,
                default="25000",
                material=True,
            ),
        ],
        "outputs": [
            {
                "key": "annual_admin_hours_saved",
                "label": "Annual admin hours saved",
                "description": "Modelled annual administration capacity released.",
                "formula": "access_changes_per_month * (minutes_current - minutes_future) / 60 * 12",
                "unit": "hours_per_year",
                "displayPrecision": 2,
                "customerFacing": True,
                "highlight": False,
                "scenarioSensitive": True,
                "displayOrder": 1,
            },
            {
                "key": "annual_labour_savings",
                "label": "Annual labour savings",
                "description": "Modelled labour value from released capacity.",
                "formula": "annual_admin_hours_saved * labour_cost_per_hour",
                "unit": "currency_per_year",
                "displayPrecision": 2,
                "customerFacing": True,
                "highlight": True,
                "scenarioSensitive": True,
                "displayOrder": 2,
            },
            {
                "key": "annual_gross_benefit",
                "label": "Annual gross benefit",
                "description": "Annual labour savings plus explicitly supplied avoided cost.",
                "formula": "annual_labour_savings + annual_rekey_cost",
                "unit": "currency_per_year",
                "displayPrecision": 2,
                "customerFacing": True,
                "highlight": True,
                "scenarioSensitive": True,
                "displayOrder": 3,
            },
            {
                "key": "first_year_total_cost",
                "label": "First-year total cost",
                "description": "Approved implementation and annual subscription cost.",
                "formula": "annual_subscription_cost + implementation_cost",
                "unit": "currency",
                "displayPrecision": 2,
                "customerFacing": True,
                "highlight": False,
                "scenarioSensitive": False,
                "displayOrder": 4,
            },
            {
                "key": "first_year_net_benefit",
                "label": "First-year net benefit",
                "description": "Annual gross benefit less first-year total cost.",
                "formula": "annual_gross_benefit - first_year_total_cost",
                "unit": "currency",
                "displayPrecision": 2,
                "customerFacing": True,
                "highlight": True,
                "scenarioSensitive": True,
                "displayOrder": 5,
            },
            {
                "key": "roi_percentage",
                "label": "First-year ROI",
                "description": "First-year net benefit divided by first-year total cost, multiplied by 100.",
                "formula": "safe_divide(first_year_net_benefit, first_year_total_cost) * 100",
                "unit": "percentage",
                "displayPrecision": 1,
                "customerFacing": True,
                "highlight": True,
                "scenarioSensitive": True,
                "displayOrder": 6,
            },
            {
                "key": "payback_months",
                "label": "Payback",
                "description": "Implementation cost divided by positive annual net benefit, expressed in months.",
                "formula": "payback_months(implementation_cost, annual_gross_benefit - annual_subscription_cost)",
                "unit": "months",
                "displayPrecision": 1,
                "customerFacing": True,
                "highlight": True,
                "scenarioSensitive": True,
                "displayOrder": 7,
            },
        ],
        "customerDisclaimer": "Based on the inputs and assumptions shown; not a guarantee of future results.",
    }


def _create_approved_model(client: TestClient) -> dict[str, object]:
    created = client.post(
        "/api/v1/create/value-models",
        json={
            "name": "Multi-Site Access Efficiency",
            "description": "Models explicit administration and avoided-cost inputs.",
            "definition": _definition(),
            "idempotencyKey": "model-create-1",
        },
    )
    assert created.status_code == 201, created.text
    model = created.json()
    assert model["latestVersion"]["state"] == "draft"
    approved = client.post(
        f"/api/v1/create/value-models/{model['id']}/versions/{model['latestVersion']['id']}/approve",
        json={"confirmed": True},
    )
    assert approved.status_code == 200, approved.text
    return approved.json()


def _inputs(rekey_cost: str = "30000") -> list[dict[str, object]]:
    return [
        {"key": "access_changes_per_month", "value": "120", "origin": "salesperson_reported"},
        {"key": "minutes_current", "value": "15", "origin": "user_entered"},
        {"key": "minutes_future", "value": "5", "origin": "user_entered"},
        {"key": "labour_cost_per_hour", "value": "55", "origin": "organisation_assumption"},
        {"key": "annual_rekey_cost", "value": rekey_cost, "origin": "salesperson_reported"},
        {"key": "annual_subscription_cost", "value": "36000", "origin": "organisation_assumption"},
        {"key": "implementation_cost", "value": "25000", "origin": "organisation_assumption"},
    ]


def test_admin_model_and_member_business_case_lifecycle(client: TestClient, app: FastAPI) -> None:
    company = create_company(client, name="Northstar Facilities")
    opportunity = create_opportunity(client, str(company["id"]), name="Northstar access programme")
    model = _create_approved_model(client)
    model_version = model["latestVersion"]
    assert model_version["formulaEngineVersion"] == "bounded_decimal_v1"
    assert len(model_version["fingerprint"]) == 64

    member = AuthenticatedUser(
        user_id=PRIMARY_USER_ID,
        external_auth_id="user_dev_001",
        display_name="Create Member",
        email="member@example.test",
        organisation_id=PRIMARY_ORGANISATION_ID,
        organisation_name="Example Revenue Team",
        organisation_slug="example-revenue-team",
        role="member",
        auth_mode="mock",
    )
    app.dependency_overrides[get_current_user] = cast_auth_dependency(member)
    denied_model = client.post(
        "/api/v1/create/value-models",
        json={
            "name": "Member formula",
            "description": "Members cannot author approved formula definitions.",
            "definition": _definition(),
            "idempotencyKey": "member-model-1",
        },
    )
    assert denied_model.status_code == 403
    assert client.get("/api/v1/create/value-models").json()["items"][0]["latestVersion"]["state"] == "approved"

    created = client.post(
        "/api/v1/create/business-cases",
        json={
            "accountId": company["id"],
            "opportunityId": opportunity["id"],
            "modelVersionId": model_version["id"],
            "currency": "AUD",
            "idempotencyKey": "northstar-case-1",
        },
    )
    assert created.status_code == 201, created.text
    business_case = created.json()
    assert business_case["state"] == "draft"
    assert business_case["currency"] == "AUD"

    missing = client.post(
        f"/api/v1/create/business-cases/{business_case['id']}/calculate",
        json={"inputs": _inputs()[:-1], "idempotencyKey": "case-missing-1"},
    )
    assert missing.status_code == 422
    assert missing.json()["code"] == "business_case_input_missing"
    client_output = client.post(
        f"/api/v1/create/business-cases/{business_case['id']}/calculate",
        json={
            "inputs": _inputs(),
            "outputs": [{"key": "roi_percentage", "value": "999"}],
            "idempotencyKey": "case-output-1",
        },
    )
    assert client_output.status_code == 422

    calculated = client.post(
        f"/api/v1/create/business-cases/{business_case['id']}/calculate",
        json={
            "inputs": _inputs(),
            "scenarios": [
                {"name": "conservative", "overrides": [{"key": "minutes_future", "value": "10"}]},
                {"name": "upside", "overrides": [{"key": "minutes_future", "value": "2"}]},
            ],
            "sensitivity": {"inputKey": "minutes_future", "values": ["2", "5", "10"]},
            "idempotencyKey": "case-calculate-1",
        },
    )
    assert calculated.status_code == 200, calculated.text
    current = calculated.json()["currentVersion"]
    assert calculated.json()["state"] == "calculated"
    assert [scenario["name"] for scenario in current["scenarios"]] == ["base", "conservative", "upside"]
    base_outputs = {item["key"]: item for item in current["scenarios"][0]["outputs"]}
    assert base_outputs["annual_admin_hours_saved"]["displayValue"] == "240.00"
    assert base_outputs["annual_gross_benefit"]["displayValue"] == "43200.00"
    assert base_outputs["first_year_net_benefit"]["displayValue"] == "-17800.00"
    assert base_outputs["roi_percentage"]["displayValue"] == "-29.2"
    assert base_outputs["payback_months"]["displayValue"] == "41.7"
    assert base_outputs["annual_labour_savings"]["formula"] == "annual_admin_hours_saved * labour_cost_per_hour"
    assert current["sensitivity"]["inputKey"] == "minutes_future"
    assert len(current["sensitivity"]["rows"]) == 3
    assert all(item["sourceLabel"] for item in current["inputs"])
    assert next(item for item in current["inputs"] if item["key"] == "labour_cost_per_hour")["assumption"]

    approved = client.post(
        f"/api/v1/create/business-cases/{business_case['id']}/approve",
        json={"confirmed": True},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "approved"
    assert approved.json()["currentVersion"]["reviewState"] == "approved"
    approved_list = client.get("/api/v1/create/business-cases?approvedOnly=true")
    assert [item["id"] for item in approved_list.json()["items"]] == [business_case["id"]]

    recalculated = client.post(
        f"/api/v1/create/business-cases/{business_case['id']}/calculate",
        json={"inputs": _inputs(rekey_cost="0"), "idempotencyKey": "case-calculate-2"},
    )
    assert recalculated.status_code == 200, recalculated.text
    assert recalculated.json()["state"] == "calculated"
    assert recalculated.json()["currentVersion"]["version"] == 2
    negative_outputs = {item["key"]: item for item in recalculated.json()["currentVersion"]["scenarios"][0]["outputs"]}
    assert negative_outputs["roi_percentage"]["displayValue"].startswith("-")
    assert negative_outputs["payback_months"]["displayValue"] is None
    assert negative_outputs["payback_months"]["unavailableReason"] == "non_positive_denominator"


def test_formula_security_origin_authority_and_tenant_boundaries(client: TestClient, app: FastAPI) -> None:
    hostile = _definition()
    outputs = hostile["outputs"]
    assert isinstance(outputs, list)
    assert isinstance(outputs[0], dict)
    outputs[0]["formula"] = "__import__('os').system('id')"
    rejected = client.post(
        "/api/v1/create/value-models",
        json={
            "name": "Hostile formula",
            "description": "Must never become executable model content.",
            "definition": hostile,
            "idempotencyKey": "hostile-model-1",
        },
    )
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "unsupported_character"

    company = create_company(client)
    model = _create_approved_model(client)
    business_case = client.post(
        "/api/v1/create/business-cases",
        json={
            "accountId": company["id"],
            "modelVersionId": model["latestVersion"]["id"],
            "currency": "AUD",
            "idempotencyKey": "authority-case-1",
        },
    ).json()
    invented_customer_evidence = _inputs()
    invented_customer_evidence[0]["origin"] = "validated_customer_evidence"
    blocked = client.post(
        f"/api/v1/create/business-cases/{business_case['id']}/calculate",
        json={"inputs": invented_customer_evidence, "idempotencyKey": "invented-source-1"},
    )
    assert blocked.status_code == 422
    assert blocked.json()["code"] in {"input_origin_not_allowed", "typed_numeric_evidence_unavailable"}

    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    cross_tenant_model = client.get(f"/api/v1/create/value-models/{model['id']}")
    assert cross_tenant_model.status_code == 404
    cross_tenant_case = client.get(f"/api/v1/create/business-cases/{business_case['id']}")
    assert cross_tenant_case.status_code == 404


def test_deleted_linked_evidence_marks_approved_case_needs_review(client: TestClient) -> None:
    company = create_company(client)
    model = _create_approved_model(client)
    evidence_id = uuid.uuid4()

    async def write_evidence(lifecycle_status: str) -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            if lifecycle_status == "available":
                session.add(
                    Evidence(
                        id=evidence_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        evidence_type="user_observation",
                        origin_class="salesperson_reported",
                        support_class="reported",
                        validation_state="verified",
                        captured_by_user_id=PRIMARY_USER_ID,
                        lifecycle_status="available",
                        retention_class="standard",
                    )
                )
            else:
                item = await session.get(Evidence, evidence_id)
                assert item is not None
                item.lifecycle_status = "deleted"
                item.deleted_at = datetime.now(UTC)
            await session.commit()
        await engine.dispose()

    asyncio.run(write_evidence("available"))
    created = client.post(
        "/api/v1/create/business-cases",
        json={
            "accountId": company["id"],
            "modelVersionId": model["latestVersion"]["id"],
            "currency": "AUD",
            "idempotencyKey": "source-change-case-1",
        },
    ).json()
    inputs = _inputs()
    inputs[0]["sourceId"] = str(evidence_id)
    calculated = client.post(
        f"/api/v1/create/business-cases/{created['id']}/calculate",
        json={"inputs": inputs, "idempotencyKey": "source-change-calculate-1"},
    )
    assert calculated.status_code == 200, calculated.text
    approved = client.post(
        f"/api/v1/create/business-cases/{created['id']}/approve",
        json={"confirmed": True},
    )
    assert approved.status_code == 200, approved.text

    asyncio.run(write_evidence("deleted"))
    reviewed = client.get(f"/api/v1/create/business-cases/{created['id']}")
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["state"] == "needs_review"
    assert reviewed.json()["currentVersion"]["reviewState"] == "needs_review"
    assert client.get("/api/v1/create/business-cases?approvedOnly=true").json()["items"] == []


def test_changed_canonical_company_number_invalidates_case_and_create_reuse(client: TestClient) -> None:
    company = create_company(client)
    definition = {
        "inputs": [
            {
                "key": "employee_count",
                "label": "Employees",
                "description": "Canonical Account employee count.",
                "valueType": "count",
                "unit": "count",
                "required": True,
                "minimum": "1",
                "maximum": "1000000",
                "decimalPrecision": 0,
                "defaultValue": "100",
                "defaultOrigin": "approved_company_data",
                "defaultSourceReference": "Approved fallback company size.",
                "sourcePolicy": "approved_org_only",
                "assumptionLocked": False,
                "customerFacing": True,
                "material": True,
                "sensitivityEligible": False,
                "displayOrder": 1,
            }
        ],
        "outputs": [
            {
                "key": "modelled_employees",
                "label": "Modelled employees",
                "description": "The explicit employee-count input.",
                "formula": "employee_count",
                "unit": "count",
                "displayPrecision": 0,
                "customerFacing": True,
                "highlight": True,
                "scenarioSensitive": False,
                "displayOrder": 1,
            }
        ],
        "customerDisclaimer": "Based on the current canonical Account value.",
    }
    model = client.post(
        "/api/v1/create/value-models",
        json={
            "name": "Canonical company-size model",
            "description": "Tests exact approved Company data reuse.",
            "definition": definition,
            "idempotencyKey": "company-value-model-1",
        },
    ).json()
    approved_model = client.post(
        f"/api/v1/create/value-models/{model['id']}/versions/{model['latestVersion']['id']}/approve",
        json={"confirmed": True},
    ).json()
    business_case = client.post(
        "/api/v1/create/business-cases",
        json={
            "accountId": company["id"],
            "modelVersionId": approved_model["latestVersion"]["id"],
            "currency": "AUD",
            "idempotencyKey": "company-value-case-1",
        },
    ).json()
    calculated = client.post(
        f"/api/v1/create/business-cases/{business_case['id']}/calculate",
        json={
            "inputs": [
                {
                    "key": "employee_count",
                    "value": "125",
                    "origin": "approved_company_data",
                }
            ],
            "idempotencyKey": "company-value-calculation-1",
        },
    )
    assert calculated.status_code == 200, calculated.text
    case_version_id = calculated.json()["currentVersion"]["id"]
    approved_case = client.post(
        f"/api/v1/create/business-cases/{business_case['id']}/approve",
        json={"confirmed": True},
    )
    assert approved_case.status_code == 200, approved_case.text

    changed = client.patch(
        f"/api/v1/companies/{company['id']}",
        json={"employeeCount": 126},
    )
    assert changed.status_code == 200, changed.text

    async def available_to_create() -> bool:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            selected = await CreateRepository(session).approved_business_case_version(
                PRIMARY_ORGANISATION_ID,
                uuid.UUID(case_version_id),
            )
        await engine.dispose()
        return selected is not None

    assert not asyncio.run(available_to_create())
    reviewed = client.get(f"/api/v1/create/business-cases/{business_case['id']}")
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["state"] == "needs_review"
