from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, update
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import ConnectionPoolEntry

from revenueos.config import Settings
from revenueos.main import create_app
from revenueos.models import (
    AIArtifact,
    AIJob,
    AIUsageCounter,
    Base,
    BetaDataRequest,
    BetaFeedback,
    BetaSystemEvent,
    CandidateEvidence,
    CaptureSession,
    Company,
    Contact,
    DataNoticeAcknowledgement,
    DebriefSession,
    DebriefTurn,
    Evidence,
    EvidenceFragment,
    Interaction,
    InteractionAuditEvent,
    InteractionIntelligenceSnapshot,
    Meeting,
    MeetingAuditEvent,
    MeetingParticipant,
    OnboardingProgress,
    Opportunity,
    OpportunityAuditEvent,
    Organisation,
    OrganisationBetaSettings,
    OrganisationMembership,
    PreInteractionBrief,
    RevenueBrainInsight,
    RevenueBrainInteractionSnapshot,
    RevenueBrainSnapshot,
    Task,
    Transcript,
    User,
)

TEST_DB = Path(__file__).with_name("test_revenueos.db")
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB}"
PRIMARY_ORGANISATION_ID = UUID("00000000-0000-4000-8000-000000000002")
PRIMARY_USER_ID = UUID("00000000-0000-4000-8000-000000000001")
SECONDARY_ORGANISATION_ID = UUID("00000000-0000-4000-8000-000000000012")
SECONDARY_USER_ID = UUID("00000000-0000-4000-8000-000000000011")


@pytest.fixture(scope="session", autouse=True)
def database() -> Iterator[None]:
    if TEST_DB.exists():
        TEST_DB.unlink()
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})

    def enable_foreign_keys(
        connection: DBAPIConnection,
        connection_record: ConnectionPoolEntry,
    ) -> None:
        del connection_record
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    event.listen(engine.sync_engine, "connect", enable_foreign_keys)

    async def create_tables_and_identities() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add_all(
                [
                    Organisation(
                        id=PRIMARY_ORGANISATION_ID,
                        external_auth_id="org_dev_001",
                        name="Example Revenue Team",
                        slug="example-revenue-team",
                    ),
                    User(
                        id=PRIMARY_USER_ID,
                        external_auth_id="user_dev_001",
                        email="alex@example.test",
                        display_name="Alex Morgan",
                    ),
                    OrganisationMembership(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=PRIMARY_USER_ID,
                        role="admin",
                    ),
                    Organisation(
                        id=SECONDARY_ORGANISATION_ID,
                        external_auth_id="org_other_001",
                        name="Other Revenue Team",
                        slug="other-revenue-team",
                    ),
                    User(
                        id=SECONDARY_USER_ID,
                        external_auth_id="user_other_001",
                        email="other@example.test",
                        display_name="Other User",
                    ),
                    OrganisationMembership(
                        organisation_id=SECONDARY_ORGANISATION_ID,
                        user_id=SECONDARY_USER_ID,
                        role="admin",
                    ),
                ]
            )
            await session.commit()
            session.add_all(
                [
                    DataNoticeAcknowledgement(
                        id=UUID("00000000-0000-4000-8000-000000000003"),
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=PRIMARY_USER_ID,
                        notice_version=1,
                    ),
                    DataNoticeAcknowledgement(
                        id=UUID("00000000-0000-4000-8000-000000000013"),
                        organisation_id=SECONDARY_ORGANISATION_ID,
                        user_id=SECONDARY_USER_ID,
                        notice_version=1,
                    ),
                ]
            )
            await session.commit()

    async def dispose() -> None:
        await engine.dispose()
        if TEST_DB.exists():
            TEST_DB.unlink()

    asyncio.run(create_tables_and_identities())
    yield
    asyncio.run(dispose())


@pytest.fixture(autouse=True)
def clean_business_entities() -> Iterator[None]:
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})

    async def clean() -> None:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            for model in (
                BetaFeedback,
                BetaSystemEvent,
                BetaDataRequest,
                AIUsageCounter,
                OnboardingProgress,
                OrganisationBetaSettings,
                RevenueBrainInsight,
                RevenueBrainInteractionSnapshot,
                InteractionIntelligenceSnapshot,
                RevenueBrainSnapshot,
                PreInteractionBrief,
                AIArtifact,
                AIJob,
                OpportunityAuditEvent,
                InteractionAuditEvent,
                CandidateEvidence,
                EvidenceFragment,
                DebriefTurn,
                DebriefSession,
                Evidence,
                CaptureSession,
                MeetingAuditEvent,
                Transcript,
                MeetingParticipant,
                Meeting,
                Interaction,
                Task,
                Contact,
                Opportunity,
                Company,
            ):
                await session.execute(delete(model))
            await session.execute(
                delete(DataNoticeAcknowledgement).where(DataNoticeAcknowledgement.notice_version != 1)
            )
            await session.execute(update(User).values(status="active"))
            await session.execute(update(OrganisationMembership).values(status="active"))
            await session.commit()

    asyncio.run(clean())
    yield
    asyncio.run(clean())
    asyncio.run(engine.dispose())


@pytest.fixture
def app() -> FastAPI:
    return create_app(
        Settings(
            environment="test",
            auth_mode="mock",
            mock_auth_enabled=True,
            database_url=TEST_DB_URL,
            log_level="WARNING",
            cors_origins="http://localhost:3000",
        ),
    )


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
