from __future__ import annotations

import asyncio
import shutil
from collections.abc import Iterator
from datetime import UTC, datetime
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
    ActionAuditEvent,
    ActionExecution,
    ActionExecutionAttempt,
    ActionProposal,
    ActionProposalVersion,
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
    ContactFieldSource,
    ContactSuppression,
    CreateApprovedContentItem,
    CreateBusinessCase,
    CreateBusinessCaseVersion,
    CreateDownloadGrant,
    CreatePresentation,
    CreatePresentationVersion,
    CreateTemplate,
    CreateTemplateSlide,
    CreateTemplateVersion,
    CreateUsageCounter,
    CreateValueModel,
    CreateValueModelVersion,
    CRMCustomFieldDefinition,
    CRMCustomFieldValue,
    CRMEntityMapping,
    CRMFieldMapping,
    CRMRecordChange,
    CRMStageMapping,
    DataNoticeAcknowledgement,
    DebriefSession,
    DebriefTurn,
    DocumentFragment,
    DocumentSource,
    EmailSource,
    EncryptedConnectorCredential,
    EngageCampaign,
    EngageCampaignAudience,
    EngageCampaignEnrollment,
    EngageCampaignVersion,
    EngageEnrollmentStep,
    EngageSequenceStep,
    EventAttendee,
    EventAttendeeImport,
    EventAttendeeUserState,
    EventCampaignLink,
    EventEncounter,
    Evidence,
    EvidenceFragment,
    ExecutionPreview,
    IntegrationAuditEvent,
    IntegrationConnection,
    Interaction,
    InteractionAuditEvent,
    InteractionIntelligenceSnapshot,
    LiveBriefProgress,
    LiveInteractionSession,
    LiveProcessingWindow,
    Meeting,
    MeetingAuditEvent,
    MeetingParticipant,
    MethodologyDefinition,
    MethodologyDefinitionVersion,
    MethodologyProjection,
    MethodologyReview,
    MockConnectorObject,
    OAuthConnectionState,
    OnboardingProgress,
    OnlineMeetingMetadata,
    OnlineMeetingTranscriptImport,
    Opportunity,
    OpportunityAuditEvent,
    OpportunityStageEvent,
    Organisation,
    OrganisationBetaSettings,
    OrganisationCRMSetting,
    OrganisationMembership,
    OrganisationMethodologySetting,
    OrganisationModuleEntitlement,
    OutreachMessage,
    OutreachPersonalizationSource,
    OutreachPolicy,
    OutreachVersion,
    PreInteractionBrief,
    ProspectBuyingRoleHypothesis,
    ProspectBuyingRoleSource,
    ProspectCandidateReason,
    ProspectContactPoint,
    ProspectDiscoveryCandidate,
    ProspectDiscoveryRun,
    ProspectPerson,
    ProspectResearchObservation,
    ProspectResearchObservationSource,
    ProspectResearchRun,
    ProspectResearchSource,
    ProspectResearchTarget,
    ProspectTargetFeedback,
    ProspectTargetMarket,
    ProspectTargetMarketVersion,
    ProspectUsageCounter,
    ProvisionalSignal,
    RecordingChunk,
    RecordingConsent,
    RecordingSession,
    RecordingUsageCounter,
    RevenueBrainInsight,
    RevenueBrainInteractionSnapshot,
    RevenueBrainSnapshot,
    RevenueBrainSourceSnapshot,
    SalesEvent,
    SalesForecastJudgment,
    SalesForecastJudgmentRevision,
    SalesForecastPeriod,
    SalesPipeline,
    SalesPipelineStage,
    SalesTarget,
    SalesTargetRevision,
    SourceCandidateEvidence,
    Task,
    Transcript,
    TranscriptSegment,
    TranscriptVersion,
    User,
    VisualAsset,
    VisualCandidateEvidence,
)

TEST_DB = Path(__file__).with_name("test_revenueos.db")
TEST_VISUAL_STORAGE = Path(__file__).with_name("test-visual-storage")
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB}"
PRIMARY_ORGANISATION_ID = UUID("00000000-0000-4000-8000-000000000002")
PRIMARY_USER_ID = UUID("00000000-0000-4000-8000-000000000001")
SECONDARY_ORGANISATION_ID = UUID("00000000-0000-4000-8000-000000000012")
SECONDARY_USER_ID = UUID("00000000-0000-4000-8000-000000000011")


@pytest.fixture(scope="session", autouse=True)
def database() -> Iterator[None]:
    if TEST_DB.exists():
        TEST_DB.unlink()
    shutil.rmtree(TEST_VISUAL_STORAGE, ignore_errors=True)
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
                    OrganisationModuleEntitlement(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        module_key="prospect",
                        enabled=True,
                        source="manual_private_beta",
                        configured_by_user_id=PRIMARY_USER_ID,
                        enabled_at=datetime.now(UTC),
                    ),
                    OrganisationModuleEntitlement(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        module_key="engage",
                        enabled=True,
                        source="manual_private_beta",
                        configured_by_user_id=PRIMARY_USER_ID,
                        enabled_at=datetime.now(UTC),
                    ),
                    OrganisationModuleEntitlement(
                        organisation_id=SECONDARY_ORGANISATION_ID,
                        module_key="engage",
                        enabled=True,
                        source="manual_private_beta",
                        configured_by_user_id=SECONDARY_USER_ID,
                        enabled_at=datetime.now(UTC),
                    ),
                    OrganisationModuleEntitlement(
                        organisation_id=SECONDARY_ORGANISATION_ID,
                        module_key="prospect",
                        enabled=True,
                        source="manual_private_beta",
                        configured_by_user_id=SECONDARY_USER_ID,
                        enabled_at=datetime.now(UTC),
                    ),
                    OrganisationModuleEntitlement(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        module_key="create",
                        enabled=True,
                        source="manual_private_beta",
                        configured_by_user_id=PRIMARY_USER_ID,
                        enabled_at=datetime.now(UTC),
                    ),
                    OrganisationModuleEntitlement(
                        organisation_id=SECONDARY_ORGANISATION_ID,
                        module_key="create",
                        enabled=True,
                        source="manual_private_beta",
                        configured_by_user_id=SECONDARY_USER_ID,
                        enabled_at=datetime.now(UTC),
                    ),
                    OrganisationModuleEntitlement(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        module_key="crm",
                        enabled=True,
                        source="manual_private_beta",
                        configured_by_user_id=PRIMARY_USER_ID,
                        enabled_at=datetime.now(UTC),
                    ),
                    OrganisationModuleEntitlement(
                        organisation_id=SECONDARY_ORGANISATION_ID,
                        module_key="crm",
                        enabled=True,
                        source="manual_private_beta",
                        configured_by_user_id=SECONDARY_USER_ID,
                        enabled_at=datetime.now(UTC),
                    ),
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
        shutil.rmtree(TEST_VISUAL_STORAGE, ignore_errors=True)

    asyncio.run(create_tables_and_identities())
    yield
    asyncio.run(dispose())


@pytest.fixture(autouse=True)
def clean_business_entities() -> Iterator[None]:
    engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})

    async def clean() -> None:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            await session.execute(update(RecordingSession).values(transcript_version_id=None))
            for model in (
                BetaFeedback,
                BetaSystemEvent,
                BetaDataRequest,
                OAuthConnectionState,
                CRMStageMapping,
                CRMFieldMapping,
                CRMEntityMapping,
                EncryptedConnectorCredential,
                MockConnectorObject,
                IntegrationAuditEvent,
                ActionExecutionAttempt,
                ActionExecution,
                ExecutionPreview,
                IntegrationConnection,
                EventCampaignLink,
                EngageEnrollmentStep,
                EngageCampaignEnrollment,
                EngageCampaignAudience,
                EngageSequenceStep,
                EngageCampaignVersion,
                EngageCampaign,
                EventEncounter,
                EventAttendeeUserState,
                EventAttendee,
                EventAttendeeImport,
                ContactSuppression,
                OutreachPersonalizationSource,
                OutreachVersion,
                OutreachMessage,
                OutreachPolicy,
                ActionAuditEvent,
                ActionProposalVersion,
                ActionProposal,
                MethodologyReview,
                MethodologyProjection,
                OrganisationMethodologySetting,
                MethodologyDefinitionVersion,
                MethodologyDefinition,
                AIUsageCounter,
                ContactFieldSource,
                ProspectTargetFeedback,
                ProspectCandidateReason,
                ProspectDiscoveryCandidate,
                ProspectDiscoveryRun,
                ProspectTargetMarketVersion,
                ProspectTargetMarket,
                ProspectBuyingRoleSource,
                ProspectContactPoint,
                ProspectBuyingRoleHypothesis,
                ProspectResearchObservationSource,
                ProspectResearchObservation,
                ProspectResearchSource,
                ProspectResearchRun,
                ProspectPerson,
                ProspectResearchTarget,
                ProspectUsageCounter,
                OnboardingProgress,
                OrganisationBetaSettings,
                RevenueBrainInsight,
                RevenueBrainInteractionSnapshot,
                InteractionIntelligenceSnapshot,
                RevenueBrainSnapshot,
                RevenueBrainSourceSnapshot,
                LiveBriefProgress,
                ProvisionalSignal,
                LiveProcessingWindow,
                LiveInteractionSession,
                PreInteractionBrief,
                AIArtifact,
                AIJob,
                CreateDownloadGrant,
                CreatePresentationVersion,
                CreatePresentation,
                CreateBusinessCaseVersion,
                CreateBusinessCase,
                CreateValueModelVersion,
                CreateValueModel,
                CreateApprovedContentItem,
                CreateTemplateSlide,
                CreateTemplateVersion,
                CreateTemplate,
                CreateUsageCounter,
                OpportunityAuditEvent,
                CRMRecordChange,
                CRMCustomFieldValue,
                CRMCustomFieldDefinition,
                OrganisationCRMSetting,
                InteractionAuditEvent,
                OnlineMeetingTranscriptImport,
                TranscriptSegment,
                TranscriptVersion,
                RecordingChunk,
                RecordingConsent,
                RecordingSession,
                RecordingUsageCounter,
                VisualCandidateEvidence,
                VisualAsset,
                SourceCandidateEvidence,
                DocumentFragment,
                DocumentSource,
                EmailSource,
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
                OnlineMeetingMetadata,
                Interaction,
                SalesEvent,
                SalesForecastJudgmentRevision,
                SalesForecastJudgment,
                SalesForecastPeriod,
                SalesTargetRevision,
                SalesTarget,
                Task,
                Contact,
                OpportunityStageEvent,
                Opportunity,
                SalesPipelineStage,
                SalesPipeline,
                Company,
            ):
                await session.execute(delete(model))
            await session.execute(
                delete(DataNoticeAcknowledgement).where(DataNoticeAcknowledgement.notice_version != 1)
            )
            await session.execute(update(User).values(status="active"))
            await session.execute(update(OrganisationMembership).values(status="active"))
            await session.execute(update(Organisation).values(timezone="UTC"))
            await session.execute(
                update(OrganisationModuleEntitlement).values(
                    enabled=True,
                    disabled_at=None,
                )
            )
            await session.commit()

    shutil.rmtree(TEST_VISUAL_STORAGE, ignore_errors=True)
    asyncio.run(clean())
    yield
    asyncio.run(clean())
    shutil.rmtree(TEST_VISUAL_STORAGE, ignore_errors=True)
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
            visual_storage_directory=str(TEST_VISUAL_STORAGE),
            feature_engage_events_enabled=True,
        ),
    )


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
