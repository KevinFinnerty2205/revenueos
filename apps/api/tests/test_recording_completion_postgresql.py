from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from revenueos.beta_maintenance import _delete_organisation_records
from revenueos.beta_services import BetaService
from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.interaction_contracts import InteractionComplete, InteractionCreate
from revenueos.interaction_services import InteractionService
from revenueos.operations import provision_organisation
from revenueos.recording_contracts import RecordingCreateRequest, RecordingStartRequest
from revenueos.recording_repositories import RecordingRepository
from revenueos.recording_services import RecordingService
from revenueos.tenant import TenantContext


def test_postgresql_live_recording_start_and_completion_share_the_interaction_lock(tmp_path: Path) -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required to test recording/completion row locking.")

    settings = Settings(
        environment="test",
        database_url=database_url,
        feature_recording_capture_enabled=True,
        visual_storage_directory=str(tmp_path),
    )

    async def scenario() -> None:
        engine = create_async_engine(database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        organisation_id: UUID | None = None
        suffix = uuid4().hex
        try:
            provisioned = await provision_organisation(
                factory,
                settings,
                external_organisation_id=f"org_live_recording_race_{suffix}",
                organisation_name="Synthetic recording race team",
                timezone="UTC",
                admin_external_user_id=f"user_live_recording_race_{suffix}",
                admin_email=f"live-recording-race-{suffix}@example.com",
                admin_display_name="Synthetic recording administrator",
                idempotency_key=f"live-recording-race-{suffix}",
                operator_reference="live-recording-race-test",
            )
            organisation_id = UUID(provisioned.organisation_id)
            tenant = TenantContext(organisation_id, UUID(provisioned.user_id), "admin")
            async with factory() as setup:
                await set_tenant_database_context(setup, tenant.organisation_id)
                await BetaService(setup, tenant, settings).acknowledge_notice()

            async def play_race(*, recording_wins: bool) -> None:
                async with factory() as setup:
                    await set_tenant_database_context(setup, tenant.organisation_id)
                    interaction = await InteractionService(setup, tenant).create_interaction(
                        InteractionCreate(title="Synthetic race conversation")
                    )
                    interaction_id = interaction.interaction.id
                    await set_tenant_database_context(setup, tenant.organisation_id)
                    recording = await RecordingService(setup, tenant, settings).create(
                        interaction_id,
                        RecordingCreateRequest(
                            recording_type="live_audio_recording",
                            expected_mime_type="audio/webm",
                            notice_version=settings.private_beta_data_notice_version,
                            consent_method="participant_notice_confirmed",
                            user_attested_authority=True,
                            idempotency_key="create-recording",
                        ),
                    )

                async def start(session: AsyncSession) -> str:
                    result = await RecordingService(session, tenant, settings).start(
                        interaction_id,
                        recording.id,
                        RecordingStartRequest(idempotency_key="start-recording"),
                    )
                    return result.lifecycle_status

                async def end(session: AsyncSession) -> str:
                    result = await InteractionService(session, tenant).complete_interaction(
                        interaction_id, InteractionComplete()
                    )
                    return result.interaction.lifecycle_status

                first, second = (start, end) if recording_wins else (end, start)
                expected_state = "recording" if recording_wins else "completed"
                expected_error = "live_recording_in_progress" if recording_wins else "interaction_not_recordable"

                async with factory() as winner, factory() as loser, factory() as observer:
                    await set_tenant_database_context(winner, tenant.organisation_id)
                    assert await RecordingRepository(winner).get_interaction(
                        tenant.organisation_id, interaction_id, for_update=True
                    )
                    await set_tenant_database_context(loser, tenant.organisation_id)
                    loser_pid = await loser.scalar(select(func.pg_backend_pid()))
                    assert isinstance(loser_pid, int)
                    pending = asyncio.create_task(second(loser))
                    try:
                        async with asyncio.timeout(5):
                            while not await observer.scalar(select(func.cardinality(func.pg_blocking_pids(loser_pid)))):
                                assert not pending.done(), "The concurrent request bypassed the Interaction lock."
                                await asyncio.sleep(0.01)
                            assert await first(winner) == expected_state
                            with pytest.raises(PublicAPIError) as fault:
                                await pending
                            assert fault.value.code == expected_error
                    finally:
                        if not pending.done():
                            pending.cancel()
                        await asyncio.gather(pending, return_exceptions=True)

            await play_race(recording_wins=True)
            await play_race(recording_wins=False)
        finally:
            if organisation_id is not None:
                await _delete_organisation_records(factory, settings, organisation_id)
            await engine.dispose()

    asyncio.run(scenario())
