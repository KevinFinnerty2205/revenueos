from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.beta_maintenance import EXPORT_VERSION, _delete_organisation_records, _export_payload
from revenueos.config import Settings
from revenueos.models import (
    Company,
    ConversationThread,
    ConversationThreadAssignment,
    ConversationThreadAuditEvent,
    ConversationUserWorkspace,
    Interaction,
    Organisation,
    OrganisationMembership,
    User,
)

from .conftest import PRIMARY_ORGANISATION_ID, TEST_DB_URL


def test_conversation_threads_and_private_live_notes_export_and_erase_with_organisation() -> None:
    organisation_id = uuid4()
    user_id = uuid4()
    company_id = uuid4()
    interaction_id = uuid4()
    thread_id = uuid4()
    assignment_id = uuid4()
    audit_id = uuid4()
    workspace_id = uuid4()
    live_notes = "Private synthetic notes that must remain user-scoped."
    settings = Settings(
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url=TEST_DB_URL,
    )

    async def scenario() -> tuple[dict[str, object], dict[str, int]]:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with factory() as session:
                session.add_all(
                    [
                        Organisation(
                            id=organisation_id,
                            name="Synthetic conversation lifecycle organisation",
                            slug=f"conversation-lifecycle-{organisation_id.hex}",
                        ),
                        User(
                            id=user_id,
                            external_auth_id=f"conversation-lifecycle-{user_id.hex}",
                            email=f"{user_id.hex}@example.test",
                            display_name="Synthetic Conversation Owner",
                        ),
                    ]
                )
                await session.commit()
                session.add(
                    OrganisationMembership(
                        organisation_id=organisation_id,
                        user_id=user_id,
                        role="admin",
                    )
                )
                await session.commit()
                session.add(
                    Company(
                        id=company_id,
                        organisation_id=organisation_id,
                        name="Synthetic lifecycle company",
                        owner_user_id=user_id,
                    )
                )
                await session.commit()
                now = datetime.now(UTC)
                session.add(
                    Interaction(
                        id=interaction_id,
                        organisation_id=organisation_id,
                        company_id=company_id,
                        interaction_type="manual_interaction",
                        lifecycle_status="completed",
                        title="Synthetic lifecycle conversation",
                        actual_start_at=now,
                        actual_end_at=now,
                        timezone="Australia/Sydney",
                        created_by_user_id=user_id,
                    )
                )
                session.add(
                    ConversationThread(
                        id=thread_id,
                        organisation_id=organisation_id,
                        company_id=company_id,
                        name="Synthetic confirmed initiative",
                        status="active",
                        created_by_user_id=user_id,
                        updated_by_user_id=user_id,
                        lock_version=1,
                    )
                )
                await session.commit()
                session.add_all(
                    [
                        ConversationThreadAssignment(
                            id=assignment_id,
                            organisation_id=organisation_id,
                            thread_id=thread_id,
                            interaction_id=interaction_id,
                            confirmed_by_user_id=user_id,
                            confirmation_kind="user_confirmed",
                            lock_version=1,
                        ),
                        ConversationThreadAuditEvent(
                            id=audit_id,
                            organisation_id=organisation_id,
                            thread_id=thread_id,
                            interaction_id=interaction_id,
                            actor_user_id=user_id,
                            action="assigned",
                            metadata_json={"confirmation_kind": "user_confirmed"},
                            created_at=now,
                        ),
                        ConversationUserWorkspace(
                            id=workspace_id,
                            organisation_id=organisation_id,
                            interaction_id=interaction_id,
                            user_id=user_id,
                            live_notes=live_notes,
                            enhanced_notes=None,
                            follow_up_draft=None,
                            follow_up_reviewed=False,
                            lock_version=1,
                        ),
                    ]
                )
                await session.commit()
                exported = await _export_payload(
                    session,
                    organisation_id,
                    settings,
                    private_user_id=user_id,
                )

            await _delete_organisation_records(factory, settings, organisation_id)
            async with factory() as session:
                remaining = {
                    "threads": int(
                        await session.scalar(
                            select(func.count())
                            .select_from(ConversationThread)
                            .where(ConversationThread.organisation_id == organisation_id)
                        )
                        or 0
                    ),
                    "assignments": int(
                        await session.scalar(
                            select(func.count())
                            .select_from(ConversationThreadAssignment)
                            .where(ConversationThreadAssignment.organisation_id == organisation_id)
                        )
                        or 0
                    ),
                    "audits": int(
                        await session.scalar(
                            select(func.count())
                            .select_from(ConversationThreadAuditEvent)
                            .where(ConversationThreadAuditEvent.organisation_id == organisation_id)
                        )
                        or 0
                    ),
                    "workspaces": int(
                        await session.scalar(
                            select(func.count())
                            .select_from(ConversationUserWorkspace)
                            .where(ConversationUserWorkspace.organisation_id == organisation_id)
                        )
                        or 0
                    ),
                    "organisations": int(
                        await session.scalar(
                            select(func.count()).select_from(Organisation).where(Organisation.id == organisation_id)
                        )
                        or 0
                    ),
                }
            return exported, remaining
        finally:
            await engine.dispose()

    exported, remaining = asyncio.run(scenario())

    assert exported["exportVersion"] == EXPORT_VERSION
    threads = exported["conversationThreads"]
    assignments = exported["conversationThreadAssignments"]
    audits = exported["conversationThreadAuditEvents"]
    workspaces = exported["privateConversationWorkspaces"]
    assert isinstance(threads, list) and isinstance(threads[0], dict)
    assert isinstance(assignments, list) and isinstance(assignments[0], dict)
    assert isinstance(audits, list) and isinstance(audits[0], dict)
    assert isinstance(workspaces, list) and isinstance(workspaces[0], dict)
    assert threads[0]["id"] == thread_id
    assert assignments[0]["id"] == assignment_id
    assert audits[0]["id"] == audit_id
    assert workspaces[0]["live_notes"] == live_notes
    assert str(PRIMARY_ORGANISATION_ID) not in json.dumps(exported, default=str)
    assert remaining == {
        "threads": 0,
        "assignments": 0,
        "audits": 0,
        "workspaces": 0,
        "organisations": 0,
    }
