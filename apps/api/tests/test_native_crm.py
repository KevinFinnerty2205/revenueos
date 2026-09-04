from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import AuthenticatedUser, get_current_user
from revenueos.beta_maintenance import _export_payload
from revenueos.database import set_tenant_database_context
from revenueos.models import CRMCustomFieldValue, CRMFieldMapping, CRMRecordChange, IntegrationConnection

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, TEST_DB_URL
from .test_business_api import create_company, create_contact, create_opportunity
from .test_meeting_api import secondary_user


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


def test_crm_configuration_custom_fields_history_activity_and_archive(app: FastAPI, client: TestClient) -> None:
    availability = client.get("/api/v1/crm/availability")
    assert availability.status_code == 200
    assert availability.json()["state"] == "setup_required"
    assert availability.json()["mode"] == "unconfigured"

    configured = client.put("/api/v1/crm/settings", json={"mode": "native", "confirmed": True})
    assert configured.status_code == 200, configured.text
    assert configured.json()["mode"] == "native"

    definition = client.post(
        "/api/v1/crm/custom-fields",
        json={
            "entityType": "account",
            "fieldKey": "customer_tier",
            "label": "Customer tier",
            "fieldType": "single_select",
            "options": ["Strategic", "Growth"],
            "displayOrder": 0,
        },
    )
    assert definition.status_code == 201, definition.text
    definition_id = definition.json()["id"]

    company = create_company(client, name="Native CRM Account")
    company_id = str(company["id"])
    value = client.put(
        f"/api/v1/crm/records/account/{company_id}/custom-fields/{definition_id}",
        json={"value": "Strategic", "expectedRecordUpdatedAt": company["updatedAt"]},
    )
    assert value.status_code == 200, value.text
    assert value.json()["value"] == "Strategic"

    contact = create_contact(client, company_id, first_name="Activity")
    opportunity = create_opportunity(client, company_id, name="Native CRM Deal")
    task = client.post(
        "/api/v1/tasks",
        json={
            "companyId": company_id,
            "contactId": contact["id"],
            "opportunityId": opportunity["id"],
            "title": "Confirm mutual action plan",
        },
    )
    assert task.status_code == 201

    record = client.get(f"/api/v1/crm/records/account/{company_id}")
    assert record.status_code == 200, record.text
    body = record.json()
    assert body["title"] == "Native CRM Account"
    assert body["ownerName"] == "Alex Morgan"
    assert {field["key"] for field in body["coreFields"]} >= {"website", "location", "status"}
    assert body["customFields"][0]["value"] == "Strategic"
    assert {item["activityType"] for item in body["activity"]} >= {"action", "opportunity"}
    assert {item["fieldKey"] for item in body["history"]} >= {"name", "custom.customer_tier"}

    archived = client.post(f"/api/v1/crm/records/account/{company_id}/archive")
    assert archived.status_code == 200
    assert archived.json()["archivedAt"] is not None
    archived_edit = client.patch(f"/api/v1/companies/{company_id}", json={"location": "Perth"})
    assert archived_edit.status_code == 409
    assert archived_edit.json()["code"] == "record_archived"
    assert client.get("/api/v1/companies").json()["items"] == []
    assert client.get("/api/v1/companies", params={"includeArchived": True}).json()["total"] == 1
    assert client.post(f"/api/v1/crm/records/account/{company_id}/restore").status_code == 200
    assert client.get("/api/v1/companies").json()["total"] == 1

    async def export_payload() -> dict[str, object]:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            payload = await _export_payload(session, PRIMARY_ORGANISATION_ID, app.state.settings)
        await engine.dispose()
        return payload

    exported = asyncio.run(export_payload())
    assert exported["exportVersion"] == 30
    assert len(exported["crmCustomFieldDefinitions"]) == 1  # type: ignore[arg-type]
    assert len(exported["crmCustomFieldValues"]) == 1  # type: ignore[arg-type]
    assert exported["companies"][0]["archived_at"] is None  # type: ignore[index]


def test_strong_dedupe_returns_open_existing_metadata_and_remains_tenant_scoped(
    app: FastAPI, client: TestClient
) -> None:
    company = create_company(client, name="Dedupe Account")
    definition = client.post(
        "/api/v1/crm/custom-fields",
        json={
            "entityType": "account",
            "fieldKey": "tenant_marker",
            "label": "Tenant marker",
            "fieldType": "short_text",
        },
    ).json()
    duplicate = client.post(
        "/api/v1/companies",
        json={"name": "Duplicate name", "website": "https://DEDUPE-account.example/about"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "duplicate_company_domain"
    assert duplicate.json()["details"] == {"entityType": "account", "entityId": company["id"]}
    same_name = client.post(
        "/api/v1/companies",
        json={"name": "Dedupe Account", "website": "https://different-domain.example"},
    )
    assert same_name.status_code == 201

    contact = create_contact(client, str(company["id"]), first_name="Unique")
    duplicate_contact = client.post(
        "/api/v1/contacts",
        json={
            "companyId": company["id"],
            "firstName": "Another",
            "lastName": "Person",
            "email": "UNIQUE@example.com",
        },
    )
    assert duplicate_contact.status_code == 409
    assert duplicate_contact.json()["details"]["entityId"] == contact["id"]
    same_name_without_email = client.post(
        "/api/v1/contacts",
        json={
            "companyId": company["id"],
            "firstName": "Unique",
            "lastName": "Contact",
        },
    )
    assert same_name_without_email.status_code == 201
    assert same_name_without_email.json()["email"] is None

    app.dependency_overrides[get_current_user] = lambda: secondary_user()
    try:
        secondary_company = create_company(client, name="Dedupe Account")
        assert secondary_company["id"] != company["id"]
        assert client.get(f"/api/v1/crm/records/account/{company['id']}").status_code == 404
        cross_tenant_definition = client.put(
            f"/api/v1/crm/records/account/{secondary_company['id']}/custom-fields/{definition['id']}",
            json={"value": "Blocked"},
        )
        assert cross_tenant_definition.status_code == 404
        assert cross_tenant_definition.json()["code"] == "custom_field_not_found"
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    cross_tenant_record = client.put(
        f"/api/v1/crm/records/account/{secondary_company['id']}/custom-fields/{definition['id']}",
        json={"value": "Blocked"},
    )
    assert cross_tenant_record.status_code == 404
    assert cross_tenant_record.json()["code"] == "crm_record_not_found"


def test_hard_delete_removes_polymorphic_crm_values_and_history(client: TestClient) -> None:
    company = create_company(client, name="Privacy deletion Account")
    definition = client.post(
        "/api/v1/crm/custom-fields",
        json={
            "entityType": "account",
            "fieldKey": "deletion_marker",
            "label": "Deletion marker",
            "fieldType": "short_text",
        },
    ).json()
    assert (
        client.put(
            f"/api/v1/crm/records/account/{company['id']}/custom-fields/{definition['id']}",
            json={"value": "Remove with record"},
        ).status_code
        == 200
    )

    assert client.delete(f"/api/v1/companies/{company['id']}").status_code == 204

    async def crm_row_counts() -> tuple[int, int]:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            value_count = await session.scalar(
                select(func.count())
                .select_from(CRMCustomFieldValue)
                .where(
                    CRMCustomFieldValue.organisation_id == PRIMARY_ORGANISATION_ID,
                    CRMCustomFieldValue.entity_type == "account",
                    CRMCustomFieldValue.entity_id == UUID(str(company["id"])),
                )
            )
            history_count = await session.scalar(
                select(func.count())
                .select_from(CRMRecordChange)
                .where(
                    CRMRecordChange.organisation_id == PRIMARY_ORGANISATION_ID,
                    CRMRecordChange.entity_type == "account",
                    CRMRecordChange.entity_id == UUID(str(company["id"])),
                )
            )
        await engine.dispose()
        return int(value_count or 0), int(history_count or 0)

    assert asyncio.run(crm_row_counts()) == (0, 0)


def test_entitlement_off_preserves_reads_and_blocks_advanced_mutation(client: TestClient) -> None:
    company = create_company(client, name="Entitlement Account")
    definition = client.post(
        "/api/v1/crm/custom-fields",
        json={
            "entityType": "account",
            "fieldKey": "renewal_date",
            "label": "Renewal date",
            "fieldType": "date",
        },
    ).json()
    set_value = client.put(
        f"/api/v1/crm/records/account/{company['id']}/custom-fields/{definition['id']}",
        json={"value": "2027-06-30"},
    )
    assert set_value.status_code == 200, set_value.text

    disabled = client.patch("/api/v1/crm/admin/entitlement", json={"enabled": False})
    assert disabled.status_code == 200
    assert disabled.json()["state"] == "not_in_plan"
    record = client.get(f"/api/v1/crm/records/account/{company['id']}")
    assert record.status_code == 200
    assert record.json()["customFields"][0]["value"] == "2027-06-30"
    assert record.json()["customFields"][0]["editable"] is False
    assert (
        client.put(
            f"/api/v1/crm/records/account/{company['id']}/custom-fields/{definition['id']}",
            json={"value": "2028-06-30"},
        ).status_code
        == 403
    )
    assert client.post(f"/api/v1/crm/records/account/{company['id']}/archive").status_code == 403
    assert client.patch(f"/api/v1/companies/{company['id']}", json={"location": "Sydney"}).status_code == 200


def test_roles_concurrency_and_custom_field_validation(app: FastAPI, client: TestClient) -> None:
    company = create_company(client, name="Role Account")
    definition = client.post(
        "/api/v1/crm/custom-fields",
        json={
            "entityType": "account",
            "fieldKey": "segment",
            "label": "Segment",
            "fieldType": "single_select",
            "options": ["Enterprise", "SMB"],
        },
    ).json()
    invalid = client.put(
        f"/api/v1/crm/records/account/{company['id']}/custom-fields/{definition['id']}",
        json={"value": "Consumer"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "invalid_custom_field_value"

    changed = client.patch(
        f"/api/v1/companies/{company['id']}",
        json={"location": "Melbourne", "expectedUpdatedAt": company["updatedAt"]},
    )
    assert changed.status_code == 200
    stale = client.put(
        f"/api/v1/crm/records/account/{company['id']}/custom-fields/{definition['id']}",
        json={"value": "Enterprise", "expectedRecordUpdatedAt": company["updatedAt"]},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_write"

    member = replace(primary_user(), role="member")
    app.dependency_overrides[get_current_user] = lambda: member
    try:
        assert (
            client.post(
                "/api/v1/crm/custom-fields",
                json={
                    "entityType": "contact",
                    "fieldKey": "member_field",
                    "label": "Member field",
                    "fieldType": "short_text",
                },
            ).status_code
            == 403
        )
        owner_change = client.patch(
            f"/api/v1/companies/{company['id']}",
            json={"ownerUserId": str(UUID("00000000-0000-4000-8000-000000000011"))},
        )
        assert owner_change.status_code == 403
        assert owner_change.json()["code"] == "forbidden_owner_assignment"
        archived = client.post(f"/api/v1/crm/records/account/{company['id']}/archive")
        assert archived.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_external_crm_authority_blocks_only_authoritative_fields(client: TestClient) -> None:
    company = create_company(client, name="Authority Account")
    contact = create_contact(client, str(company["id"]), first_name="Authority")
    connection_id = uuid4()

    async def seed_mapping() -> None:
        engine = create_async_engine(TEST_DB_URL)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            session.add(
                IntegrationConnection(
                    id=connection_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    connector_key="hubspot",
                    connection_status="active",
                    created_by_user_id=PRIMARY_USER_ID,
                    connected_at=datetime.now(UTC),
                    last_verified_at=datetime.now(UTC),
                    capability_state_json=["crm_read", "crm_write"],
                    metadata_version=1,
                )
            )
            session.add(
                CRMFieldMapping(
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    connection_id=connection_id,
                    entity_type="contact",
                    revenueos_field="first_name",
                    external_property_name="firstname",
                    external_property_type="string",
                    authority="crm_authoritative",
                    configured_by_user_id=PRIMARY_USER_ID,
                )
            )
            await session.commit()
        await engine.dispose()

    asyncio.run(seed_mapping())
    configured = client.put("/api/v1/crm/settings", json={"mode": "external", "confirmed": True})
    assert configured.status_code == 200, configured.text
    blocked = client.patch(f"/api/v1/contacts/{contact['id']}", json={"firstName": "Blocked"})
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "crm_authoritative_field"
    blocked_create = client.post(
        "/api/v1/contacts",
        json={
            "companyId": company["id"],
            "firstName": "Externally",
            "lastName": "Managed",
        },
    )
    assert blocked_create.status_code == 409
    assert blocked_create.json()["code"] == "crm_authoritative_field"
    allowed = client.patch(f"/api/v1/contacts/{contact['id']}", json={"phone": "+61 400 100 200"})
    assert allowed.status_code == 200
    assert allowed.json()["phone"] == "+61 400 100 200"
    crm_record = client.get(f"/api/v1/crm/records/contact/{contact['id']}").json()
    first_name = next(field for field in crm_record["coreFields"] if field["key"] == "first_name")
    assert first_name["authority"] == "crm_authoritative"


@pytest.mark.parametrize(
    ("field_type", "options", "value", "expected"),
    [
        ("short_text", [], "Priority account", "Priority account"),
        ("number", [], 12.5, "12.5"),
        ("date", [], "2027-01-31", "2027-01-31"),
        ("boolean", [], False, False),
        ("single_select", ["Gold", "Silver"], "Gold", "Gold"),
        ("url", [], "https://example.com/path", "https://example.com/path"),
    ],
)
def test_supported_custom_field_types_round_trip(
    client: TestClient,
    field_type: str,
    options: list[str],
    value: object,
    expected: object,
) -> None:
    company = create_company(client, name=f"Typed {field_type} Account")
    definition = client.post(
        "/api/v1/crm/custom-fields",
        json={
            "entityType": "account",
            "fieldKey": f"typed_{field_type}",
            "label": f"Typed {field_type}",
            "fieldType": field_type,
            "options": options,
        },
    )
    assert definition.status_code == 201, definition.text
    updated = client.put(
        f"/api/v1/crm/records/account/{company['id']}/custom-fields/{definition.json()['id']}",
        json={"value": value},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["value"] == expected


def test_custom_field_limit_counts_active_definitions(client: TestClient) -> None:
    definition_ids: list[str] = []
    for index in range(25):
        response = client.post(
            "/api/v1/crm/custom-fields",
            json={
                "entityType": "contact",
                "fieldKey": f"bounded_{index}",
                "label": f"Bounded {index}",
                "fieldType": "short_text",
                "displayOrder": index,
            },
        )
        assert response.status_code == 201, response.text
        definition_ids.append(response.json()["id"])
    blocked = client.post(
        "/api/v1/crm/custom-fields",
        json={
            "entityType": "contact",
            "fieldKey": "bounded_overflow",
            "label": "Bounded overflow",
            "fieldType": "short_text",
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "custom_field_limit_reached"
    assert client.post(f"/api/v1/crm/custom-fields/{definition_ids[0]}/archive").status_code == 200
    replacement = client.post(
        "/api/v1/crm/custom-fields",
        json={
            "entityType": "contact",
            "fieldKey": "bounded_replacement",
            "label": "Bounded replacement",
            "fieldType": "short_text",
        },
    )
    assert replacement.status_code == 201, replacement.text


def test_custom_field_rejects_reserved_core_key(client: TestClient) -> None:
    response = client.post(
        "/api/v1/crm/custom-fields",
        json={
            "entityType": "opportunity",
            "fieldKey": "expected_close_date",
            "label": "Conflicting close date",
            "fieldType": "date",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "reserved_custom_field_key"
