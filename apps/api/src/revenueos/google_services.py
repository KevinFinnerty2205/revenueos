from __future__ import annotations

import base64
import logging
import re
import uuid
from datetime import UTC, date, datetime, time, timedelta
from email.utils import getaddresses
from html.parser import HTMLParser
from typing import Literal, cast
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.commercial_services import CommercialService
from revenueos.config import Settings
from revenueos.credential_store import CredentialStore, EncryptedDatabaseCredentialStore
from revenueos.domain import ConnectionStatus, ConnectorKey
from revenueos.errors import PublicAPIError
from revenueos.google_workspace import GoogleAPIError, GoogleWorkspaceClient, gmail_message_url
from revenueos.integration_contracts import (
    ProviderCalendarEventListResponse,
    ProviderCalendarEventResponse,
    ProviderReplyListResponse,
    ProviderReplyResponse,
    ProviderSyncResourceResponse,
    ProviderSyncResponse,
    ProviderSyncStatusResponse,
)
from revenueos.integration_executors import ExecutorConnectionContext
from revenueos.models import (
    ActionExecution,
    ActionProposal,
    ActionProposalVersion,
    Contact,
    EngageCampaignEnrollment,
    EngageEnrollmentStep,
    IntegrationAuditEvent,
    IntegrationConnection,
    Interaction,
    Opportunity,
    OutreachMessage,
    ProviderCalendarEvent,
    ProviderOutboundOperation,
    ProviderReply,
    ProviderSyncState,
)
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.google_sync")
_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
_MAX_PAGES = 10
_PAGE_SIZE = "50"
_MAX_REPLY_BODY = 10_000
_MAX_MIME_PARTS = 50
_MAX_MIME_DEPTH = 8


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.casefold() in {"script", "style", "svg", "iframe", "object"}:
            self._ignored_depth += 1
        elif tag.casefold() in {"br", "p", "div", "li", "tr"} and not self._ignored_depth:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "svg", "iframe", "object"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


class GoogleSyncService:
    """Bounded, tenant-scoped Gmail history and Google Calendar reconciliation."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
        *,
        credential_store: CredentialStore | None = None,
        client: GoogleWorkspaceClient | None = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.credential_store = credential_store or self._credential_store()
        self.client = client or GoogleWorkspaceClient(settings, self.credential_store)

    async def sync(self, connection_id: UUID) -> ProviderSyncResponse:
        self._require_feature()
        commercial = CommercialService(self.session, self.settings)
        await commercial.require_module_write(self.tenant.organisation_id, "core")
        connection = await self._connection(connection_id, for_update=True)
        now = datetime.now(UTC)
        resources: list[ProviderSyncResourceResponse] = []
        resources.append(await self._sync_resource(connection, "calendar", now))
        if (
            connection.connection_status == ConnectionStatus.ACTIVE.value
            and await commercial.module_access(self.tenant.organisation_id, "engage", lock_for_write=True) == "write"
        ):
            resources.append(await self._sync_resource(connection, "mail_sent", now))
            if connection.connection_status == ConnectionStatus.ACTIVE.value:
                resources.append(await self._sync_resource(connection, "mail_inbox", now))
        self.session.add(
            IntegrationAuditEvent(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                actor_user_id=self.tenant.user_id,
                event_type="provider_sync_completed",
                subject_type="connection",
                subject_id=connection.id,
                connector_key=ConnectorKey.GOOGLE_WORKSPACE.value,
                capability=None,
                risk_class=None,
                attempt_count=None,
                safe_failure_code=(
                    "google_sync_degraded" if any(item.state == "degraded" for item in resources) else None
                ),
                external_result_id=None,
                duration_ms=None,
                created_at=now,
            )
        )
        await self._commit("Google Workspace synchronisation could not be saved.")
        logger.info(
            "google_sync_completed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "connection_id": str(connection.id),
                "resource_count": len(resources),
                "degraded": any(item.state == "degraded" for item in resources),
            },
        )
        return ProviderSyncResponse(connection_id=connection.id, synced_at=now, resources=resources)

    async def list_replies(self, *, limit: int = 50) -> ProviderReplyListResponse:
        self._require_feature()
        await self._require_module_read("engage")
        connection_ids = await self._visible_connection_ids()
        if not connection_ids:
            return ProviderReplyListResponse(items=[], total=0)
        values = await self.session.scalars(
            select(ProviderReply)
            .where(
                ProviderReply.organisation_id == self.tenant.organisation_id,
                ProviderReply.connection_id.in_(connection_ids),
            )
            .order_by(ProviderReply.received_at.desc(), ProviderReply.id)
            .limit(limit)
        )
        items = [self._reply_response(item) for item in values.all()]
        return ProviderReplyListResponse(items=items, total=len(items))

    async def status(self, connection_id: UUID) -> ProviderSyncStatusResponse:
        self._require_feature()
        await self._require_module_read("core")
        connection = await self._connection(connection_id, for_update=False, allow_reauthorisation=True)
        states = list(
            (
                await self.session.scalars(
                    select(ProviderSyncState).where(
                        ProviderSyncState.organisation_id == self.tenant.organisation_id,
                        ProviderSyncState.connection_id == connection.id,
                    )
                )
            ).all()
        )
        successes = [item.last_successful_sync_at for item in states if item.last_successful_sync_at]
        errors = [item.last_error_category for item in states if item.last_error_category]
        return ProviderSyncStatusResponse(
            connection_id=connection.id,
            last_successful_sync_at=max(successes) if successes else None,
            last_error_category=errors[0] if errors else None,
            state="degraded" if errors else ("healthy" if successes else "not_started"),
        )

    async def list_calendar_events(self, *, limit: int = 50) -> ProviderCalendarEventListResponse:
        self._require_feature()
        await self._require_module_read("core")
        connection_ids = await self._visible_connection_ids()
        if not connection_ids:
            return ProviderCalendarEventListResponse(items=[], total=0)
        values = await self.session.scalars(
            select(ProviderCalendarEvent)
            .where(
                ProviderCalendarEvent.organisation_id == self.tenant.organisation_id,
                ProviderCalendarEvent.connection_id.in_(connection_ids),
                ProviderCalendarEvent.state == "active",
                ProviderCalendarEvent.end_at >= datetime.now(UTC) - timedelta(days=1),
            )
            .order_by(ProviderCalendarEvent.start_at, ProviderCalendarEvent.id)
            .limit(limit)
        )
        items = [self._calendar_response(item) for item in values.all()]
        return ProviderCalendarEventListResponse(items=items, total=len(items))

    async def link_interaction(
        self,
        event_id: UUID,
        interaction_id: UUID | None,
    ) -> ProviderCalendarEventResponse:
        self._require_feature()
        await CommercialService(self.session, self.settings).require_module_write(
            self.tenant.organisation_id,
            "core",
        )
        event = await self.session.scalar(
            select(ProviderCalendarEvent)
            .join(
                IntegrationConnection,
                (IntegrationConnection.organisation_id == ProviderCalendarEvent.organisation_id)
                & (IntegrationConnection.id == ProviderCalendarEvent.connection_id),
            )
            .where(
                ProviderCalendarEvent.organisation_id == self.tenant.organisation_id,
                ProviderCalendarEvent.id == event_id,
                IntegrationConnection.created_by_user_id == self.tenant.user_id,
                IntegrationConnection.connector_key == ConnectorKey.GOOGLE_WORKSPACE.value,
            )
            .with_for_update()
        )
        if event is None:
            raise PublicAPIError("calendar_event_not_found", "The Google calendar event was not found.", 404)
        if interaction_id is None:
            event.interaction_id = None
            await self._commit("The calendar event link could not be removed.")
            return self._calendar_response(event)
        if event.match_state == "private":
            raise PublicAPIError(
                "google_private_calendar_event_not_linkable",
                "Private Google calendar events cannot be linked to an Interaction.",
                409,
            )
        if event.state != "active":
            raise PublicAPIError(
                "google_calendar_event_not_active",
                "Only active Google calendar events can be linked to an Interaction.",
                409,
            )
        interaction = await self.session.scalar(
            select(Interaction).where(
                Interaction.organisation_id == self.tenant.organisation_id,
                Interaction.id == interaction_id,
                Interaction.deleted_at.is_(None),
            )
        )
        if interaction is None:
            raise PublicAPIError("interaction_not_found", "The requested Interaction was not found.", 404)
        event.interaction_id = interaction.id
        await self._commit("The calendar event could not be linked.")
        return self._calendar_response(event)

    async def _sync_resource(
        self,
        connection: IntegrationConnection,
        resource_kind: Literal["mail_sent", "mail_inbox", "calendar"],
        now: datetime,
    ) -> ProviderSyncResourceResponse:
        state = await self._sync_state(connection.id, resource_kind, now)
        if resource_kind == "calendar":
            self._roll_calendar_window(state, now)
        try:
            items, cursor = await (
                self._fetch_calendar(self._context(connection), state)
                if resource_kind == "calendar"
                else self._fetch_mail(self._context(connection), state, resource_kind)
            )
            retained = 0
            for item in items:
                if resource_kind == "mail_sent":
                    retained += await self._reconcile_sent(connection, item, now)
                elif resource_kind == "mail_inbox":
                    retained += await self._retain_reply(connection, item, now)
                else:
                    retained += await self._retain_calendar_event(connection, item, now, state)
            if resource_kind == "calendar":
                await self.session.execute(
                    delete(ProviderCalendarEvent).where(
                        ProviderCalendarEvent.organisation_id == self.tenant.organisation_id,
                        ProviderCalendarEvent.connection_id == connection.id,
                        ProviderCalendarEvent.end_at < state.window_start_at,
                    )
                )
            state.delta_link = cursor
            state.last_successful_sync_at = now
            state.last_error_category = None
            state.consecutive_failures = 0
            return ProviderSyncResourceResponse(
                resource_kind=resource_kind,
                processed=len(items),
                retained=retained,
                state="healthy",
                safe_message="Google changes were synchronised.",
            )
        except GoogleAPIError as exc:
            state.last_error_category = exc.code
            state.consecutive_failures += 1
            if exc.code in {"connection_reauthorisation_required", "provider_permission_denied"}:
                connection.connection_status = ConnectionStatus.REAUTHORISATION_REQUIRED.value
                connection.metadata_version += 1
            return ProviderSyncResourceResponse(
                resource_kind=resource_kind,
                processed=0,
                retained=0,
                state="degraded",
                safe_message=(
                    "Google Workspace needs to be reconnected."
                    if exc.code in {"connection_reauthorisation_required", "provider_permission_denied"}
                    else "Google synchronisation is temporarily delayed."
                ),
            )

    async def _fetch_mail(
        self,
        context: ExecutorConnectionContext,
        state: ProviderSyncState,
        resource_kind: Literal["mail_sent", "mail_inbox"],
    ) -> tuple[list[dict[str, object]], str]:
        try:
            message_ids, cursor = await self._mail_message_ids(context, state, resource_kind)
        except GoogleAPIError as exc:
            if exc.code != "provider_cursor_expired" or state.delta_link is None:
                raise
            state.delta_link = None
            message_ids, cursor = await self._mail_message_ids(context, state, resource_kind)
        items: list[dict[str, object]] = []
        for message_id in message_ids[: _MAX_PAGES * int(_PAGE_SIZE)]:
            item = await self.client.google_json(
                context,
                gmail_message_url(self.settings, message_id),
                # Omitting metadataHeaders asks Gmail for metadata only with all
                # headers. This keeps bodies out of the broad scan and avoids a
                # non-standard indexed encoding for the repeated query field.
                params={"format": "metadata"},
            )
            items.append(item)
        return items, cursor

    async def _mail_message_ids(
        self,
        context: ExecutorConnectionContext,
        state: ProviderSyncState,
        resource_kind: Literal["mail_sent", "mail_inbox"],
    ) -> tuple[list[str], str]:
        label = "SENT" if resource_kind == "mail_sent" else "INBOX"
        ids: list[str] = []
        if state.delta_link is None:
            url = f"{self.settings.google_gmail_base_url}/users/me/messages"
            page_token: str | None = None
            for _ in range(_MAX_PAGES):
                params = {
                    "labelIds": label,
                    "maxResults": _PAGE_SIZE,
                    "q": f"newer_than:{self.settings.google_mail_sync_lookback_days}d",
                }
                if page_token is not None:
                    params["pageToken"] = page_token
                payload = await self.client.google_json(context, url, params=params)
                ids.extend(self._message_ids(payload.get("messages")))
                page_token = self._string(payload.get("nextPageToken"), 2048)
                if page_token is None:
                    break
            else:
                raise GoogleAPIError("provider_sync_page_limit")
            profile = await self.client.google_json(
                context,
                f"{self.settings.google_gmail_base_url}/users/me/profile",
            )
            cursor = self._string(profile.get("historyId"), 255)
            if cursor is None:
                raise GoogleAPIError("provider_response_invalid")
            return list(dict.fromkeys(ids)), cursor
        url = f"{self.settings.google_gmail_base_url}/users/me/history"
        page_token = None
        cursor = state.delta_link
        for _ in range(_MAX_PAGES):
            params = {
                "startHistoryId": state.delta_link,
                "historyTypes": "messageAdded",
                "labelId": label,
                "maxResults": _PAGE_SIZE,
            }
            if page_token is not None:
                params["pageToken"] = page_token
            payload = await self.client.google_json(context, url, params=params)
            history = payload.get("history")
            if isinstance(history, list):
                for record in history:
                    if not isinstance(record, dict):
                        continue
                    additions = record.get("messagesAdded")
                    if not isinstance(additions, list):
                        continue
                    for addition in additions:
                        if not isinstance(addition, dict):
                            continue
                        message = addition.get("message")
                        if not isinstance(message, dict):
                            continue
                        labels = message.get("labelIds")
                        message_id = self._string(message.get("id"), 255)
                        if message_id is not None and isinstance(labels, list) and label in labels:
                            ids.append(message_id)
            page_token = self._string(payload.get("nextPageToken"), 2048)
            latest = self._string(payload.get("historyId"), 255)
            if latest is not None:
                cursor = latest
            if page_token is None:
                return list(dict.fromkeys(ids)), cursor
        raise GoogleAPIError("provider_sync_page_limit")

    async def _fetch_calendar(
        self,
        context: ExecutorConnectionContext,
        state: ProviderSyncState,
    ) -> tuple[list[dict[str, object]], str]:
        try:
            return await self._calendar_pages(context, state)
        except GoogleAPIError as exc:
            if exc.code != "provider_cursor_expired" or state.delta_link is None:
                raise
            state.delta_link = None
            return await self._calendar_pages(context, state)

    async def _calendar_pages(
        self,
        context: ExecutorConnectionContext,
        state: ProviderSyncState,
    ) -> tuple[list[dict[str, object]], str]:
        url = f"{self.settings.google_calendar_base_url}/calendars/primary/events"
        page_token: str | None = None
        items: list[dict[str, object]] = []
        for _ in range(_MAX_PAGES):
            params = {
                "maxResults": _PAGE_SIZE,
                "singleEvents": "true",
                "showDeleted": "true",
            }
            if state.delta_link is None:
                params["timeMin"] = self._iso(state.window_start_at)
                params["timeMax"] = self._iso(state.window_end_at)
            else:
                params["syncToken"] = state.delta_link
            if page_token is not None:
                params["pageToken"] = page_token
            payload = await self.client.google_json(context, url, params=params)
            values = payload.get("items")
            if not isinstance(values, list):
                raise GoogleAPIError("provider_response_invalid")
            items.extend(cast(dict[str, object], item) for item in values if isinstance(item, dict))
            page_token = self._string(payload.get("nextPageToken"), 2048)
            if page_token is not None:
                continue
            cursor = self._string(payload.get("nextSyncToken"), 4096)
            if cursor is None:
                raise GoogleAPIError("provider_response_invalid")
            return items, cursor
        raise GoogleAPIError("provider_sync_page_limit")

    async def _reconcile_sent(
        self,
        connection: IntegrationConnection,
        item: dict[str, object],
        now: datetime,
    ) -> int:
        provider_id = self._string(item.get("id"), 255)
        operation_key = self._header(item, "x-oryntela-operation-id")
        if provider_id is None or operation_key is None or len(operation_key) != 64:
            return 0
        operation = await self.session.scalar(
            select(ProviderOutboundOperation)
            .where(
                ProviderOutboundOperation.organisation_id == self.tenant.organisation_id,
                ProviderOutboundOperation.connection_id == connection.id,
                ProviderOutboundOperation.idempotency_key == operation_key,
            )
            .with_for_update()
        )
        if operation is None:
            return 0
        sender = self._first_address(self._header(item, "from"))
        recipients = self._addresses(self._header(item, "to"))
        if sender != operation.sender_email.casefold() or operation.recipient_email.casefold() not in recipients:
            return 0
        operation.provider_message_id = provider_id
        operation.internet_message_id = self._header(item, "message-id")
        operation.conversation_id = self._string(item.get("threadId"), 255)
        operation.state = "reconciled"
        operation.reconciled_at = now
        operation.safe_failure_code = None
        execution = await self.session.scalar(
            select(ActionExecution).where(
                ActionExecution.organisation_id == self.tenant.organisation_id,
                ActionExecution.action_id == operation.action_id,
                ActionExecution.idempotency_key == operation.idempotency_key,
            )
        )
        if execution is not None and execution.execution_status == "unknown_external_state":
            execution.execution_status = "succeeded"
            execution.external_result_id = provider_id
            execution.safe_failure_code = None
            execution.completed_at = now
        return 1

    async def _retain_reply(
        self,
        connection: IntegrationConnection,
        item: dict[str, object],
        now: datetime,
    ) -> int:
        provider_id = self._string(item.get("id"), 255)
        sender = self._first_address(self._header(item, "from"))
        if provider_id is None or sender is None:
            return 0
        connected_email = (connection.external_account_email or "").casefold()
        recipients = self._addresses(self._header(item, "to")) | self._addresses(self._header(item, "delivered-to"))
        if connected_email not in recipients:
            return 0
        duplicate = await self.session.scalar(
            select(ProviderReply.id).where(
                ProviderReply.organisation_id == self.tenant.organisation_id,
                ProviderReply.connection_id == connection.id,
                ProviderReply.provider_message_id == provider_id,
            )
        )
        if duplicate is not None:
            return 0
        internet_message_id = self._header(item, "message-id")
        conversation_id = self._string(item.get("threadId"), 255)
        in_reply_to = self._header(item, "in-reply-to")
        references = self._header(item, "references") or ""
        kind = self._reply_kind(item, sender)
        operations = list(
            (
                await self.session.scalars(
                    select(ProviderOutboundOperation).where(
                        ProviderOutboundOperation.organisation_id == self.tenant.organisation_id,
                        ProviderOutboundOperation.connection_id == connection.id,
                        ProviderOutboundOperation.state.in_(("accepted", "reconciled", "unknown")),
                        or_(
                            ProviderOutboundOperation.internet_message_id.is_not(None),
                            ProviderOutboundOperation.conversation_id.is_not(None),
                        ),
                    )
                )
            ).all()
        )
        matches = [
            operation
            for operation in operations
            if (sender == operation.recipient_email.casefold() or kind == "ndr")
            and (
                (
                    operation.internet_message_id is not None
                    and (operation.internet_message_id == in_reply_to or operation.internet_message_id in references)
                )
                or (
                    kind != "ndr"
                    and operation.conversation_id is not None
                    and conversation_id is not None
                    and operation.conversation_id == conversation_id
                )
            )
        ]
        if len(matches) != 1:
            return 0
        operation = matches[0]
        contact, company_id, opportunity_id = await self._action_context(
            operation.action_id,
            operation.recipient_email.casefold(),
        )
        received_at = self._message_datetime(item)
        if received_at is None:
            return 0
        # Body content is fetched only after one strong Oryntela-managed correlation.
        body_payload = await self.client.google_json(
            self._context(connection),
            gmail_message_url(self.settings, provider_id),
            params={"format": "full"},
        )
        subject = self._header(body_payload, "subject") or "(No subject)"
        self.session.add(
            ProviderReply(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                connection_id=connection.id,
                outbound_operation_id=operation.id,
                provider_key=ConnectorKey.GOOGLE_WORKSPACE.value,
                provider_message_id=provider_id,
                internet_message_id=internet_message_id,
                conversation_id=conversation_id,
                sender_email=sender,
                recipient_emails_json=sorted(recipients),
                subject=subject[:500],
                body_text=self._mime_body(body_payload.get("payload")),
                kind=kind,
                match_state="matched" if opportunity_id is not None else "review_required",
                contact_id=contact.id if contact is not None else None,
                company_id=company_id,
                opportunity_id=opportunity_id,
                received_at=received_at,
                created_at=now,
                updated_at=now,
            )
        )
        if kind == "reply":
            await self._stop_campaign(operation.action_id, now)
        return 1

    async def _retain_calendar_event(
        self,
        connection: IntegrationConnection,
        item: dict[str, object],
        now: datetime,
        sync_state: ProviderSyncState,
    ) -> int:
        provider_id = self._string(item.get("id"), 255)
        if provider_id is None:
            return 0
        existing = await self.session.scalar(
            select(ProviderCalendarEvent)
            .where(
                ProviderCalendarEvent.organisation_id == self.tenant.organisation_id,
                ProviderCalendarEvent.connection_id == connection.id,
                ProviderCalendarEvent.provider_event_id == provider_id,
            )
            .with_for_update()
        )
        status = self._string(item.get("status"), 24)
        if status == "cancelled" and item.get("start") is None:
            if existing is not None:
                existing.state = "deleted"
                existing.last_synced_at = now
                return 1
            return 0
        modified_at = self._datetime(item.get("updated"))
        if (
            existing is not None
            and modified_at is not None
            and existing.provider_last_modified_at is not None
            and self._aware(existing.provider_last_modified_at) >= modified_at
        ):
            return 0
        start, timezone = self._event_datetime(item.get("start"))
        end, _ = self._event_datetime(item.get("end"))
        if start is None or end is None or end <= start:
            return 0
        if end < self._aware(sync_state.window_start_at) or start > self._aware(sync_state.window_end_at):
            if existing is not None:
                await self.session.delete(existing)
                return 1
            return 0
        visibility = (self._string(item.get("visibility"), 24) or "default").casefold()
        private = visibility in {"private", "confidential"}
        attendees = [] if private else sorted(self._attendee_addresses(item.get("attendees")))
        organiser = None if private else self._calendar_address(item.get("organizer"))
        match_state, contact, company_id, opportunity_id = await self._calendar_context(
            connection.external_account_email or "",
            attendees,
            organiser,
        )
        if private:
            match_state, contact, company_id, opportunity_id = "private", None, None, None
        values: dict[str, object] = {
            "i_cal_uid": None if private else self._string(item.get("iCalUID"), 255),
            "series_master_id": None if private else self._string(item.get("recurringEventId"), 255),
            "change_key": None if private else self._string(item.get("etag"), 255),
            "title": "Private event" if private else (self._string(item.get("summary"), 500) or "Calendar event"),
            "start_at": start,
            "end_at": end,
            "provider_timezone": timezone,
            "organiser_email": organiser,
            "attendee_emails_json": attendees,
            "location": None if private else self._string(item.get("location"), 500),
            "online_meeting_url": None if private else self._meeting_url(item.get("hangoutLink")),
            "sensitivity": "private" if private else visibility[:24],
            "state": "cancelled" if status == "cancelled" else "active",
            "match_state": match_state,
            "contact_id": contact.id if contact is not None else None,
            "company_id": company_id,
            "opportunity_id": opportunity_id,
            "provider_last_modified_at": modified_at,
            "last_synced_at": now,
        }
        if existing is None:
            self.session.add(
                ProviderCalendarEvent(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    connection_id=connection.id,
                    provider_key=ConnectorKey.GOOGLE_WORKSPACE.value,
                    provider_event_id=provider_id,
                    interaction_id=None,
                    created_at=now,
                    updated_at=now,
                    **values,
                )
            )
        else:
            for key, value in values.items():
                setattr(existing, key, value)
            if private:
                existing.interaction_id = None
        return 1

    async def _calendar_context(
        self,
        connected_email: str,
        attendees: list[str],
        organiser: str | None,
    ) -> tuple[str, Contact | None, UUID | None, UUID | None]:
        participant_addresses = set(attendees)
        if organiser is not None:
            participant_addresses.add(organiser)
        external = sorted(email for email in participant_addresses if email != connected_email.casefold())
        if external and all(self._domain(item) == self._domain(connected_email) for item in external):
            return "internal", None, None, None
        if len(external) != 1:
            return ("review_required" if external else "unmatched"), None, None, None
        contacts = list(
            (
                await self.session.scalars(
                    select(Contact).where(
                        Contact.organisation_id == self.tenant.organisation_id,
                        Contact.archived_at.is_(None),
                        func.lower(Contact.email).in_(external),
                    )
                )
            ).all()
        )
        if len(contacts) != 1:
            return ("review_required" if contacts or external else "unmatched"), None, None, None
        contact = contacts[0]
        opportunities = list(
            (
                await self.session.scalars(
                    select(Opportunity).where(
                        Opportunity.organisation_id == self.tenant.organisation_id,
                        Opportunity.company_id == contact.company_id,
                        Opportunity.status.in_(("open", "on_hold")),
                        Opportunity.archived_at.is_(None),
                    )
                )
            ).all()
        )
        if len(opportunities) == 1:
            return "matched", contact, contact.company_id, opportunities[0].id
        return "review_required", contact, contact.company_id, None

    async def _action_context(
        self,
        action_id: UUID,
        sender_email: str,
    ) -> tuple[Contact | None, UUID | None, UUID | None]:
        action = await self.session.scalar(
            select(ActionProposal).where(
                ActionProposal.organisation_id == self.tenant.organisation_id,
                ActionProposal.id == action_id,
            )
        )
        outreach = await self.session.scalar(
            select(OutreachMessage).where(
                OutreachMessage.organisation_id == self.tenant.organisation_id,
                OutreachMessage.action_id == action_id,
            )
        )
        contact_id = outreach.contact_id if outreach is not None else None
        if contact_id is None and action is not None:
            version = await self.session.scalar(
                select(ActionProposalVersion).where(
                    ActionProposalVersion.organisation_id == self.tenant.organisation_id,
                    ActionProposalVersion.action_id == action.id,
                    ActionProposalVersion.version == action.approved_version,
                    ActionProposalVersion.target_entity_type == "contact",
                )
            )
            contact_id = version.target_entity_id if version is not None else None
        contact = None
        if contact_id is not None:
            contact = await self.session.scalar(
                select(Contact).where(
                    Contact.organisation_id == self.tenant.organisation_id,
                    Contact.id == contact_id,
                    func.lower(Contact.email) == sender_email,
                )
            )
        opportunity_id = action.opportunity_id if action is not None else None
        return contact, contact.company_id if contact is not None else None, opportunity_id

    async def _stop_campaign(self, action_id: UUID, now: datetime) -> None:
        enrollment = await self.session.scalar(
            select(EngageCampaignEnrollment)
            .join(
                EngageEnrollmentStep,
                (EngageEnrollmentStep.organisation_id == EngageCampaignEnrollment.organisation_id)
                & (EngageEnrollmentStep.enrollment_id == EngageCampaignEnrollment.id),
            )
            .join(
                OutreachMessage,
                (OutreachMessage.organisation_id == EngageEnrollmentStep.organisation_id)
                & (OutreachMessage.id == EngageEnrollmentStep.outreach_message_id),
            )
            .where(
                EngageCampaignEnrollment.organisation_id == self.tenant.organisation_id,
                OutreachMessage.action_id == action_id,
            )
            .with_for_update()
        )
        if enrollment is None or enrollment.state in {"stopped", "completed"}:
            return
        enrollment.state = "stopped"
        enrollment.stop_reason = "provider_reply"
        enrollment.outcome = "replied"
        enrollment.outcome_provenance = "provider"
        enrollment.outcome_reported_at = now
        enrollment.next_scheduled_at = None

    async def _sync_state(
        self,
        connection_id: UUID,
        resource_kind: Literal["mail_sent", "mail_inbox", "calendar"],
        now: datetime,
    ) -> ProviderSyncState:
        state = await self.session.scalar(
            select(ProviderSyncState)
            .where(
                ProviderSyncState.organisation_id == self.tenant.organisation_id,
                ProviderSyncState.connection_id == connection_id,
                ProviderSyncState.resource_kind == resource_kind,
            )
            .with_for_update()
        )
        if state is not None:
            return state
        if resource_kind == "calendar":
            start = now - timedelta(days=self.settings.google_calendar_past_days)
            end = now + timedelta(days=self.settings.google_calendar_future_days)
        else:
            start = now - timedelta(days=self.settings.google_mail_sync_lookback_days)
            end = now
        state = ProviderSyncState(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            connection_id=connection_id,
            provider_key=ConnectorKey.GOOGLE_WORKSPACE.value,
            resource_kind=resource_kind,
            delta_link=None,
            window_start_at=start,
            window_end_at=end,
            last_successful_sync_at=None,
            last_error_category=None,
            consecutive_failures=0,
            created_at=now,
            updated_at=now,
        )
        self.session.add(state)
        await self.session.flush()
        return state

    def _roll_calendar_window(self, state: ProviderSyncState, now: datetime) -> None:
        desired_end = now + timedelta(days=self.settings.google_calendar_future_days)
        if self._aware(state.window_end_at) >= desired_end - timedelta(days=1):
            return
        state.window_start_at = now - timedelta(days=self.settings.google_calendar_past_days)
        state.window_end_at = desired_end
        state.delta_link = None

    async def _connection(
        self,
        connection_id: UUID,
        *,
        for_update: bool,
        allow_reauthorisation: bool = False,
    ) -> IntegrationConnection:
        statement = select(IntegrationConnection).where(
            IntegrationConnection.organisation_id == self.tenant.organisation_id,
            IntegrationConnection.id == connection_id,
            IntegrationConnection.connector_key == ConnectorKey.GOOGLE_WORKSPACE.value,
        )
        if for_update:
            statement = statement.with_for_update()
        connection = await self.session.scalar(statement)
        if connection is None:
            raise PublicAPIError("connection_not_found", "The Google Workspace connection was not found.", 404)
        if connection.created_by_user_id != self.tenant.user_id:
            raise PublicAPIError("forbidden", "You cannot synchronise another seller's Google account.", 403)
        if (
            connection.connection_status == ConnectionStatus.REAUTHORISATION_REQUIRED.value
            and not allow_reauthorisation
        ):
            raise PublicAPIError(
                "connection_reauthorisation_required",
                "Google Workspace needs to be reconnected.",
                409,
            )
        if connection.connection_status != ConnectionStatus.ACTIVE.value and not (
            allow_reauthorisation and connection.connection_status == ConnectionStatus.REAUTHORISATION_REQUIRED.value
        ):
            raise PublicAPIError("connection_revoked", "This Google Workspace connection is disconnected.", 409)
        return connection

    async def _visible_connection_ids(self) -> list[UUID]:
        values = await self.session.scalars(
            select(IntegrationConnection.id).where(
                IntegrationConnection.organisation_id == self.tenant.organisation_id,
                IntegrationConnection.connector_key == ConnectorKey.GOOGLE_WORKSPACE.value,
                IntegrationConnection.created_by_user_id == self.tenant.user_id,
            )
        )
        return list(values.all())

    @staticmethod
    def _context(connection: IntegrationConnection) -> ExecutorConnectionContext:
        return ExecutorConnectionContext(
            organisation_id=connection.organisation_id,
            connection_id=connection.id,
            credential_reference=connection.credential_reference,
            execution_mode="live",
            external_account_id=connection.external_account_id,
            external_account_email=connection.external_account_email,
            external_tenant_id=connection.external_tenant_id,
        )

    def _credential_store(self) -> CredentialStore:
        if self.settings.connector_credential_master_key is None:
            raise RuntimeError("Connector credential storage is not configured.")
        return EncryptedDatabaseCredentialStore(
            self.session,
            self.settings.connector_credential_master_key.get_secret_value(),
        )

    def _require_feature(self) -> None:
        if not self.settings.feature_integrations_enabled or not self.settings.feature_google_workspace_enabled:
            raise PublicAPIError("feature_unavailable", "Google Workspace is not configured.", 404)

    async def _require_module_read(self, module: Literal["core", "engage"]) -> None:
        if (
            await CommercialService(self.session, self.settings).module_access(
                self.tenant.organisation_id,
                module,
            )
            == "none"
        ):
            raise PublicAPIError(
                f"{module}_not_in_plan",
                "This Google Workspace history is unavailable under the organisation's current plan.",
                403,
            )

    async def _commit(self, message: str) -> None:
        try:
            await self.session.flush()
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PublicAPIError("integration_conflict", message, 409) from exc

    @staticmethod
    def _reply_response(item: ProviderReply) -> ProviderReplyResponse:
        return ProviderReplyResponse(
            id=item.id,
            kind=cast(Literal["reply", "automatic_reply", "ndr"], item.kind),
            match_state=cast(Literal["matched", "review_required"], item.match_state),
            sender_email=item.sender_email,
            subject=item.subject,
            body_text=item.body_text,
            contact_id=item.contact_id,
            company_id=item.company_id,
            opportunity_id=item.opportunity_id,
            received_at=item.received_at,
        )

    @staticmethod
    def _calendar_response(item: ProviderCalendarEvent) -> ProviderCalendarEventResponse:
        return ProviderCalendarEventResponse(
            id=item.id,
            title=item.title,
            start_at=item.start_at,
            end_at=item.end_at,
            provider_timezone=item.provider_timezone,
            attendee_emails=list(item.attendee_emails_json),
            location=item.location,
            online_meeting_url=item.online_meeting_url,
            sensitivity=item.sensitivity,
            state=cast(Literal["active", "cancelled", "deleted"], item.state),
            match_state=cast(
                Literal["unmatched", "matched", "review_required", "internal", "private"],
                item.match_state,
            ),
            contact_id=item.contact_id,
            company_id=item.company_id,
            opportunity_id=item.opportunity_id,
            interaction_id=item.interaction_id,
            last_synced_at=item.last_synced_at,
        )

    @staticmethod
    def _string(value: object, maximum: int) -> str | None:
        if not isinstance(value, str):
            return None
        clean = " ".join(value.split()).strip()
        return clean[:maximum] if clean else None

    @classmethod
    def _header(cls, item: dict[str, object], name: str) -> str | None:
        payload = item.get("payload")
        if not isinstance(payload, dict):
            return None
        headers = payload.get("headers")
        if not isinstance(headers, list):
            return None
        for header in headers[:100]:
            if not isinstance(header, dict):
                continue
            header_name = cls._string(header.get("name"), 200)
            if header_name is not None and header_name.casefold() == name.casefold():
                return cls._string(header.get("value"), 2_000)
        return None

    @staticmethod
    def _addresses(value: str | None) -> set[str]:
        return {
            address.casefold()
            for _, address in getaddresses([value or ""])
            if len(address) <= 320 and _EMAIL.fullmatch(address)
        }

    @classmethod
    def _first_address(cls, value: str | None) -> str | None:
        values = sorted(cls._addresses(value))
        return values[0] if len(values) == 1 else None

    @classmethod
    def _reply_kind(cls, item: dict[str, object], sender: str) -> Literal["reply", "automatic_reply", "ndr"]:
        auto_submitted = (cls._header(item, "auto-submitted") or "").casefold()
        if sender.startswith(("postmaster@", "mailer-daemon@")):
            return "ndr"
        if auto_submitted and auto_submitted != "no":
            return "automatic_reply"
        return "reply"

    @classmethod
    def _message_datetime(cls, item: dict[str, object]) -> datetime | None:
        internal_date = cls._string(item.get("internalDate"), 32)
        if internal_date is not None and internal_date.isdigit():
            try:
                return datetime.fromtimestamp(int(internal_date) / 1000, tz=UTC)
            except (OverflowError, OSError, ValueError):
                return None
        return None

    @classmethod
    def _mime_body(cls, payload: object) -> str:
        text_parts: list[str] = []
        html_parts: list[str] = []
        stack: list[tuple[object, int]] = [(payload, 0)]
        seen = 0
        while stack and seen < _MAX_MIME_PARTS:
            value, depth = stack.pop()
            seen += 1
            if not isinstance(value, dict) or depth > _MAX_MIME_DEPTH:
                continue
            parts = value.get("parts")
            if isinstance(parts, list):
                stack.extend((part, depth + 1) for part in reversed(parts[:_MAX_MIME_PARTS]))
            filename = cls._string(value.get("filename"), 500)
            body = value.get("body")
            if filename or not isinstance(body, dict) or body.get("attachmentId") is not None:
                continue
            data_value = body.get("data")
            mime_type = (cls._string(value.get("mimeType"), 100) or "").casefold()
            if not isinstance(data_value, str) or len(data_value) > 100_000:
                continue
            try:
                padded = data_value + "=" * (-len(data_value) % 4)
                decoded = base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
            except (ValueError, UnicodeError):
                continue
            if mime_type == "text/plain":
                text_parts.append(decoded)
            elif mime_type == "text/html":
                html_parts.append(decoded)
        content = "\n".join(text_parts)
        if not content and html_parts:
            parser = _HTMLTextExtractor()
            parser.feed("\n".join(html_parts)[:100_000])
            content = "".join(parser.parts)
        clean = "\n".join(line.strip() for line in content.splitlines() if line.strip())
        return clean[:_MAX_REPLY_BODY]

    @classmethod
    def _event_datetime(cls, value: object) -> tuple[datetime | None, str]:
        if not isinstance(value, dict):
            return None, "UTC"
        timezone = cls._string(value.get("timeZone"), 100) or "UTC"
        date_time = cls._datetime(value.get("dateTime"))
        if date_time is not None:
            return date_time, timezone
        date_value = cls._string(value.get("date"), 10)
        if date_value is None:
            return None, timezone
        try:
            parsed_date = date.fromisoformat(date_value)
        except ValueError:
            return None, timezone
        return datetime.combine(parsed_date, time.min, tzinfo=UTC), timezone

    @staticmethod
    def _datetime(value: object) -> datetime | None:
        if not isinstance(value, str) or len(value) > 64:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)

    @classmethod
    def _calendar_address(cls, value: object) -> str | None:
        if not isinstance(value, dict):
            return None
        address = cls._string(value.get("email"), 320)
        if address is None or not _EMAIL.fullmatch(address):
            return None
        return address.casefold()

    @classmethod
    def _attendee_addresses(cls, value: object) -> set[str]:
        if not isinstance(value, list):
            return set()
        return {address for item in value[:100] if (address := cls._calendar_address(item)) is not None}

    @classmethod
    def _meeting_url(cls, value: object) -> str | None:
        url = cls._string(value, 2_048)
        if url is None:
            return None
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in {"meet.google.com", "hangouts.google.com"}:
            return None
        return url

    @classmethod
    def _message_ids(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [
            message_id
            for item in value
            if isinstance(item, dict) and (message_id := cls._string(item.get("id"), 255)) is not None
        ]

    @staticmethod
    def _domain(email: str) -> str:
        return email.rpartition("@")[2].casefold()

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @classmethod
    def _iso(cls, value: datetime) -> str:
        return cls._aware(value).isoformat().replace("+00:00", "Z")
