from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from revenueos.auth import get_current_user
from revenueos.models import (
    CaptureSession,
    ConversationThreadAuditEvent,
    Evidence,
    Interaction,
    InteractionIntelligenceSnapshot,
)

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID
from .test_business_api import create_company, create_contact, create_opportunity
from .test_interaction_api import create_interaction
from .test_meeting_api import cast_auth_dependency, secondary_user


def test_confirmed_threads_keep_same_company_initiatives_separate_across_months(
    app: FastAPI,
    client: TestClient,
) -> None:
    company_id = str(create_company(client, name="Northstar Energy")["id"])
    contact_id = str(create_contact(client, company_id, first_name="Morgan")["id"])
    january = create_interaction(
        client,
        title="January expansion discovery",
        interaction_type="phone_call",
        company_id=company_id,
        contact_id=contact_id,
        call_direction="outbound",
    )
    february = create_interaction(
        client,
        title="February renewal discussion",
        interaction_type="phone_call",
        company_id=company_id,
        contact_id=contact_id,
        call_direction="outbound",
    )
    april = create_interaction(
        client,
        title="April expansion follow-up",
        interaction_type="phone_call",
        company_id=company_id,
        contact_id=contact_id,
        call_direction="outbound",
    )
    july = create_interaction(
        client,
        title="July expansion planning",
        interaction_type="phone_call",
        company_id=company_id,
        contact_id=contact_id,
        call_direction="outbound",
    )

    async def seed_validated_history() -> None:
        entries = (
            (
                UUID(str(january["id"])),
                datetime(2026, 1, 15, 2, 0, tzinfo=UTC),
                "The expansion launch is confirmed for January 2027.",
                "not_assessed",
            ),
            (
                UUID(str(february["id"])),
                datetime(2026, 2, 20, 2, 0, tzinfo=UTC),
                "The renewal will not proceed before November 2027.",
                "not_assessed",
            ),
            (
                UUID(str(april["id"])),
                datetime(2026, 4, 21, 2, 0, tzinfo=UTC),
                "The expansion launch moved to April 2027.",
                "conflicting",
            ),
        )
        async with app.state.session_factory() as session:
            for interaction_id, occurred_at, statement, conflict_state in entries:
                interaction = await session.scalar(
                    select(Interaction).where(
                        Interaction.organisation_id == PRIMARY_ORGANISATION_ID,
                        Interaction.id == interaction_id,
                    )
                )
                assert interaction is not None
                interaction.lifecycle_status = "completed"
                interaction.actual_start_at = occurred_at
                interaction.actual_end_at = occurred_at
                capture_id = uuid4()
                evidence_id = uuid4()
                session.add(
                    CaptureSession(
                        id=capture_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_id=interaction_id,
                        capture_type="manual_notes",
                        status="completed",
                        started_by_user_id=PRIMARY_USER_ID,
                        started_at=occurred_at,
                        completed_at=occurred_at,
                    )
                )
                session.add(
                    Evidence(
                        id=evidence_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_id=interaction_id,
                        capture_session_id=capture_id,
                        evidence_type="user_observation",
                        origin_class="salesperson_reported",
                        support_class="reported",
                        validation_state="verified",
                        captured_by_user_id=PRIMARY_USER_ID,
                        captured_at=occurred_at,
                        lifecycle_status="available",
                        retention_class="inherited",
                    )
                )
                session.add(
                    InteractionIntelligenceSnapshot(
                        id=uuid4(),
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_id=interaction_id,
                        opportunity_id=None,
                        session_id=capture_id,
                        schema_version=1,
                        version=1,
                        validation_state="validated",
                        content_json={
                            "items": [
                                {
                                    "evidenceId": str(evidence_id),
                                    "category": "timeline",
                                    "statement": statement,
                                    "origin": "salesperson_reported",
                                    "validationState": "verified",
                                    "conflictState": conflict_state,
                                }
                            ]
                        },
                        source_evidence_ids=[str(evidence_id)],
                        created_at=occurred_at,
                    )
                )
            july_record = await session.scalar(
                select(Interaction).where(
                    Interaction.organisation_id == PRIMARY_ORGANISATION_ID,
                    Interaction.id == UUID(str(july["id"])),
                )
            )
            assert july_record is not None
            july_record.scheduled_start_at = datetime(2026, 7, 10, 2, 0, tzinfo=UTC)
            await session.commit()

    asyncio.run(seed_validated_history())

    selected = client.patch("/api/v1/methodologies/current", json={"selection": "bant"})
    assert selected.status_code == 200, selected.text

    ungrouped = client.get(f"/api/v1/interactions/{april['id']}/conversation-memory")
    assert ungrouped.status_code == 200, ungrouped.text
    assert ungrouped.json()["assignment"]["thread"] is None
    assert ungrouped.json()["confirmedThread"] is None
    assert [item["interactionTitle"] for item in ungrouped.json()["currentConversation"]["sourceConversations"]] == [
        "April expansion follow-up"
    ]

    expansion = client.post(
        "/api/v1/conversation-threads",
        json={
            "name": "Expansion programme",
            "companyId": company_id,
            "initialInteractionId": january["id"],
            "expectedAssignmentLockVersion": 0,
        },
    )
    assert expansion.status_code == 201, expansion.text
    renewal = client.post(
        "/api/v1/conversation-threads",
        json={
            "name": "Renewal",
            "companyId": company_id,
            "initialInteractionId": february["id"],
            "expectedAssignmentLockVersion": 0,
        },
    )
    assert renewal.status_code == 201, renewal.text

    suggested = client.get(f"/api/v1/interactions/{april['id']}/conversation-memory").json()
    assert suggested["assignment"]["thread"] is None
    assert {item["thread"]["name"] for item in suggested["suggestions"]} == {
        "Expansion programme",
        "Renewal",
    }
    assert all("Same company" in item["reasons"] for item in suggested["suggestions"])
    assert all("1 participant in common" in item["reasons"] for item in suggested["suggestions"])

    assigned = client.put(
        f"/api/v1/interactions/{april['id']}/thread-assignment",
        json={"threadId": expansion.json()["id"], "expectedLockVersion": 0},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["confirmationKind"] == "user_confirmed"
    assert assigned.json()["lockVersion"] == 1
    july_assigned = client.put(
        f"/api/v1/interactions/{july['id']}/thread-assignment",
        json={"threadId": expansion.json()["id"], "expectedLockVersion": 0},
    )
    assert july_assigned.status_code == 200, july_assigned.text

    memory = client.get(f"/api/v1/interactions/{april['id']}/conversation-memory")
    assert memory.status_code == 200, memory.text
    body = memory.json()
    assert body["assignment"]["thread"]["name"] == "Expansion programme"
    current_titles = {item["interactionTitle"] for item in body["currentConversation"]["sourceConversations"]}
    cumulative_titles = {item["interactionTitle"] for item in body["confirmedThread"]["sourceConversations"]}
    assert current_titles == {"April expansion follow-up"}
    assert cumulative_titles == {"January expansion discovery", "April expansion follow-up"}
    assert "February renewal discussion" not in cumulative_titles
    timing = next(item for item in body["confirmedThread"]["items"] if item["fieldKey"] == "timing")
    assert timing["state"] == "conflicting"
    assert len(timing["conflicts"]) >= 1
    source_dates = {
        item["interactionTitle"]: item["occurredAt"] for item in body["confirmedThread"]["sourceConversations"]
    }
    assert source_dates["January expansion discovery"].startswith("2026-01-15")
    assert source_dates["April expansion follow-up"].startswith("2026-04-21")

    corrected = client.put(
        f"/api/v1/interactions/{april['id']}/thread-assignment",
        json={"threadId": renewal.json()["id"], "expectedLockVersion": 1},
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["confirmationKind"] == "user_corrected"
    assert corrected.json()["lockVersion"] == 2
    stale_write = client.put(
        f"/api/v1/interactions/{april['id']}/thread-assignment",
        json={"threadId": expansion.json()["id"], "expectedLockVersion": 1},
    )
    assert stale_write.status_code == 409
    assert stale_write.json()["code"] == "conversation_thread_assignment_conflict"

    corrected_memory = client.get(f"/api/v1/interactions/{april['id']}/conversation-memory").json()
    corrected_titles = {item["interactionTitle"] for item in corrected_memory["confirmedThread"]["sourceConversations"]}
    assert corrected_titles == {"February renewal discussion", "April expansion follow-up"}

    async def audit_actions() -> set[str]:
        async with app.state.session_factory() as session:
            actions = await session.scalars(
                select(ConversationThreadAuditEvent.action).where(
                    ConversationThreadAuditEvent.organisation_id == PRIMARY_ORGANISATION_ID,
                )
            )
            return set(actions.all())

    assert {"created", "assigned", "reassigned", "unassigned"}.issubset(asyncio.run(audit_actions()))


def test_memory_excludes_snapshot_when_its_evidence_is_deleted(
    app: FastAPI,
    client: TestClient,
) -> None:
    company_id = str(create_company(client, name="Evidence liveness account")["id"])
    source = create_interaction(
        client,
        title="Reviewed phone conversation",
        interaction_type="phone_call",
        company_id=company_id,
        call_direction="outbound",
    )
    target = create_interaction(
        client,
        title="Upcoming evidence review",
        interaction_type="online_meeting",
        company_id=company_id,
    )
    source_id = UUID(str(source["id"]))
    evidence_id = uuid4()
    capture_id = uuid4()
    occurred_at = datetime(2026, 8, 10, 2, 0, tzinfo=UTC)

    async def seed_snapshot() -> None:
        async with app.state.session_factory() as session:
            interaction = await session.scalar(
                select(Interaction).where(
                    Interaction.organisation_id == PRIMARY_ORGANISATION_ID,
                    Interaction.id == source_id,
                )
            )
            assert interaction is not None
            interaction.lifecycle_status = "completed"
            interaction.actual_start_at = occurred_at
            interaction.actual_end_at = occurred_at
            session.add_all(
                (
                    CaptureSession(
                        id=capture_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_id=source_id,
                        capture_type="manual_notes",
                        status="completed",
                        started_by_user_id=PRIMARY_USER_ID,
                        started_at=occurred_at,
                        completed_at=occurred_at,
                    ),
                    Evidence(
                        id=evidence_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_id=source_id,
                        capture_session_id=capture_id,
                        evidence_type="user_observation",
                        origin_class="salesperson_reported",
                        support_class="reported",
                        validation_state="verified",
                        captured_by_user_id=PRIMARY_USER_ID,
                        captured_at=occurred_at,
                        lifecycle_status="available",
                        retention_class="inherited",
                    ),
                    InteractionIntelligenceSnapshot(
                        id=uuid4(),
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_id=source_id,
                        opportunity_id=None,
                        session_id=capture_id,
                        schema_version=1,
                        version=1,
                        validation_state="validated",
                        content_json={
                            "items": [
                                {
                                    "evidenceId": str(evidence_id),
                                    "category": "timeline",
                                    "statement": "The review is planned for September 2026.",
                                    "origin": "salesperson_reported",
                                    "validationState": "verified",
                                    "conflictState": "not_assessed",
                                }
                            ]
                        },
                        source_evidence_ids=[str(evidence_id)],
                        created_at=occurred_at,
                    ),
                )
            )
            await session.commit()

    asyncio.run(seed_snapshot())
    selected = client.patch("/api/v1/methodologies/current", json={"selection": "bant"})
    assert selected.status_code == 200, selected.text
    thread = client.post(
        "/api/v1/conversation-threads",
        json={
            "name": "Evidence-backed initiative",
            "companyId": company_id,
            "initialInteractionId": source["id"],
            "expectedAssignmentLockVersion": 0,
        },
    )
    assert thread.status_code == 201, thread.text
    assigned = client.put(
        f"/api/v1/interactions/{target['id']}/thread-assignment",
        json={"threadId": thread.json()["id"], "expectedLockVersion": 0},
    )
    assert assigned.status_code == 200, assigned.text

    current = client.get(f"/api/v1/interactions/{source['id']}/conversation-memory")
    cumulative = client.get(f"/api/v1/interactions/{target['id']}/conversation-memory")
    assert current.status_code == 200, current.text
    assert cumulative.status_code == 200, cumulative.text
    assert [item["interactionTitle"] for item in current.json()["currentConversation"]["sourceConversations"]] == [
        "Reviewed phone conversation"
    ]
    assert [item["interactionTitle"] for item in cumulative.json()["confirmedThread"]["sourceConversations"]] == [
        "Reviewed phone conversation"
    ]

    async def delete_evidence() -> None:
        async with app.state.session_factory() as session:
            evidence = await session.scalar(
                select(Evidence).where(
                    Evidence.organisation_id == PRIMARY_ORGANISATION_ID,
                    Evidence.id == evidence_id,
                )
            )
            assert evidence is not None
            evidence.lifecycle_status = "deleted"
            evidence.deleted_at = datetime(2026, 8, 11, 2, 0, tzinfo=UTC)
            await session.commit()

    asyncio.run(delete_evidence())
    current_after_delete = client.get(f"/api/v1/interactions/{source['id']}/conversation-memory")
    cumulative_after_delete = client.get(f"/api/v1/interactions/{target['id']}/conversation-memory")
    assert current_after_delete.status_code == 200, current_after_delete.text
    assert cumulative_after_delete.status_code == 200, cumulative_after_delete.text
    assert current_after_delete.json()["currentConversation"]["sourceConversations"] == []
    assert cumulative_after_delete.json()["confirmedThread"]["sourceConversations"] == []


def test_thread_company_compatibility_uses_all_authoritative_relationships(
    app: FastAPI,
    client: TestClient,
) -> None:
    company_a = str(create_company(client, name="Authoritative company A")["id"])
    company_b = str(create_company(client, name="Authoritative company B")["id"])
    opportunity_a = str(create_opportunity(client, company_a, name="Company A programme")["id"])
    opportunity_b = str(create_opportunity(client, company_b, name="Company B programme")["id"])
    contact_a = str(create_contact(client, company_a, first_name="Alex")["id"])

    opportunity_linked = create_interaction(
        client,
        title="Opportunity-linked conversation",
        opportunity_id=opportunity_a,
    )
    inferred = client.post(
        "/api/v1/conversation-threads",
        json={
            "name": "Inferred company initiative",
            "initialInteractionId": opportunity_linked["id"],
            "expectedAssignmentLockVersion": 0,
        },
    )
    assert inferred.status_code == 201, inferred.text
    assert inferred.json()["companyId"] == company_a

    company_b_thread = client.post(
        "/api/v1/conversation-threads",
        json={"name": "Company B initiative", "companyId": company_b},
    )
    assert company_b_thread.status_code == 201, company_b_thread.text
    another_opportunity_linked = create_interaction(
        client,
        title="Another opportunity-linked conversation",
        opportunity_id=opportunity_a,
    )
    mismatch = client.put(
        f"/api/v1/interactions/{another_opportunity_linked['id']}/thread-assignment",
        json={"threadId": company_b_thread.json()["id"], "expectedLockVersion": 0},
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "conversation_thread_company_mismatch"

    contact_linked = create_interaction(
        client,
        title="Person-linked phone conversation",
        interaction_type="phone_call",
        contact_id=contact_a,
        call_direction="outbound",
    )
    contact_mismatch = client.post(
        "/api/v1/conversation-threads",
        json={
            "name": "Wrong company from Person",
            "companyId": company_b,
            "initialInteractionId": contact_linked["id"],
            "expectedAssignmentLockVersion": 0,
        },
    )
    assert contact_mismatch.status_code == 409
    assert contact_mismatch.json()["code"] == "conversation_thread_company_mismatch"

    ambiguous = create_interaction(
        client,
        title="Legacy ambiguous relationships",
        company_id=company_a,
    )

    async def make_relationships_ambiguous() -> None:
        async with app.state.session_factory() as session:
            interaction = await session.scalar(
                select(Interaction).where(
                    Interaction.organisation_id == PRIMARY_ORGANISATION_ID,
                    Interaction.id == UUID(str(ambiguous["id"])),
                )
            )
            assert interaction is not None
            interaction.opportunity_id = UUID(opportunity_b)
            await session.commit()

    asyncio.run(make_relationships_ambiguous())
    ambiguous_create = client.post(
        "/api/v1/conversation-threads",
        json={
            "name": "Must not choose relationship precedence",
            "initialInteractionId": ambiguous["id"],
            "expectedAssignmentLockVersion": 0,
        },
    )
    assert ambiguous_create.status_code == 409
    assert ambiguous_create.json()["code"] == "conversation_thread_company_ambiguous"
    ambiguous_assignment = client.put(
        f"/api/v1/interactions/{ambiguous['id']}/thread-assignment",
        json={"threadId": company_b_thread.json()["id"], "expectedLockVersion": 0},
    )
    assert ambiguous_assignment.status_code == 409
    assert ambiguous_assignment.json()["code"] == "conversation_thread_company_ambiguous"


def test_assignment_version_is_monotonic_across_unassign_reassign_and_create(
    client: TestClient,
) -> None:
    interaction = create_interaction(client, title="ABA-safe assignment")
    first_thread = client.post("/api/v1/conversation-threads", json={"name": "First initiative"})
    second_thread = client.post("/api/v1/conversation-threads", json={"name": "Second initiative"})
    assert first_thread.status_code == 201, first_thread.text
    assert second_thread.status_code == 201, second_thread.text

    assigned = client.put(
        f"/api/v1/interactions/{interaction['id']}/thread-assignment",
        json={"threadId": first_thread.json()["id"], "expectedLockVersion": 0},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["lockVersion"] == 1

    unassigned = client.put(
        f"/api/v1/interactions/{interaction['id']}/thread-assignment",
        json={"threadId": None, "expectedLockVersion": 1},
    )
    assert unassigned.status_code == 200, unassigned.text
    assert unassigned.json()["thread"] is None
    assert unassigned.json()["lockVersion"] == 2

    for stale_version in (0, 1):
        stale = client.put(
            f"/api/v1/interactions/{interaction['id']}/thread-assignment",
            json={
                "threadId": second_thread.json()["id"],
                "expectedLockVersion": stale_version,
            },
        )
        assert stale.status_code == 409
        assert stale.json()["code"] == "conversation_thread_assignment_conflict"

    reassigned = client.put(
        f"/api/v1/interactions/{interaction['id']}/thread-assignment",
        json={"threadId": second_thread.json()["id"], "expectedLockVersion": 2},
    )
    assert reassigned.status_code == 200, reassigned.text
    assert reassigned.json()["lockVersion"] == 3
    assert reassigned.json()["confirmationKind"] == "user_corrected"

    removed_again = client.put(
        f"/api/v1/interactions/{interaction['id']}/thread-assignment",
        json={"threadId": None, "expectedLockVersion": 3},
    )
    assert removed_again.status_code == 200, removed_again.text
    assert removed_again.json()["lockVersion"] == 4

    missing_version = client.post(
        "/api/v1/conversation-threads",
        json={"name": "Missing version", "initialInteractionId": interaction["id"]},
    )
    assert missing_version.status_code == 422

    stale_create = client.post(
        "/api/v1/conversation-threads",
        json={
            "name": "Stale create",
            "initialInteractionId": interaction["id"],
            "expectedAssignmentLockVersion": 3,
        },
    )
    assert stale_create.status_code == 409
    assert stale_create.json()["code"] == "conversation_thread_assignment_conflict"

    recreated = client.post(
        "/api/v1/conversation-threads",
        json={
            "name": "Fresh create",
            "initialInteractionId": interaction["id"],
            "expectedAssignmentLockVersion": 4,
        },
    )
    assert recreated.status_code == 201, recreated.text
    final_assignment = client.get(f"/api/v1/interactions/{interaction['id']}/thread-assignment")
    assert final_assignment.status_code == 200, final_assignment.text
    assert final_assignment.json()["thread"]["id"] == recreated.json()["id"]
    assert final_assignment.json()["lockVersion"] == 5


def test_conversation_threads_are_tenant_scoped_and_hide_cross_tenant_attachments(
    app: FastAPI,
    client: TestClient,
) -> None:
    primary_interaction = create_interaction(client, title="Primary tenant conversation")
    primary_thread = client.post("/api/v1/conversation-threads", json={"name": "Primary initiative"})
    assert primary_thread.status_code == 201, primary_thread.text

    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    secondary_company = create_company(client, name="Secondary thread company")
    secondary_interaction = create_interaction(
        client,
        title="Secondary tenant conversation",
        company_id=str(secondary_company["id"]),
    )
    secondary_thread = client.post(
        "/api/v1/conversation-threads",
        json={"name": "Secondary initiative", "companyId": secondary_company["id"]},
    )
    assert secondary_thread.status_code == 201, secondary_thread.text
    hidden_primary_attachment = client.put(
        f"/api/v1/interactions/{secondary_interaction['id']}/thread-assignment",
        json={"threadId": primary_thread.json()["id"], "expectedLockVersion": 0},
    )
    assert hidden_primary_attachment.status_code == 404
    assert hidden_primary_attachment.json()["code"] == "conversation_thread_not_found"
    app.dependency_overrides.pop(get_current_user)

    listed_ids = {item["id"] for item in client.get("/api/v1/conversation-threads").json()}
    assert primary_thread.json()["id"] in listed_ids
    assert secondary_thread.json()["id"] not in listed_ids
    assert client.get(f"/api/v1/interactions/{secondary_interaction['id']}/conversation-memory").status_code == 404
    assert client.get(f"/api/v1/interactions/{secondary_interaction['id']}/thread-assignment").status_code == 404
    assert (
        client.patch(
            f"/api/v1/conversation-threads/{secondary_thread.json()['id']}",
            json={"name": "Cross-tenant rename", "expectedLockVersion": 1},
        ).status_code
        == 404
    )
    hidden_secondary_attachment = client.put(
        f"/api/v1/interactions/{primary_interaction['id']}/thread-assignment",
        json={"threadId": secondary_thread.json()["id"], "expectedLockVersion": 0},
    )
    assert hidden_secondary_attachment.status_code == 404
    assert hidden_secondary_attachment.json()["code"] == "conversation_thread_not_found"
    hidden_company = client.post(
        "/api/v1/conversation-threads",
        json={"name": "Cross-tenant company", "companyId": secondary_company["id"]},
    )
    assert hidden_company.status_code == 404
    assert hidden_company.json()["code"] == "company_not_found"
