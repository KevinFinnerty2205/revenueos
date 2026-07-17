from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient

from revenueos.auth import AuthenticatedUser, get_current_user

from .conftest import (
    SECONDARY_ORGANISATION_ID,
    SECONDARY_USER_ID,
)


def create_company(
    client: TestClient,
    *,
    name: str = "Acme Australia",
    status: str = "prospect",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/companies",
        json={
            "name": name,
            "website": "https://acme.example",
            "industry": "Software",
            "employeeCount": 125,
            "status": status,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_contact(
    client: TestClient,
    company_id: str,
    *,
    first_name: str = "Jordan",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/contacts",
        json={
            "companyId": company_id,
            "firstName": first_name,
            "lastName": "Lee",
            "email": f"{first_name.lower()}@example.com",
            "phone": "+61 400 000 000",
            "jobTitle": "Revenue Director",
            "linkedinUrl": "https://www.linkedin.com/in/jordan-lee",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_opportunity(
    client: TestClient,
    company_id: str,
    *,
    name: str = "Platform expansion",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/opportunities",
        json={
            "companyId": company_id,
            "name": name,
            "stage": "proposal",
            "value": "125000.50",
            "currency": "AUD",
            "probability": 65,
            "expectedCloseDate": "2026-09-30",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_task(
    client: TestClient,
    *,
    company_id: str,
    contact_id: str,
    opportunity_id: str,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/tasks",
        json={
            "companyId": company_id,
            "contactId": contact_id,
            "opportunityId": opportunity_id,
            "title": "Send commercial proposal",
            "description": "Include the agreed security appendix.",
            "priority": "high",
            "dueAt": "2026-08-01T01:00:00Z",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_company_crud_and_safe_dependency_conflict(client: TestClient) -> None:
    company = create_company(client)
    company_id = str(company["id"])
    assert company["ownerUserId"] == "00000000-0000-4000-8000-000000000001"
    assert company["organisationId"] == "00000000-0000-4000-8000-000000000002"

    response = client.patch(
        f"/api/v1/companies/{company_id}",
        json={"name": "Acme Enterprise", "status": "active"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Acme Enterprise"
    assert response.json()["status"] == "active"

    response = client.get(f"/api/v1/companies/{company_id}")
    assert response.status_code == 200
    assert response.json()["employeeCount"] == 125

    create_contact(client, company_id)
    response = client.delete(f"/api/v1/companies/{company_id}")
    assert response.status_code == 409
    assert response.json()["code"] == "resource_in_use"
    assert "database" not in response.text.lower()


def test_contact_crud(client: TestClient) -> None:
    company_id = str(create_company(client)["id"])
    contact = create_contact(client, company_id)
    contact_id = str(contact["id"])

    response = client.patch(
        f"/api/v1/contacts/{contact_id}",
        json={"jobTitle": "Chief Revenue Officer", "phone": None},
    )
    assert response.status_code == 200
    assert response.json()["jobTitle"] == "Chief Revenue Officer"
    assert response.json()["phone"] is None

    assert client.get(f"/api/v1/contacts/{contact_id}").status_code == 200
    assert client.delete(f"/api/v1/contacts/{contact_id}").status_code == 204
    assert client.get(f"/api/v1/contacts/{contact_id}").status_code == 404


def test_opportunity_crud(client: TestClient) -> None:
    company_id = str(create_company(client)["id"])
    opportunity = create_opportunity(client, company_id)
    opportunity_id = str(opportunity["id"])
    assert opportunity["currency"] == "AUD"
    assert opportunity["value"] == "125000.50"

    response = client.patch(
        f"/api/v1/opportunities/{opportunity_id}",
        json={"stage": "negotiation", "probability": 80},
    )
    assert response.status_code == 200
    assert response.json()["stage"] == "negotiation"
    assert response.json()["probability"] == 80

    assert client.delete(f"/api/v1/opportunities/{opportunity_id}").status_code == 204


def test_task_crud_and_relationship_derivation(client: TestClient) -> None:
    company_id = str(create_company(client)["id"])
    contact_id = str(create_contact(client, company_id)["id"])
    opportunity_id = str(create_opportunity(client, company_id)["id"])
    task = create_task(
        client,
        company_id=company_id,
        contact_id=contact_id,
        opportunity_id=opportunity_id,
    )
    task_id = str(task["id"])
    assert task["companyId"] == company_id
    assert task["assignedUserId"] is None
    assert task["createdByUserId"] == "00000000-0000-4000-8000-000000000001"

    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "completed", "description": None},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["description"] is None
    assert client.delete(f"/api/v1/tasks/{task_id}").status_code == 204


def test_pagination_filters_search_and_sorting(client: TestClient) -> None:
    create_company(client, name="Zulu Limited", status="inactive")
    create_company(client, name="Alpha Labs", status="active")
    create_company(client, name="Alpine Systems", status="active")

    response = client.get(
        "/api/v1/companies",
        params={
            "page": 1,
            "pageSize": 1,
            "search": "Al",
            "status": "active",
            "sortBy": "name",
            "sortOrder": "desc",
        },
    )
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["pages"] == 2
    assert response.json()["pageSize"] == 1
    assert [item["name"] for item in response.json()["items"]] == ["Alpine Systems"]


def test_relationship_and_enum_filters(client: TestClient) -> None:
    company_id = str(create_company(client, name="Filter Company")["id"])
    other_company_id = str(create_company(client, name="Other Company")["id"])
    contact_id = str(create_contact(client, company_id, first_name="Filtered")["id"])
    create_contact(client, other_company_id, first_name="Other")
    opportunity_id = str(create_opportunity(client, company_id, name="Filtered Deal")["id"])
    create_opportunity(client, other_company_id, name="Other Deal")
    task_id = str(
        create_task(
            client,
            company_id=company_id,
            contact_id=contact_id,
            opportunity_id=opportunity_id,
        )["id"]
    )
    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"status": "in_progress", "priority": "urgent"},
    )
    assert response.status_code == 200

    contacts = client.get("/api/v1/contacts", params={"companyId": company_id})
    opportunities = client.get(
        "/api/v1/opportunities",
        params={"companyId": company_id, "stage": "proposal"},
    )
    tasks = client.get(
        "/api/v1/tasks",
        params={
            "companyId": company_id,
            "contactId": contact_id,
            "opportunityId": opportunity_id,
            "status": "in_progress",
            "priority": "urgent",
        },
    )
    assert [item["firstName"] for item in contacts.json()["items"]] == ["Filtered"]
    assert [item["name"] for item in opportunities.json()["items"]] == ["Filtered Deal"]
    assert [item["id"] for item in tasks.json()["items"]] == [task_id]


def test_invalid_input_and_empty_updates_are_rejected_safely(client: TestClient) -> None:
    invalid_cases = [
        ("/api/v1/companies", {"name": " ", "employeeCount": -1}),
        (
            "/api/v1/contacts",
            {
                "companyId": "00000000-0000-4000-8000-000000000099",
                "firstName": "A",
                "lastName": "B",
                "email": "not-an-email",
            },
        ),
        (
            "/api/v1/opportunities",
            {
                "companyId": "00000000-0000-4000-8000-000000000099",
                "name": "Bad",
                "value": -1,
                "probability": 101,
            },
        ),
        ("/api/v1/tasks", {"title": "Bad timezone", "dueAt": "2026-01-01T10:00:00"}),
    ]
    for path, body in invalid_cases:
        response = client.post(path, json=body)
        assert response.status_code == 422
        assert response.json()["code"] == "invalid_request"
        assert "input" not in response.json()

    company_id = str(create_company(client)["id"])
    response = client.patch(f"/api/v1/companies/{company_id}", json={})
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"

    response = client.patch(
        f"/api/v1/companies/{company_id}",
        json={"ownerUserId": str(SECONDARY_USER_ID)},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_relationship"


def test_missing_and_cross_company_task_relationships_are_rejected(client: TestClient) -> None:
    first_company_id = str(create_company(client, name="First Company")["id"])
    second_company_id = str(create_company(client, name="Second Company")["id"])
    contact_id = str(create_contact(client, first_company_id)["id"])
    opportunity_id = str(create_opportunity(client, second_company_id)["id"])

    response = client.post(
        "/api/v1/tasks",
        json={
            "contactId": contact_id,
            "opportunityId": opportunity_id,
            "title": "Invalid task",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "inconsistent_relationship"

    missing = client.get("/api/v1/tasks/00000000-0000-4000-8000-000000000099")
    assert missing.status_code == 404
    assert missing.json()["code"] == "task_not_found"


def test_cross_tenant_records_are_not_visible_or_mutable(
    app: FastAPI,
    client: TestClient,
) -> None:
    secondary_user = AuthenticatedUser(
        user_id=SECONDARY_USER_ID,
        external_auth_id="user_other_001",
        display_name="Other User",
        email="other@example.test",
        organisation_id=SECONDARY_ORGANISATION_ID,
        organisation_name="Other Revenue Team",
        organisation_slug="other-revenue-team",
        role="admin",
        auth_mode="mock",
    )
    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user)
    other_company_id = str(create_company(client, name="Other Tenant Company")["id"])
    app.dependency_overrides.pop(get_current_user)

    response = client.get("/api/v1/companies")
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert client.get(f"/api/v1/companies/{other_company_id}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/companies/{other_company_id}",
            json={"name": "Stolen"},
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/companies/{other_company_id}").status_code == 404

    response = client.post(
        "/api/v1/contacts",
        json={
            "companyId": other_company_id,
            "firstName": "Cross",
            "lastName": "Tenant",
            "email": "cross@example.com",
        },
    )
    assert response.status_code == 404
    assert response.json()["code"] == "company_not_found"


def cast_auth_dependency(user: AuthenticatedUser) -> Callable[[], AuthenticatedUser]:
    return lambda: user
