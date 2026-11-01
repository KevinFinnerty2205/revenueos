from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Protocol, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, case, or_, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.config import Settings
from revenueos.credential_store import EncryptedDatabaseCredentialStore
from revenueos.daily_repositories import DailyRepository
from revenueos.daily_services import (
    AMBIGUOUS_BRIEFING_DELIVERY_FAILURE_CODES,
    RevenueOSDailyService,
    enabled_briefing_delivery_connector_keys,
)
from revenueos.database import set_private_user_database_context, set_tenant_database_context
from revenueos.domain import ConnectorKey
from revenueos.google_workspace import GoogleAPIError, GoogleWorkspaceClient
from revenueos.integration_executors import ExecutorConnectionContext
from revenueos.microsoft_graph import MicrosoftAPIError, MicrosoftGraphClient
from revenueos.models import (
    ConversationBriefingOutbox,
    ConversationDeliveryPreference,
    IntegrationConnection,
    OrganisationMembership,
    User,
)
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.briefing_delivery")
DISCOVERY_LIMIT = 1000
REAUTHORISATION_REQUIRED_CODES = frozenset({"connection_reauthorisation_required", "provider_permission_denied"})


@dataclass(frozen=True)
class BriefingDeliveryTarget:
    organisation_id: UUID
    user_id: UUID


@dataclass(frozen=True)
class ClaimedBriefingDelivery:
    organisation_id: UUID
    user_id: UUID
    outbox_id: UUID
    worker_id: str


@dataclass(frozen=True)
class BriefingDeliveryMessage:
    outbox_id: UUID
    organisation_id: UUID
    user_id: UUID
    connection_id: UUID
    connector_key: str
    sender_name: str | None
    sender_email: str
    recipient_name: str | None
    recipient_email: str
    subject: str
    body: str
    href: str
    operation_key: str
    credential_reference: str | None = None
    external_account_id: str | None = None
    external_tenant_id: str | None = None


@dataclass(frozen=True)
class BriefingDeliveryResult:
    provider_message_id: str


class BriefingDeliveryError(Exception):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool = False,
        uncertain: bool = False,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.uncertain = uncertain
        self.retry_after_seconds = retry_after_seconds


class BriefingDeliveryTransport(Protocol):
    async def send(self, message: BriefingDeliveryMessage) -> BriefingDeliveryResult: ...


@dataclass(frozen=True)
class PreparedBriefingDelivery:
    message: BriefingDeliveryMessage
    transport: BriefingDeliveryTransport


class LocalBriefingDeliveryTransport:
    """Deterministic local/test transport. It never performs network I/O."""

    async def send(self, message: BriefingDeliveryMessage) -> BriefingDeliveryResult:
        identifier = hashlib.sha256(f"local-briefing:{message.operation_key}".encode()).hexdigest()[:32]
        return BriefingDeliveryResult(provider_message_id=f"local-{identifier}")


class GoogleBriefingDeliveryTransport:
    """Existing Gmail adapter behind the briefing transport contract."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings

    async def send(self, message: BriefingDeliveryMessage) -> BriefingDeliveryResult:
        try:
            async with self._session_factory() as session, session.begin():
                await set_tenant_database_context(session, message.organisation_id)
                await set_private_user_database_context(session, message.user_id)
                assert self._settings.connector_credential_master_key is not None
                store = EncryptedDatabaseCredentialStore(
                    session,
                    self._settings.connector_credential_master_key.get_secret_value(),
                )
                result = await GoogleWorkspaceClient(self._settings, store).send_mail(
                    _connection_context(message),
                    sender_name=message.sender_name,
                    sender_email=message.sender_email,
                    recipient_name=message.recipient_name,
                    recipient_email=message.recipient_email,
                    subject=message.subject,
                    body=message.body,
                    operation_key=message.operation_key,
                )
        except GoogleAPIError as exc:
            raise BriefingDeliveryError(
                exc.code,
                retryable=exc.retryable,
                uncertain=exc.uncertain,
                retry_after_seconds=exc.retry_after_seconds,
            ) from exc
        return BriefingDeliveryResult(provider_message_id=result.message_id)


class MicrosoftBriefingDeliveryTransport:
    """Existing Graph adapter behind the briefing transport contract."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings

    async def send(self, message: BriefingDeliveryMessage) -> BriefingDeliveryResult:
        try:
            async with self._session_factory() as session, session.begin():
                await set_tenant_database_context(session, message.organisation_id)
                await set_private_user_database_context(session, message.user_id)
                assert self._settings.connector_credential_master_key is not None
                store = EncryptedDatabaseCredentialStore(
                    session,
                    self._settings.connector_credential_master_key.get_secret_value(),
                )
                await MicrosoftGraphClient(self._settings, store).send_mail(
                    _connection_context(message),
                    sender_name=message.sender_name,
                    sender_email=message.sender_email,
                    recipient_name=message.recipient_name,
                    recipient_email=message.recipient_email,
                    subject=message.subject,
                    body=message.body,
                    operation_key=message.operation_key,
                )
        except MicrosoftAPIError as exc:
            raise BriefingDeliveryError(
                exc.code,
                retryable=exc.retryable,
                uncertain=exc.uncertain,
                retry_after_seconds=exc.retry_after_seconds,
            ) from exc
        # Graph's sendMail endpoint returns no provider identifier. The durable,
        # stable operation key is retained as the local acceptance receipt.
        return BriefingDeliveryResult(provider_message_id=f"microsoft-{message.operation_key}")


def configured_briefing_delivery_transports(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> dict[str, BriefingDeliveryTransport]:
    """Resolve the activation boundary without changing worker implementation.

    Local mode maps every supported mailbox authority to the deterministic
    no-network transport so connector-specific permission checks are exercised.
    Provider mode uses only already-enabled, approval-gated production adapters.
    """

    enabled_connector_keys = enabled_briefing_delivery_connector_keys(settings)
    if not enabled_connector_keys:
        return {}
    if settings.briefing_delivery_transport_mode == "local":
        local = LocalBriefingDeliveryTransport()
        return {connector_key: local for connector_key in enabled_connector_keys}
    transports: dict[str, BriefingDeliveryTransport] = {}
    if ConnectorKey.GOOGLE_WORKSPACE.value in enabled_connector_keys:
        transports[ConnectorKey.GOOGLE_WORKSPACE.value] = GoogleBriefingDeliveryTransport(
            session_factory,
            settings,
        )
    if ConnectorKey.MICROSOFT_365.value in enabled_connector_keys:
        transports[ConnectorKey.MICROSOFT_365.value] = MicrosoftBriefingDeliveryTransport(
            session_factory,
            settings,
        )
    return transports


def _connection_context(message: BriefingDeliveryMessage) -> ExecutorConnectionContext:
    return ExecutorConnectionContext(
        organisation_id=message.organisation_id,
        connection_id=message.connection_id,
        credential_reference=message.credential_reference,
        execution_mode="live",
        external_account_id=message.external_account_id,
        external_account_email=message.sender_email,
        external_tenant_id=message.external_tenant_id,
    )


class BriefingDeliveryWorkerService:
    """Leased, owner-scoped briefing delivery with fail-closed authority checks."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        transports: Mapping[str, BriefingDeliveryTransport],
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._transports = dict(transports)
        self._clock = clock or (lambda: datetime.now(UTC))

    async def run_once(self, worker_id: str) -> bool:
        if not self._settings.feature_briefing_delivery_enabled:
            return False
        processed = False
        for target in await self.discover_eligible_targets():
            scheduled = await self.schedule_target(target)
            recovered = await self.recover_expired_claims(target)
            claim = await self.claim_next(target, worker_id)
            processed = processed or bool(scheduled or recovered or claim)
            if claim is not None:
                await self.execute_claimed(claim)
        return processed

    async def discover_eligible_targets(self) -> list[BriefingDeliveryTarget]:
        now = self._now()
        async with self._session_factory() as session:
            if session.get_bind().dialect.name == "postgresql":
                rows = (
                    await session.execute(
                        text(
                            """SELECT organisation_id, user_id
                            FROM public.revenueos_briefing_worker_eligible_owners(
                                :eligible_at,
                                :result_limit
                            )"""
                        ),
                        {"eligible_at": now, "result_limit": DISCOVERY_LIMIT},
                    )
                ).all()
                return [BriefingDeliveryTarget(UUID(str(row[0])), UUID(str(row[1]))) for row in rows]
            outbox_rows = (
                await session.execute(
                    select(
                        ConversationBriefingOutbox.organisation_id,
                        ConversationBriefingOutbox.user_id,
                    )
                    .where(
                        or_(
                            and_(
                                ConversationBriefingOutbox.delivery_intent == "scheduled",
                                ConversationBriefingOutbox.status == "queued",
                                ConversationBriefingOutbox.prepared_for_at <= now,
                                or_(
                                    ConversationBriefingOutbox.next_attempt_at.is_(None),
                                    ConversationBriefingOutbox.next_attempt_at <= now,
                                ),
                                ConversationBriefingOutbox.attempt_count < ConversationBriefingOutbox.max_attempts,
                            ),
                            and_(
                                ConversationBriefingOutbox.delivery_intent == "scheduled",
                                ConversationBriefingOutbox.status == "sending",
                                ConversationBriefingOutbox.lease_expires_at.is_not(None),
                                ConversationBriefingOutbox.lease_expires_at <= now,
                            ),
                        )
                    )
                    .distinct()
                    .order_by(
                        ConversationBriefingOutbox.organisation_id,
                        ConversationBriefingOutbox.user_id,
                    )
                    .limit(DISCOVERY_LIMIT)
                )
            ).all()
            preference_rows = (
                await session.execute(
                    select(
                        ConversationDeliveryPreference.organisation_id,
                        ConversationDeliveryPreference.user_id,
                    )
                    .join(
                        OrganisationMembership,
                        and_(
                            OrganisationMembership.organisation_id == ConversationDeliveryPreference.organisation_id,
                            OrganisationMembership.user_id == ConversationDeliveryPreference.user_id,
                            OrganisationMembership.status == "active",
                        ),
                    )
                    .join(User, User.id == ConversationDeliveryPreference.user_id)
                    .where(
                        User.status == "active",
                        or_(
                            ConversationDeliveryPreference.morning_digest_enabled.is_(True),
                            ConversationDeliveryPreference.pre_meeting_enabled.is_(True),
                        ),
                    )
                    .order_by(
                        case(
                            (ConversationDeliveryPreference.last_scheduler_discovered_at.is_(None), 0),
                            else_=1,
                        ),
                        ConversationDeliveryPreference.last_scheduler_discovered_at,
                        ConversationDeliveryPreference.organisation_id,
                        ConversationDeliveryPreference.user_id,
                    )
                    .limit(DISCOVERY_LIMIT)
                )
            ).all()
            due_targets = {(row[0], row[1]) for row in outbox_rows}
            preference_targets = {(row[0], row[1]) for row in preference_rows} - due_targets
            ordered_targets = [
                *sorted(due_targets, key=lambda item: (str(item[0]), str(item[1]))),
                *sorted(preference_targets, key=lambda item: (str(item[0]), str(item[1]))),
            ]
            return [
                BriefingDeliveryTarget(organisation_id, user_id)
                for organisation_id, user_id in ordered_targets[:DISCOVERY_LIMIT]
            ]

    async def schedule_target(self, target: BriefingDeliveryTarget) -> int:
        async with self._session_factory() as session:
            await self._set_context(session, target)
            scheduled = await RevenueOSDailyService(
                session,
                TenantContext(target.organisation_id, target.user_id, "member"),
                self._settings,
                delivery_connector_keys=self._transports,
            ).schedule_delivery_briefings(now=self._now())
            await self._set_context(session, target)
            await session.execute(
                update(ConversationDeliveryPreference)
                .where(
                    ConversationDeliveryPreference.organisation_id == target.organisation_id,
                    ConversationDeliveryPreference.user_id == target.user_id,
                )
                # SQLAlchemy's ``onupdate`` otherwise advances ``updated_at``
                # for this internal fairness cursor write. Keep the public
                # preference timestamp tied only to user-visible edits.
                .values(
                    last_scheduler_discovered_at=self._now(),
                    updated_at=ConversationDeliveryPreference.updated_at,
                )
            )
            await session.commit()
            return scheduled

    async def recover_expired_claims(self, target: BriefingDeliveryTarget) -> int:
        now = self._now()
        async with self._session_factory() as session, session.begin():
            await self._set_context(session, target)
            values = await session.scalars(
                select(ConversationBriefingOutbox)
                .where(
                    ConversationBriefingOutbox.organisation_id == target.organisation_id,
                    ConversationBriefingOutbox.user_id == target.user_id,
                    ConversationBriefingOutbox.delivery_intent == "scheduled",
                    ConversationBriefingOutbox.status == "sending",
                    ConversationBriefingOutbox.lease_expires_at.is_not(None),
                    ConversationBriefingOutbox.lease_expires_at <= now,
                )
                .with_for_update(skip_locked=True)
            )
            rows = list(values.all())
            for row in rows:
                if row.submission_started_at is None:
                    # Claiming is separate from provider submission. A worker
                    # that died during preflight can be retried safely.
                    row.status = "queued"
                    row.attempt_count = max(0, row.attempt_count - 1)
                    row.worker_id = None
                    row.lease_expires_at = None
                    row.connection_id = None
                    row.failure_code = "worker_lease_recovered"
                else:
                    # A crashed process may have submitted the provider request
                    # but failed before committing the receipt. Never retry it.
                    self._fail(row, now, "delivery_outcome_unknown")
            return len(rows)

    async def claim_next(
        self,
        target: BriefingDeliveryTarget,
        worker_id: str,
    ) -> ClaimedBriefingDelivery | None:
        now = self._now()
        async with self._session_factory() as session, session.begin():
            await self._set_context(session, target)
            row = cast(
                ConversationBriefingOutbox | None,
                await session.scalar(
                    select(ConversationBriefingOutbox)
                    .where(
                        ConversationBriefingOutbox.organisation_id == target.organisation_id,
                        ConversationBriefingOutbox.user_id == target.user_id,
                        ConversationBriefingOutbox.delivery_intent == "scheduled",
                        ConversationBriefingOutbox.status == "queued",
                        ConversationBriefingOutbox.prepared_for_at <= now,
                        or_(
                            ConversationBriefingOutbox.next_attempt_at.is_(None),
                            ConversationBriefingOutbox.next_attempt_at <= now,
                        ),
                        ConversationBriefingOutbox.attempt_count < ConversationBriefingOutbox.max_attempts,
                    )
                    .order_by(
                        ConversationBriefingOutbox.prepared_for_at,
                        ConversationBriefingOutbox.created_at,
                        ConversationBriefingOutbox.id,
                    )
                    .with_for_update(skip_locked=True)
                    .limit(1)
                ),
            )
            if row is None:
                return None
            row.status = "sending"
            row.worker_id = worker_id
            row.lease_expires_at = now + timedelta(seconds=self._settings.worker_lease_duration_seconds)
            row.attempt_count += 1
            row.next_attempt_at = None
            row.failure_code = None
            row.failed_at = None
            row.connection_id = None
            row.submission_started_at = None
            return ClaimedBriefingDelivery(
                organisation_id=target.organisation_id,
                user_id=target.user_id,
                outbox_id=row.id,
                worker_id=worker_id,
            )

    async def execute_claimed(self, claim: ClaimedBriefingDelivery) -> None:
        prepared = await self._prepare_claimed(claim)
        if prepared is None:
            return
        result: BriefingDeliveryResult | None = None
        error: BriefingDeliveryError | None = None
        stop_heartbeat = asyncio.Event()
        heartbeat = asyncio.create_task(
            self._submission_heartbeat_loop(claim, stop_heartbeat),
            name=f"briefing-submission-heartbeat-{claim.outbox_id}",
        )
        try:
            result = await prepared.transport.send(prepared.message)
        except BriefingDeliveryError as exc:
            error = exc
        except Exception:
            # Once transport invocation begins an unexpected exception may
            # follow provider acceptance. Treat it as ambiguous, terminal.
            error = BriefingDeliveryError("delivery_outcome_unknown", uncertain=True)
            logger.error(
                "briefing_delivery_outcome_unknown",
                extra={
                    "organisation_id": str(claim.organisation_id),
                    "outbox_id": str(claim.outbox_id),
                },
            )
        finally:
            stop_heartbeat.set()
            await heartbeat
        await self._reconcile_submission(claim, result=result, error=error)

    async def _prepare_claimed(self, claim: ClaimedBriefingDelivery) -> PreparedBriefingDelivery | None:
        target = BriefingDeliveryTarget(claim.organisation_id, claim.user_id)
        async with self._session_factory() as session, session.begin():
            await self._set_context(session, target)
            row, logical_rows = await self._lock_claim_scope(session, claim)
            if row is None:
                return None
            # Lock acquisition can wait behind another transaction. Every
            # schedule and lease decision below uses a fresh time boundary.
            now = self._now()
            if row.delivery_intent != "scheduled":
                self._cancel(row, "delivery_preview_not_authorised")
                return None
            fence = self._unresolved_delivery_fence(row, logical_rows)
            if fence is not None:
                if fence.status == "sending":
                    self._defer_for_in_flight_delivery(row, fence, now)
                else:
                    self._cancel(row, "delivery_logical_fence_unresolved")
                return None
            if self._has_active_replacement(row, logical_rows):
                self._supersede(row, "delivery_source_superseded")
                return None
            membership, user = await self._active_owner(session, target)
            if membership is None or user is None:
                self._cancel(row, "delivery_authority_revoked")
                return None
            preference = await session.scalar(
                select(ConversationDeliveryPreference).where(
                    ConversationDeliveryPreference.organisation_id == claim.organisation_id,
                    ConversationDeliveryPreference.user_id == claim.user_id,
                )
            )
            if not await self._schedule_is_current(session, row, preference, now):
                return None
            if not self._href_is_safe(row):
                self._fail(row, now, "unsafe_delivery_link")
                return None
            connection = await self._active_connection(session, target)
            if connection is None:
                self._cancel(row, "delivery_authority_unavailable")
                return None
            transport = self._transports.get(connection.connector_key)
            if transport is None:
                self._fail(row, now, "delivery_transport_unavailable")
                return None
            sender_email = (connection.external_account_email or user.email).strip().casefold()
            if not self._safe_email(sender_email) or not self._safe_email(user.email):
                self._fail(row, now, "delivery_identity_invalid")
                return None
            submission_started_at = self._now()
            row.connection_id = connection.id
            row.submission_started_at = submission_started_at
            row.lease_expires_at = submission_started_at + timedelta(
                seconds=self._settings.worker_lease_duration_seconds
            )
            message = BriefingDeliveryMessage(
                outbox_id=row.id,
                organisation_id=row.organisation_id,
                user_id=row.user_id,
                connection_id=connection.id,
                connector_key=connection.connector_key,
                sender_name=connection.external_account_name,
                sender_email=sender_email,
                recipient_name=user.display_name,
                recipient_email=user.email.strip().casefold(),
                subject=row.subject,
                body=f"{row.body_text}\n\nOpen Oryntela: {self._absolute_href(row.href)}",
                href=row.href,
                operation_key=row.operation_key,
                credential_reference=connection.credential_reference,
                external_account_id=connection.external_account_id,
                external_tenant_id=connection.external_tenant_id,
            )
            return PreparedBriefingDelivery(message=message, transport=transport)

    async def _submission_heartbeat_loop(
        self,
        claim: ClaimedBriefingDelivery,
        stop: asyncio.Event,
    ) -> None:
        interval = min(
            float(self._settings.worker_heartbeat_interval_seconds),
            max(1.0, self._settings.worker_lease_duration_seconds / 4),
        )
        while True:
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                return
            except TimeoutError:
                pass
            try:
                if not await self._refresh_submission_lease(claim):
                    return
            except SQLAlchemyError:
                # The provider call may already have been accepted, so a
                # heartbeat failure cannot safely trigger another submission.
                # Recovery retains the existing ambiguous-outcome fence.
                logger.error(
                    "briefing_submission_heartbeat_failed",
                    extra={
                        "organisation_id": str(claim.organisation_id),
                        "outbox_id": str(claim.outbox_id),
                    },
                )

    async def _refresh_submission_lease(self, claim: ClaimedBriefingDelivery) -> bool:
        target = BriefingDeliveryTarget(claim.organisation_id, claim.user_id)
        async with self._session_factory() as session, session.begin():
            await self._set_context(session, target)
            row = await session.scalar(
                select(ConversationBriefingOutbox)
                .where(
                    ConversationBriefingOutbox.organisation_id == claim.organisation_id,
                    ConversationBriefingOutbox.user_id == claim.user_id,
                    ConversationBriefingOutbox.id == claim.outbox_id,
                    ConversationBriefingOutbox.status == "sending",
                    ConversationBriefingOutbox.worker_id == claim.worker_id,
                    ConversationBriefingOutbox.submission_started_at.is_not(None),
                )
                .with_for_update()
            )
            if row is None:
                return False
            row.lease_expires_at = self._now() + timedelta(seconds=self._settings.worker_lease_duration_seconds)
            return True

    async def _lock_claim_scope(
        self,
        session: AsyncSession,
        claim: ClaimedBriefingDelivery,
    ) -> tuple[ConversationBriefingOutbox | None, list[ConversationBriefingOutbox]]:
        candidate = cast(
            ConversationBriefingOutbox | None,
            await session.scalar(
                select(ConversationBriefingOutbox).where(
                    ConversationBriefingOutbox.organisation_id == claim.organisation_id,
                    ConversationBriefingOutbox.user_id == claim.user_id,
                    ConversationBriefingOutbox.id == claim.outbox_id,
                )
            ),
        )
        if candidate is None:
            return None, []
        scope = [
            ConversationBriefingOutbox.organisation_id == claim.organisation_id,
            ConversationBriefingOutbox.user_id == claim.user_id,
            ConversationBriefingOutbox.kind == candidate.kind,
            ConversationBriefingOutbox.delivery_intent == "scheduled",
        ]
        if candidate.kind == "morning_digest":
            logical_key = self._morning_logical_key(candidate.deduplication_key)
            if logical_key is None:
                scope.append(ConversationBriefingOutbox.id == candidate.id)
            else:
                scope.append(ConversationBriefingOutbox.deduplication_key.startswith(f"{logical_key}:"))
        elif candidate.interaction_id is not None:
            scope.append(ConversationBriefingOutbox.interaction_id == candidate.interaction_id)
        else:
            scope.append(ConversationBriefingOutbox.id == candidate.id)
        logical_rows = list(
            (
                await session.scalars(
                    select(ConversationBriefingOutbox)
                    .where(*scope)
                    .order_by(
                        ConversationBriefingOutbox.created_at,
                        ConversationBriefingOutbox.id,
                    )
                    .with_for_update()
                )
            ).all()
        )
        row = next((item for item in logical_rows if item.id == claim.outbox_id), None)
        if row is None or row.status != "sending" or row.worker_id != claim.worker_id:
            return None, logical_rows
        return row, logical_rows

    @classmethod
    def _has_active_replacement(
        cls,
        row: ConversationBriefingOutbox,
        logical_rows: list[ConversationBriefingOutbox],
    ) -> bool:
        replacements = [
            item for item in logical_rows if item.id != row.id and item.status in {"queued", "sending", "sent"}
        ]
        if not replacements:
            return False
        # A queued row can only become visible after this row left the queue,
        # and a sent row has already won delivery for this logical source.
        if any(item.status in {"queued", "sent"} for item in replacements):
            return True
        # If two workers raced claims for previously coexisting source rows,
        # select one deterministically so both cannot submit. The most recently
        # updated source wins; UUID ordering provides a stable tie-break only.
        current = max(
            [row, *replacements],
            key=lambda item: (
                cls._aware(item.updated_at),
                cls._aware(item.created_at),
                str(item.id),
            ),
        )
        return current.id != row.id

    @staticmethod
    def _unresolved_delivery_fence(
        row: ConversationBriefingOutbox,
        logical_rows: list[ConversationBriefingOutbox],
    ) -> ConversationBriefingOutbox | None:
        return next(
            (
                item
                for item in logical_rows
                if item.id != row.id
                and (
                    (item.status == "sending" and item.submission_started_at is not None)
                    or (item.status == "failed" and item.failure_code in AMBIGUOUS_BRIEFING_DELIVERY_FAILURE_CODES)
                )
            ),
            None,
        )

    @staticmethod
    def _morning_logical_key(deduplication_key: str) -> str | None:
        parts = deduplication_key.split(":")
        if len(parts) == 4 and parts[0] == "delivery" and parts[1] == "morning" and parts[2]:
            return f"delivery:morning:{parts[2]}"
        if len(parts) != 3 or parts[0] != "morning" or not parts[1]:
            return None
        return f"morning:{parts[1]}"

    async def _reconcile_submission(
        self,
        claim: ClaimedBriefingDelivery,
        *,
        result: BriefingDeliveryResult | None,
        error: BriefingDeliveryError | None,
    ) -> None:
        now = self._now()
        target = BriefingDeliveryTarget(claim.organisation_id, claim.user_id)
        async with self._session_factory() as session, session.begin():
            await self._set_context(session, target)
            row = cast(
                ConversationBriefingOutbox | None,
                await session.scalar(
                    select(ConversationBriefingOutbox)
                    .where(
                        ConversationBriefingOutbox.organisation_id == claim.organisation_id,
                        ConversationBriefingOutbox.user_id == claim.user_id,
                        ConversationBriefingOutbox.id == claim.outbox_id,
                        ConversationBriefingOutbox.status == "sending",
                        ConversationBriefingOutbox.worker_id == claim.worker_id,
                        ConversationBriefingOutbox.submission_started_at.is_not(None),
                    )
                    .with_for_update()
                ),
            )
            if row is None:
                logger.error(
                    "briefing_delivery_receipt_not_reconciled",
                    extra={
                        "organisation_id": str(claim.organisation_id),
                        "outbox_id": str(claim.outbox_id),
                    },
                )
                return
            if error is not None:
                if error.code in REAUTHORISATION_REQUIRED_CODES and not error.uncertain:
                    if row.connection_id is not None:
                        connection = await session.scalar(
                            select(IntegrationConnection)
                            .where(
                                IntegrationConnection.organisation_id == row.organisation_id,
                                IntegrationConnection.id == row.connection_id,
                                IntegrationConnection.created_by_user_id == row.user_id,
                            )
                            .with_for_update()
                        )
                        if connection is not None and connection.connection_status == "active":
                            connection.connection_status = "reauthorisation_required"
                            connection.metadata_version += 1
                    self._cancel(row, "delivery_connection_reauthorisation_required")
                    return
                self._handle_delivery_error(row, error, now)
                return
            if result is None:
                self._fail(row, now, "delivery_outcome_unknown")
                return
            row.status = "sent"
            row.provider_message_id = result.provider_message_id[:255]
            row.sent_at = now
            row.failed_at = None
            row.failure_code = None
            row.worker_id = None
            row.lease_expires_at = None

    async def _schedule_is_current(
        self,
        session: AsyncSession,
        row: ConversationBriefingOutbox,
        preference: ConversationDeliveryPreference | None,
        now: datetime,
    ) -> bool:
        if preference is None:
            self._cancel(row, "delivery_preference_missing")
            return False
        timezone_name = preference.timezone
        try:
            timezone = ZoneInfo(timezone_name)
            prior_timezone = ZoneInfo(row.delivery_timezone)
        except ZoneInfoNotFoundError:
            self._fail(row, now, "delivery_timezone_invalid")
            return False
        if row.kind == "morning_digest":
            enabled = preference.morning_digest_enabled
            delivery_time = preference.morning_digest_time
            if not enabled:
                self._cancel(row, "delivery_preference_disabled")
                return False
            local_date = self._aware(row.prepared_for_at).astimezone(prior_timezone).date()
            due_at = datetime.combine(local_date, time.fromisoformat(delivery_time), timezone).astimezone(UTC)
        else:
            enabled = preference.pre_meeting_enabled
            lead_minutes = preference.pre_meeting_minutes
            if not enabled or row.interaction_id is None:
                self._cancel(row, "delivery_preference_disabled")
                return False
            record = await DailyRepository(session).briefing_interaction(
                row.organisation_id,
                row.user_id,
                row.interaction_id,
            )
            provider_cancelled = (
                record is not None and record.provider_event is not None and record.provider_event.state != "active"
            )
            if (
                record is None
                or record.interaction.lifecycle_status in {"completed", "cancelled"}
                or provider_cancelled
            ):
                self._cancel(row, "delivery_source_cancelled")
                return False
            if record.provider_event is not None and record.provider_connection_status != "active":
                self._cancel(row, "delivery_provider_authority_unavailable")
                return False
            starts_at = (
                record.provider_event.start_at
                if record.provider_event is not None
                else record.interaction.scheduled_start_at
            )
            if starts_at is None:
                self._cancel(row, "delivery_source_unscheduled")
                return False
            aware_start = self._aware(starts_at)
            if aware_start <= now:
                self._cancel(row, "delivery_source_started")
                return False
            due_at = aware_start - timedelta(minutes=lead_minutes)
        if self._aware(row.prepared_for_at) != due_at or row.delivery_timezone != timezone_name:
            row.attempt_count = max(0, row.attempt_count - 1)
            self._supersede(row, "delivery_schedule_changed")
            return False
        if due_at > now:
            row.status = "queued"
            # Claiming performs the locked recheck, but a reschedule is not a
            # provider attempt and must not consume the retry budget.
            row.attempt_count = max(0, row.attempt_count - 1)
            row.worker_id = None
            row.lease_expires_at = None
            row.submission_started_at = None
            return False
        return True

    async def _active_owner(
        self,
        session: AsyncSession,
        target: BriefingDeliveryTarget,
    ) -> tuple[OrganisationMembership | None, User | None]:
        row = (
            await session.execute(
                select(OrganisationMembership, User)
                .join(User, User.id == OrganisationMembership.user_id)
                .where(
                    OrganisationMembership.organisation_id == target.organisation_id,
                    OrganisationMembership.user_id == target.user_id,
                    OrganisationMembership.status == "active",
                    User.status == "active",
                )
            )
        ).one_or_none()
        if row is None:
            return None, None
        return row[0], row[1]

    async def _active_connection(
        self,
        session: AsyncSession,
        target: BriefingDeliveryTarget,
    ) -> IntegrationConnection | None:
        if not self._transports:
            return None
        values = await session.scalars(
            select(IntegrationConnection)
            .where(
                IntegrationConnection.organisation_id == target.organisation_id,
                IntegrationConnection.created_by_user_id == target.user_id,
                IntegrationConnection.connector_key.in_(tuple(self._transports)),
                IntegrationConnection.connection_status == "active",
            )
            .order_by(IntegrationConnection.created_at, IntegrationConnection.id)
            .with_for_update()
        )
        return next(
            (connection for connection in values.all() if "send_email" in connection.capability_state_json),
            None,
        )

    def _handle_delivery_error(
        self,
        row: ConversationBriefingOutbox,
        error: BriefingDeliveryError,
        now: datetime,
    ) -> None:
        if error.uncertain:
            self._fail(row, now, "provider_outcome_unknown")
            return
        if error.retryable and row.attempt_count < row.max_attempts:
            requested_delay = error.retry_after_seconds or (
                self._settings.worker_base_retry_delay_seconds * (2 ** max(0, row.attempt_count - 1))
            )
            delay = min(requested_delay, self._settings.worker_max_retry_delay_seconds)
            row.status = "queued"
            row.next_attempt_at = now + timedelta(seconds=delay)
            row.failure_code = error.code[:100]
            row.failed_at = None
            row.worker_id = None
            row.lease_expires_at = None
            row.submission_started_at = None
            return
        self._fail(row, now, error.code)

    def _defer_for_in_flight_delivery(
        self,
        row: ConversationBriefingOutbox,
        fence: ConversationBriefingOutbox,
        now: datetime,
    ) -> None:
        retry_at = now + timedelta(seconds=max(1, self._settings.worker_base_retry_delay_seconds))
        if fence.lease_expires_at is not None:
            retry_at = max(retry_at, self._aware(fence.lease_expires_at))
        row.status = "queued"
        row.attempt_count = max(0, row.attempt_count - 1)
        row.next_attempt_at = retry_at
        row.failure_code = "delivery_submission_in_flight"
        row.failed_at = None
        row.worker_id = None
        row.lease_expires_at = None
        row.connection_id = None
        row.submission_started_at = None

    @staticmethod
    def _cancel(row: ConversationBriefingOutbox, code: str) -> None:
        row.status = "cancelled"
        row.failure_code = code[:100]
        row.next_attempt_at = None
        row.worker_id = None
        row.lease_expires_at = None
        row.submission_started_at = None

    @staticmethod
    def _supersede(row: ConversationBriefingOutbox, code: str) -> None:
        row.status = "superseded"
        row.failure_code = code[:100]
        row.next_attempt_at = None
        row.worker_id = None
        row.lease_expires_at = None
        row.connection_id = None
        row.submission_started_at = None

    @staticmethod
    def _fail(row: ConversationBriefingOutbox, now: datetime, code: str) -> None:
        row.status = "failed"
        row.failure_code = code[:100]
        row.failed_at = now
        row.next_attempt_at = None
        row.worker_id = None
        row.lease_expires_at = None

    @staticmethod
    def _href_is_safe(row: ConversationBriefingOutbox) -> bool:
        if row.kind == "morning_digest":
            return row.interaction_id is None and row.href == "/"
        return row.interaction_id is not None and row.href == f"/conversations/{row.interaction_id}#preparation"

    def _absolute_href(self, href: str) -> str:
        return f"{self._settings.briefing_delivery_app_base_url.rstrip('/')}{href}"

    @staticmethod
    def _safe_email(value: str) -> bool:
        return (
            3 <= len(value) <= 320
            and "@" in value
            and "\r" not in value
            and "\n" not in value
            and not any(character.isspace() for character in value)
        )

    async def _set_context(self, session: AsyncSession, target: BriefingDeliveryTarget) -> None:
        await set_tenant_database_context(session, target.organisation_id)
        await set_private_user_database_context(session, target.user_id)

    def _now(self) -> datetime:
        return self._aware(self._clock())

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
