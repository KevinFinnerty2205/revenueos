from __future__ import annotations

import asyncio
import copy
import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select, update
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import ConnectionPoolEntry

import revenueos.demo_data as demo_data_module
from revenueos.config import Settings
from revenueos.create_pptx import PPTX_MIME_TYPE
from revenueos.database import create_engine as create_database_engine
from revenueos.database import set_tenant_database_context
from revenueos.deal_room_contracts import (
    DealRoomDraftUpdate,
    DealRoomLinkRotationRequest,
    DealRoomPublishRequest,
)
from revenueos.deal_room_services import DealRoomService
from revenueos.demo_data import (
    demo_campaign_ids,
    demo_ids,
    demo_phone_contact_id,
    demo_sales_analytics_ids,
    demo_sales_forecast_ids,
    demo_sales_target_ids,
    reset_demo_data,
    seed_demo_data,
)
from revenueos.handover_contracts import HandoverLifecycleRequest
from revenueos.handover_services import HandoverService
from revenueos.methodology_contracts import MethodologySelectionUpdate
from revenueos.methodology_services import SalesMethodologyProjectionService
from revenueos.models import (
    BetaSystemEvent,
    ClosedWonHandover,
    ClosedWonHandoverRevision,
    ClosedWonHandoverSource,
    Company,
    Contact,
    CreateBusinessCase,
    CreateBusinessCaseVersion,
    CreatePresentation,
    CreatePresentationVersion,
    CreateTemplate,
    CreateTemplateVersion,
    CreateValueModel,
    DealRoom,
    DealRoomRevision,
    DocumentSource,
    EngageCampaignAudience,
    EngageCampaignEnrollment,
    Interaction,
    MethodologyProjection,
    Opportunity,
    OrganisationMembership,
    OrganisationMethodologySetting,
    ProspectDiscoveryCandidate,
    ProspectResearchTarget,
    ProspectTargetMarket,
    SalesForecastPeriod,
    SalesTarget,
    SellingProfileRevision,
    Task,
    VisualAsset,
)
from revenueos.owner_demo_data import (
    OWNER_BASE_MANIFEST_EVENT,
    OWNER_BASE_RESERVATION_EVENT,
    OWNER_DEMO_DATASET_VERSION,
    OWNER_PRESENTATION_KEY,
    OWNER_PRESENTATION_TITLE,
    OWNER_RESET_CLEANUP_EVENT,
    OWNER_TEMPLATE_FILE_NAME,
    OWNER_TEMPLATE_NAME,
    _assert_private_demo_database_binding,
    _assert_private_demo_settings,
    _owner_deal_room_content,
    _owner_template,
    _process_create_work,
    _template_bytes,
    owner_demo_base_manifest_id,
    owner_demo_cleanup_event_id,
    owner_demo_template_id,
    reset_owner_demo_extensions,
    seed_owner_demo_data,
)
from revenueos.pipeline_contracts import OpportunityCloseWonRequest
from revenueos.pipeline_services import PipelineService
from revenueos.tenant import Role, TenantContext
from revenueos.visual_storage import LocalVisualStorage, VisualStorageError
from tests.conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, TEST_DB_URL, TEST_VISUAL_STORAGE


def owner_demo_settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        auth_mode="mock",
        mock_auth_enabled=True,
        database_url=TEST_DB_URL,
        log_level="WARNING",
        cors_origins="http://localhost:3000",
        visual_storage_backend="local",
        visual_storage_directory=str(TEST_VISUAL_STORAGE),
        ai_provider_name="mock",
        feature_openai_provider_enabled=False,
        prospect_research_provider_name="mock",
        feature_prospect_external_provider_enabled=False,
        private_beta_real_data_enabled=False,
        billing_mode="test",
        billing_provider_name="deterministic",
    )


@pytest.mark.parametrize(
    ("updates", "message"),
    (
        ({"environment": "production"}, "environment must be development or test"),
        ({"environment": "staging"}, "environment must be development or test"),
        ({"auth_mode": "clerk"}, "mock authentication must be enabled"),
        ({"mock_auth_enabled": False}, "mock authentication must be enabled"),
        ({"ai_provider_name": "openai"}, "AI must use the deterministic mock provider"),
        ({"feature_openai_provider_enabled": True}, "AI must use the deterministic mock provider"),
        ({"prospect_research_provider_name": "apollo"}, "Prospect must use the deterministic mock provider"),
        ({"feature_prospect_external_provider_enabled": True}, "Prospect must use the deterministic mock provider"),
        ({"feature_microsoft_365_enabled": True}, "Microsoft 365"),
        ({"feature_google_workspace_enabled": True}, "Google Workspace"),
        ({"feature_hubspot_crm_enabled": True}, "HubSpot"),
        ({"feature_salesforce_crm_enabled": True}, "Salesforce"),
        ({"visual_storage_backend": "s3_compatible"}, "visual storage must be local"),
        ({"private_beta_real_data_enabled": True}, "real-customer data release"),
        ({"billing_mode": "live"}, "deterministic test adapter"),
        ({"billing_provider_name": "stripe"}, "deterministic test adapter"),
        ({"feature_billing_enabled": True}, "billing and Credits must remain disabled"),
        ({"feature_credits_enabled": True}, "billing and Credits must remain disabled"),
    ),
)
def test_owner_demo_refuses_live_or_external_capabilities(
    updates: dict[str, object],
    message: str,
) -> None:
    settings = owner_demo_settings()
    unsafe = settings.model_copy(update=updates)

    with pytest.raises(ValueError, match=message):
        _assert_private_demo_settings(unsafe)


@pytest.mark.parametrize(
    "database_url",
    (
        "postgresql+asyncpg://demo:secret@db.example.invalid/demo",
        "postgresql+asyncpg://demo:secret@%2Fvar%2Frun%2Fpostgresql/demo",
        "sqlite+aiosqlite:///file:owner-demo.db?mode=memory&cache=shared",
    ),
)
def test_owner_demo_refuses_non_local_database_urls(database_url: str) -> None:
    unsafe = owner_demo_settings().model_copy(update={"database_url": database_url})

    with pytest.raises(ValueError, match="database must be local"):
        _assert_private_demo_settings(unsafe)


def test_owner_demo_refuses_a_mismatched_or_remote_session_factory_before_database_access() -> None:
    async def scenario() -> None:
        settings = owner_demo_settings()
        remote_engine = create_async_engine(
            "postgresql+asyncpg://demo:secret@db.example.invalid/demo",
        )
        remote_factory = async_sessionmaker(remote_engine, expire_on_commit=False)
        with pytest.raises(ValueError, match="session factory database must be local"):
            await seed_owner_demo_data(
                remote_factory,
                PRIMARY_ORGANISATION_ID,
                PRIMARY_USER_ID,
                settings,
            )
        await remote_engine.dispose()

        other_local_engine = create_async_engine("sqlite+aiosqlite:////tmp/owner-demo-other.db")
        other_local_factory = async_sessionmaker(other_local_engine, expire_on_commit=False)
        with pytest.raises(ValueError, match="does not match the validated local database"):
            _assert_private_demo_database_binding(settings, other_local_factory)
        await other_local_engine.dispose()

    asyncio.run(scenario())


def _queued_template_version(
    *,
    template_id: UUID,
    checksum: str,
    storage_key: str,
    file_name: str = "unrelated.pptx",
    byte_size: int = 1,
    version_id: UUID | None = None,
) -> CreateTemplateVersion:
    return CreateTemplateVersion(
        id=version_id or uuid4(),
        organisation_id=PRIMARY_ORGANISATION_ID,
        template_id=template_id,
        version=1,
        uploaded_by_user_id=PRIMARY_USER_ID,
        processing_state="processing",
        approval_state="pending",
        display_filename=file_name,
        storage_key=storage_key,
        storage_status="available",
        mime_type=PPTX_MIME_TYPE,
        byte_size=byte_size,
        checksum_sha256=checksum,
        processing_schema_version=1,
        slide_count=0,
        warning_codes_json=[],
        manifest_json={},
        compatibility_state="needs_attention",
        compatibility_details_json=["slide_review_required"],
        validation_profile_version=1,
        authority_attestation_version=1,
        authority_attested_by_user_id=PRIMARY_USER_ID,
        authority_attested_at=datetime.now(UTC),
        processing_attempts=0,
    )


def test_owner_demo_template_bytes_are_deterministic() -> None:
    assert _template_bytes() == _template_bytes()


def test_owner_demo_seed_is_linked_idempotent_and_resettable() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        unrelated_template_id = uuid4()
        unrelated_version = _queued_template_version(
            template_id=unrelated_template_id,
            checksum="a" * 64,
            storage_key=f"{PRIMARY_ORGANISATION_ID}/create/templates/{unrelated_template_id}/unrelated.pptx",
        )
        unrelated_version_id = unrelated_version.id
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            session.add(
                CreateTemplate(
                    id=unrelated_template_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    name="Unrelated queued customer template",
                    state="active",
                    created_by_user_id=PRIMARY_USER_ID,
                )
            )
            session.add(unrelated_version)
            await session.commit()

        first = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        second = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )

        assert first == second
        assert first["dataset_version"] == OWNER_DEMO_DATASET_VERSION
        assert first["provider_calls"] == 0
        assert first["methodology_setting_preexisting"] is False
        assert first["methodology_projection_versions"] == (1, 2)

        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            company = await session.get(Company, first["company_id"])
            opportunity = await session.get(Opportunity, first["opportunity_id"])
            contact = await session.get(Contact, first["contact_id"])
            profile = await session.get(SellingProfileRevision, first["selling_profile_revision_id"])
            business_case = await session.get(CreateBusinessCase, first["business_case_id"])
            presentation = await session.get(CreatePresentation, first["presentation_id"])
            presentation_version = await session.get(
                CreatePresentationVersion,
                first["presentation_version_id"],
            )
            deal_room = await session.get(DealRoom, first["deal_room_id"])
            handover = await session.get(ClosedWonHandover, first["handover_id"])
            handover_revision = await session.get(
                ClosedWonHandoverRevision,
                first["handover_revision_id"],
            )
            owner_task = await session.get(Task, first["task_id"])
            methodology_setting = await session.get(
                OrganisationMethodologySetting,
                PRIMARY_ORGANISATION_ID,
            )
            methodology_projections = list(
                (
                    await session.scalars(
                        select(MethodologyProjection)
                        .where(
                            MethodologyProjection.organisation_id == PRIMARY_ORGANISATION_ID,
                            MethodologyProjection.opportunity_id == first["opportunity_id"],
                        )
                        .order_by(MethodologyProjection.projection_version)
                    )
                ).all()
            )

            assert company is not None
            assert company.name == "[DEMO] Northstar Facilities Group"
            assert company.website == "https://northstar-facilities.example/"
            assert company.normalized_domain == "northstar-facilities.example"
            assert opportunity is not None
            assert opportunity.company_id == company.id
            assert contact is not None
            assert contact.company_id == company.id
            assert profile is not None and profile.state == "approved"
            assert business_case is not None
            assert business_case.state == "approved"
            assert business_case.account_id == company.id
            assert business_case.opportunity_id == opportunity.id
            assert presentation is not None
            assert presentation.state == "ready"
            assert presentation.review_state == "approved"
            assert presentation.account_id == company.id
            assert presentation.opportunity_id == opportunity.id
            assert presentation.business_case_id == business_case.id
            assert presentation_version is not None
            assert all(
                isinstance(slide, dict) and slide.get("reviewState") == "ready"
                for slide in presentation_version.generated_content_json
            )
            assert deal_room is not None
            assert deal_room.status == "published"
            assert deal_room.opportunity_id == opportunity.id
            assert handover is not None
            assert handover.opportunity_id == opportunity.id
            assert handover_revision is not None
            assert handover_revision.status == "draft"
            assert owner_task is not None
            assert owner_task.title == "[DEMO] Prepare the Northstar security workshop"
            assert owner_task.company_id == company.id
            assert owner_task.contact_id == contact.id
            assert owner_task.opportunity_id == opportunity.id
            assert methodology_setting is not None
            assert methodology_setting.selection == "meddpicc"
            assert [item.definition_key for item in methodology_projections] == ["bant", "meddpicc"]
            assert [item.projection_version for item in methodology_projections] == [1, 2]
            assert presentation.template_id == owner_demo_template_id(PRIMARY_ORGANISATION_ID)

            queued = await session.get(CreateTemplateVersion, unrelated_version_id)
            assert queued is not None
            assert queued.processing_state == "processing"
            assert queued.processing_attempts == 0
            assert queued.worker_id is None

            northstar_target = await session.scalar(
                select(ProspectResearchTarget).where(
                    ProspectResearchTarget.organisation_id == PRIMARY_ORGANISATION_ID,
                    ProspectResearchTarget.provider_key == "mock",
                    ProspectResearchTarget.provider_candidate_id == "northstar-facilities-group",
                )
            )
            assert northstar_target is not None
            northstar_candidate = await session.scalar(
                select(ProspectDiscoveryCandidate).where(
                    ProspectDiscoveryCandidate.organisation_id == PRIMARY_ORGANISATION_ID,
                    ProspectDiscoveryCandidate.target_id == northstar_target.id,
                )
            )
            assert northstar_candidate is not None
            assert northstar_candidate.relationship_state == "active_opportunity"
            assert northstar_candidate.matched_company_id == company.id
            assert northstar_candidate.active_opportunity_id == opportunity.id

            audience_company_ids = list(
                (
                    await session.scalars(
                        select(EngageCampaignAudience.company_id).where(
                            EngageCampaignAudience.organisation_id == PRIMARY_ORGANISATION_ID
                        )
                    )
                ).all()
            )
            enrollment_company_ids = list(
                (
                    await session.scalars(
                        select(EngageCampaignEnrollment.company_id).where(
                            EngageCampaignEnrollment.organisation_id == PRIMARY_ORGANISATION_ID
                        )
                    )
                ).all()
            )
            assert audience_company_ids and set(audience_company_ids) == {company.id}
            assert enrollment_company_ids and set(enrollment_company_ids) == {company.id}

            source_types = set(
                (
                    await session.scalars(
                        select(ClosedWonHandoverSource.source_type).where(
                            ClosedWonHandoverSource.organisation_id == PRIMARY_ORGANISATION_ID,
                            ClosedWonHandoverSource.revision_id == handover_revision.id,
                        )
                    )
                ).all()
            )
            assert {"opportunity", "business_case", "deal_room", "task"}.issubset(source_types)
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DealRoomRevision)
                    .where(
                        DealRoomRevision.organisation_id == PRIMARY_ORGANISATION_ID,
                        DealRoomRevision.room_id == deal_room.id,
                    )
                )
                == 1
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ClosedWonHandoverRevision)
                    .where(
                        ClosedWonHandoverRevision.organisation_id == PRIMARY_ORGANISATION_ID,
                        ClosedWonHandoverRevision.handover_id == handover.id,
                    )
                )
                == 1
            )

            template_storage_key = await session.scalar(
                select(CreateTemplateVersion.storage_key).where(
                    CreateTemplateVersion.organisation_id == PRIMARY_ORGANISATION_ID,
                    CreateTemplateVersion.id == first["template_version_id"],
                )
            )
            presentation_storage_key = await session.scalar(
                select(CreatePresentationVersion.pptx_storage_key).where(
                    CreatePresentationVersion.organisation_id == PRIMARY_ORGANISATION_ID,
                    CreatePresentationVersion.id == first["presentation_version_id"],
                )
            )
            assert template_storage_key is not None
            assert presentation_storage_key is not None
            assert (TEST_VISUAL_STORAGE / template_storage_key).is_file()
            assert (TEST_VISUAL_STORAGE / presentation_storage_key).is_file()

        def fail_owner_database_delete(
            _connection: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            if "delete from closed_won_handovers" in statement.casefold():
                raise RuntimeError("synthetic owner reset database failure")

        event.listen(engine.sync_engine, "before_cursor_execute", fail_owner_database_delete)
        try:
            with pytest.raises(RuntimeError, match="synthetic owner reset database failure"):
                await reset_owner_demo_extensions(factory, PRIMARY_ORGANISATION_ID, settings)
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", fail_owner_database_delete)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            assert await session.get(CreatePresentation, first["presentation_id"]) is not None
            assert await session.get(ClosedWonHandover, first["handover_id"]) is not None
        assert (TEST_VISUAL_STORAGE / template_storage_key).is_file()
        assert (TEST_VISUAL_STORAGE / presentation_storage_key).is_file()

        reset = await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)
        assert reset == {"status": "reset", "provider_calls": 0}
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            assert await session.get(Company, first["company_id"]) is None
            assert await session.get(CreateBusinessCase, first["business_case_id"]) is None
            assert await session.get(CreatePresentation, first["presentation_id"]) is None
            assert await session.get(DealRoom, first["deal_room_id"]) is None
            assert await session.get(ClosedWonHandover, first["handover_id"]) is None
            assert await session.get(Task, first["task_id"]) is None
            assert await session.get(OrganisationMethodologySetting, PRIMARY_ORGANISATION_ID) is None
            assert not list(
                (
                    await session.scalars(
                        select(MethodologyProjection).where(
                            MethodologyProjection.organisation_id == PRIMARY_ORGANISATION_ID,
                            MethodologyProjection.opportunity_id == first["opportunity_id"],
                        )
                    )
                ).all()
            )
            queued = await session.get(CreateTemplateVersion, unrelated_version_id)
            assert queued is not None
            assert queued.processing_state == "processing"
            assert queued.processing_attempts == 0
        assert not (TEST_VISUAL_STORAGE / template_storage_key).exists()
        assert not (TEST_VISUAL_STORAGE / presentation_storage_key).exists()
        await engine.dispose()

    asyncio.run(scenario())


def test_owner_demo_reset_refuses_an_unowned_presentation_linked_to_its_business_case() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        seeded = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        presentation_id = uuid4()
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            session.add(
                CreatePresentation(
                    id=presentation_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    account_id=seeded["company_id"],
                    opportunity_id=seeded["opportunity_id"],
                    template_id=owner_demo_template_id(PRIMARY_ORGANISATION_ID),
                    template_version_id=seeded["template_version_id"],
                    business_case_id=seeded["business_case_id"],
                    business_case_version_id=seeded["business_case_version_id"],
                    business_case_scenario="all",
                    created_by_user_id=PRIMARY_USER_ID,
                    title="Legitimate local presentation",
                    objective="business_case",
                    audience_json=[],
                    focus_instruction=None,
                    state="draft_plan",
                    review_state="pending",
                    plan_json=[],
                    source_context_fingerprint="f" * 64,
                    idempotency_key="legitimate-dependent-presentation",
                )
            )
            await session.commit()

        with pytest.raises(
            ValueError,
            match="another Presentation references a manifest-owned demo Account, Opportunity or Business Case",
        ):
            await reset_owner_demo_extensions(factory, PRIMARY_ORGANISATION_ID, settings)

        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            preserved = await session.get(CreatePresentation, presentation_id)
            assert preserved is not None
            assert preserved.title == "Legitimate local presentation"
            assert await session.get(CreatePresentation, seeded["presentation_id"]) is not None
            assert await session.get(CreateBusinessCase, seeded["business_case_id"]) is not None
            assert (
                await session.get(
                    BetaSystemEvent,
                    owner_demo_cleanup_event_id(PRIMARY_ORGANISATION_ID),
                )
                is None
            )
        await engine.dispose()

    asyncio.run(scenario())


def test_owner_demo_reset_refuses_a_standalone_presentation_linked_to_demo_parents() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        seeded = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        presentation_id = uuid4()
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            manifest = await session.get(
                BetaSystemEvent,
                owner_demo_base_manifest_id(PRIMARY_ORGANISATION_ID),
            )
            template_version = await session.get(
                CreateTemplateVersion,
                seeded["template_version_id"],
            )
            presentation_version = await session.get(
                CreatePresentationVersion,
                seeded["presentation_version_id"],
            )
            assert manifest is not None
            assert template_version is not None
            assert presentation_version is not None
            assert presentation_version.pptx_storage_key is not None
            manifest_metadata = copy.deepcopy(manifest.metadata_json)
            template_storage_key = template_version.storage_key
            presentation_storage_key = presentation_version.pptx_storage_key
            session.add(
                CreatePresentation(
                    id=presentation_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    account_id=seeded["company_id"],
                    opportunity_id=seeded["opportunity_id"],
                    template_id=owner_demo_template_id(PRIMARY_ORGANISATION_ID),
                    template_version_id=seeded["template_version_id"],
                    business_case_id=None,
                    business_case_version_id=None,
                    business_case_scenario=None,
                    created_by_user_id=PRIMARY_USER_ID,
                    title="Legitimate standalone local presentation",
                    objective="solution_overview",
                    audience_json=[],
                    focus_instruction=None,
                    state="draft_plan",
                    review_state="pending",
                    plan_json=[],
                    source_context_fingerprint="f" * 64,
                    idempotency_key="legitimate-standalone-presentation",
                )
            )
            await session.commit()

        assert (TEST_VISUAL_STORAGE / template_storage_key).is_file()
        assert (TEST_VISUAL_STORAGE / presentation_storage_key).is_file()
        with pytest.raises(
            ValueError,
            match="another Presentation references a manifest-owned demo Account, Opportunity or Business Case",
        ):
            await reset_owner_demo_extensions(factory, PRIMARY_ORGANISATION_ID, settings)

        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            preserved = await session.get(CreatePresentation, presentation_id)
            assert preserved is not None
            assert preserved.business_case_id is None
            assert preserved.title == "Legitimate standalone local presentation"
            assert (
                await session.get(
                    SellingProfileRevision,
                    seeded["selling_profile_revision_id"],
                )
                is not None
            )
            assert await session.get(CreateValueModel, seeded["value_model_id"]) is not None
            assert await session.get(CreateBusinessCase, seeded["business_case_id"]) is not None
            assert await session.get(CreateTemplateVersion, seeded["template_version_id"]) is not None
            assert await session.get(CreatePresentation, seeded["presentation_id"]) is not None
            assert (
                await session.get(
                    CreatePresentationVersion,
                    seeded["presentation_version_id"],
                )
                is not None
            )
            assert await session.get(DealRoom, seeded["deal_room_id"]) is not None
            assert await session.get(ClosedWonHandover, seeded["handover_id"]) is not None
            assert await session.get(Task, seeded["task_id"]) is not None
            preserved_manifest = await session.get(
                BetaSystemEvent,
                owner_demo_base_manifest_id(PRIMARY_ORGANISATION_ID),
            )
            assert preserved_manifest is not None
            assert preserved_manifest.metadata_json == manifest_metadata
            assert (
                await session.get(
                    BetaSystemEvent,
                    owner_demo_cleanup_event_id(PRIMARY_ORGANISATION_ID),
                )
                is None
            )
        assert (TEST_VISUAL_STORAGE / template_storage_key).is_file()
        assert (TEST_VISUAL_STORAGE / presentation_storage_key).is_file()
        await engine.dispose()

    asyncio.run(scenario())


def test_owner_demo_reset_refuses_an_unowned_business_case_linked_to_demo_parents() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        seeded = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        business_case_id = uuid4()
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            owner_case = await session.get(CreateBusinessCase, seeded["business_case_id"])
            assert owner_case is not None
            session.add(
                CreateBusinessCase(
                    id=business_case_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    account_id=seeded["company_id"],
                    opportunity_id=seeded["opportunity_id"],
                    model_id=seeded["value_model_id"],
                    model_version_id=owner_case.model_version_id,
                    created_by_user_id=PRIMARY_USER_ID,
                    title="Legitimate local Business Case",
                    currency="AUD",
                    state="draft",
                    idempotency_key="legitimate-dependent-business-case",
                )
            )
            await session.commit()

        with pytest.raises(
            ValueError,
            match="another Business Case references a manifest-owned demo parent",
        ):
            await reset_owner_demo_extensions(factory, PRIMARY_ORGANISATION_ID, settings)

        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            preserved = await session.get(CreateBusinessCase, business_case_id)
            assert preserved is not None
            assert preserved.title == "Legitimate local Business Case"
            assert await session.get(CreateBusinessCase, seeded["business_case_id"]) is not None
            assert await session.get(CreateValueModel, seeded["value_model_id"]) is not None
            assert await session.get(CreatePresentation, seeded["presentation_id"]) is not None
            presentation_version = await session.get(
                CreatePresentationVersion,
                seeded["presentation_version_id"],
            )
            assert presentation_version is not None
            assert presentation_version.pptx_storage_key is not None
            assert (
                await session.get(
                    BetaSystemEvent,
                    owner_demo_cleanup_event_id(PRIMARY_ORGANISATION_ID),
                )
                is None
            )
        assert (TEST_VISUAL_STORAGE / presentation_version.pptx_storage_key).is_file()
        await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("dependent_kind", ("task", "interaction"))
def test_full_owner_demo_reset_rolls_back_before_removing_extensions_for_unowned_base_dependants(
    dependent_kind: str,
) -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)

        def enable_foreign_keys(
            connection: DBAPIConnection,
            connection_record: ConnectionPoolEntry,
        ) -> None:
            del connection_record
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        event.listen(engine.sync_engine, "connect", enable_foreign_keys)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        seeded = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        dependent_id = uuid4()
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            manifest = await session.get(
                BetaSystemEvent,
                owner_demo_base_manifest_id(PRIMARY_ORGANISATION_ID),
            )
            template_version = await session.get(
                CreateTemplateVersion,
                seeded["template_version_id"],
            )
            presentation_version = await session.get(
                CreatePresentationVersion,
                seeded["presentation_version_id"],
            )
            base_visual_storage_key = await session.scalar(
                select(VisualAsset.storage_key).where(
                    VisualAsset.organisation_id == PRIMARY_ORGANISATION_ID,
                )
            )
            base_document_storage_key = await session.scalar(
                select(DocumentSource.storage_key).where(
                    DocumentSource.organisation_id == PRIMARY_ORGANISATION_ID,
                )
            )
            assert manifest is not None
            assert template_version is not None
            assert presentation_version is not None
            assert presentation_version.pptx_storage_key is not None
            assert base_visual_storage_key is not None
            assert base_document_storage_key is not None
            manifest_metadata = copy.deepcopy(manifest.metadata_json)
            template_storage_key = template_version.storage_key
            presentation_storage_key = presentation_version.pptx_storage_key
            if dependent_kind == "task":
                session.add(
                    Task(
                        id=dependent_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        company_id=seeded["company_id"],
                        contact_id=demo_phone_contact_id(PRIMARY_ORGANISATION_ID),
                        opportunity_id=None,
                        title="Legitimate local Task",
                        description="Must survive a refused owner-demo reset.",
                        status="open",
                        priority="medium",
                        created_by_user_id=PRIMARY_USER_ID,
                    )
                )
            else:
                session.add(
                    Interaction(
                        id=dependent_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        company_id=seeded["company_id"],
                        contact_id=demo_phone_contact_id(PRIMARY_ORGANISATION_ID),
                        opportunity_id=None,
                        interaction_type="phone_call",
                        lifecycle_status="planned",
                        title="Legitimate local interaction",
                        creation_origin="manual",
                        call_direction="outbound",
                        created_by_user_id=PRIMARY_USER_ID,
                    )
                )
            await session.commit()

        assert (TEST_VISUAL_STORAGE / template_storage_key).is_file()
        assert (TEST_VISUAL_STORAGE / presentation_storage_key).is_file()
        assert (TEST_VISUAL_STORAGE / base_visual_storage_key).is_file()
        assert (TEST_VISUAL_STORAGE / base_document_storage_key).is_file()
        with pytest.raises(
            ValueError,
            match="another local record references a manifest-owned demo Account, Person or Opportunity",
        ):
            await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)

        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            dependent_model = Task if dependent_kind == "task" else Interaction
            assert await session.get(dependent_model, dependent_id) is not None
            assert await session.get(Company, seeded["company_id"]) is not None
            assert await session.get(Contact, demo_phone_contact_id(PRIMARY_ORGANISATION_ID)) is not None
            assert await session.get(Opportunity, seeded["opportunity_id"]) is not None
            for model, row_id in (
                (SellingProfileRevision, seeded["selling_profile_revision_id"]),
                (CreateValueModel, seeded["value_model_id"]),
                (CreateBusinessCase, seeded["business_case_id"]),
                (CreateBusinessCaseVersion, seeded["business_case_version_id"]),
                (CreateTemplate, owner_demo_template_id(PRIMARY_ORGANISATION_ID)),
                (CreateTemplateVersion, seeded["template_version_id"]),
                (CreatePresentation, seeded["presentation_id"]),
                (CreatePresentationVersion, seeded["presentation_version_id"]),
                (DealRoom, seeded["deal_room_id"]),
                (ClosedWonHandover, seeded["handover_id"]),
                (ClosedWonHandoverRevision, seeded["handover_revision_id"]),
                (Task, seeded["task_id"]),
            ):
                assert await session.get(model, row_id) is not None
            preserved_manifest = await session.get(
                BetaSystemEvent,
                owner_demo_base_manifest_id(PRIMARY_ORGANISATION_ID),
            )
            assert preserved_manifest is not None
            assert preserved_manifest.metadata_json == manifest_metadata
            assert (
                await session.get(
                    BetaSystemEvent,
                    owner_demo_cleanup_event_id(PRIMARY_ORGANISATION_ID),
                )
                is None
            )
        assert (TEST_VISUAL_STORAGE / template_storage_key).is_file()
        assert (TEST_VISUAL_STORAGE / presentation_storage_key).is_file()
        assert (TEST_VISUAL_STORAGE / base_visual_storage_key).is_file()
        assert (TEST_VISUAL_STORAGE / base_document_storage_key).is_file()
        await engine.dispose()

    asyncio.run(scenario())


def test_owner_demo_requires_the_stored_active_admin_role_before_seed_or_reset_mutation() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        company_id, _, _, _ = demo_ids(PRIMARY_ORGANISATION_ID)

        async with factory() as session:
            membership = await session.get(
                OrganisationMembership,
                (PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID),
            )
            assert membership is not None
            membership.role = "member"
            await session.commit()
        with pytest.raises(ValueError, match="active organisation administrator"):
            await seed_owner_demo_data(
                factory,
                PRIMARY_ORGANISATION_ID,
                PRIMARY_USER_ID,
                settings,
            )
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            assert await session.get(Company, company_id) is None
            membership = await session.get(
                OrganisationMembership,
                (PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID),
            )
            assert membership is not None
            membership.role = "admin"
            await session.commit()

        seeded = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            membership = await session.get(
                OrganisationMembership,
                (PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID),
            )
            assert membership is not None
            membership.role = "member"
            await session.commit()
        with pytest.raises(ValueError, match="active administrator"):
            await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            assert await session.get(Company, seeded["company_id"]) is not None
            assert await session.get(Task, seeded["task_id"]) is not None
            membership = await session.get(
                OrganisationMembership,
                (PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID),
            )
            assert membership is not None
            membership.role = "admin"
            await session.commit()
        await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)
        await engine.dispose()

    asyncio.run(scenario())


def test_owner_demo_preserves_an_existing_organisation_methodology_setting() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            setting = await session.get(OrganisationMethodologySetting, PRIMARY_ORGANISATION_ID)
            if setting is None:
                session.add(
                    OrganisationMethodologySetting(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        selection="bant",
                        updated_by_user_id=PRIMARY_USER_ID,
                    )
                )
            else:
                setting.selection = "bant"
                setting.custom_definition_id = None
                setting.updated_by_user_id = PRIMARY_USER_ID
            await session.commit()

        seeded = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        assert seeded["methodology_setting_preexisting"] is True
        assert seeded["methodology_projection_versions"] == (1, 2)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            setting = await session.get(OrganisationMethodologySetting, PRIMARY_ORGANISATION_ID)
            assert setting is not None
            assert setting.selection == "bant"
            projections = list(
                (
                    await session.scalars(
                        select(MethodologyProjection)
                        .where(
                            MethodologyProjection.organisation_id == PRIMARY_ORGANISATION_ID,
                            MethodologyProjection.opportunity_id == seeded["opportunity_id"],
                        )
                        .order_by(MethodologyProjection.projection_version)
                    )
                ).all()
            )
            assert [item.definition_key for item in projections] == ["bant", "meddpicc"]

        await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            setting = await session.get(OrganisationMethodologySetting, PRIMARY_ORGANISATION_ID)
            assert setting is not None
            assert setting.selection == "bant"
        await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("setting_preexisted", (False, True))
def test_owner_demo_methodology_reservation_recovers_an_interrupted_seed(
    monkeypatch: pytest.MonkeyPatch,
    setting_preexisted: bool,
) -> None:
    async def scenario() -> None:
        settings = owner_demo_settings()
        engine = create_database_engine(settings)
        assert engine is not None
        factory = async_sessionmaker(engine, expire_on_commit=False)
        if setting_preexisted:
            async with factory() as session:
                await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
                session.add(
                    OrganisationMethodologySetting(
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        # Deliberately indistinguishable in content from the
                        # synthetic default: only the pre-seed reservation must
                        # prevent reset from claiming and deleting this row.
                        selection="meddpicc",
                        updated_by_user_id=PRIMARY_USER_ID,
                    )
                )
                await session.commit()

        original_methodology_seed = demo_data_module._seed_methodology_views

        async def interrupt_after_methodology(
            interrupted_factory: async_sessionmaker[AsyncSession],
            organisation_id: UUID,
            user_id: UUID,
            active_settings: Settings,
            opportunity_id: UUID,
            tenant_role: Role,
            *,
            preserve_existing_setting: bool = False,
        ) -> tuple[int, ...]:
            del preserve_existing_setting
            tenant = TenantContext(
                organisation_id=organisation_id,
                user_id=user_id,
                role=tenant_role,
            )
            async with interrupted_factory() as session:
                await set_tenant_database_context(session, organisation_id)
                service = SalesMethodologyProjectionService(session, tenant, active_settings)
                await service.select_methodology(MethodologySelectionUpdate(selection="bant"))
                await service.generate(opportunity_id)
            raise RuntimeError("synthetic interruption after methodology commit")

        monkeypatch.setattr(demo_data_module, "_seed_methodology_views", interrupt_after_methodology)
        with pytest.raises(RuntimeError, match="after methodology commit"):
            await seed_owner_demo_data(
                factory,
                PRIMARY_ORGANISATION_ID,
                PRIMARY_USER_ID,
                settings,
            )
        monkeypatch.setattr(demo_data_module, "_seed_methodology_views", original_methodology_seed)

        company_id, opportunity_id, _, _ = demo_ids(PRIMARY_ORGANISATION_ID)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            reservation = await session.get(
                BetaSystemEvent,
                owner_demo_base_manifest_id(PRIMARY_ORGANISATION_ID),
            )
            setting = await session.get(
                OrganisationMethodologySetting,
                PRIMARY_ORGANISATION_ID,
            )
            projections = list(
                (
                    await session.scalars(
                        select(MethodologyProjection).where(
                            MethodologyProjection.organisation_id == PRIMARY_ORGANISATION_ID,
                            MethodologyProjection.opportunity_id == opportunity_id,
                        )
                    )
                ).all()
            )
            assert reservation is not None
            assert reservation.event_type == OWNER_BASE_RESERVATION_EVENT
            assert set(reservation.metadata_json) == {
                "schemaVersion",
                "methodologySettingPreexisting",
                "methodologySettingOriginal",
            }
            assert reservation.metadata_json["schemaVersion"] == 1
            assert reservation.metadata_json["methodologySettingPreexisting"] is setting_preexisted
            original_setting = reservation.metadata_json["methodologySettingOriginal"]
            if setting_preexisted:
                assert isinstance(original_setting, dict)
                assert original_setting["selection"] == "meddpicc"
                assert original_setting["customDefinitionId"] is None
                assert original_setting["updatedByUserId"] == str(PRIMARY_USER_ID)
            else:
                assert original_setting is None
            assert setting is not None
            assert setting.selection == "bant"
            assert {projection.definition_key for projection in projections} == {"bant"}

        await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            assert await session.get(Company, company_id) is None
            assert (
                await session.get(
                    BetaSystemEvent,
                    owner_demo_base_manifest_id(PRIMARY_ORGANISATION_ID),
                )
                is None
            )
            setting = await session.get(
                OrganisationMethodologySetting,
                PRIMARY_ORGANISATION_ID,
            )
            if setting_preexisted:
                assert setting is not None
                assert setting.selection == "meddpicc"
                assert isinstance(original_setting, dict)
                assert setting.custom_definition_id is None
                assert str(setting.updated_by_user_id) == original_setting["updatedByUserId"]
                assert setting.created_at.isoformat() == original_setting["createdAt"]
                assert setting.updated_at.isoformat() == original_setting["updatedAt"]
            else:
                assert setting is None

        reseeded = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        assert reseeded["methodology_setting_preexisting"] is setting_preexisted
        assert reseeded["methodology_projection_versions"] == (1, 2)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            manifest = await session.get(
                BetaSystemEvent,
                owner_demo_base_manifest_id(PRIMARY_ORGANISATION_ID),
            )
            setting = await session.get(
                OrganisationMethodologySetting,
                PRIMARY_ORGANISATION_ID,
            )
            assert manifest is not None
            assert manifest.event_type == OWNER_BASE_MANIFEST_EVENT
            assert setting is not None
            assert setting.selection == "meddpicc"

        await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)
        await engine.dispose()

    asyncio.run(scenario())


def test_owner_demo_reset_validates_methodology_before_extension_mutation() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        seeded = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            setting = await session.get(
                OrganisationMethodologySetting,
                PRIMARY_ORGANISATION_ID,
            )
            assert setting is not None
            setting.selection = "spiced"
            await session.commit()

        with pytest.raises(ValueError, match="methodology setting manifest"):
            await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)

        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            assert await session.get(Company, seeded["company_id"]) is not None
            assert await session.get(CreateBusinessCase, seeded["business_case_id"]) is not None
            assert await session.get(CreatePresentation, seeded["presentation_id"]) is not None
            assert await session.get(DealRoom, seeded["deal_room_id"]) is not None
            assert await session.get(ClosedWonHandover, seeded["handover_id"]) is not None
            setting = await session.get(
                OrganisationMethodologySetting,
                PRIMARY_ORGANISATION_ID,
            )
            assert setting is not None
            setting.selection = "meddpicc"
            await session.commit()

        await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)
        await engine.dispose()

    asyncio.run(scenario())


def test_owner_demo_refuses_and_preserves_a_legitimate_same_named_target_market() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        market_id = uuid4()
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            session.add(
                ProspectTargetMarket(
                    id=market_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    name="[DEMO] Australian multi-site enterprises",
                    status="active",
                    current_version=1,
                    created_by_user_id=PRIMARY_USER_ID,
                )
            )
            await session.commit()

        with pytest.raises(ValueError, match="deterministic base"):
            await seed_owner_demo_data(
                factory,
                PRIMARY_ORGANISATION_ID,
                PRIMARY_USER_ID,
                settings,
            )
        with pytest.raises(ValueError, match="deterministic base"):
            await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            preserved = await session.get(ProspectTargetMarket, market_id)
            assert preserved is not None
            assert preserved.created_by_user_id == PRIMARY_USER_ID
        await engine.dispose()

    asyncio.run(scenario())


def test_owner_demo_refuses_a_reserved_dependent_identity_before_any_mutation() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        company_id, _, _, _ = demo_ids(PRIMARY_ORGANISATION_ID)
        _, analytics_interaction_ids = demo_sales_analytics_ids(PRIMARY_ORGANISATION_ID)
        collision_id = analytics_interaction_ids[0]
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            session.add(
                Interaction(
                    id=collision_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    interaction_type="manual_interaction",
                    lifecycle_status="planned",
                    title="Legitimate same-ID interaction",
                    creation_origin="manual",
                    created_by_user_id=PRIMARY_USER_ID,
                )
            )
            await session.commit()

        with pytest.raises(ValueError, match="reserved interactions identity"):
            await seed_owner_demo_data(
                factory,
                PRIMARY_ORGANISATION_ID,
                PRIMARY_USER_ID,
                settings,
            )
        with pytest.raises(ValueError, match="reserved interactions identity"):
            await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            preserved = await session.get(Interaction, collision_id)
            assert preserved is not None
            assert preserved.title == "Legitimate same-ID interaction"
            assert await session.get(Company, company_id) is None
        await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "collision",
    ("company", "opportunity", "task", "sales_target", "sales_forecast"),
)
def test_owner_demo_base_collisions_fail_seed_and_reset_without_mutation(collision: str) -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        seeded = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        target_ids = demo_sales_target_ids(PRIMARY_ORGANISATION_ID)
        forecast_ids = demo_sales_forecast_ids(PRIMARY_ORGANISATION_ID)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            if collision == "company":
                row = await session.get(Company, seeded["company_id"])
                assert row is not None
                row.name = "Legitimate same-ID Account"
            elif collision == "opportunity":
                row = await session.get(Opportunity, seeded["opportunity_id"])
                assert row is not None
                row.name = "Legitimate same-ID Opportunity"
            elif collision == "task":
                row = await session.get(Task, seeded["task_id"])
                assert row is not None
                row.title = "Legitimate same-ID Task"
            elif collision == "sales_target":
                row = await session.get(SalesTarget, target_ids["won-value"])
                assert row is not None
                row.timezone = "Australia/Sydney"
            else:
                row = await session.get(SalesForecastPeriod, forecast_ids["period"])
                assert row is not None
                row.timezone = "Australia/Sydney"
            await session.commit()

        with pytest.raises(ValueError, match="deterministic base"):
            await seed_owner_demo_data(
                factory,
                PRIMARY_ORGANISATION_ID,
                PRIMARY_USER_ID,
                settings,
            )
        with pytest.raises(ValueError, match="deterministic base"):
            await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            if collision == "company":
                preserved = await session.get(Company, seeded["company_id"])
                assert preserved is not None and preserved.name == "Legitimate same-ID Account"
                preserved.name = "[DEMO] Northstar Facilities Group"
            elif collision == "opportunity":
                preserved = await session.get(Opportunity, seeded["opportunity_id"])
                assert preserved is not None and preserved.name == "Legitimate same-ID Opportunity"
                preserved.name = "[DEMO] Northstar multi-site workflow pilot"
            elif collision == "task":
                preserved = await session.get(Task, seeded["task_id"])
                assert preserved is not None and preserved.title == "Legitimate same-ID Task"
                preserved.title = "[DEMO] Prepare the Northstar security workshop"
            elif collision == "sales_target":
                preserved = await session.get(SalesTarget, target_ids["won-value"])
                assert preserved is not None and preserved.timezone == "Australia/Sydney"
                preserved.timezone = "UTC"
            else:
                preserved = await session.get(SalesForecastPeriod, forecast_ids["period"])
                assert preserved is not None and preserved.timezone == "Australia/Sydney"
                preserved.timezone = "UTC"
            await session.commit()
        await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)
        await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("collision", ("name", "identity", "checksum"))
def test_owner_demo_template_collisions_fail_closed_and_are_preserved(collision: str) -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        expected_id = owner_demo_template_id(PRIMARY_ORGANISATION_ID)
        collision_id = expected_id if collision == "identity" else uuid4()
        collision_name = OWNER_TEMPLATE_NAME if collision == "name" else "Legitimate customer template"
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            session.add(
                CreateTemplate(
                    id=collision_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    name=collision_name,
                    state="active",
                    created_by_user_id=PRIMARY_USER_ID,
                )
            )
            if collision == "checksum":
                session.add(
                    _queued_template_version(
                        template_id=collision_id,
                        checksum=hashlib.sha256(_template_bytes()).hexdigest(),
                        storage_key=(f"{PRIMARY_ORGANISATION_ID}/create/templates/{collision_id}/legitimate.pptx"),
                    )
                )
            await session.commit()

        tenant = TenantContext(
            organisation_id=PRIMARY_ORGANISATION_ID,
            user_id=PRIMARY_USER_ID,
            role="admin",
        )
        with pytest.raises(ValueError, match="Owner demo refused"):
            await _owner_template(factory, tenant, settings, _template_bytes())

        if collision == "identity":
            with pytest.raises(ValueError, match="identity/content collision"):
                await reset_owner_demo_extensions(factory, PRIMARY_ORGANISATION_ID, settings)
        else:
            await reset_owner_demo_extensions(factory, PRIMARY_ORGANISATION_ID, settings)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            preserved = await session.get(CreateTemplate, collision_id)
            assert preserved is not None
            assert preserved.name == collision_name
        await engine.dispose()

    asyncio.run(scenario())


def test_late_extension_collision_preserves_the_row_and_exposes_the_staged_boundary() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        legitimate_template_id = uuid4()
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            session.add(
                CreateTemplate(
                    id=legitimate_template_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    name=OWNER_TEMPLATE_NAME,
                    state="active",
                    created_by_user_id=PRIMARY_USER_ID,
                )
            )
            await session.commit()

        with pytest.raises(ValueError, match="non-demo template already uses"):
            await seed_owner_demo_data(
                factory,
                PRIMARY_ORGANISATION_ID,
                PRIMARY_USER_ID,
                settings,
            )

        company_id, _, _, _ = demo_ids(PRIMARY_ORGANISATION_ID)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            preserved = await session.get(CreateTemplate, legitimate_template_id)
            manifest = await session.get(
                BetaSystemEvent,
                owner_demo_base_manifest_id(PRIMARY_ORGANISATION_ID),
            )
            profile = await session.scalar(
                select(SellingProfileRevision).where(
                    SellingProfileRevision.organisation_id == PRIMARY_ORGANISATION_ID,
                    SellingProfileRevision.idempotency_key == "owner-demo-selling-profile-v1",
                )
            )
            value_model = await session.scalar(
                select(CreateValueModel).where(
                    CreateValueModel.organisation_id == PRIMARY_ORGANISATION_ID,
                    CreateValueModel.idempotency_key == "owner-demo-value-model-v1",
                )
            )
            assert preserved is not None
            assert preserved.name == OWNER_TEMPLATE_NAME
            assert await session.get(Company, company_id) is not None
            assert manifest is not None
            assert manifest.metadata_json["extensions"] is None
            assert profile is not None
            assert value_model is not None

        await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            preserved = await session.get(CreateTemplate, legitimate_template_id)
            assert preserved is not None
            assert preserved.name == OWNER_TEMPLATE_NAME
            assert await session.get(Company, company_id) is None
        await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "collision",
    ("profile", "value_model", "business_case", "presentation"),
)
def test_owner_demo_reserved_idempotency_collisions_are_never_adopted_or_deleted(collision: str) -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        seeded = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            if collision == "profile":
                row = await session.get(SellingProfileRevision, seeded["selling_profile_revision_id"])
                assert row is not None
                edited = copy.deepcopy(row.content_json)
                edited["companyNarrative"] = "Legitimate seller-authored narrative."
                row.content_json = edited
            elif collision == "value_model":
                row = await session.get(CreateValueModel, seeded["value_model_id"])
                assert row is not None
                row.name = "Legitimate same-key Value Model"
            elif collision == "business_case":
                row = await session.get(CreateBusinessCase, seeded["business_case_id"])
                assert row is not None
                row.title = "Legitimate same-key Business Case"
            else:
                row = await session.get(CreatePresentation, seeded["presentation_id"])
                assert row is not None
                row.title = "Legitimate same-key Presentation"
            row_id = row.id
            await session.commit()

        expected_resource = {
            "profile": "Company & Selling Profile",
            "value_model": "Value Model",
            "business_case": "Business Case",
            "presentation": "Presentation",
        }[collision]
        with pytest.raises(ValueError, match=expected_resource):
            await seed_owner_demo_data(
                factory,
                PRIMARY_ORGANISATION_ID,
                PRIMARY_USER_ID,
                settings,
            )
        with pytest.raises(ValueError, match=expected_resource):
            await reset_owner_demo_extensions(factory, PRIMARY_ORGANISATION_ID, settings)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            model = {
                "profile": SellingProfileRevision,
                "value_model": CreateValueModel,
                "business_case": CreateBusinessCase,
                "presentation": CreatePresentation,
            }[collision]
            assert await session.get(model, row_id) is not None
        await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("blob_kind", ("template", "presentation"))
def test_owner_demo_refuses_tampered_template_or_presentation_blobs_without_mutation(blob_kind: str) -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        seeded = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            if blob_kind == "template":
                version = await session.get(CreateTemplateVersion, seeded["template_version_id"])
                assert version is not None
                storage_key = version.storage_key
            else:
                version = await session.get(CreatePresentationVersion, seeded["presentation_version_id"])
                assert version is not None and version.pptx_storage_key is not None
                storage_key = version.pptx_storage_key
        storage = LocalVisualStorage(str(TEST_VISUAL_STORAGE))
        original = await storage.read(storage_key)
        await storage.write(storage_key, b"tampered synthetic blob", PPTX_MIME_TYPE)

        with pytest.raises(ValueError, match="[Tt]emplate|[Pp]resentation"):
            await seed_owner_demo_data(
                factory,
                PRIMARY_ORGANISATION_ID,
                PRIMARY_USER_ID,
                settings,
            )
        with pytest.raises(ValueError, match="[Tt]emplate|[Pp]resentation"):
            await reset_owner_demo_extensions(factory, PRIMARY_ORGANISATION_ID, settings)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            assert await session.get(CreatePresentation, seeded["presentation_id"]) is not None
            assert await session.get(CreateTemplateVersion, seeded["template_version_id"]) is not None

        await storage.write(storage_key, original, PPTX_MIME_TYPE)
        await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)
        await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("edit_kind", ("generated_content", "claim_manifest"))
def test_owner_demo_refuses_seller_edited_presentation_output(edit_kind: str) -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        seeded = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            version = await session.get(CreatePresentationVersion, seeded["presentation_version_id"])
            assert version is not None
            if edit_kind == "generated_content":
                edited = copy.deepcopy(version.generated_content_json)
                assert edited and isinstance(edited[0], dict)
                edited[0]["title"] = "Seller-edited real-customer title"
                version.generated_content_json = edited
            else:
                edited = copy.deepcopy(version.claim_manifest_json)
                assert edited and isinstance(edited[0], dict)
                edited[0]["text"] = "Seller-edited real-customer claim"
                version.claim_manifest_json = edited
            await session.commit()

        with pytest.raises(ValueError, match="Presentation identity/content collision"):
            await seed_owner_demo_data(
                factory,
                PRIMARY_ORGANISATION_ID,
                PRIMARY_USER_ID,
                settings,
            )
        with pytest.raises(ValueError, match="Presentation identity/content collision"):
            await reset_owner_demo_extensions(factory, PRIMARY_ORGANISATION_ID, settings)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            assert await session.get(CreatePresentation, seeded["presentation_id"]) is not None
        await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("collision", ("deal_room", "handover"))
def test_owner_demo_refuses_edited_room_or_handover_without_deleting_it(collision: str) -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        seeded = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            if collision == "deal_room":
                row = await session.get(DealRoom, seeded["deal_room_id"])
                assert row is not None
                edited = copy.deepcopy(row.draft_content_json)
                edited["overview"] = "Legitimate customer-authored Deal Room text."
                row.draft_content_json = edited
            else:
                row = await session.get(ClosedWonHandoverRevision, seeded["handover_revision_id"])
                assert row is not None
                edited = copy.deepcopy(row.content_json)
                executive_summary = edited.get("executiveSummary")
                assert isinstance(executive_summary, list) and executive_summary
                assert isinstance(executive_summary[0], dict)
                executive_summary[0]["text"] = "Legitimate seller-authored handover text."
                row.content_json = edited
            row_id = row.id
            await session.commit()

        label = "Deal Room" if collision == "deal_room" else "Closed-Won Handover"
        with pytest.raises(ValueError, match=label):
            await seed_owner_demo_data(
                factory,
                PRIMARY_ORGANISATION_ID,
                PRIMARY_USER_ID,
                settings,
            )
        with pytest.raises(ValueError, match=label):
            await reset_owner_demo_extensions(factory, PRIMARY_ORGANISATION_ID, settings)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            model = DealRoom if collision == "deal_room" else ClosedWonHandoverRevision
            assert await session.get(model, row_id) is not None
        await engine.dispose()

    asyncio.run(scenario())


def test_owner_demo_exact_worker_claim_accepts_only_an_expired_lease() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        seeded = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            version = await session.get(CreateTemplateVersion, seeded["template_version_id"])
            assert version is not None
            version.processing_state = "processing"
            version.processing_attempts = 0
            version.worker_id = "general-worker-active"
            version.lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)
            await session.commit()

        with pytest.raises(ValueError, match="not eligible for an exact claim"):
            await _process_create_work(
                factory,
                settings,
                PRIMARY_ORGANISATION_ID,
                "template",
                seeded["template_version_id"],
                "owner-demo-worker",
            )
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            version = await session.get(CreateTemplateVersion, seeded["template_version_id"])
            assert version is not None
            assert version.worker_id == "general-worker-active"
            assert version.processing_attempts == 0
            version.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()

        await _process_create_work(
            factory,
            settings,
            PRIMARY_ORGANISATION_ID,
            "template",
            seeded["template_version_id"],
            "owner-demo-worker",
        )
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            version = await session.get(CreateTemplateVersion, seeded["template_version_id"])
            assert version is not None
            assert version.processing_state in {"ready", "partial"}
            assert version.processing_attempts == 1
            assert version.worker_id is None
        await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("interrupted_stage", ("create_only", "updated_draft"))
def test_owner_demo_resumes_exact_interrupted_deal_room_seed(interrupted_stage: str) -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        seeded = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            handover = await session.get(ClosedWonHandover, seeded["handover_id"])
            room = await session.get(DealRoom, seeded["deal_room_id"])
            manifest = await session.get(
                BetaSystemEvent,
                owner_demo_base_manifest_id(PRIMARY_ORGANISATION_ID),
            )
            assert handover is not None and room is not None and manifest is not None
            await session.delete(handover)
            await session.delete(room)
            metadata = copy.deepcopy(manifest.metadata_json)
            metadata["extensions"] = None
            manifest.metadata_json = metadata
            await session.commit()

        tenant = TenantContext(
            organisation_id=PRIMARY_ORGANISATION_ID,
            user_id=PRIMARY_USER_ID,
            role="admin",
        )
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            service = DealRoomService(session, tenant, settings)
            mutation = await service.create(seeded["opportunity_id"])
            room = mutation.workspace.room
            assert room is not None
            if interrupted_stage == "updated_draft":
                content = _owner_deal_room_content(
                    PRIMARY_ORGANISATION_ID,
                    seeded["opportunity_id"],
                    seeded["contact_id"],
                    seeded["business_case_version_id"],
                    seeded["presentation_version_id"],
                )
                mutation = await service.update_draft(
                    seeded["opportunity_id"],
                    DealRoomDraftUpdate(
                        expected_draft_version=room.draft_version,
                        expected_lock_version=room.lock_version,
                        content=content,
                    ),
                )
                room = mutation.workspace.room
                assert room is not None and room.draft_version == 2
            interrupted_room_id = room.id

        resumed = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        assert resumed["deal_room_id"] == interrupted_room_id
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            room = await session.get(DealRoom, interrupted_room_id)
            assert room is not None and room.status == "published"
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(DealRoomRevision)
                    .where(
                        DealRoomRevision.organisation_id == PRIMARY_ORGANISATION_ID,
                        DealRoomRevision.room_id == interrupted_room_id,
                    )
                )
                == 1
            )
        await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)
        await engine.dispose()

    asyncio.run(scenario())


def test_owner_demo_reset_recovers_reviewed_close_won_handover_and_deal_room_lifecycle() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        seeded = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        tenant = TenantContext(
            organisation_id=PRIMARY_ORGANISATION_ID,
            user_id=PRIMARY_USER_ID,
            role="admin",
        )
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            deal_room_service = DealRoomService(session, tenant, settings)
            workspace = await deal_room_service.workspace(seeded["opportunity_id"])
            assert workspace.room is not None
            republished = await deal_room_service.publish(
                seeded["opportunity_id"],
                DealRoomPublishRequest(
                    expected_draft_version=workspace.room.draft_version,
                    expected_lock_version=workspace.room.lock_version,
                    confirmed=True,
                ),
            )
            assert republished.workspace.room is not None
            rotated = await deal_room_service.rotate_link(
                seeded["opportunity_id"],
                DealRoomLinkRotationRequest(
                    expected_lock_version=republished.workspace.room.lock_version,
                ),
            )
            assert rotated.share_token is not None

        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            opportunity = await session.get(Opportunity, seeded["opportunity_id"])
            task = await session.get(Task, seeded["task_id"])
            assert opportunity is not None and opportunity.pipeline_stage_id is not None
            assert task is not None
            task.status = "completed"
            pipeline_service = PipelineService(session, tenant, settings)
            await pipeline_service.close_won(
                opportunity.id,
                OpportunityCloseWonRequest(
                    expected_current_stage_id=opportunity.pipeline_stage_id,
                    actual_close_date=datetime.now(UTC).date(),
                    final_amount=opportunity.estimated_value,
                    outcome_reason="solution_fit",
                    outcome_note="Synthetic owner-demo lifecycle review.",
                    idempotency_key="owner-demo-close-won-reset-proof",
                ),
            )

        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            service = HandoverService(session, tenant, settings)
            workspace = await service.workspace(seeded["opportunity_id"])
            assert workspace.active_revision is not None
            assert workspace.handover_lock_version is not None
            refreshed = await service.refresh_sources(
                seeded["opportunity_id"],
                workspace.active_revision.id,
                HandoverLifecycleRequest(
                    expected_handover_version=workspace.handover_lock_version,
                    expected_revision_version=workspace.active_revision.lock_version,
                    confirmed=True,
                ),
            )
            assert refreshed.active_revision is not None
            assert refreshed.handover_lock_version is not None
            reviewed = await service.submit_for_review(
                seeded["opportunity_id"],
                refreshed.active_revision.id,
                HandoverLifecycleRequest(
                    expected_handover_version=refreshed.handover_lock_version,
                    expected_revision_version=refreshed.active_revision.lock_version,
                    confirmed=True,
                ),
            )
            assert reviewed.active_revision is not None
            assert reviewed.handover_lock_version is not None
            approved = await service.approve(
                seeded["opportunity_id"],
                reviewed.active_revision.id,
                HandoverLifecycleRequest(
                    expected_handover_version=reviewed.handover_lock_version,
                    expected_revision_version=reviewed.active_revision.lock_version,
                    confirmed=True,
                ),
            )
            assert approved.active_revision is not None
            assert approved.active_revision.status == "approved"

        reset = await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)
        assert reset == {"status": "reset", "provider_calls": 0}
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            assert await session.get(Opportunity, seeded["opportunity_id"]) is None
            assert await session.get(DealRoom, seeded["deal_room_id"]) is None
            assert await session.get(ClosedWonHandover, seeded["handover_id"]) is None
            assert await session.get(Task, seeded["task_id"]) is None
        await engine.dispose()

    asyncio.run(scenario())


def test_owner_demo_reset_guard_runs_before_mutation() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        marker_id = uuid4()
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            session.add(
                CreateTemplate(
                    id=marker_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    name="Guard preservation marker",
                    state="active",
                    created_by_user_id=PRIMARY_USER_ID,
                )
            )
            await session.commit()
        unsafe = owner_demo_settings().model_copy(update={"feature_google_workspace_enabled": True})
        with pytest.raises(ValueError, match="Google Workspace"):
            await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, unsafe)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            assert await session.get(CreateTemplate, marker_id) is not None
        await engine.dispose()

    asyncio.run(scenario())


def test_owner_demo_published_campaign_upgrade_fails_without_rewriting_snapshot() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        seeded = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        campaign_ids = demo_campaign_ids(PRIMARY_ORGANISATION_ID)
        legacy_company_id = campaign_ids["company"]
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            session.add(
                Company(
                    id=legacy_company_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    name="[DEMO] Northstar Facilities Group",
                    website="https://northstar.example.test",
                    normalized_domain=None,
                    industry="Synthetic multi-site facilities",
                    employee_count=850,
                    status="prospect",
                    owner_user_id=PRIMARY_USER_ID,
                )
            )
            await session.flush()
            await session.execute(
                update(EngageCampaignAudience)
                .where(EngageCampaignAudience.organisation_id == PRIMARY_ORGANISATION_ID)
                .values(company_id=legacy_company_id)
            )
            await session.execute(
                update(EngageCampaignEnrollment)
                .where(EngageCampaignEnrollment.organisation_id == PRIMARY_ORGANISATION_ID)
                .values(company_id=legacy_company_id)
            )
            await session.execute(
                update(Contact)
                .where(
                    Contact.organisation_id == PRIMARY_ORGANISATION_ID,
                    Contact.id.in_((campaign_ids["contact-jane"], campaign_ids["contact-sam"])),
                )
                .values(company_id=legacy_company_id)
            )
            await session.commit()

        with pytest.raises(ValueError, match="published campaign audience.*pnpm demo:reset"):
            await seed_owner_demo_data(
                factory,
                PRIMARY_ORGANISATION_ID,
                PRIMARY_USER_ID,
                settings,
            )
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            audience_company_ids = set(
                (
                    await session.scalars(
                        select(EngageCampaignAudience.company_id).where(
                            EngageCampaignAudience.organisation_id == PRIMARY_ORGANISATION_ID
                        )
                    )
                ).all()
            )
            assert audience_company_ids == {legacy_company_id}
            assert legacy_company_id != seeded["company_id"]
        await engine.dispose()

    asyncio.run(scenario())


def test_owner_demo_reset_refuses_an_inexact_legacy_presentation_marker() -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        base = await seed_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        template_id = uuid4()
        template_version_id = uuid4()
        presentation_id = uuid4()
        template_bytes = _template_bytes()
        storage_key = f"{PRIMARY_ORGANISATION_ID}/create/templates/{template_id}/{template_version_id}.pptx"
        storage = LocalVisualStorage(str(TEST_VISUAL_STORAGE))
        await storage.write(storage_key, template_bytes, PPTX_MIME_TYPE)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            session.add(
                CreateTemplate(
                    id=template_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    name=OWNER_TEMPLATE_NAME,
                    state="active",
                    created_by_user_id=PRIMARY_USER_ID,
                )
            )
            session.add(
                CreateTemplateVersion(
                    id=template_version_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    template_id=template_id,
                    version=1,
                    uploaded_by_user_id=PRIMARY_USER_ID,
                    processing_state="ready",
                    approval_state="approved",
                    display_filename=OWNER_TEMPLATE_FILE_NAME,
                    storage_key=storage_key,
                    storage_status="available",
                    mime_type=PPTX_MIME_TYPE,
                    byte_size=len(template_bytes),
                    checksum_sha256=hashlib.sha256(template_bytes).hexdigest(),
                    processing_schema_version=1,
                    slide_count=1,
                    warning_codes_json=[],
                    manifest_json={},
                    compatibility_state="compatible",
                    compatibility_details_json=[],
                    validation_profile_version=1,
                    validated_at=datetime.now(UTC),
                    authority_attestation_version=1,
                    authority_attested_by_user_id=PRIMARY_USER_ID,
                    authority_attested_at=datetime.now(UTC),
                    processing_attempts=1,
                    approved_by_user_id=PRIMARY_USER_ID,
                    approved_at=datetime.now(UTC),
                    processed_at=datetime.now(UTC),
                )
            )
            session.add(
                CreatePresentation(
                    id=presentation_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    account_id=base["company_id"],
                    opportunity_id=base["opportunity_id"],
                    template_id=template_id,
                    template_version_id=template_version_id,
                    business_case_id=None,
                    business_case_version_id=None,
                    business_case_scenario=None,
                    created_by_user_id=PRIMARY_USER_ID,
                    title=OWNER_PRESENTATION_TITLE,
                    objective="solution_overview",
                    audience_json=[],
                    focus_instruction=None,
                    state="draft_plan",
                    review_state="pending",
                    plan_json=[],
                    source_context_fingerprint="f" * 64,
                    idempotency_key=OWNER_PRESENTATION_KEY,
                )
            )
            await session.commit()

        with pytest.raises(ValueError, match="Presentation identity/content collision"):
            await reset_owner_demo_extensions(factory, PRIMARY_ORGANISATION_ID, settings)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            assert await session.get(CreatePresentation, presentation_id) is not None
            assert await session.get(CreateTemplate, template_id) is not None
            assert await session.get(Company, base["company_id"]) is not None
        assert (TEST_VISUAL_STORAGE / storage_key).is_file()
        await engine.dispose()

    asyncio.run(scenario())


def test_owner_demo_reset_surfaces_post_commit_blob_cleanup_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        await seed_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        template_id = owner_demo_template_id(PRIMARY_ORGANISATION_ID)
        template_version_id = uuid4()
        storage_key = f"{PRIMARY_ORGANISATION_ID}/create/templates/{template_id}/{template_version_id}.pptx"
        template_bytes = _template_bytes()
        storage = LocalVisualStorage(str(TEST_VISUAL_STORAGE))
        await storage.write(storage_key, template_bytes, PPTX_MIME_TYPE)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            session.add(
                CreateTemplate(
                    id=template_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    name=OWNER_TEMPLATE_NAME,
                    state="active",
                    created_by_user_id=PRIMARY_USER_ID,
                )
            )
            session.add(
                _queued_template_version(
                    template_id=template_id,
                    checksum=hashlib.sha256(template_bytes).hexdigest(),
                    storage_key=storage_key,
                    file_name=OWNER_TEMPLATE_FILE_NAME,
                    byte_size=len(template_bytes),
                    version_id=template_version_id,
                )
            )
            await session.commit()

        class FailOnceDeleteStorage:
            failed = False

            async def read(self, selected_storage_key: str) -> bytes:
                return await storage.read(selected_storage_key)

            async def delete(self, selected_storage_key: str) -> None:
                if not self.failed:
                    self.failed = True
                    raise VisualStorageError("synthetic post-commit cleanup failure")
                await storage.delete(selected_storage_key)

        failing_storage = FailOnceDeleteStorage()

        monkeypatch.setattr(
            "revenueos.owner_demo_data.create_visual_storage",
            lambda _settings: failing_storage,
        )
        with pytest.raises(VisualStorageError, match="database reset committed"):
            await reset_owner_demo_extensions(factory, PRIMARY_ORGANISATION_ID, settings)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            assert await session.get(CreateTemplate, template_id) is None
            cleanup_event = await session.get(
                BetaSystemEvent,
                owner_demo_cleanup_event_id(PRIMARY_ORGANISATION_ID),
            )
            assert cleanup_event is not None
            assert cleanup_event.event_type == OWNER_RESET_CLEANUP_EVENT
            assert cleanup_event.metadata_json["storageKeys"] == [storage_key]
        assert (TEST_VISUAL_STORAGE / storage_key).is_file()

        await reset_owner_demo_extensions(factory, PRIMARY_ORGANISATION_ID, settings)
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            assert (
                await session.get(
                    BetaSystemEvent,
                    owner_demo_cleanup_event_id(PRIMARY_ORGANISATION_ID),
                )
                is None
            )
        assert not (TEST_VISUAL_STORAGE / storage_key).exists()
        await engine.dispose()

    asyncio.run(scenario())


def test_full_owner_demo_reset_retries_a_failed_base_blob_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    async def scenario() -> None:
        engine = create_async_engine(TEST_DB_URL)

        def enable_foreign_keys(
            connection: DBAPIConnection,
            connection_record: ConnectionPoolEntry,
        ) -> None:
            del connection_record
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        event.listen(engine.sync_engine, "connect", enable_foreign_keys)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = owner_demo_settings()
        seeded = await seed_owner_demo_data(
            factory,
            PRIMARY_ORGANISATION_ID,
            PRIMARY_USER_ID,
            settings,
        )
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            base_document_storage_key = await session.scalar(
                select(DocumentSource.storage_key).where(
                    DocumentSource.organisation_id == PRIMARY_ORGANISATION_ID,
                )
            )
        assert base_document_storage_key is not None
        storage = LocalVisualStorage(str(TEST_VISUAL_STORAGE))
        assert (TEST_VISUAL_STORAGE / base_document_storage_key).is_file()

        class FailSelectedDeleteStorage:
            failed = False

            async def read(self, selected_storage_key: str) -> bytes:
                return await storage.read(selected_storage_key)

            async def delete(self, selected_storage_key: str) -> None:
                if selected_storage_key == base_document_storage_key and not self.failed:
                    self.failed = True
                    raise VisualStorageError("synthetic base-object cleanup failure")
                await storage.delete(selected_storage_key)

        failing_storage = FailSelectedDeleteStorage()
        monkeypatch.setattr(
            "revenueos.owner_demo_data.create_visual_storage",
            lambda _settings: failing_storage,
        )
        with pytest.raises(VisualStorageError, match="database reset committed"):
            await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)

        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            assert await session.get(Company, seeded["company_id"]) is None
            cleanup_event = await session.get(
                BetaSystemEvent,
                owner_demo_cleanup_event_id(PRIMARY_ORGANISATION_ID),
            )
            assert cleanup_event is not None
            cleanup_keys = cleanup_event.metadata_json["storageKeys"]
            assert isinstance(cleanup_keys, list)
            assert base_document_storage_key in cleanup_keys
        assert (TEST_VISUAL_STORAGE / base_document_storage_key).is_file()

        reset = await reset_demo_data(factory, PRIMARY_ORGANISATION_ID, settings)
        assert reset == {"status": "reset", "provider_calls": 0}
        async with factory() as session:
            await set_tenant_database_context(session, PRIMARY_ORGANISATION_ID)
            assert (
                await session.get(
                    BetaSystemEvent,
                    owner_demo_cleanup_event_id(PRIMARY_ORGANISATION_ID),
                )
                is None
            )
        assert not (TEST_VISUAL_STORAGE / base_document_storage_key).exists()
        await engine.dispose()

    asyncio.run(scenario())
