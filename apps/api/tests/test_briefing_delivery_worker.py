from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.briefing_delivery import (
    DISCOVERY_LIMIT,
    BriefingDeliveryError,
    BriefingDeliveryMessage,
    BriefingDeliveryResult,
    BriefingDeliveryTarget,
    BriefingDeliveryWorkerService,
    configured_briefing_delivery_transports,
)
from revenueos.config import Settings
from revenueos.daily_contracts import BriefingPreviewRequest, DeliveryPreferenceUpdate
from revenueos.daily_services import RevenueOSDailyService
from revenueos.interaction_contracts import InteractionUpdate
from revenueos.interaction_services import InteractionService
from revenueos.models import (
    ConversationBriefingOutbox,
    ConversationDeliveryPreference,
    IntegrationConnection,
    Interaction,
    OrganisationMembership,
    PreInteractionBrief,
    ProviderCalendarEvent,
    User,
)
from revenueos.tenant import TenantContext

from .conftest import PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, TEST_DB_URL


class ScriptedTransport:
    def __init__(self, outcomes: Sequence[BriefingDeliveryResult | BriefingDeliveryError]) -> None:
        self._outcomes = list(outcomes)
        self.messages: list[BriefingDeliveryMessage] = []

    async def send(self, message: BriefingDeliveryMessage) -> BriefingDeliveryResult:
        self.messages.append(message)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BriefingDeliveryError):
            raise outcome
        return outcome


class BlockingTransport:
    def __init__(self, result: BriefingDeliveryResult) -> None:
        self._result = result
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.messages: list[BriefingDeliveryMessage] = []

    async def send(self, message: BriefingDeliveryMessage) -> BriefingDeliveryResult:
        self.messages.append(message)
        self.started.set()
        await self.release.wait()
        return self._result


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "feature_briefing_delivery_enabled": True,
        "worker_base_retry_delay_seconds": 1,
        "worker_max_retry_delay_seconds": 10,
        "worker_lease_duration_seconds": 30,
        "worker_heartbeat_interval_seconds": 10,
    }
    values.update(overrides)
    return Settings.model_validate(values)


def _outbox(now: datetime, *, operation_key: str = "a" * 64) -> ConversationBriefingOutbox:
    return ConversationBriefingOutbox(
        id=uuid4(),
        organisation_id=PRIMARY_ORGANISATION_ID,
        user_id=PRIMARY_USER_ID,
        interaction_id=None,
        kind="morning_digest",
        delivery_intent="scheduled",
        status="queued",
        deduplication_key=f"morning:2026-11-01:{uuid4().hex[:24]}",
        source_fingerprint="b" * 64,
        source_observed_at=now,
        subject="Your Oryntela briefing",
        body_text="Review today's authorised conversation work.",
        href="/",
        prepared_for_at=now - timedelta(minutes=30),
        delivery_timezone="UTC",
        operation_key=operation_key,
        attempt_count=0,
        max_attempts=3,
    )


def _connection(
    now: datetime,
    *,
    connector_key: str = "mock_email",
    status: str = "active",
    capabilities: list[str] | None = None,
) -> IntegrationConnection:
    return IntegrationConnection(
        id=uuid4(),
        organisation_id=PRIMARY_ORGANISATION_ID,
        connector_key=connector_key,
        connection_status=status,
        created_by_user_id=PRIMARY_USER_ID,
        connected_at=now,
        last_verified_at=now,
        revoked_at=now if status == "revoked" else None,
        credential_reference=None,
        capability_state_json=["send_email"] if capabilities is None else capabilities,
        external_account_id="local-briefing-test",
        external_account_name="Alex Morgan",
        external_account_email="alex@example.test",
        external_tenant_id=None,
        granted_scopes_json=[],
        metadata_version=1,
    )


def _preference(
    *,
    timezone: str = "UTC",
    morning_digest_enabled: bool = True,
    morning_digest_time: str = "07:30",
    pre_meeting_enabled: bool = True,
    pre_meeting_minutes: int = 30,
) -> ConversationDeliveryPreference:
    return ConversationDeliveryPreference(
        id=uuid4(),
        organisation_id=PRIMARY_ORGANISATION_ID,
        user_id=PRIMARY_USER_ID,
        timezone=timezone,
        morning_digest_enabled=morning_digest_enabled,
        morning_digest_time=morning_digest_time,
        pre_meeting_enabled=pre_meeting_enabled,
        pre_meeting_minutes=pre_meeting_minutes,
        lock_version=1,
    )


async def _row(session_factory: async_sessionmaker, outbox_id: UUID) -> ConversationBriefingOutbox:
    async with session_factory() as session:
        row = await session.scalar(select(ConversationBriefingOutbox).where(ConversationBriefingOutbox.id == outbox_id))
        assert row is not None
        session.expunge(row)
        return row


def test_transport_factory_maps_local_google_and_microsoft_without_network() -> None:
    engine = create_async_engine(TEST_DB_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    transports = configured_briefing_delivery_transports(session_factory, _settings())

    assert set(transports) == {"mock_email", "google_workspace", "microsoft_365"}
    assert configured_briefing_delivery_transports(session_factory, Settings(environment="test")) == {}
    asyncio.run(engine.dispose())


def test_due_owner_is_prioritised_over_a_full_page_of_preference_only_owners() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        due_user_id = UUID(int=(1 << 128) - 1)
        filler_user_ids = [UUID(int=4096 + index) for index in range(DISCOVERY_LIMIT)]
        due = _outbox(now)
        due.user_id = due_user_id
        due.delivery_intent = "scheduled"

        try:
            async with session_factory() as session:
                session.add_all(
                    [
                        User(
                            id=user_id,
                            external_auth_id=f"briefing-discovery-{index}",
                            email=f"briefing-discovery-{index}@example.test",
                            display_name=f"Preference owner {index}",
                        )
                        for index, user_id in enumerate(filler_user_ids)
                    ]
                    + [
                        User(
                            id=due_user_id,
                            external_auth_id="briefing-discovery-due",
                            email="briefing-discovery-due@example.test",
                            display_name="Due owner",
                        )
                    ]
                )
                session.add_all(
                    [
                        OrganisationMembership(
                            organisation_id=PRIMARY_ORGANISATION_ID,
                            user_id=user_id,
                            role="member",
                        )
                        for user_id in [*filler_user_ids, due_user_id]
                    ]
                )
                session.add_all(
                    [
                        ConversationDeliveryPreference(
                            id=uuid4(),
                            organisation_id=PRIMARY_ORGANISATION_ID,
                            user_id=user_id,
                            timezone="UTC",
                            morning_digest_enabled=True,
                            morning_digest_time="07:30",
                            pre_meeting_enabled=False,
                            pre_meeting_minutes=30,
                            lock_version=1,
                        )
                        for user_id in filler_user_ids
                    ]
                )
                session.add(due)
                await session.commit()

            worker = BriefingDeliveryWorkerService(
                session_factory,
                _settings(),
                {},
                clock=lambda: now,
            )

            targets = await worker.discover_eligible_targets()

            assert len(targets) == DISCOVERY_LIMIT
            assert targets[0] == BriefingDeliveryTarget(PRIMARY_ORGANISATION_ID, due_user_id)
            assert BriefingDeliveryTarget(PRIMARY_ORGANISATION_ID, due_user_id) in targets
        finally:
            async with session_factory() as session:
                synthetic_user_ids = select(User.id).where(User.external_auth_id.like("briefing-discovery-%"))
                await session.execute(
                    delete(ConversationBriefingOutbox).where(ConversationBriefingOutbox.user_id.in_(synthetic_user_ids))
                )
                await session.execute(
                    delete(ConversationDeliveryPreference).where(
                        ConversationDeliveryPreference.user_id.in_(synthetic_user_ids)
                    )
                )
                await session.execute(
                    delete(OrganisationMembership).where(OrganisationMembership.user_id.in_(synthetic_user_ids))
                )
                await session.execute(delete(User).where(User.external_auth_id.like("briefing-discovery-%")))
                await session.commit()
            await engine.dispose()

    asyncio.run(scenario())


def test_outbox_accepts_the_global_worker_retry_limit() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        outbox = _outbox(now)
        outbox.max_attempts = 20
        async with session_factory() as session:
            session.add(outbox)
            await session.commit()
        stored = await _row(session_factory, outbox.id)
        assert stored.max_attempts == 20
        await engine.dispose()

    asyncio.run(scenario())


def test_preview_outbox_is_permanently_unclaimable_by_the_delivery_worker() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        preview = _outbox(now, operation_key=f"preview_{'a' * 56}")
        preview.delivery_intent = "preview"
        async with session_factory() as session:
            session.add_all([preview, _connection(now, connector_key="google_workspace")])
            await session.commit()
        transport = ScriptedTransport([BriefingDeliveryResult("must-not-send")])
        worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {"google_workspace": transport},
            clock=lambda: now,
        )

        assert await worker.run_once("provider-preview-guard") is False
        retained = await _row(session_factory, preview.id)
        assert retained.status == "queued"
        assert (
            await worker.claim_next(
                BriefingDeliveryTarget(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID),
                "direct-preview-claim",
            )
            is None
        )
        assert transport.messages == []
        await engine.dispose()

    asyncio.run(scenario())


def test_saved_preferences_schedule_timezone_aware_rows_without_delivering_previews() -> None:
    async def scenario() -> None:
        # 07:00 in Sydney on this date; the morning row is due at 07:15.
        now = datetime(2026, 10, 31, 20, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        interaction_id = uuid4()
        async with session_factory() as session:
            session.add_all(
                [
                    ConversationDeliveryPreference(
                        id=uuid4(),
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=PRIMARY_USER_ID,
                        timezone="Australia/Sydney",
                        morning_digest_enabled=True,
                        morning_digest_time="07:15",
                        pre_meeting_enabled=True,
                        pre_meeting_minutes=30,
                        lock_version=1,
                    ),
                    Interaction(
                        id=interaction_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_type="online_meeting",
                        lifecycle_status="planned",
                        title="Synthetic due briefing",
                        scheduled_start_at=now + timedelta(minutes=20),
                        scheduled_end_at=now + timedelta(minutes=50),
                        creation_origin="manual",
                        created_by_user_id=PRIMARY_USER_ID,
                    ),
                    _connection(now),
                ]
            )
            await session.commit()
        disabled_worker = BriefingDeliveryWorkerService(
            session_factory,
            Settings(environment="test"),
            {},
            clock=lambda: now,
        )
        assert await disabled_worker.run_once("disabled-scheduler") is False
        async with session_factory() as session:
            assert (
                await session.scalar(
                    select(ConversationBriefingOutbox).where(
                        ConversationBriefingOutbox.organisation_id == PRIMARY_ORGANISATION_ID,
                        ConversationBriefingOutbox.user_id == PRIMARY_USER_ID,
                    )
                )
            ) is None
        transport = ScriptedTransport([BriefingDeliveryResult("scheduled-pre-meeting-accepted")])
        worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {"mock_email": transport},
            clock=lambda: now,
        )

        assert await worker.run_once("scheduler-worker") is True
        async with session_factory() as session:
            rows = list(
                (
                    await session.scalars(
                        select(ConversationBriefingOutbox).where(
                            ConversationBriefingOutbox.organisation_id == PRIMARY_ORGANISATION_ID,
                            ConversationBriefingOutbox.user_id == PRIMARY_USER_ID,
                        )
                    )
                ).all()
            )
        scheduled = {row.kind: row for row in rows if row.delivery_intent == "scheduled"}
        assert set(scheduled) == {"morning_digest", "pre_meeting"}
        assert scheduled["morning_digest"].status == "queued"
        assert scheduled["morning_digest"].prepared_for_at.replace(tzinfo=UTC) == now + timedelta(minutes=15)
        assert scheduled["morning_digest"].delivery_timezone == "Australia/Sydney"
        assert scheduled["pre_meeting"].status == "sent"
        assert scheduled["pre_meeting"].prepared_for_at.replace(tzinfo=UTC) == now - timedelta(minutes=10)
        assert all(row.operation_key.startswith("delivery_") for row in scheduled.values())
        assert [message.outbox_id for message in transport.messages] == [scheduled["pre_meeting"].id]

        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        async with session_factory() as session:
            preview = await RevenueOSDailyService(session, tenant, _settings()).prepare_briefing_preview(
                BriefingPreviewRequest(kind="pre_meeting", interaction_id=interaction_id),
                now=now,
            )
        retained_preview = await _row(session_factory, preview.id)
        assert retained_preview.delivery_intent == "preview"
        assert retained_preview.status == "queued"
        assert await worker.run_once("scheduler-worker-again") is False
        assert len(transport.messages) == 1
        await engine.dispose()

    asyncio.run(scenario())


def test_scheduler_uses_latest_linked_provider_start_and_state_for_materialisation() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        connection = _connection(now, connector_key="microsoft_365")
        unscheduled_id = uuid4()
        stale_schedule_id = uuid4()
        provider_cancelled_id = uuid4()
        provider_starts = {
            unscheduled_id: now + timedelta(days=1),
            stale_schedule_id: now + timedelta(days=2),
        }

        def provider_event(
            interaction_id: UUID,
            *,
            suffix: str,
            starts_at: datetime,
            state: str,
            synced_at: datetime,
        ) -> ProviderCalendarEvent:
            return ProviderCalendarEvent(
                id=uuid4(),
                organisation_id=PRIMARY_ORGANISATION_ID,
                connection_id=connection.id,
                provider_key="microsoft_365",
                provider_event_id=f"briefing-materialisation-{suffix}",
                title=f"Synthetic provider event {suffix}",
                start_at=starts_at,
                end_at=starts_at + timedelta(hours=1),
                provider_timezone="UTC",
                attendee_emails_json=[],
                sensitivity="normal",
                state=state,
                match_state="matched",
                interaction_id=interaction_id,
                last_synced_at=synced_at,
            )

        async with session_factory() as session:
            session.add_all(
                [
                    ConversationDeliveryPreference(
                        id=uuid4(),
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=PRIMARY_USER_ID,
                        timezone="UTC",
                        morning_digest_enabled=False,
                        morning_digest_time="07:30",
                        pre_meeting_enabled=True,
                        pre_meeting_minutes=30,
                        lock_version=1,
                    ),
                    connection,
                    Interaction(
                        id=unscheduled_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_type="online_meeting",
                        lifecycle_status="planned",
                        title="Provider-only scheduled conversation",
                        scheduled_start_at=None,
                        scheduled_end_at=None,
                        creation_origin="manual",
                        created_by_user_id=PRIMARY_USER_ID,
                    ),
                    Interaction(
                        id=stale_schedule_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_type="online_meeting",
                        lifecycle_status="planned",
                        title="Provider-rescheduled conversation",
                        scheduled_start_at=now + timedelta(days=30),
                        scheduled_end_at=now + timedelta(days=30, hours=1),
                        creation_origin="manual",
                        created_by_user_id=PRIMARY_USER_ID,
                    ),
                    Interaction(
                        id=provider_cancelled_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_type="online_meeting",
                        lifecycle_status="planned",
                        title="Provider-cancelled conversation",
                        scheduled_start_at=now + timedelta(days=3),
                        scheduled_end_at=now + timedelta(days=3, hours=1),
                        creation_origin="manual",
                        created_by_user_id=PRIMARY_USER_ID,
                    ),
                ]
            )
            session.add_all(
                [
                    provider_event(
                        unscheduled_id,
                        suffix="unscheduled-old",
                        starts_at=now + timedelta(days=20),
                        state="active",
                        synced_at=now - timedelta(minutes=2),
                    ),
                    provider_event(
                        unscheduled_id,
                        suffix="unscheduled-latest",
                        starts_at=provider_starts[unscheduled_id],
                        state="active",
                        synced_at=now - timedelta(minutes=1),
                    ),
                    provider_event(
                        stale_schedule_id,
                        suffix="stale-latest",
                        starts_at=provider_starts[stale_schedule_id],
                        state="active",
                        synced_at=now - timedelta(minutes=1),
                    ),
                    provider_event(
                        provider_cancelled_id,
                        suffix="cancelled-old",
                        starts_at=now + timedelta(days=3),
                        state="active",
                        synced_at=now - timedelta(minutes=2),
                    ),
                    provider_event(
                        provider_cancelled_id,
                        suffix="cancelled-latest",
                        starts_at=now + timedelta(days=3),
                        state="cancelled",
                        synced_at=now - timedelta(minutes=1),
                    ),
                ]
            )
            await session.commit()

        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        async with session_factory() as session:
            created = await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now)
        assert created == 2

        async with session_factory() as session:
            rows = list(
                (
                    await session.scalars(
                        select(ConversationBriefingOutbox).where(
                            ConversationBriefingOutbox.delivery_intent == "scheduled",
                            ConversationBriefingOutbox.kind == "pre_meeting",
                        )
                    )
                ).all()
            )
        assert {row.interaction_id for row in rows} == {unscheduled_id, stale_schedule_id}
        for row in rows:
            assert row.interaction_id is not None
            assert row.prepared_for_at.replace(tzinfo=UTC) == provider_starts[row.interaction_id] - timedelta(
                minutes=30
            )
        await engine.dispose()

    asyncio.run(scenario())


def test_scheduler_catches_up_same_day_morning_digest_after_due_time_once() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add_all(
                [
                    ConversationDeliveryPreference(
                        id=uuid4(),
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=PRIMARY_USER_ID,
                        timezone="UTC",
                        morning_digest_enabled=True,
                        morning_digest_time="07:30",
                        pre_meeting_enabled=False,
                        pre_meeting_minutes=30,
                        lock_version=1,
                    ),
                    _connection(now),
                ]
            )
            await session.commit()
        transport = ScriptedTransport([BriefingDeliveryResult("catch-up-accepted")])
        worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {"mock_email": transport},
            clock=lambda: now,
        )

        assert await worker.run_once("catch-up-worker") is True
        async with session_factory() as session:
            rows = list((await session.scalars(select(ConversationBriefingOutbox))).all())
        assert len(rows) == 1
        catch_up = rows[0]
        assert catch_up.delivery_intent == "scheduled"
        assert catch_up.status == "sent"
        assert catch_up.prepared_for_at.replace(tzinfo=UTC) == datetime(2026, 11, 1, 7, 30, tzinfo=UTC)
        assert catch_up.deduplication_key.startswith("delivery:morning:2026-11-01:")
        assert [message.outbox_id for message in transport.messages] == [catch_up.id]

        assert await worker.run_once("catch-up-worker-again") is False
        assert len(transport.messages) == 1
        await engine.dispose()

    asyncio.run(scenario())


def test_scheduler_does_not_reactivate_a_worker_cancelled_authority_row() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add(
                ConversationDeliveryPreference(
                    id=uuid4(),
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    user_id=PRIMARY_USER_ID,
                    timezone="UTC",
                    morning_digest_enabled=True,
                    morning_digest_time="07:30",
                    pre_meeting_enabled=False,
                    pre_meeting_minutes=30,
                    lock_version=1,
                )
            )
            await session.commit()
        worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {},
            clock=lambda: now,
        )

        assert await worker.run_once("missing-authority-worker") is True
        async with session_factory() as session:
            rows = list((await session.scalars(select(ConversationBriefingOutbox))).all())
        assert len(rows) == 1
        assert rows[0].status == "cancelled"
        assert rows[0].failure_code == "delivery_authority_unavailable"
        assert await worker.run_once("missing-authority-worker-again") is False
        retained = await _row(session_factory, rows[0].id)
        assert retained.status == "cancelled"
        assert retained.failure_code == "delivery_authority_unavailable"
        await engine.dispose()

    asyncio.run(scenario())


def test_preference_disable_clears_retry_state_and_same_source_can_reactivate() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        async with session_factory() as session:
            session.add(_preference(pre_meeting_enabled=False))
            await session.commit()
        async with session_factory() as session:
            assert await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now) == 1
        async with session_factory() as session:
            initial = await session.scalar(
                select(ConversationBriefingOutbox).where(
                    ConversationBriefingOutbox.delivery_intent == "scheduled",
                    ConversationBriefingOutbox.kind == "morning_digest",
                )
            )
            assert initial is not None
            initial_id = initial.id
            initial.attempt_count = 2
            initial.next_attempt_at = now + timedelta(minutes=5)
            initial.failed_at = now
            initial.failure_code = "provider_busy"
            await session.commit()

        async with session_factory() as session:
            await RevenueOSDailyService(session, tenant, _settings()).save_delivery_preferences(
                DeliveryPreferenceUpdate(
                    expected_lock_version=1,
                    timezone="UTC",
                    morning_digest_enabled=False,
                    morning_digest_time="07:30",
                    pre_meeting_enabled=False,
                    pre_meeting_minutes=30,
                )
            )
        disabled = await _row(session_factory, initial_id)
        assert disabled.status == "cancelled"
        assert disabled.attempt_count == 0
        assert disabled.next_attempt_at is None
        assert disabled.failed_at is None
        assert disabled.failure_code is None

        async with session_factory() as session:
            await RevenueOSDailyService(session, tenant, _settings()).save_delivery_preferences(
                DeliveryPreferenceUpdate(
                    expected_lock_version=2,
                    timezone="UTC",
                    morning_digest_enabled=True,
                    morning_digest_time="07:30",
                    pre_meeting_enabled=False,
                    pre_meeting_minutes=30,
                )
            )
        async with session_factory() as session:
            assert await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now) == 1
        reactivated = await _row(session_factory, initial_id)
        assert reactivated.status == "queued"
        assert reactivated.attempt_count == 0
        assert reactivated.next_attempt_at is None
        assert reactivated.failed_at is None
        assert reactivated.failure_code is None
        async with session_factory() as session:
            assert (
                await session.scalar(
                    select(ConversationBriefingOutbox.id).where(
                        ConversationBriefingOutbox.delivery_intent == "scheduled",
                        ConversationBriefingOutbox.kind == "morning_digest",
                    )
                )
                == initial_id
            )
        await engine.dispose()

    asyncio.run(scenario())


def test_preference_reschedule_clears_stale_retry_and_unsubmitted_claim_state() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        async with session_factory() as session:
            session.add(_preference(pre_meeting_enabled=False))
            await session.commit()
        async with session_factory() as session:
            assert await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now) == 1
        async with session_factory() as session:
            row = await session.scalar(
                select(ConversationBriefingOutbox).where(
                    ConversationBriefingOutbox.delivery_intent == "scheduled",
                    ConversationBriefingOutbox.kind == "morning_digest",
                )
            )
            assert row is not None
            row_id = row.id
            row.status = "sending"
            row.attempt_count = 2
            row.next_attempt_at = now + timedelta(minutes=5)
            row.worker_id = "abandoned-before-submission"
            row.lease_expires_at = now + timedelta(minutes=1)
            row.failed_at = now
            row.failure_code = "provider_busy"
            await session.commit()

        async with session_factory() as session:
            await RevenueOSDailyService(session, tenant, _settings()).save_delivery_preferences(
                DeliveryPreferenceUpdate(
                    expected_lock_version=1,
                    timezone="UTC",
                    morning_digest_enabled=True,
                    morning_digest_time="09:00",
                    pre_meeting_enabled=False,
                    pre_meeting_minutes=30,
                )
            )
        rescheduled = await _row(session_factory, row_id)
        assert rescheduled.status == "superseded"
        assert rescheduled.attempt_count == 0
        assert rescheduled.next_attempt_at is None
        assert rescheduled.worker_id is None
        assert rescheduled.lease_expires_at is None
        assert rescheduled.failed_at is None
        assert rescheduled.failure_code is None
        async with session_factory() as session:
            assert await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now) == 1
            replacement = await session.scalar(
                select(ConversationBriefingOutbox).where(
                    ConversationBriefingOutbox.kind == "morning_digest",
                    ConversationBriefingOutbox.delivery_intent == "scheduled",
                    ConversationBriefingOutbox.id != row_id,
                )
            )
            assert replacement is not None
            assert replacement.status == "queued"
            assert replacement.prepared_for_at.replace(tzinfo=UTC) == datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
        await engine.dispose()

    asyncio.run(scenario())


def test_due_claim_is_exclusive_and_retry_reuses_stable_operation_key() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        current = [now]
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        outbox = _outbox(now, operation_key="stable-operation-key")
        linked_interaction_id = uuid4()
        outbox.body_text = (
            "Northstar & Partners\n\n"
            f"Prepare: /conversations/{linked_interaction_id}#preparation\n"
            "Open: /daily#priority"
        )
        async with session_factory() as session:
            session.add_all([outbox, _connection(now, connector_key="google_workspace"), _preference()])
            await session.commit()
        transport = ScriptedTransport(
            [
                BriefingDeliveryError("provider_busy", retryable=True, retry_after_seconds=600),
                BriefingDeliveryResult("accepted-1"),
            ]
        )
        worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {"google_workspace": transport},
            clock=lambda: current[0],
        )

        target = (await worker.discover_eligible_targets())[0]
        claim = await worker.claim_next(target, "worker-a")
        assert claim is not None
        assert await worker.claim_next(target, "worker-b") is None
        await worker.execute_claimed(claim)
        retrying = await _row(session_factory, outbox.id)
        assert retrying.status == "queued"
        assert retrying.attempt_count == 1
        assert retrying.failure_code == "provider_busy"
        assert retrying.next_attempt_at is not None
        assert retrying.next_attempt_at.replace(tzinfo=UTC) == now + timedelta(seconds=10)

        current[0] += timedelta(seconds=10)
        retry_claim = await worker.claim_next(target, "worker-b")
        assert retry_claim is not None
        await worker.execute_claimed(retry_claim)
        sent = await _row(session_factory, outbox.id)
        assert sent.status == "sent"
        assert sent.attempt_count == 2
        assert sent.provider_message_id == "accepted-1"
        assert [message.operation_key for message in transport.messages] == [
            "stable-operation-key",
            "stable-operation-key",
        ]
        assert all(message.href == "/" for message in transport.messages)
        assert all(
            f"http://localhost:3000/conversations/{linked_interaction_id}#preparation" in message.body
            for message in transport.messages
        )
        assert all("Open: http://localhost:3000/daily#priority" in message.body for message in transport.messages)
        assert all(message.html_body is not None for message in transport.messages)
        assert all("ORYNTELA" in (message.html_body or "") for message in transport.messages)
        assert all("Northstar &amp; Partners" in (message.html_body or "") for message in transport.messages)
        assert all(
            f'href="http://localhost:3000/conversations/{linked_interaction_id}#preparation"'
            in (message.html_body or "")
            for message in transport.messages
        )
        assert all("Open Oryntela: http://localhost:3000/" in message.body for message in transport.messages)
        await engine.dispose()

    asyncio.run(scenario())


def test_claimed_morning_digest_is_superseded_by_new_source_before_submission() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        old = _outbox(now, operation_key="old-morning-operation")
        async with session_factory() as session:
            session.add_all([old, _connection(now, connector_key="google_workspace"), _preference()])
            await session.commit()
        transport = ScriptedTransport([BriefingDeliveryResult("replacement-accepted")])
        worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {"google_workspace": transport},
            clock=lambda: now,
        )

        target = (await worker.discover_eligible_targets())[0]
        old_claim = await worker.claim_next(target, "worker-old-morning")
        assert old_claim is not None
        replacement = _outbox(now, operation_key="new-morning-operation")
        replacement.source_fingerprint = "c" * 64
        replacement.subject = "Current synthetic morning briefing"
        async with session_factory() as session:
            session.add(replacement)
            await session.commit()

        await worker.execute_claimed(old_claim)
        superseded = await _row(session_factory, old.id)
        assert superseded.status == "superseded"
        assert superseded.failure_code == "delivery_source_superseded"
        assert transport.messages == []

        replacement_claim = await worker.claim_next(target, "worker-current-morning")
        assert replacement_claim is not None
        await worker.execute_claimed(replacement_claim)
        delivered = await _row(session_factory, replacement.id)
        assert delivered.status == "sent"
        assert [message.outbox_id for message in transport.messages] == [replacement.id]
        await engine.dispose()

    asyncio.run(scenario())


def test_rescheduled_pre_meeting_replacement_wins_after_old_row_was_claimed() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        interaction_id = uuid4()
        old = _outbox(now, operation_key="old-pre-meeting-operation")
        old.kind = "pre_meeting"
        old.prepared_for_at = now - timedelta(minutes=1)
        old.interaction_id = interaction_id
        old.deduplication_key = f"pre:{interaction_id}:{'a' * 24}"
        old.href = f"/conversations/{interaction_id}#preparation"
        old.subject = "Prepare: stale synthetic meeting"
        async with session_factory() as session:
            session.add_all(
                [
                    Interaction(
                        id=interaction_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_type="online_meeting",
                        lifecycle_status="planned",
                        title="Synthetic rescheduled meeting",
                        scheduled_start_at=now + timedelta(minutes=29),
                        scheduled_end_at=now + timedelta(minutes=59),
                        creation_origin="manual",
                        created_by_user_id=PRIMARY_USER_ID,
                    ),
                    ConversationDeliveryPreference(
                        id=uuid4(),
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=PRIMARY_USER_ID,
                        timezone="UTC",
                        morning_digest_enabled=False,
                        morning_digest_time="07:30",
                        pre_meeting_enabled=True,
                        pre_meeting_minutes=30,
                        lock_version=1,
                    ),
                    old,
                    _connection(now, connector_key="microsoft_365"),
                ]
            )
            await session.commit()
        transport = ScriptedTransport([BriefingDeliveryResult("current-pre-meeting-accepted")])
        worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {"microsoft_365": transport},
            clock=lambda: now,
        )
        target = (await worker.discover_eligible_targets())[0]
        old_claim = await worker.claim_next(target, "worker-old-pre-meeting")
        assert old_claim is not None

        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        async with session_factory() as session:
            await InteractionService(session, tenant).update_interaction(
                interaction_id,
                InteractionUpdate(
                    scheduled_start_at=now + timedelta(minutes=25),
                    scheduled_end_at=now + timedelta(minutes=55),
                ),
            )
        async with session_factory() as session:
            assert await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now) == 1
        async with session_factory() as session:
            replacement = await session.scalar(
                select(ConversationBriefingOutbox).where(
                    ConversationBriefingOutbox.interaction_id == interaction_id,
                    ConversationBriefingOutbox.delivery_intent == "scheduled",
                    ConversationBriefingOutbox.id != old.id,
                )
            )
            assert replacement is not None

        await worker.execute_claimed(old_claim)
        superseded = await _row(session_factory, old.id)
        assert superseded.status == "superseded"
        assert transport.messages == []

        assert await worker.run_once("worker-current-pre-meeting") is True
        delivered = await _row(session_factory, replacement.id)
        assert delivered.status == "sent"
        assert [message.outbox_id for message in transport.messages] == [replacement.id]
        await engine.dispose()

    asyncio.run(scenario())


def test_in_flight_submission_fences_changed_source_and_concurrent_replacement() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        current = [now]
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        interaction_id = uuid4()
        outbox = _outbox(now, operation_key="in-flight-source-operation")
        outbox.kind = "pre_meeting"
        outbox.prepared_for_at = now - timedelta(minutes=1)
        outbox.interaction_id = interaction_id
        outbox.deduplication_key = f"delivery:pre:{interaction_id}:{'a' * 24}"
        outbox.href = f"/conversations/{interaction_id}#preparation"
        async with session_factory() as session:
            session.add_all(
                [
                    Interaction(
                        id=interaction_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_type="online_meeting",
                        lifecycle_status="planned",
                        title="Synthetic in-flight meeting",
                        scheduled_start_at=now + timedelta(minutes=29),
                        scheduled_end_at=now + timedelta(minutes=59),
                        creation_origin="manual",
                        created_by_user_id=PRIMARY_USER_ID,
                    ),
                    _preference(morning_digest_enabled=False),
                    _connection(now, connector_key="google_workspace"),
                    outbox,
                ]
            )
            await session.commit()
        transport = BlockingTransport(BriefingDeliveryResult("in-flight-accepted"))
        worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {"google_workspace": transport},
            clock=lambda: current[0],
        )
        target = BriefingDeliveryTarget(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID)
        claim = await worker.claim_next(target, "worker-in-flight")
        assert claim is not None
        execution = asyncio.create_task(worker.execute_claimed(claim))
        await asyncio.wait_for(transport.started.wait(), timeout=2)

        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        try:
            async with session_factory() as session:
                await InteractionService(session, tenant).update_interaction(
                    interaction_id,
                    InteractionUpdate(
                        scheduled_start_at=now + timedelta(minutes=25),
                        scheduled_end_at=now + timedelta(minutes=55),
                    ),
                )
            async with session_factory() as session:
                assert (
                    await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now) == 0
                )
            async with session_factory() as session:
                scheduled_rows = list(
                    (
                        await session.scalars(
                            select(ConversationBriefingOutbox).where(
                                ConversationBriefingOutbox.interaction_id == interaction_id,
                                ConversationBriefingOutbox.delivery_intent == "scheduled",
                            )
                        )
                    ).all()
                )
            assert [row.id for row in scheduled_rows] == [outbox.id]
            assert scheduled_rows[0].status == "sending"
            assert scheduled_rows[0].submission_started_at is not None

            replacement = _outbox(now, operation_key="concurrent-replacement-operation")
            replacement.kind = "pre_meeting"
            replacement.prepared_for_at = now - timedelta(minutes=5)
            replacement.interaction_id = interaction_id
            replacement.deduplication_key = f"delivery:pre:{interaction_id}:{'c' * 24}"
            replacement.href = f"/conversations/{interaction_id}#preparation"
            async with session_factory() as session:
                session.add(replacement)
                await session.commit()
            replacement_claim = await worker.claim_next(target, "worker-concurrent-replacement")
            assert replacement_claim is not None
            await worker.execute_claimed(replacement_claim)
            deferred = await _row(session_factory, replacement.id)
            assert deferred.status == "queued"
            assert deferred.failure_code == "delivery_submission_in_flight"
            assert deferred.attempt_count == 0
            assert len(transport.messages) == 1
        finally:
            transport.release.set()
            await execution

        delivered = await _row(session_factory, outbox.id)
        assert delivered.status == "sent"
        current[0] += timedelta(seconds=31)
        replacement_claim = await worker.claim_next(target, "worker-after-reconciliation")
        assert replacement_claim is not None
        await worker.execute_claimed(replacement_claim)
        fenced = await _row(session_factory, replacement.id)
        assert fenced.status == "superseded"
        assert len(transport.messages) == 1
        await engine.dispose()

    asyncio.run(scenario())


def test_completed_pre_meeting_source_is_cancelled_before_delivery() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        interaction_id = uuid4()
        outbox = _outbox(now)
        outbox.interaction_id = interaction_id
        outbox.kind = "pre_meeting"
        outbox.prepared_for_at = now
        outbox.href = f"/conversations/{interaction_id}#preparation"
        async with session_factory() as session:
            session.add_all(
                [
                    Interaction(
                        id=interaction_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_type="online_meeting",
                        lifecycle_status="completed",
                        title="Already completed synthetic meeting",
                        scheduled_start_at=now + timedelta(minutes=30),
                        scheduled_end_at=now + timedelta(minutes=60),
                        creation_origin="manual",
                        created_by_user_id=PRIMARY_USER_ID,
                    ),
                    outbox,
                    _connection(now, connector_key="google_workspace"),
                    _preference(morning_digest_enabled=False),
                ]
            )
            await session.commit()
        transport = ScriptedTransport([BriefingDeliveryResult("must-not-send")])
        worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {"google_workspace": transport},
            clock=lambda: now,
        )

        target = BriefingDeliveryTarget(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID)
        claim = await worker.claim_next(target, "worker-completed")
        assert claim is not None
        await worker.execute_claimed(claim)
        cancelled = await _row(session_factory, outbox.id)
        assert cancelled.status == "cancelled"
        assert cancelled.failure_code == "delivery_source_cancelled"
        assert transport.messages == []
        await engine.dispose()

    asyncio.run(scenario())


def test_preference_is_rechecked_after_claim_and_cancels_without_delivery() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        outbox = _outbox(now)
        async with session_factory() as session:
            session.add_all(
                [
                    outbox,
                    _connection(now, connector_key="microsoft_365"),
                    ConversationDeliveryPreference(
                        id=uuid4(),
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=PRIMARY_USER_ID,
                        timezone="Australia/Sydney",
                        morning_digest_enabled=False,
                        morning_digest_time="07:30",
                        pre_meeting_enabled=True,
                        pre_meeting_minutes=30,
                        lock_version=1,
                    ),
                ]
            )
            await session.commit()
        transport = ScriptedTransport([BriefingDeliveryResult("must-not-send")])
        worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {"microsoft_365": transport},
            clock=lambda: now,
        )

        assert await worker.run_once("worker-cancel") is True
        cancelled = await _row(session_factory, outbox.id)
        assert cancelled.status == "cancelled"
        assert cancelled.failure_code == "delivery_preference_disabled"
        assert transport.messages == []
        await engine.dispose()

    asyncio.run(scenario())


def test_deleted_preference_after_claim_cancels_before_transport() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        outbox = _outbox(now)
        preference = _preference()
        async with session_factory() as session:
            session.add_all(
                [
                    outbox,
                    preference,
                    _connection(now, connector_key="google_workspace"),
                ]
            )
            await session.commit()
        transport = ScriptedTransport([BriefingDeliveryResult("must-not-send")])
        worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {"google_workspace": transport},
            clock=lambda: now,
        )
        target = BriefingDeliveryTarget(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID)
        claim = await worker.claim_next(target, "worker-preference-deleted")
        assert claim is not None

        async with session_factory() as session:
            saved_preference = await session.scalar(
                select(ConversationDeliveryPreference).where(ConversationDeliveryPreference.id == preference.id)
            )
            assert saved_preference is not None
            await session.delete(saved_preference)
            await session.commit()

        await worker.execute_claimed(claim)
        cancelled = await _row(session_factory, outbox.id)
        assert cancelled.status == "cancelled"
        assert cancelled.failure_code == "delivery_preference_missing"
        assert cancelled.submission_started_at is None
        assert transport.messages == []
        await engine.dispose()

    asyncio.run(scenario())


def test_timezone_preference_change_reschedules_without_consuming_an_attempt() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        outbox = _outbox(now)
        async with session_factory() as session:
            session.add_all(
                [
                    outbox,
                    _connection(now, connector_key="google_workspace"),
                    ConversationDeliveryPreference(
                        id=uuid4(),
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        user_id=PRIMARY_USER_ID,
                        timezone="Australia/Sydney",
                        morning_digest_enabled=True,
                        morning_digest_time="20:00",
                        pre_meeting_enabled=True,
                        pre_meeting_minutes=30,
                        lock_version=1,
                    ),
                ]
            )
            await session.commit()
        transport = ScriptedTransport([BriefingDeliveryResult("must-not-send")])
        worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {"google_workspace": transport},
            clock=lambda: now,
        )

        assert await worker.run_once("worker-reschedule") is True
        rescheduled = await _row(session_factory, outbox.id)
        assert rescheduled.status == "superseded"
        assert rescheduled.attempt_count == 0
        async with session_factory() as session:
            replacement = await session.scalar(
                select(ConversationBriefingOutbox).where(
                    ConversationBriefingOutbox.kind == "morning_digest",
                    ConversationBriefingOutbox.delivery_intent == "scheduled",
                    ConversationBriefingOutbox.id != outbox.id,
                )
            )
            assert replacement is not None
            assert replacement.status == "queued"
            assert replacement.prepared_for_at.replace(tzinfo=UTC) == datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
            assert replacement.delivery_timezone == "Australia/Sydney"
        assert transport.messages == []
        await engine.dispose()

    asyncio.run(scenario())


def test_revoked_authority_cancels_and_ambiguous_provider_outcome_never_retries() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        current = [now]
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        revoked_outbox = _outbox(now)
        async with session_factory() as session:
            session.add_all(
                [
                    revoked_outbox,
                    _connection(now, connector_key="google_workspace", status="revoked"),
                    _preference(),
                ]
            )
            await session.commit()
        revoked_transport = ScriptedTransport([BriefingDeliveryResult("must-not-send")])
        revoked_worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {"google_workspace": revoked_transport},
            clock=lambda: current[0],
        )

        target = BriefingDeliveryTarget(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID)
        revoked_claim = await revoked_worker.claim_next(target, "worker-revoked")
        assert revoked_claim is not None
        await revoked_worker.execute_claimed(revoked_claim)
        revoked = await _row(session_factory, revoked_outbox.id)
        assert revoked.status == "cancelled"
        assert revoked.failure_code == "delivery_authority_unavailable"
        assert revoked_transport.messages == []

        async with session_factory() as session:
            connection = await session.scalar(
                select(IntegrationConnection).where(
                    IntegrationConnection.organisation_id == PRIMARY_ORGANISATION_ID,
                    IntegrationConnection.connector_key == "google_workspace",
                )
            )
            assert connection is not None
            await session.delete(connection)
            await session.flush()
            ambiguous_outbox = _outbox(now, operation_key="ambiguous-operation-key")
            session.add_all(
                [
                    ambiguous_outbox,
                    _connection(now, connector_key="microsoft_365"),
                ]
            )
            await session.commit()
        ambiguous_transport = ScriptedTransport(
            [BriefingDeliveryError("provider_timeout_after_submit", retryable=True, uncertain=True)]
        )
        ambiguous_worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {"microsoft_365": ambiguous_transport},
            clock=lambda: current[0],
        )

        ambiguous_claim = await ambiguous_worker.claim_next(target, "worker-ambiguous")
        assert ambiguous_claim is not None
        await ambiguous_worker.execute_claimed(ambiguous_claim)
        ambiguous = await _row(session_factory, ambiguous_outbox.id)
        assert ambiguous.status == "failed"
        assert ambiguous.failure_code == "provider_outcome_unknown"
        current[0] += timedelta(hours=1)
        assert await ambiguous_worker.claim_next(target, "worker-ambiguous-again") is None
        assert len(ambiguous_transport.messages) == 1
        await engine.dispose()

    asyncio.run(scenario())


def test_ambiguous_outcome_fences_changed_fingerprint_until_manual_reset() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        interaction_id = uuid4()
        outbox = _outbox(now, operation_key="ambiguous-source-operation")
        outbox.kind = "pre_meeting"
        outbox.prepared_for_at = now - timedelta(minutes=1)
        outbox.interaction_id = interaction_id
        outbox.deduplication_key = f"delivery:pre:{interaction_id}:{'a' * 24}"
        outbox.href = f"/conversations/{interaction_id}#preparation"
        async with session_factory() as session:
            session.add_all(
                [
                    Interaction(
                        id=interaction_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_type="online_meeting",
                        lifecycle_status="planned",
                        title="Synthetic ambiguous meeting",
                        scheduled_start_at=now + timedelta(minutes=29),
                        scheduled_end_at=now + timedelta(minutes=59),
                        creation_origin="manual",
                        created_by_user_id=PRIMARY_USER_ID,
                    ),
                    _preference(morning_digest_enabled=False),
                    _connection(now, connector_key="microsoft_365"),
                    outbox,
                ]
            )
            await session.commit()
        transport = ScriptedTransport(
            [
                BriefingDeliveryError("provider_timeout_after_submit", retryable=True, uncertain=True),
                BriefingDeliveryResult("must-not-send"),
            ]
        )
        worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {"microsoft_365": transport},
            clock=lambda: now,
        )
        target = BriefingDeliveryTarget(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID)
        claim = await worker.claim_next(target, "worker-ambiguous-source")
        assert claim is not None
        await worker.execute_claimed(claim)
        ambiguous = await _row(session_factory, outbox.id)
        assert ambiguous.status == "failed"
        assert ambiguous.failure_code == "provider_outcome_unknown"

        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        async with session_factory() as session:
            await InteractionService(session, tenant).update_interaction(
                interaction_id,
                InteractionUpdate(
                    scheduled_start_at=now + timedelta(minutes=25),
                    scheduled_end_at=now + timedelta(minutes=55),
                ),
            )
        async with session_factory() as session:
            assert await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now) == 0
        async with session_factory() as session:
            scheduled_rows = list(
                (
                    await session.scalars(
                        select(ConversationBriefingOutbox).where(
                            ConversationBriefingOutbox.interaction_id == interaction_id,
                            ConversationBriefingOutbox.delivery_intent == "scheduled",
                        )
                    )
                ).all()
            )
        assert [row.id for row in scheduled_rows] == [outbox.id]

        replacement = _outbox(now, operation_key="ambiguous-replacement-operation")
        replacement.kind = "pre_meeting"
        replacement.prepared_for_at = now - timedelta(minutes=5)
        replacement.interaction_id = interaction_id
        replacement.deduplication_key = f"delivery:pre:{interaction_id}:{'c' * 24}"
        replacement.href = f"/conversations/{interaction_id}#preparation"
        async with session_factory() as session:
            session.add(replacement)
            await session.commit()
        replacement_claim = await worker.claim_next(target, "worker-ambiguous-replacement")
        assert replacement_claim is not None
        await worker.execute_claimed(replacement_claim)
        blocked = await _row(session_factory, replacement.id)
        assert blocked.status == "cancelled"
        assert blocked.failure_code == "delivery_logical_fence_unresolved"
        assert len(transport.messages) == 1
        await engine.dispose()

    asyncio.run(scenario())


def test_expired_claim_requeues_only_when_submission_never_started() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        safe_retry = _outbox(now)
        safe_retry.status = "sending"
        safe_retry.worker_id = "dead-before-submit"
        safe_retry.lease_expires_at = now - timedelta(seconds=1)
        safe_retry.attempt_count = 1
        ambiguous = _outbox(now)
        ambiguous.status = "sending"
        ambiguous.worker_id = "dead-after-submit"
        ambiguous.lease_expires_at = now - timedelta(seconds=1)
        ambiguous.submission_started_at = now - timedelta(seconds=2)
        ambiguous.attempt_count = 1
        async with session_factory() as session:
            session.add_all([safe_retry, ambiguous])
            await session.commit()
        worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {},
            clock=lambda: now,
        )
        target = (await worker.discover_eligible_targets())[0]

        assert await worker.recover_expired_claims(target) == 2
        recovered = await _row(session_factory, safe_retry.id)
        unknown = await _row(session_factory, ambiguous.id)
        assert recovered.status == "queued"
        assert recovered.attempt_count == 0
        assert recovered.failure_code == "worker_lease_recovered"
        assert unknown.status == "failed"
        assert unknown.failure_code == "delivery_outcome_unknown"
        await engine.dispose()

    asyncio.run(scenario())


def test_preference_discovery_rotates_after_a_full_page_is_schedule_marked() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        synthetic_user_ids = [uuid4() for _ in range(DISCOVERY_LIMIT + 1)]

        try:
            async with session_factory() as session:
                session.add_all(
                    [
                        User(
                            id=user_id,
                            external_auth_id=f"briefing-rotation-{index}",
                            email=f"briefing-rotation-{index}@example.test",
                            display_name=f"Rotation owner {index}",
                        )
                        for index, user_id in enumerate(synthetic_user_ids)
                    ]
                )
                session.add_all(
                    [
                        OrganisationMembership(
                            organisation_id=PRIMARY_ORGANISATION_ID,
                            user_id=user_id,
                            role="member",
                        )
                        for user_id in synthetic_user_ids
                    ]
                )
                session.add_all(
                    [
                        ConversationDeliveryPreference(
                            id=uuid4(),
                            organisation_id=PRIMARY_ORGANISATION_ID,
                            user_id=user_id,
                            timezone="UTC",
                            morning_digest_enabled=False,
                            morning_digest_time="07:30",
                            pre_meeting_enabled=True,
                            pre_meeting_minutes=30,
                            lock_version=1,
                        )
                        for user_id in synthetic_user_ids
                    ]
                )
                await session.commit()

            worker = BriefingDeliveryWorkerService(
                session_factory,
                _settings(),
                {},
                clock=lambda: now,
            )
            first_page = await worker.discover_eligible_targets()
            assert len(first_page) == DISCOVERY_LIMIT
            first_page_ids = {target.user_id for target in first_page}
            undiscovered_ids = set(synthetic_user_ids) - first_page_ids
            assert len(undiscovered_ids) == 1

            for target in first_page:
                assert await worker.schedule_target(target) == 0

            next_page = await worker.discover_eligible_targets()
            assert undiscovered_ids <= {target.user_id for target in next_page}
            async with session_factory() as session:
                next_owner_discovered_at = await session.scalar(
                    select(ConversationDeliveryPreference.last_scheduler_discovered_at).where(
                        ConversationDeliveryPreference.user_id == next(iter(undiscovered_ids))
                    )
                )
                first_owner_discovered_at = await session.scalar(
                    select(ConversationDeliveryPreference.last_scheduler_discovered_at).where(
                        ConversationDeliveryPreference.user_id == first_page[0].user_id
                    )
                )
            assert next_owner_discovered_at is None
            assert first_owner_discovered_at is not None
        finally:
            async with session_factory() as session:
                matching_users = select(User.id).where(User.external_auth_id.like("briefing-rotation-%"))
                await session.execute(
                    delete(ConversationBriefingOutbox).where(ConversationBriefingOutbox.user_id.in_(matching_users))
                )
                await session.execute(
                    delete(ConversationDeliveryPreference).where(
                        ConversationDeliveryPreference.user_id.in_(matching_users)
                    )
                )
                await session.execute(
                    delete(OrganisationMembership).where(OrganisationMembership.user_id.in_(matching_users))
                )
                await session.execute(delete(User).where(User.external_auth_id.like("briefing-rotation-%")))
                await session.commit()
            await engine.dispose()

    asyncio.run(scenario())


def test_pre_meeting_materialisation_progresses_beyond_five_hundred_interactions() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        interaction_ids = sorted((uuid4() for _ in range(501)), key=str)
        already_materialised_ids = interaction_ids[:500]
        remaining_id = interaction_ids[500]

        async with session_factory() as session:
            session.add(_preference(morning_digest_enabled=False))
            session.add_all(
                [
                    Interaction(
                        id=interaction_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_type="online_meeting",
                        lifecycle_status="planned",
                        title=f"Synthetic paged conversation {index}",
                        scheduled_start_at=now + timedelta(days=1, seconds=index),
                        scheduled_end_at=now + timedelta(days=1, hours=1, seconds=index),
                        creation_origin="manual",
                        created_by_user_id=PRIMARY_USER_ID,
                        created_at=now - timedelta(hours=1),
                        updated_at=now - timedelta(hours=1),
                    )
                    for index, interaction_id in enumerate(interaction_ids)
                ]
            )
            rows: list[ConversationBriefingOutbox] = []
            for index, interaction_id in enumerate(already_materialised_ids):
                row = _outbox(now, operation_key=f"{index:064x}")
                row.interaction_id = interaction_id
                row.kind = "pre_meeting"
                row.deduplication_key = f"delivery:pre:{interaction_id}:seed"
                row.href = f"/conversations/{interaction_id}#preparation"
                rows.append(row)
            session.add_all(rows)
            await session.commit()

        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        async with session_factory() as session:
            created = await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now)
        assert created == 1

        async with session_factory() as session:
            scheduled_ids = set(
                (
                    await session.scalars(
                        select(ConversationBriefingOutbox.interaction_id).where(
                            ConversationBriefingOutbox.delivery_intent == "scheduled",
                            ConversationBriefingOutbox.kind == "pre_meeting",
                        )
                    )
                ).all()
            )
        assert len(scheduled_ids) == 501
        assert scheduled_ids == set(interaction_ids)
        assert remaining_id in scheduled_ids
        await engine.dispose()

    asyncio.run(scenario())


def test_started_effective_provider_meeting_is_cancelled_before_transport() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        interaction_id = uuid4()
        connection = _connection(now, connector_key="microsoft_365")
        outbox = _outbox(now)
        outbox.interaction_id = interaction_id
        outbox.kind = "pre_meeting"
        outbox.prepared_for_at = now - timedelta(minutes=30)
        outbox.deduplication_key = f"delivery:pre:{interaction_id}:{'a' * 24}"
        outbox.href = f"/conversations/{interaction_id}#preparation"

        async with session_factory() as session:
            session.add_all(
                [
                    Interaction(
                        id=interaction_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_type="online_meeting",
                        lifecycle_status="planned",
                        title="Provider meeting that has started",
                        scheduled_start_at=now + timedelta(hours=1),
                        scheduled_end_at=now + timedelta(hours=2),
                        creation_origin="manual",
                        created_by_user_id=PRIMARY_USER_ID,
                    ),
                    connection,
                    ProviderCalendarEvent(
                        id=uuid4(),
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        connection_id=connection.id,
                        provider_key="microsoft_365",
                        provider_event_id="briefing-started-effective-provider-event",
                        title="Provider meeting that has started",
                        start_at=now,
                        end_at=now + timedelta(hours=1),
                        provider_timezone="UTC",
                        attendee_emails_json=[],
                        sensitivity="normal",
                        state="active",
                        match_state="matched",
                        interaction_id=interaction_id,
                        last_synced_at=now,
                    ),
                    _preference(morning_digest_enabled=False),
                    outbox,
                ]
            )
            await session.commit()

        transport = ScriptedTransport([BriefingDeliveryResult("must-not-send")])
        worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {"microsoft_365": transport},
            clock=lambda: now,
        )
        target = BriefingDeliveryTarget(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID)
        claim = await worker.claim_next(target, "started-meeting-worker")
        assert claim is not None
        await worker.execute_claimed(claim)

        cancelled = await _row(session_factory, outbox.id)
        assert cancelled.status == "cancelled"
        assert cancelled.failure_code == "delivery_source_started"
        assert cancelled.submission_started_at is None
        assert transport.messages == []
        await engine.dispose()

    asyncio.run(scenario())


def test_timezone_change_rematerialises_an_exact_fresh_morning_envelope() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        async with session_factory() as session:
            session.add(_preference(pre_meeting_enabled=False))
            await session.commit()
        async with session_factory() as session:
            assert await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now) == 1
            original = await session.scalar(
                select(ConversationBriefingOutbox).where(
                    ConversationBriefingOutbox.kind == "morning_digest",
                    ConversationBriefingOutbox.delivery_intent == "scheduled",
                )
            )
            assert original is not None
            original_id = original.id
            original_body = original.body_text
            original_fingerprint = original.source_fingerprint
            original_key = original.deduplication_key
            original_operation_key = original.operation_key

        interaction_id = uuid4()
        async with session_factory() as session:
            session.add(
                Interaction(
                    id=interaction_id,
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    interaction_type="online_meeting",
                    lifecycle_status="planned",
                    title="New timezone briefing conversation",
                    scheduled_start_at=now + timedelta(minutes=30),
                    scheduled_end_at=now + timedelta(hours=1),
                    creation_origin="manual",
                    created_by_user_id=PRIMARY_USER_ID,
                )
            )
            await session.commit()
        async with session_factory() as session:
            await RevenueOSDailyService(session, tenant, _settings()).save_delivery_preferences(
                DeliveryPreferenceUpdate(
                    expected_lock_version=1,
                    timezone="Australia/Sydney",
                    morning_digest_enabled=True,
                    morning_digest_time="20:00",
                    pre_meeting_enabled=False,
                    pre_meeting_minutes=30,
                )
            )
        async with session_factory() as session:
            assert await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now) == 1
            rows = list(
                (
                    await session.scalars(
                        select(ConversationBriefingOutbox).where(
                            ConversationBriefingOutbox.kind == "morning_digest",
                            ConversationBriefingOutbox.delivery_intent == "scheduled",
                        )
                    )
                ).all()
            )

        assert len(rows) == 2
        superseded = next(row for row in rows if row.id == original_id)
        replacement = next(row for row in rows if row.id != original_id)
        assert superseded.status == "superseded"
        assert replacement.status == "queued"
        assert replacement.delivery_timezone == "Australia/Sydney"
        assert replacement.body_text != original_body
        assert "New timezone briefing conversation" in replacement.body_text
        assert replacement.source_fingerprint != original_fingerprint
        assert replacement.deduplication_key != original_key
        assert replacement.operation_key != original_operation_key
        assert len(original_operation_key) == 64
        assert len(replacement.operation_key) == 64
        await engine.dispose()

    asyncio.run(scenario())


def test_submission_heartbeat_keeps_a_live_blocked_transport_out_of_recovery() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        current = [now]
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        outbox = _outbox(now, operation_key="heartbeat-operation")
        async with session_factory() as session:
            session.add_all([outbox, _connection(now, connector_key="google_workspace"), _preference()])
            await session.commit()

        transport = BlockingTransport(BriefingDeliveryResult("heartbeat-accepted"))
        worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(
                worker_lease_duration_seconds=10,
                worker_heartbeat_interval_seconds=1,
            ),
            {"google_workspace": transport},
            clock=lambda: current[0],
        )
        target = BriefingDeliveryTarget(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID)
        claim = await worker.claim_next(target, "heartbeat-worker")
        assert claim is not None
        execution = asyncio.create_task(worker.execute_claimed(claim))
        await asyncio.wait_for(transport.started.wait(), timeout=2)

        try:
            original = await _row(session_factory, outbox.id)
            assert original.lease_expires_at is not None
            original_lease = original.lease_expires_at.replace(tzinfo=UTC)
            current[0] = now + timedelta(seconds=11)
            assert original_lease < current[0]

            refreshed: ConversationBriefingOutbox | None = None
            for _ in range(30):
                await asyncio.sleep(0.1)
                candidate = await _row(session_factory, outbox.id)
                if (
                    candidate.lease_expires_at is not None
                    and candidate.lease_expires_at.replace(tzinfo=UTC) > current[0]
                ):
                    refreshed = candidate
                    break
            assert refreshed is not None
            assert await worker.recover_expired_claims(target) == 0
            retained = await _row(session_factory, outbox.id)
            assert retained.status == "sending"
            assert retained.failure_code is None
        finally:
            transport.release.set()
            await execution

        sent = await _row(session_factory, outbox.id)
        assert sent.status == "sent"
        assert sent.provider_message_id == "heartbeat-accepted"
        await engine.dispose()

    asyncio.run(scenario())


def test_inactive_provider_calendar_connections_do_not_authorise_materialisation() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        revoked_connection = _connection(now, connector_key="google_workspace", status="revoked")
        reauth_connection = _connection(
            now,
            connector_key="microsoft_365",
            status="reauthorisation_required",
        )
        provider_cases = (
            (uuid4(), revoked_connection, "google_workspace", "revoked"),
            (uuid4(), reauth_connection, "microsoft_365", "reauthorisation-required"),
        )

        async with session_factory() as session:
            session.add(_preference(morning_digest_enabled=False))
            session.add_all([revoked_connection, reauth_connection])
            for index, (interaction_id, connection, provider_key, suffix) in enumerate(provider_cases):
                session.add(
                    Interaction(
                        id=interaction_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_type="online_meeting",
                        lifecycle_status="planned",
                        title=f"Inactive provider authority {suffix}",
                        scheduled_start_at=None,
                        scheduled_end_at=None,
                        creation_origin="manual",
                        created_by_user_id=PRIMARY_USER_ID,
                    )
                )
                session.add(
                    ProviderCalendarEvent(
                        id=uuid4(),
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        connection_id=connection.id,
                        provider_key=provider_key,
                        provider_event_id=f"inactive-provider-materialisation-{suffix}",
                        title=f"Inactive provider authority {suffix}",
                        start_at=now + timedelta(days=1, minutes=index),
                        end_at=now + timedelta(days=1, hours=1, minutes=index),
                        provider_timezone="UTC",
                        attendee_emails_json=[],
                        sensitivity="normal",
                        state="active",
                        match_state="matched",
                        interaction_id=interaction_id,
                        last_synced_at=now,
                    )
                )
            await session.commit()

        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        async with session_factory() as session:
            created = await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now)
        assert created == 0
        async with session_factory() as session:
            assert (
                await session.scalar(
                    select(ConversationBriefingOutbox.id).where(
                        ConversationBriefingOutbox.delivery_intent == "scheduled",
                        ConversationBriefingOutbox.kind == "pre_meeting",
                    )
                )
            ) is None
        await engine.dispose()

    asyncio.run(scenario())


def test_generated_preview_and_delivery_operation_keys_use_the_64_character_limit() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        async with session_factory() as session:
            session.add(_preference(pre_meeting_enabled=False))
            await session.commit()
        async with session_factory() as session:
            service = RevenueOSDailyService(session, tenant, _settings())
            preview = await service.prepare_briefing_preview(
                BriefingPreviewRequest(kind="morning_digest"),
                now=now,
            )
        async with session_factory() as session:
            assert await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now) == 1
            rows = list((await session.scalars(select(ConversationBriefingOutbox))).all())

        operation_keys = {row.delivery_intent: row.operation_key for row in rows}
        assert set(operation_keys) == {"preview", "scheduled"}
        assert preview.id in {row.id for row in rows}
        assert operation_keys["preview"].startswith("preview_")
        assert operation_keys["scheduled"].startswith("delivery_")
        assert all(len(operation_key) == 64 for operation_key in operation_keys.values())
        assert all(len(operation_key) <= 64 for operation_key in operation_keys.values())
        await engine.dispose()

    asyncio.run(scenario())


def test_identical_preference_save_and_interaction_schedule_patch_preserve_retry_state() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        scheduled_start = now + timedelta(hours=2)
        scheduled_end = scheduled_start + timedelta(hours=1)
        interaction_id = uuid4()
        preference_outbox = _outbox(now)
        preference_outbox.status = "queued"
        preference_outbox.attempt_count = 2
        preference_outbox.next_attempt_at = now + timedelta(minutes=17)
        preference_outbox.failure_code = "provider_busy"
        interaction_outbox = _outbox(now)
        interaction_outbox.kind = "pre_meeting"
        interaction_outbox.interaction_id = interaction_id
        interaction_outbox.deduplication_key = f"delivery:pre:{interaction_id}:{'a' * 24}"
        interaction_outbox.href = f"/conversations/{interaction_id}#preparation"
        interaction_outbox.status = "failed"
        interaction_outbox.attempt_count = 2
        interaction_outbox.next_attempt_at = now + timedelta(minutes=19)
        interaction_outbox.failed_at = now
        interaction_outbox.failure_code = "provider_busy"
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        async with session_factory() as session:
            session.add_all(
                [
                    _preference(),
                    preference_outbox,
                    Interaction(
                        id=interaction_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_type="manual_interaction",
                        lifecycle_status="planned",
                        title="No-op schedule source",
                        scheduled_start_at=scheduled_start,
                        scheduled_end_at=scheduled_end,
                        timezone="UTC",
                        creation_origin="manual",
                        created_by_user_id=PRIMARY_USER_ID,
                    ),
                    interaction_outbox,
                ]
            )
            await session.commit()

        async with session_factory() as session:
            await RevenueOSDailyService(session, tenant, _settings()).save_delivery_preferences(
                DeliveryPreferenceUpdate(
                    expected_lock_version=1,
                    timezone="UTC",
                    morning_digest_enabled=True,
                    morning_digest_time="07:30",
                    pre_meeting_enabled=True,
                    pre_meeting_minutes=30,
                )
            )
        retained_preference = await _row(session_factory, preference_outbox.id)
        assert retained_preference.status == "queued"
        assert retained_preference.attempt_count == 2
        assert retained_preference.next_attempt_at is not None
        assert retained_preference.next_attempt_at.replace(tzinfo=UTC) == now + timedelta(minutes=17)
        assert retained_preference.failure_code == "provider_busy"

        async with session_factory() as session:
            await RevenueOSDailyService(session, tenant, _settings()).save_delivery_preferences(
                DeliveryPreferenceUpdate(
                    expected_lock_version=2,
                    timezone="UTC",
                    morning_digest_enabled=True,
                    morning_digest_time="08:15",
                    pre_meeting_enabled=True,
                    pre_meeting_minutes=30,
                )
            )
        changed_morning = await _row(session_factory, preference_outbox.id)
        unaffected_pre_meeting = await _row(session_factory, interaction_outbox.id)
        assert changed_morning.status == "superseded"
        assert unaffected_pre_meeting.status == "failed"
        assert unaffected_pre_meeting.attempt_count == 2
        assert unaffected_pre_meeting.failure_code == "provider_busy"

        async with session_factory() as session:
            await InteractionService(session, tenant).update_interaction(
                interaction_id,
                InteractionUpdate(
                    scheduled_start_at=scheduled_start,
                    scheduled_end_at=scheduled_end + timedelta(hours=1),
                    timezone="UTC",
                ),
            )
        retained_interaction = await _row(session_factory, interaction_outbox.id)
        assert retained_interaction.status == "failed"
        assert retained_interaction.attempt_count == 2
        assert retained_interaction.next_attempt_at is not None
        assert retained_interaction.next_attempt_at.replace(tzinfo=UTC) == now + timedelta(minutes=19)
        assert retained_interaction.failed_at is not None
        assert retained_interaction.failure_code == "provider_busy"
        await engine.dispose()

    asyncio.run(scenario())


def test_provider_schedule_ignores_fallback_start_changes_without_resetting_retry_state() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        interaction_id = uuid4()
        provider_start = now + timedelta(hours=2)
        connection = _connection(now, connector_key="microsoft_365")
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        async with session_factory() as session:
            session.add_all(
                [
                    _preference(morning_digest_enabled=False),
                    connection,
                    Interaction(
                        id=interaction_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_type="online_meeting",
                        lifecycle_status="planned",
                        title="Provider-authoritative schedule",
                        scheduled_start_at=now + timedelta(hours=1),
                        scheduled_end_at=now + timedelta(hours=6),
                        timezone="UTC",
                        creation_origin="manual",
                        created_by_user_id=PRIMARY_USER_ID,
                    ),
                    ProviderCalendarEvent(
                        id=uuid4(),
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        connection_id=connection.id,
                        provider_key="microsoft_365",
                        provider_event_id="provider-authoritative-retry",
                        title="Provider-authoritative schedule",
                        start_at=provider_start,
                        end_at=provider_start + timedelta(hours=1),
                        provider_timezone="UTC",
                        attendee_emails_json=[],
                        sensitivity="normal",
                        state="active",
                        match_state="matched",
                        interaction_id=interaction_id,
                        last_synced_at=now,
                    ),
                ]
            )
            await session.commit()
        async with session_factory() as session:
            assert await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now) == 1
            row = await session.scalar(
                select(ConversationBriefingOutbox).where(
                    ConversationBriefingOutbox.interaction_id == interaction_id,
                    ConversationBriefingOutbox.delivery_intent == "scheduled",
                )
            )
            assert row is not None
            row_id = row.id
            row.status = "failed"
            row.attempt_count = 2
            row.next_attempt_at = now + timedelta(minutes=23)
            row.failed_at = now
            row.failure_code = "provider_busy"
            await session.commit()

        async with session_factory() as session:
            await InteractionService(session, tenant).update_interaction(
                interaction_id,
                InteractionUpdate(scheduled_start_at=now + timedelta(hours=4)),
            )
            interaction = await session.get(Interaction, interaction_id)
            assert interaction is not None
            changed_at = interaction.updated_at.replace(tzinfo=UTC)

        retained = await _row(session_factory, row_id)
        assert retained.status == "failed"
        assert retained.attempt_count == 2
        assert retained.failure_code == "provider_busy"
        assert retained.next_attempt_at is not None
        assert retained.next_attempt_at.replace(tzinfo=UTC) == now + timedelta(minutes=23)

        async with session_factory() as session:
            assert await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now) == 0
        recomputed = await _row(session_factory, row_id)
        assert recomputed.status == "failed"
        assert recomputed.attempt_count == 2
        assert recomputed.failure_code == "provider_busy"
        assert recomputed.next_attempt_at is not None
        assert recomputed.next_attempt_at.replace(tzinfo=UTC) == now + timedelta(minutes=23)
        assert recomputed.prepared_for_at.replace(tzinfo=UTC) == provider_start - timedelta(minutes=30)
        assert recomputed.source_observed_at.replace(tzinfo=UTC) >= changed_at
        await engine.dispose()

    asyncio.run(scenario())


def test_restored_mailbox_authority_accepts_an_enabled_send_capable_replacement() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        interaction_id = uuid4()
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        connection = _connection(now, connector_key="google_workspace")
        async with session_factory() as session:
            session.add_all(
                [
                    _preference(morning_digest_enabled=False),
                    connection,
                    Interaction(
                        id=interaction_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_type="manual_interaction",
                        lifecycle_status="planned",
                        title="Authority restoration",
                        scheduled_start_at=now + timedelta(hours=2),
                        scheduled_end_at=now + timedelta(hours=3),
                        timezone="UTC",
                        creation_origin="manual",
                        created_by_user_id=PRIMARY_USER_ID,
                    ),
                ]
            )
            await session.commit()
        async with session_factory() as session:
            assert (
                await RevenueOSDailyService(
                    session,
                    tenant,
                    _settings(),
                    delivery_connector_keys={"google_workspace"},
                ).schedule_delivery_briefings(now=now)
                == 1
            )
            row = await session.scalar(
                select(ConversationBriefingOutbox).where(
                    ConversationBriefingOutbox.interaction_id == interaction_id,
                    ConversationBriefingOutbox.delivery_intent == "scheduled",
                )
            )
            assert row is not None
            row_id = row.id
            row.status = "cancelled"
            row.attempt_count = 2
            row.failure_code = "delivery_connection_reauthorisation_required"
            row.connection_id = connection.id
            connection_row = await session.get(IntegrationConnection, connection.id)
            assert connection_row is not None
            connection_row.connection_status = "reauthorisation_required"
            connection_row.metadata_version += 1
            await session.commit()

        async with session_factory() as session:
            assert await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now) == 0
        still_cancelled = await _row(session_factory, row_id)
        assert still_cancelled.status == "cancelled"
        assert still_cancelled.attempt_count == 2

        async with session_factory() as session:
            connection_row = await session.get(IntegrationConnection, connection.id)
            assert connection_row is not None
            connection_row.connection_status = "active"
            connection_row.capability_state_json = []
            connection_row.metadata_version += 1
            await session.commit()
        target = BriefingDeliveryTarget(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID)
        google_worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {"google_workspace": ScriptedTransport([])},
            clock=lambda: now,
        )
        assert await google_worker.schedule_target(target) == 0
        async with session_factory() as session:
            connection_row = await session.get(IntegrationConnection, connection.id)
            assert connection_row is not None
            connection_row.capability_state_json = ["send_email"]
            await session.commit()
        microsoft_worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {"microsoft_365": ScriptedTransport([])},
            clock=lambda: now,
        )
        assert await microsoft_worker.schedule_target(target) == 0
        still_cancelled = await _row(session_factory, row_id)
        assert still_cancelled.status == "cancelled"
        replacement = _connection(now, connector_key="microsoft_365")
        async with session_factory() as session:
            failed_connection = await session.get(IntegrationConnection, connection.id)
            assert failed_connection is not None
            failed_connection.connection_status = "revoked"
            failed_connection.revoked_at = now
            failed_connection.metadata_version += 1
            session.add(replacement)
            await session.commit()
        # The failed row retains the old Google connection until reactivation,
        # but the worker may safely restore it through a different configured
        # mailbox with equivalent active send authority.
        assert await microsoft_worker.schedule_target(target) == 1
        reactivated = await _row(session_factory, row_id)
        assert reactivated.status == "queued"
        assert reactivated.attempt_count == 0
        assert reactivated.failure_code is None
        assert reactivated.connection_id is None
        await engine.dispose()

    asyncio.run(scenario())


def test_newer_brief_refreshes_a_queued_pre_meeting_envelope() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        interaction_id = uuid4()
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        async with session_factory() as session:
            session.add_all(
                [
                    _preference(morning_digest_enabled=False),
                    Interaction(
                        id=interaction_id,
                        organisation_id=PRIMARY_ORGANISATION_ID,
                        interaction_type="manual_interaction",
                        lifecycle_status="planned",
                        title="Queued brief refresh",
                        scheduled_start_at=now + timedelta(hours=2),
                        scheduled_end_at=now + timedelta(hours=3),
                        timezone="UTC",
                        creation_origin="manual",
                        created_by_user_id=PRIMARY_USER_ID,
                    ),
                ]
            )
            await session.commit()
        async with session_factory() as session:
            assert await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now) == 1
            original = await session.scalar(
                select(ConversationBriefingOutbox).where(
                    ConversationBriefingOutbox.interaction_id == interaction_id,
                    ConversationBriefingOutbox.delivery_intent == "scheduled",
                )
            )
            assert original is not None
            original_id = original.id
            original_fingerprint = original.source_fingerprint
            original_source_observed_at = original.source_observed_at.replace(tzinfo=UTC)

        brief_content = {
            "interaction_id": str(interaction_id),
            "interaction_type": "manual_interaction",
            "brief_version": 1,
            "headline": "Validate the next decision.",
            "account_context": "A newly generated preparation brief is available.",
            "recent_changes": [],
            "objectives": [
                {
                    "objective": "Validate the next decision.",
                    "priority": "high",
                    "reason": "The conversation should end with clear ownership.",
                }
            ],
            "questions_to_ask": [
                {
                    "question": "Who owns the next decision?",
                    "purpose": "Confirm responsibility.",
                    "priority": "high",
                }
            ],
            "stakeholder_focus": [],
            "open_commitments": [],
            "risks_to_watch": [],
            "success_criteria": ["Decision ownership is explicit."],
            "interaction_guidance": "Confirm the decision owner before closing.",
            "confidence": 0.8,
        }
        brief_created_at = max(
            datetime.now(UTC),
            original_source_observed_at + timedelta(microseconds=1),
        )
        async with session_factory() as session:
            session.add(
                PreInteractionBrief(
                    id=uuid4(),
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    interaction_id=interaction_id,
                    company_id=None,
                    opportunity_id=None,
                    source_context_fingerprint="d" * 64,
                    brief_version=1,
                    schema_version=1,
                    status="completed",
                    content_json=brief_content,
                    source_references_json=[],
                    created_by_user_id=PRIMARY_USER_ID,
                    created_at=brief_created_at,
                )
            )
            stale_outbox = await session.get(ConversationBriefingOutbox, original_id)
            assert stale_outbox is not None
            # A later worker retry is an operational write only. It must not
            # hide the fact that this body predates the new brief.
            stale_outbox.attempt_count = 1
            stale_outbox.next_attempt_at = now + timedelta(minutes=20)
            stale_outbox.failure_code = "provider_busy"
            stale_outbox.updated_at = brief_created_at + timedelta(minutes=1)
            await session.commit()
        stale = await _row(session_factory, original_id)
        assert stale.updated_at.replace(tzinfo=UTC) > brief_created_at
        assert stale.source_observed_at.replace(tzinfo=UTC) < brief_created_at
        async with session_factory() as session:
            assert await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now) == 1
        async with session_factory() as session:
            rows = list(
                (
                    await session.scalars(
                        select(ConversationBriefingOutbox).where(
                            ConversationBriefingOutbox.interaction_id == interaction_id,
                            ConversationBriefingOutbox.delivery_intent == "scheduled",
                        )
                    )
                ).all()
            )
        assert len(rows) == 2
        original = next(row for row in rows if row.id == original_id)
        replacement = next(row for row in rows if row.id != original_id)
        assert original.status == "superseded"
        assert replacement.status == "queued"
        assert replacement.source_fingerprint != original_fingerprint
        assert replacement.source_observed_at.replace(tzinfo=UTC) >= brief_created_at
        assert "Validate the next decision." in replacement.body_text
        await engine.dispose()

    asyncio.run(scenario())


def test_changed_daily_content_refreshes_the_queued_morning_envelope() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        async with session_factory() as session:
            session.add(_preference(pre_meeting_enabled=False))
            await session.commit()
        async with session_factory() as session:
            assert await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now) == 1
            original = await session.scalar(
                select(ConversationBriefingOutbox).where(
                    ConversationBriefingOutbox.kind == "morning_digest",
                    ConversationBriefingOutbox.delivery_intent == "scheduled",
                )
            )
            assert original is not None
            original_id = original.id
            original_fingerprint = original.source_fingerprint
        async with session_factory() as session:
            session.add(
                Interaction(
                    id=uuid4(),
                    organisation_id=PRIMARY_ORGANISATION_ID,
                    interaction_type="manual_interaction",
                    lifecycle_status="planned",
                    title="New daily content boundary",
                    scheduled_start_at=now + timedelta(hours=1),
                    scheduled_end_at=now + timedelta(hours=2),
                    timezone="UTC",
                    creation_origin="manual",
                    created_by_user_id=PRIMARY_USER_ID,
                )
            )
            await session.commit()
        async with session_factory() as session:
            assert await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now) == 1
        async with session_factory() as session:
            rows = list(
                (
                    await session.scalars(
                        select(ConversationBriefingOutbox).where(
                            ConversationBriefingOutbox.kind == "morning_digest",
                            ConversationBriefingOutbox.delivery_intent == "scheduled",
                        )
                    )
                ).all()
            )
        assert len(rows) == 2
        original = next(row for row in rows if row.id == original_id)
        replacement = next(row for row in rows if row.id != original_id)
        assert original.status == "superseded"
        assert replacement.status == "queued"
        assert replacement.source_fingerprint != original_fingerprint
        assert "New daily content boundary" in replacement.body_text
        await engine.dispose()

    asyncio.run(scenario())


def test_changed_schedule_supersedes_safe_terminal_rows_but_preserves_delivery_fences() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        tenant = TenantContext(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID, "admin")
        sources: list[tuple[UUID, ConversationBriefingOutbox]] = []
        states = (
            ("failed", "provider_busy"),
            ("cancelled", "delivery_authority_unavailable"),
            ("sent", None),
            ("failed", "provider_outcome_unknown"),
        )
        async with session_factory() as session:
            session.add(_preference(morning_digest_enabled=False))
            for index, (status, failure_code) in enumerate(states):
                interaction_id = uuid4()
                start = now + timedelta(hours=2, minutes=index)
                outbox = _outbox(now)
                outbox.kind = "pre_meeting"
                outbox.interaction_id = interaction_id
                outbox.deduplication_key = f"delivery:pre:{interaction_id}:{index:024d}"
                outbox.href = f"/conversations/{interaction_id}#preparation"
                outbox.prepared_for_at = start - timedelta(minutes=30)
                outbox.status = status
                outbox.attempt_count = 2
                outbox.failure_code = failure_code
                outbox.failed_at = now if status == "failed" else None
                outbox.sent_at = now if status == "sent" else None
                outbox.provider_message_id = "accepted" if status == "sent" else None
                sources.append((interaction_id, outbox))
                session.add_all(
                    [
                        Interaction(
                            id=interaction_id,
                            organisation_id=PRIMARY_ORGANISATION_ID,
                            interaction_type="manual_interaction",
                            lifecycle_status="planned",
                            title=f"Terminal source {index}",
                            scheduled_start_at=start,
                            scheduled_end_at=start + timedelta(hours=1),
                            timezone="UTC",
                            creation_origin="manual",
                            created_by_user_id=PRIMARY_USER_ID,
                        ),
                        outbox,
                    ]
                )
            await session.commit()

        for index, (interaction_id, _) in enumerate(sources):
            replacement_start = now + timedelta(hours=3, minutes=index)
            async with session_factory() as session:
                await InteractionService(session, tenant).update_interaction(
                    interaction_id,
                    InteractionUpdate(
                        scheduled_start_at=replacement_start,
                        scheduled_end_at=replacement_start + timedelta(hours=1),
                    ),
                )

        safe_failed = await _row(session_factory, sources[0][1].id)
        worker_cancelled = await _row(session_factory, sources[1][1].id)
        sent = await _row(session_factory, sources[2][1].id)
        ambiguous = await _row(session_factory, sources[3][1].id)
        assert safe_failed.status == "superseded"
        assert worker_cancelled.status == "superseded"
        assert sent.status == "sent"
        assert ambiguous.status == "failed"
        assert ambiguous.failure_code == "provider_outcome_unknown"

        async with session_factory() as session:
            assert await RevenueOSDailyService(session, tenant, _settings()).schedule_delivery_briefings(now=now) == 2
        async with session_factory() as session:
            rows = list(
                (
                    await session.scalars(
                        select(ConversationBriefingOutbox).where(
                            ConversationBriefingOutbox.delivery_intent == "scheduled",
                            ConversationBriefingOutbox.kind == "pre_meeting",
                        )
                    )
                ).all()
            )
        assert len(rows) == 6
        replacements = [row for row in rows if row.id not in {source[1].id for source in sources}]
        assert {row.interaction_id for row in replacements} == {sources[0][0], sources[1][0]}
        assert all(row.status == "queued" for row in replacements)
        assert all(
            row.source_fingerprint != source.source_fingerprint
            for row in replacements
            for interaction_id, source in sources[:2]
            if row.interaction_id == interaction_id
        )
        await engine.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("connector_key", "error_code"),
    [
        ("google_workspace", "connection_reauthorisation_required"),
        ("microsoft_365", "connection_reauthorisation_required"),
    ],
)
def test_delivery_reauthorisation_error_updates_connection_and_cancels_without_retry(
    connector_key: str,
    error_code: str,
) -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        outbox = _outbox(now)
        connection = _connection(now, connector_key=connector_key)
        async with session_factory() as session:
            session.add_all([outbox, connection, _preference()])
            await session.commit()
        transport = ScriptedTransport([BriefingDeliveryError(error_code, retryable=True, retry_after_seconds=9)])
        worker = BriefingDeliveryWorkerService(
            session_factory,
            _settings(),
            {connector_key: transport},
            clock=lambda: now,
        )
        target = BriefingDeliveryTarget(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID)
        claim = await worker.claim_next(target, f"{connector_key}-reauthorisation")
        assert claim is not None
        await worker.execute_claimed(claim)

        retained = await _row(session_factory, outbox.id)
        assert retained.status == "cancelled"
        assert retained.failure_code == "delivery_connection_reauthorisation_required"
        assert retained.next_attempt_at is None
        assert len(transport.messages) == 1
        async with session_factory() as session:
            stored_connection = await session.get(IntegrationConnection, connection.id)
            assert stored_connection is not None
            assert stored_connection.connection_status == "reauthorisation_required"
            assert stored_connection.metadata_version == 2
        await engine.dispose()

    asyncio.run(scenario())


def test_scheduler_fairness_cursor_does_not_change_public_preference_updated_at() -> None:
    async def scenario() -> None:
        now = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
        original_updated_at = now - timedelta(days=3)
        preference = _preference(morning_digest_enabled=False, pre_meeting_enabled=False)
        preference.updated_at = original_updated_at
        engine = create_async_engine(TEST_DB_URL)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add(preference)
            await session.commit()
        worker = BriefingDeliveryWorkerService(session_factory, _settings(), {}, clock=lambda: now)

        assert await worker.schedule_target(BriefingDeliveryTarget(PRIMARY_ORGANISATION_ID, PRIMARY_USER_ID)) == 0
        async with session_factory() as session:
            retained = await session.get(ConversationDeliveryPreference, preference.id)
            assert retained is not None
            assert retained.last_scheduler_discovered_at is not None
            assert retained.last_scheduler_discovered_at.replace(tzinfo=UTC) == now
            assert retained.updated_at.replace(tzinfo=UTC) == original_updated_at
        await engine.dispose()

    asyncio.run(scenario())
