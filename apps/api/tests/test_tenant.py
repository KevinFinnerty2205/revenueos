import asyncio
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.auth import AuthenticatedUser
from revenueos.models import Base, Organisation, OrganisationMembership, User
from revenueos.services import OrganisationAccessError, OrganisationAccessService


def test_persisted_membership_resolves_from_trusted_auth_context(tmp_path: object) -> None:
    database_path = str(tmp_path) + "/tenant.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    organisation_id = UUID("10000000-0000-4000-8000-000000000001")
    user_id = UUID("10000000-0000-4000-8000-000000000002")
    authenticated_user = AuthenticatedUser(
        user_id=user_id,
        external_auth_id="user_test_001",
        display_name="Test User",
        email="test@example.test",
        organisation_id=organisation_id,
        organisation_name="Test Organisation",
        organisation_slug="test-organisation",
        role="manager",
        auth_mode="mock",
    )

    async def scenario() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add_all(
                [
                    Organisation(id=organisation_id, name="Test Organisation", slug="test-organisation"),
                    User(
                        id=user_id,
                        external_auth_id="user_test_001",
                        email="test@example.test",
                        display_name="Test User",
                    ),
                    OrganisationMembership(
                        organisation_id=organisation_id,
                        user_id=user_id,
                        role="manager",
                    ),
                ]
            )
            await session.commit()
        async with session_factory() as session:
            context = await OrganisationAccessService(session).resolve(authenticated_user)
            assert context.organisation_id == organisation_id
            assert context.user_id == user_id
            assert context.role == "manager"
        await engine.dispose()

    asyncio.run(scenario())


def test_missing_membership_fails_closed(tmp_path: object) -> None:
    database_path = str(tmp_path) + "/missing-membership.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    authenticated_user = AuthenticatedUser(
        user_id=UUID("20000000-0000-4000-8000-000000000002"),
        external_auth_id="user_test_002",
        display_name="No Membership",
        email="none@example.test",
        organisation_id=UUID("20000000-0000-4000-8000-000000000001"),
        organisation_name="Missing Organisation",
        organisation_slug="missing-organisation",
        role="member",
        auth_mode="mock",
    )

    async def scenario() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            with pytest.raises(OrganisationAccessError):
                await OrganisationAccessService(session).resolve(authenticated_user)
        await engine.dispose()

    asyncio.run(scenario())
