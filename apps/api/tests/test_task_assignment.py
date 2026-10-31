from __future__ import annotations

import asyncio
from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import AuthenticatedUser, get_current_user
from revenueos.models import (
    Company,
    Contact,
    Opportunity,
    OrganisationMembership,
    Task,
    User,
)

from .conftest import (
    PRIMARY_ORGANISATION_ID,
    PRIMARY_USER_ID,
    SECONDARY_USER_ID,
    TEST_DB_URL,
)

PEER_USER_ID = UUID("00000000-0000-4000-8000-000000000021")


def _primary_identity(role: str) -> AuthenticatedUser:
    assert role in {"admin", "member"}
    return AuthenticatedUser(
        user_id=PRIMARY_USER_ID,
        external_auth_id="user_dev_001",
        display_name="Alex Morgan",
        email="alex@example.test",
        organisation_id=PRIMARY_ORGANISATION_ID,
        organisation_name="Example Revenue Team",
        organisation_slug="example-revenue-team",
        role="admin" if role == "admin" else "member",
        auth_mode="mock",
    )


async def _replace_peer(*, user_status: str, membership_status: str) -> None:
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await session.execute(update(User).where(User.id == PEER_USER_ID).values(status=user_status))
            await session.execute(
                update(OrganisationMembership)
                .where(
                    OrganisationMembership.organisation_id == PRIMARY_ORGANISATION_ID,
                    OrganisationMembership.user_id == PEER_USER_ID,
                )
                .values(status=membership_status)
            )
            await session.commit()
    finally:
        await engine.dispose()


@pytest.fixture
def active_peer_member() -> Iterator[UUID]:
    async def seed() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                for model in (Company, Contact, Opportunity):
                    await session.execute(
                        update(model).where(model.owner_user_id == PEER_USER_ID).values(owner_user_id=PRIMARY_USER_ID)
                    )
                await session.execute(
                    update(Task).where(Task.assigned_user_id == PEER_USER_ID).values(assigned_user_id=None)
                )
                await session.execute(
                    delete(OrganisationMembership).where(OrganisationMembership.user_id == PEER_USER_ID)
                )
                await session.execute(delete(User).where(User.id == PEER_USER_ID))
                session.add(
                    User(
                        id=PEER_USER_ID,
                        external_auth_id="user_task_peer_001",
                        email="task-peer@example.test",
                        display_name="Casey Nguyen",
                        status="active",
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
                await session.commit()
        finally:
            await engine.dispose()

    async def clean() -> None:
        engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                for model in (Company, Contact, Opportunity):
                    await session.execute(
                        update(model).where(model.owner_user_id == PEER_USER_ID).values(owner_user_id=PRIMARY_USER_ID)
                    )
                await session.execute(
                    update(Task).where(Task.assigned_user_id == PEER_USER_ID).values(assigned_user_id=None)
                )
                await session.execute(
                    delete(OrganisationMembership).where(OrganisationMembership.user_id == PEER_USER_ID)
                )
                await session.execute(delete(User).where(User.id == PEER_USER_ID))
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(seed())
    yield PEER_USER_ID
    asyncio.run(clean())


def test_admin_peer_member_self_peer_denial_and_unassign(
    app: FastAPI,
    client: TestClient,
    active_peer_member: UUID,
) -> None:
    members = client.get("/api/v1/crm/members")
    assert members.status_code == 200, members.text
    peer = next(item for item in members.json() if item["userId"] == str(active_peer_member))
    assert peer == {
        "userId": str(active_peer_member),
        "displayName": "Casey Nguyen",
        "active": True,
        "canAssign": True,
    }

    admin_assignment = client.post(
        "/api/v1/tasks",
        json={
            "title": "Administrator peer assignment",
            "assignedUserId": str(active_peer_member),
        },
    )
    assert admin_assignment.status_code == 201, admin_assignment.text
    assert admin_assignment.json()["assignedUserId"] == str(active_peer_member)

    unassigned = client.patch(
        f"/api/v1/tasks/{admin_assignment.json()['id']}",
        json={"assignedUserId": None},
    )
    assert unassigned.status_code == 200, unassigned.text
    assert unassigned.json()["assignedUserId"] is None

    app.dependency_overrides[get_current_user] = lambda: _primary_identity("member")
    try:
        member_view = client.get("/api/v1/crm/members")
        assert member_view.status_code == 200, member_view.text
        by_id = {item["userId"]: item for item in member_view.json()}
        assert by_id[str(PRIMARY_USER_ID)]["canAssign"] is True
        assert by_id[str(active_peer_member)]["active"] is True
        assert by_id[str(active_peer_member)]["canAssign"] is False

        self_assignment = client.post(
            "/api/v1/tasks",
            json={
                "title": "Member self assignment",
                "assignedUserId": str(PRIMARY_USER_ID),
            },
        )
        assert self_assignment.status_code == 201, self_assignment.text
        assert self_assignment.json()["assignedUserId"] == str(PRIMARY_USER_ID)

        peer_denial = client.post(
            "/api/v1/tasks",
            json={
                "title": "Member peer assignment",
                "assignedUserId": str(active_peer_member),
            },
        )
        assert peer_denial.status_code == 403, peer_denial.text
        assert peer_denial.json()["code"] == "forbidden_owner_assignment"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_member_active_state_requires_active_membership_and_user(
    client: TestClient,
    active_peer_member: UUID,
) -> None:
    asyncio.run(_replace_peer(user_status="disabled", membership_status="active"))
    globally_disabled = client.get("/api/v1/crm/members")
    peer = next(item for item in globally_disabled.json() if item["userId"] == str(active_peer_member))
    assert peer["active"] is False
    assert peer["canAssign"] is False
    denied = client.post(
        "/api/v1/tasks",
        json={
            "title": "Disabled user assignment",
            "assignedUserId": str(active_peer_member),
        },
    )
    assert denied.status_code == 422, denied.text
    assert denied.json()["code"] == "invalid_relationship"

    asyncio.run(_replace_peer(user_status="active", membership_status="disabled"))
    membership_disabled = client.get("/api/v1/crm/members")
    peer = next(item for item in membership_disabled.json() if item["userId"] == str(active_peer_member))
    assert peer["active"] is False
    assert peer["canAssign"] is False


def test_edit_without_assignee_change_preserves_inactive_assignment(
    client: TestClient,
    active_peer_member: UUID,
) -> None:
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "Keep historic assignee",
            "assignedUserId": str(active_peer_member),
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]
    asyncio.run(_replace_peer(user_status="active", membership_status="disabled"))

    updated = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"title": "Keep historic assignee after edit"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["assignedUserId"] == str(active_peer_member)

    explicit_resend = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"assignedUserId": str(active_peer_member)},
    )
    assert explicit_resend.status_code == 422, explicit_resend.text
    assert explicit_resend.json()["code"] == "invalid_relationship"

    unassigned = client.patch(
        f"/api/v1/tasks/{task_id}",
        json={"assignedUserId": None},
    )
    assert unassigned.status_code == 200, unassigned.text
    assert unassigned.json()["assignedUserId"] is None


def test_owner_edits_omit_unchanged_inactive_member_but_reject_explicit_resend(
    client: TestClient,
    active_peer_member: UUID,
) -> None:
    company = client.post(
        "/api/v1/companies",
        json={
            "name": "Historic Owner Account",
            "ownerUserId": str(active_peer_member),
        },
    )
    assert company.status_code == 201, company.text
    contact = client.post(
        "/api/v1/contacts",
        json={
            "companyId": company.json()["id"],
            "firstName": "Historic",
            "lastName": "Owner",
            "ownerUserId": str(active_peer_member),
        },
    )
    assert contact.status_code == 201, contact.text
    opportunity = client.post(
        "/api/v1/opportunities",
        json={
            "name": "Historic Owner Opportunity",
            "ownerUserId": str(active_peer_member),
        },
    )
    assert opportunity.status_code == 201, opportunity.text

    asyncio.run(_replace_peer(user_status="active", membership_status="disabled"))

    edit_cases = (
        (
            f"/api/v1/companies/{company.json()['id']}",
            {"industry": "Software"},
        ),
        (
            f"/api/v1/contacts/{contact.json()['id']}",
            {"jobTitle": "Former account owner"},
        ),
        (
            f"/api/v1/opportunities/{opportunity.json()['id']}",
            {"description": "Ownership remains historical."},
        ),
    )
    for path, safe_update in edit_cases:
        updated = client.patch(path, json=safe_update)
        assert updated.status_code == 200, updated.text
        assert updated.json()["ownerUserId"] == str(active_peer_member)

        explicit_resend = client.patch(
            path,
            json={"ownerUserId": str(active_peer_member)},
        )
        assert explicit_resend.status_code == 422, explicit_resend.text
        assert explicit_resend.json()["code"] == "invalid_relationship"


def test_task_assignee_must_belong_to_the_current_tenant(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/tasks",
        json={
            "title": "Cross-tenant assignment",
            "assignedUserId": str(SECONDARY_USER_ID),
        },
    )

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "invalid_relationship"
