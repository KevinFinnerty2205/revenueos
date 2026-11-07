from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable, Collection
from datetime import UTC, date, datetime, time, timedelta
from hashlib import sha256
from typing import Literal, TypeVar, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.ai_contracts import NextBestActionArtifactContent
from revenueos.config import Settings
from revenueos.daily_contracts import (
    BriefingPreviewRequest,
    BriefingPreviewResponse,
    DailyAction,
    DailyActionSection,
    DailyAvailability,
    DailyDealAttention,
    DailyDealReason,
    DailyDealSection,
    DailyInteraction,
    DailyPipelineCurrency,
    DailyPipelineSummary,
    DailyPriority,
    DailyRecommendation,
    DailyResponse,
    DeliveryPreferenceResponse,
    DeliveryPreferenceUpdate,
)
from revenueos.daily_repositories import (
    DailyActionCounts,
    DailyActionRecord,
    DailyInteractionRecord,
    DailyOpportunityRecord,
    DailyPipelineRecords,
    DailyRecommendationRecord,
    DailyRepository,
)
from revenueos.database import set_private_user_database_context, set_tenant_database_context
from revenueos.domain import ConnectorKey
from revenueos.errors import PublicAPIError
from revenueos.methodology_contracts import MethodologyProjectionContent
from revenueos.models import (
    ConversationBriefingOutbox,
    ConversationDeliveryPreference,
    MethodologyProjection,
    RevenueBrainInsight,
)
from revenueos.pre_interaction_contracts import PreInteractionBriefContent
from revenueos.revenue_brain_reasoning_contracts import RevenueBrainInsightContent
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.daily")

T = TypeVar("T")
NEAR_TERM_INTERACTION_WINDOW = timedelta(hours=4)
UPCOMING_INTERACTION_WINDOW = timedelta(days=7)
AMBIGUOUS_BRIEFING_DELIVERY_FAILURE_CODES = frozenset({"delivery_outcome_unknown", "provider_outcome_unknown"})
RESTORABLE_BRIEFING_AUTHORITY_FAILURE_CODES = frozenset(
    {
        "delivery_authority_unavailable",
        "delivery_connection_reauthorisation_required",
        "delivery_provider_authority_unavailable",
    }
)
SUPPORTED_BRIEFING_DELIVERY_CONNECTOR_KEYS = frozenset(
    {
        ConnectorKey.MOCK_EMAIL.value,
        ConnectorKey.GOOGLE_WORKSPACE.value,
        ConnectorKey.MICROSOFT_365.value,
    }
)
DEAL_CLOSE_ATTENTION_WINDOW = timedelta(days=14)
DEAL_STALENESS_DAYS: dict[str, int] = {
    "qualification": 30,
    "discovery": 21,
    "evaluation": 14,
    "proposal": 10,
    "negotiation": 7,
    "procurement": 7,
    "other": 21,
}
NEGATIVE_REVENUE_BRAIN_CHANGES: dict[str, tuple[str, str]] = {
    "timeline_became_unclear": ("conflicting_evidence", "Timeline needs clarification."),
    "decision_maker_missing": ("methodology_gap", "Decision authority needs clarification."),
    "procurement_became_unclear": ("unresolved_risk", "Procurement steps need clarification."),
    "champion_weakened": ("unresolved_risk", "Champion support may need attention."),
    "champion_disappeared": ("unresolved_risk", "Champion coverage needs attention."),
    "next_step_weakened": ("next_action_pending", "The agreed next step needs attention."),
    "stakeholder_alignment_worsened": ("unresolved_risk", "Stakeholder alignment needs attention."),
    "technical_fit_worsened": ("unresolved_risk", "Technical fit needs attention."),
    "security_or_legal_blocker_introduced": ("unresolved_risk", "Security or legal work is blocking progress."),
    "objection_introduced": ("unresolved_risk", "A material objection needs attention."),
    "objection_strengthened": ("unresolved_risk", "A material objection has strengthened."),
    "objection_reopened": ("unresolved_risk", "A previously resolved objection needs attention again."),
    "competitive_pressure_increased": ("unresolved_risk", "Competitive pressure has increased."),
    "stakeholder_stance_worsened": ("unresolved_risk", "A stakeholder concern needs attention."),
    "economic_buyer_became_unclear": ("conflicting_evidence", "Economic buyer access needs clarification."),
    "technical_buyer_became_unclear": ("conflicting_evidence", "Technical buyer coverage needs clarification."),
    "blocker_emerged": ("unresolved_risk", "A material blocker was identified."),
    "risk_introduced": ("unresolved_risk", "A material risk was identified."),
    "risk_severity_increased": ("unresolved_risk", "A current risk has become more serious."),
    "open_question_importance_increased": ("next_action_pending", "An important customer question remains open."),
    "action_item_overdue_evidence": ("overdue_action", "A customer commitment appears overdue."),
}


def enabled_briefing_delivery_connector_keys(settings: Settings) -> frozenset[str]:
    """Return the connector keys for which this process can deliver briefings."""

    if not settings.feature_briefing_delivery_enabled:
        return frozenset()
    if settings.briefing_delivery_transport_mode == "local":
        return SUPPORTED_BRIEFING_DELIVERY_CONNECTOR_KEYS
    enabled: set[str] = set()
    if settings.feature_google_workspace_enabled:
        enabled.add(ConnectorKey.GOOGLE_WORKSPACE.value)
    if settings.feature_microsoft_365_enabled:
        enabled.add(ConnectorKey.MICROSOFT_365.value)
    return frozenset(enabled)


class RevenueOSDailyService:
    """Deterministically compose the current user's bounded day plan."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
        *,
        delivery_connector_keys: Collection[str] | None = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.delivery_connector_keys = frozenset(
            delivery_connector_keys
            if delivery_connector_keys is not None
            else enabled_briefing_delivery_connector_keys(settings)
        )
        self.repository = DailyRepository(session)

    async def get_delivery_preferences(self) -> DeliveryPreferenceResponse:
        preference = await self.repository.delivery_preference(
            self.tenant.organisation_id,
            self.tenant.user_id,
        )
        return self._preference_response(preference)

    async def save_delivery_preferences(
        self,
        request: DeliveryPreferenceUpdate,
    ) -> DeliveryPreferenceResponse:
        timezone = self._timezone(request.timezone)
        preference = await self.repository.delivery_preference(
            self.tenant.organisation_id,
            self.tenant.user_id,
            for_update=True,
        )
        affected_kinds: set[Literal["morning_digest", "pre_meeting"]] = (
            {"morning_digest", "pre_meeting"} if preference is None else set()
        )
        if preference is None:
            if request.expected_lock_version != 0:
                raise self._preference_conflict()
            preference = ConversationDeliveryPreference(
                id=uuid4(),
                organisation_id=self.tenant.organisation_id,
                user_id=self.tenant.user_id,
                lock_version=1,
            )
            self.session.add(preference)
        else:
            if preference.lock_version != request.expected_lock_version:
                raise self._preference_conflict()
            if preference.timezone != timezone.key:
                affected_kinds.update(("morning_digest", "pre_meeting"))
            if (
                preference.morning_digest_enabled != request.morning_digest_enabled
                or preference.morning_digest_time != request.morning_digest_time
            ):
                affected_kinds.add("morning_digest")
            if (
                preference.pre_meeting_enabled != request.pre_meeting_enabled
                or preference.pre_meeting_minutes != request.pre_meeting_minutes
            ):
                affected_kinds.add("pre_meeting")
            preference.lock_version += 1
        preference.timezone = timezone.key
        preference.morning_digest_enabled = request.morning_digest_enabled
        preference.morning_digest_time = request.morning_digest_time
        preference.pre_meeting_enabled = request.pre_meeting_enabled
        preference.pre_meeting_minutes = request.pre_meeting_minutes
        if request.import_from_browser:
            preference.imported_from_browser_at = datetime.now(UTC)
        try:
            await self.session.flush()
            if affected_kinds:
                await self._reconcile_delivery_schedule(preference, affected_kinds)
            await self.session.refresh(preference)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise self._preference_conflict() from exc
        return self._preference_response(preference)

    async def prepare_briefing_preview(
        self,
        request: BriefingPreviewRequest,
        *,
        now: datetime | None = None,
    ) -> BriefingPreviewResponse:
        return await self._prepare_briefing_outbox(
            request,
            delivery_intent="preview",
            now=now,
        )

    async def schedule_delivery_briefings(self, *, now: datetime | None = None) -> int:
        """Materialise the next authorised rows from explicitly saved preferences.

        This is invoked by the existing worker while its delivery feature gate is
        enabled. It writes no row for implicit defaults and never selects a
        transport; connector authority is rechecked only when a due row is claimed.
        """

        generated_at = (now or datetime.now(UTC)).astimezone(UTC)
        preference = await self.repository.delivery_preference(
            self.tenant.organisation_id,
            self.tenant.user_id,
        )
        if preference is None:
            return 0
        created = 0
        if preference.morning_digest_enabled:
            response = await self._prepare_briefing_outbox(
                BriefingPreviewRequest(kind="morning_digest"),
                delivery_intent="scheduled",
                now=generated_at,
            )
            created += int(not response.duplicate_suppressed)
            await self._restore_worker_scope()
        if preference.pre_meeting_enabled:
            interaction_ids = await self.repository.upcoming_briefing_interaction_ids(
                self.tenant.organisation_id,
                self.tenant.user_id,
                starts_after=generated_at,
                starts_before=generated_at + UPCOMING_INTERACTION_WINDOW,
                delivery_connector_keys=self.delivery_connector_keys,
            )
            for interaction_id in interaction_ids:
                try:
                    response = await self._prepare_briefing_outbox(
                        BriefingPreviewRequest(kind="pre_meeting", interaction_id=interaction_id),
                        delivery_intent="scheduled",
                        now=generated_at,
                    )
                except PublicAPIError as exc:
                    await self._restore_worker_scope()
                    if exc.code in {
                        "interaction_cancelled",
                        "interaction_not_found",
                        "interaction_not_scheduled",
                    }:
                        continue
                    raise
                created += int(not response.duplicate_suppressed)
                await self._restore_worker_scope()
        return created

    async def _restore_worker_scope(self) -> None:
        """Restore transaction-local RLS scope after an idempotent row commit."""

        await set_tenant_database_context(self.session, self.tenant.organisation_id)
        await set_private_user_database_context(self.session, self.tenant.user_id)

    async def _prepare_briefing_outbox(
        self,
        request: BriefingPreviewRequest,
        *,
        delivery_intent: Literal["preview", "scheduled"],
        now: datetime | None = None,
    ) -> BriefingPreviewResponse:
        preference = await self.repository.delivery_preference(
            self.tenant.organisation_id,
            self.tenant.user_id,
        )
        timezone_name = preference.timezone if preference is not None else "UTC"
        morning_digest_enabled = preference.morning_digest_enabled if preference is not None else True
        morning_digest_time = preference.morning_digest_time if preference is not None else "07:30"
        pre_meeting_enabled = preference.pre_meeting_enabled if preference is not None else True
        pre_meeting_minutes = preference.pre_meeting_minutes if preference is not None else 30
        generated_at = (now or datetime.now(UTC)).astimezone(UTC)
        source_observed_at: datetime | None = None
        if request.kind == "morning_digest":
            if not morning_digest_enabled:
                raise PublicAPIError("briefing_disabled", "Morning briefing delivery is disabled.", 409)
            daily = await self.read(timezone_name, now=generated_at)
            subject = self._morning_digest_subject(daily)
            body = self._morning_digest_body(daily)
            local_time = time.fromisoformat(morning_digest_time)
            prepared_for_at = datetime.combine(daily.local_date, local_time, self._timezone(timezone_name)).astimezone(
                UTC
            )
            href = "/"
            interaction_id = None
            logical_key = f"morning:{daily.local_date.isoformat()}"
        else:
            if not pre_meeting_enabled:
                raise PublicAPIError("briefing_disabled", "Pre-meeting briefing delivery is disabled.", 409)
            if request.interaction_id is None:
                raise PublicAPIError(
                    "interaction_required",
                    "Choose an interaction before previewing a pre-meeting briefing.",
                    422,
                )
            record = await self.repository.briefing_interaction(
                self.tenant.organisation_id,
                self.tenant.user_id,
                request.interaction_id,
            )
            if record is None:
                raise PublicAPIError("interaction_not_found", "The requested interaction was not found.", 404)
            prior = await self.repository.active_interaction_briefings(
                self.tenant.organisation_id,
                self.tenant.user_id,
                request.interaction_id,
                delivery_intent=delivery_intent,
            )
            provider_cancelled = record.provider_event is not None and (
                record.provider_event.state != "active" or record.provider_connection_status != "active"
            )
            if record.interaction.lifecycle_status == "cancelled" or provider_cancelled:
                for item in prior:
                    self._reset_explicit_delivery_state(item, status="cancelled")
                await self.session.commit()
                raise PublicAPIError("interaction_cancelled", "Cancelled interactions do not receive briefings.", 409)
            starts_at = (
                record.provider_event.start_at
                if record.provider_event is not None
                else record.interaction.scheduled_start_at
            )
            if starts_at is None:
                raise PublicAPIError(
                    "interaction_not_scheduled",
                    "Add a scheduled start before preparing a pre-meeting briefing.",
                    409,
                )
            aware_start = starts_at.replace(tzinfo=UTC) if starts_at.tzinfo is None else starts_at.astimezone(UTC)
            content = (
                PreInteractionBriefContent.model_validate_json(json.dumps(record.brief.content_json))
                if record.brief is not None
                else None
            )
            subject = f"Prepare: {record.interaction.title}"
            body = self._pre_meeting_body(
                record.interaction.title,
                record.company_name,
                record.opportunity_name,
                content,
            )
            prepared_for_at = aware_start - timedelta(minutes=pre_meeting_minutes)
            href = f"/conversations/{record.interaction.id}#preparation"
            interaction_id = record.interaction.id
            logical_key = f"pre:{record.interaction.id}"
            source_timestamps = [record.interaction.updated_at]
            if record.company_updated_at is not None:
                source_timestamps.append(record.company_updated_at)
            if record.opportunity_updated_at is not None:
                source_timestamps.append(record.opportunity_updated_at)
            if record.provider_event is not None:
                source_timestamps.append(record.provider_event.last_synced_at)
            if record.brief is not None:
                source_timestamps.append(record.brief.created_at)
            source_observed_at = max(self._aware_utc(value) for value in source_timestamps)
        # The source fingerprint describes the complete immutable delivery
        # envelope, not merely a subset of its upstream inputs. This ensures a
        # title, linked context, rendering, schedule, timezone, or body change
        # produces a distinct operation even when the upstream brief version is
        # otherwise unchanged.
        source_parts: tuple[object, ...] = (
            subject,
            body,
            href,
            prepared_for_at.isoformat(),
            timezone_name,
        )
        fingerprint = sha256(
            json.dumps(source_parts, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()
        intent_prefix = "preview" if delivery_intent == "preview" else "delivery"
        intent_logical_key = f"{intent_prefix}:{logical_key}"
        deduplication_key = f"{intent_logical_key}:{fingerprint[:24]}"
        operation_prefix = f"{intent_prefix}_"
        operation_digest = sha256(
            f"{self.tenant.organisation_id}:{self.tenant.user_id}:{deduplication_key}".encode()
        ).hexdigest()
        operation_key = f"{operation_prefix}{operation_digest[: 64 - len(operation_prefix)]}"
        existing = await self.repository.briefing_by_key(
            self.tenant.organisation_id,
            self.tenant.user_id,
            deduplication_key,
        )
        if existing is not None:
            if existing.status in {"queued", "sending", "sent", "failed"}:
                source_observation_needed = (
                    source_observed_at is not None
                    and self._aware_utc(existing.source_observed_at) < source_observed_at
                    and (
                        existing.status == "queued"
                        or (existing.status == "sending" and existing.submission_started_at is None)
                        or (
                            existing.status == "failed"
                            and existing.failure_code not in AMBIGUOUS_BRIEFING_DELIVERY_FAILURE_CODES
                        )
                    )
                )
                operation_key_changed = False
                if existing.submission_started_at is None and existing.operation_key != operation_key:
                    existing.operation_key = operation_key
                    operation_key_changed = True
                if source_observation_needed:
                    # A source freshness change can be unrelated to the exact
                    # delivery envelope. Advance only the observation cursor so
                    # discovery does not hot-loop; retain attempts, Retry-After,
                    # and the terminal failure itself.
                    existing.source_observed_at = cast(datetime, source_observed_at)
                if source_observation_needed or operation_key_changed:
                    await self.session.commit()
                return self._briefing_response(existing, duplicate_suppressed=True)
            if existing.status in {"superseded", "cancelled"}:
                if delivery_intent == "scheduled" and existing.failure_code is not None:
                    # A worker cancellation records a durable authority/source
                    # reason and must not become a tight recreate/claim loop.
                    # Preference and calendar reconciliations leave no failure
                    # code, so an explicit later change can still reactivate.
                    authority_restored = (
                        existing.failure_code in RESTORABLE_BRIEFING_AUTHORITY_FAILURE_CODES
                        and await self.repository.has_active_delivery_connection(
                            self.tenant.organisation_id,
                            self.tenant.user_id,
                            delivery_connector_keys=self.delivery_connector_keys,
                        )
                    )
                    if not authority_restored:
                        if (
                            source_observed_at is not None
                            and self._aware_utc(existing.source_observed_at) < source_observed_at
                        ):
                            existing.source_observed_at = source_observed_at
                            await self.session.commit()
                        return self._briefing_response(existing, duplicate_suppressed=True)
                fence = await self._supersede_active_briefings(
                    logical_key=intent_logical_key,
                    interaction_id=interaction_id,
                    delivery_intent=delivery_intent,
                    except_id=existing.id,
                )
                if fence is not None:
                    await self.session.commit()
                    return self._briefing_response(fence, duplicate_suppressed=True)
                existing.status = "queued"
                existing.subject = subject
                existing.body_text = body
                existing.href = href
                existing.prepared_for_at = prepared_for_at
                existing.delivery_timezone = timezone_name
                existing.attempt_count = 0
                existing.next_attempt_at = None
                existing.worker_id = None
                existing.lease_expires_at = None
                existing.connection_id = None
                existing.submission_started_at = None
                existing.provider_message_id = None
                existing.sent_at = None
                existing.failed_at = None
                existing.failure_code = None
                existing.operation_key = operation_key
                existing.source_observed_at = source_observed_at or generated_at
                await self.session.commit()
                return self._briefing_response(existing, duplicate_suppressed=False)
        fence = await self._supersede_active_briefings(
            logical_key=intent_logical_key,
            interaction_id=interaction_id,
            delivery_intent=delivery_intent,
        )
        if fence is not None:
            await self.session.commit()
            return self._briefing_response(fence, duplicate_suppressed=True)
        outbox = ConversationBriefingOutbox(
            id=uuid4(),
            organisation_id=self.tenant.organisation_id,
            user_id=self.tenant.user_id,
            interaction_id=interaction_id,
            kind=request.kind,
            delivery_intent=delivery_intent,
            status="queued",
            deduplication_key=deduplication_key,
            source_fingerprint=fingerprint,
            source_observed_at=source_observed_at or generated_at,
            subject=subject,
            body_text=body,
            href=href,
            prepared_for_at=prepared_for_at,
            delivery_timezone=timezone_name,
            operation_key=operation_key,
            max_attempts=self.settings.worker_default_max_attempts,
        )
        self.session.add(outbox)
        try:
            await self.session.flush()
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            await set_tenant_database_context(self.session, self.tenant.organisation_id)
            await set_private_user_database_context(self.session, self.tenant.user_id)
            existing = await self.repository.briefing_by_key(
                self.tenant.organisation_id,
                self.tenant.user_id,
                deduplication_key,
            )
            if existing is None:
                raise PublicAPIError(
                    "briefing_conflict",
                    "The briefing could not be prepared safely.",
                    409,
                ) from exc
            return self._briefing_response(existing, duplicate_suppressed=True)
        return self._briefing_response(outbox, duplicate_suppressed=False)

    async def _supersede_active_briefings(
        self,
        *,
        logical_key: str,
        interaction_id: UUID | None,
        delivery_intent: Literal["preview", "scheduled"],
        except_id: UUID | None = None,
    ) -> ConversationBriefingOutbox | None:
        if delivery_intent == "scheduled":
            rows = (
                await self.repository.scheduled_interaction_briefings(
                    self.tenant.organisation_id,
                    self.tenant.user_id,
                    interaction_id,
                )
                if interaction_id is not None
                else await self.repository.scheduled_morning_briefings(
                    self.tenant.organisation_id,
                    self.tenant.user_id,
                    logical_key,
                )
            )
            fence = next((row for row in rows if self._is_delivery_fence(row)), None)
            if fence is not None:
                return fence
        else:
            rows = (
                await self.repository.active_interaction_briefings(
                    self.tenant.organisation_id,
                    self.tenant.user_id,
                    interaction_id,
                    delivery_intent=delivery_intent,
                )
                if interaction_id is not None
                else await self.repository.active_morning_briefings(
                    self.tenant.organisation_id,
                    self.tenant.user_id,
                    logical_key,
                    delivery_intent=delivery_intent,
                )
            )
        for row in rows:
            if row.id == except_id:
                continue
            safe_terminal = row.status == "cancelled" or (
                row.status == "failed" and row.failure_code not in AMBIGUOUS_BRIEFING_DELIVERY_FAILURE_CODES
            )
            if (
                row.status != "queued"
                and not (row.status == "sending" and row.submission_started_at is None)
                and not safe_terminal
            ):
                continue
            row.status = "superseded"
            row.worker_id = None
            row.lease_expires_at = None
            row.connection_id = None
            row.submission_started_at = None
            row.next_attempt_at = None
            row.failed_at = None
            row.failure_code = None
        return None

    @staticmethod
    def _is_delivery_fence(row: ConversationBriefingOutbox) -> bool:
        return (
            row.status == "sent"
            or (row.status == "sending" and row.submission_started_at is not None)
            or (row.status == "failed" and row.failure_code in AMBIGUOUS_BRIEFING_DELIVERY_FAILURE_CODES)
        )

    @staticmethod
    def _preference_response(
        preference: ConversationDeliveryPreference | None,
    ) -> DeliveryPreferenceResponse:
        if preference is None:
            return DeliveryPreferenceResponse(
                exists=False,
                lock_version=0,
                timezone="UTC",
                morning_digest_enabled=True,
                morning_digest_time="07:30",
                pre_meeting_enabled=True,
                pre_meeting_minutes=30,
            )
        return DeliveryPreferenceResponse(
            exists=True,
            lock_version=preference.lock_version,
            timezone=preference.timezone,
            morning_digest_enabled=preference.morning_digest_enabled,
            morning_digest_time=preference.morning_digest_time,
            pre_meeting_enabled=preference.pre_meeting_enabled,
            pre_meeting_minutes=preference.pre_meeting_minutes,
            imported_from_browser_at=preference.imported_from_browser_at,
            updated_at=preference.updated_at,
        )

    @staticmethod
    def _preference_conflict() -> PublicAPIError:
        return PublicAPIError(
            "delivery_preference_conflict",
            "Briefing preferences changed in another session. Reload before saving.",
            409,
        )

    @staticmethod
    def _briefing_response(
        outbox: ConversationBriefingOutbox,
        *,
        duplicate_suppressed: bool,
    ) -> BriefingPreviewResponse:
        return BriefingPreviewResponse(
            id=outbox.id,
            kind=cast(Literal["morning_digest", "pre_meeting"], outbox.kind),
            status=cast(
                Literal["queued", "sending", "sent", "failed", "superseded", "cancelled"],
                outbox.status,
            ),
            subject=outbox.subject,
            body_text=outbox.body_text,
            href=outbox.href,
            prepared_for_at=outbox.prepared_for_at,
            duplicate_suppressed=duplicate_suppressed,
        )

    async def _reconcile_delivery_schedule(
        self,
        preference: ConversationDeliveryPreference,
        affected_kinds: set[Literal["morning_digest", "pre_meeting"]],
    ) -> None:
        rows = await self.repository.active_owner_briefings(
            self.tenant.organisation_id,
            self.tenant.user_id,
            kinds=tuple(sorted(affected_kinds)),
        )
        for row in rows:
            if row.kind == "morning_digest":
                if not preference.morning_digest_enabled:
                    self._reset_explicit_delivery_state(row, status="cancelled")
                    continue
                # Briefing rows are exact-content envelopes. A preference edit
                # supersedes the old envelope so the scheduler rematerialises
                # subject/body/fingerprint and due time atomically.
                self._reset_explicit_delivery_state(row, status="superseded")
                continue
            if not preference.pre_meeting_enabled or row.interaction_id is None:
                self._reset_explicit_delivery_state(row, status="cancelled")
                continue
            self._reset_explicit_delivery_state(row, status="superseded")

    @staticmethod
    def _reset_explicit_delivery_state(
        row: ConversationBriefingOutbox,
        *,
        status: Literal["queued", "superseded", "cancelled"],
    ) -> None:
        """Clear retry/claim state after an explicit user or source transition."""

        row.status = status
        row.attempt_count = 0
        row.next_attempt_at = None
        row.worker_id = None
        row.lease_expires_at = None
        row.connection_id = None
        row.submission_started_at = None
        row.provider_message_id = None
        row.sent_at = None
        row.failed_at = None
        row.failure_code = None

    @staticmethod
    def _aware_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @staticmethod
    def _morning_digest_subject(daily: DailyResponse) -> str:
        account_names = list(
            dict.fromkeys(
                cleaned_name
                for interaction in daily.today_interactions
                if interaction.company_name and (cleaned_name := " ".join(interaction.company_name.split()))
            )
        )
        truncated = daily.total_today_interactions > len(daily.today_interactions)
        if not account_names:
            suffix = " + more" if truncated else ""
            return f"Prep for today: your conversations{suffix}"
        visible_accounts = ", ".join(account_names[:2])
        remaining = len(account_names) - 2
        suffix = " + more" if truncated else (f" +{remaining}" if remaining > 0 else "")
        return f"Prep for today: {visible_accounts}{suffix}"[:500]

    @staticmethod
    def _morning_digest_body(daily: DailyResponse) -> str:
        lines = [f"Good morning, {daily.user_display_name}.", ""]
        if daily.today_interactions:
            count = daily.total_today_interactions
            noun = "conversation" if count == 1 else "conversations"
            shown_count = len(daily.today_interactions)
            introduction = (
                f"You have {count} {noun} today. Here are the next {shown_count}."
                if count > shown_count
                else f"You have {count} {noun} today. Here’s what to know before each one."
            )
            lines.extend(
                (
                    introduction,
                    "",
                )
            )
            timezone = ZoneInfo(daily.timezone)
            for interaction in daily.today_interactions:
                local_start = interaction.starts_at.astimezone(timezone)
                local_time = local_start.strftime("%I:%M %p").lstrip("0")
                account = interaction.company_name or "General conversation"
                lines.extend(
                    (
                        f"{local_time} · {account}",
                        interaction.title,
                        *(
                            (f"With: {RevenueOSDailyService._participant_summary(interaction.participant_names)}",)
                            if interaction.participant_names
                            else ()
                        ),
                        interaction.context,
                        f"{interaction.cta_label}: {interaction.href}",
                        "",
                    )
                )
            remaining_conversations = count - shown_count
            if remaining_conversations > 0:
                remaining_noun = "conversation" if remaining_conversations == 1 else "conversations"
                lines.extend(
                    (
                        f"Open Oryntela for {remaining_conversations} more {remaining_noun}.",
                        "",
                    )
                )
        else:
            lines.extend(("You have no scheduled conversations today.", ""))
        if daily.top_priority is not None:
            lines.extend(
                (
                    "Top priority",
                    f"{daily.top_priority.title} — {daily.top_priority.reason}",
                    f"Open: {daily.top_priority.href}",
                    "",
                )
            )
        if daily.actions.attention_count:
            lines.append(f"Follow-up: {daily.actions.attention_count} item(s) need attention.")
        if daily.deal_attention.attention_count:
            lines.append(f"Deal attention: {daily.deal_attention.attention_count} opportunity item(s).")
        if daily.caught_up:
            lines.append("You’re caught up. No current conversation work needs attention.")
        lines.extend(("", "Open Oryntela to review the source records before acting."))
        return "\n".join(lines)

    @staticmethod
    def _participant_summary(names: list[str]) -> str:
        visible = ", ".join(names[:3])
        remaining = len(names) - 3
        return f"{visible} +{remaining}" if remaining > 0 else visible

    @staticmethod
    def _pre_meeting_body(
        title: str,
        company_name: str | None,
        opportunity_name: str | None,
        content: PreInteractionBriefContent | None,
    ) -> str:
        lines = [title]
        context_label = opportunity_name or company_name
        if context_label:
            lines.append(context_label)
        lines.append("")
        if content is None:
            lines.extend(
                (
                    "No generated brief is available yet.",
                    "Open the conversation to generate and review preparation from authorised records.",
                )
            )
            return "\n".join(lines)
        lines.extend((content.headline, "", content.account_context, "", "Objectives"))
        lines.extend(f"- {item.objective}" for item in content.objectives)
        lines.extend(("", "Questions to ask"))
        lines.extend(f"- {item.question}" for item in content.questions_to_ask)
        if content.risks_to_watch:
            lines.extend(("", "Risks to watch"))
            lines.extend(f"- {item.risk}" for item in content.risks_to_watch)
        lines.extend(("", "Review the full brief and its source labels in Oryntela before the conversation."))
        return "\n".join(lines)

    async def read(self, timezone_name: str | None, *, now: datetime | None = None) -> DailyResponse:
        timezone = self._timezone(timezone_name)
        generated_at = (now or datetime.now(UTC)).astimezone(UTC)
        local_now = generated_at.astimezone(timezone)
        local_date = local_now.date()
        start_at = datetime.combine(local_date, time.min, timezone).astimezone(UTC)
        end_at = datetime.combine(local_date + timedelta(days=1), time.min, timezone).astimezone(UTC)
        next_month = date(
            local_date.year + (local_date.month == 12), 1 if local_date.month == 12 else local_date.month + 1, 1
        )
        month_start = local_date.replace(day=1)

        display_name = await self.repository.user_display_name(self.tenant.user_id)
        interaction_records = await self._safe_source(
            "interactions",
            lambda: self.repository.interactions(
                self.tenant.organisation_id,
                self.tenant.user_id,
                start_at=start_at,
                upcoming_end_at=end_at + UPCOMING_INTERACTION_WINDOW,
            ),
        )
        action_source = (
            await self._safe_source(
                "actions",
                lambda: self.repository.actions(
                    self.tenant.organisation_id,
                    self.tenant.user_id,
                    start_at=start_at,
                    end_at=end_at,
                    now=generated_at,
                ),
            )
            if self.settings.feature_action_layer_enabled
            else ([], DailyActionCounts(0, 0, 0, 0, 0))
        )
        opportunity_records = await self._safe_source(
            "opportunities",
            lambda: self.repository.opportunities(self.tenant.organisation_id, self.tenant.user_id),
        )
        pipeline_records = await self._safe_source(
            "pipeline",
            lambda: self.repository.pipeline(
                self.tenant.organisation_id,
                self.tenant.user_id,
                month_start=month_start,
                next_month_start=next_month,
            ),
        )

        opportunity_ids = tuple(record.opportunity.id for record in opportunity_records or [])
        projection_rows = (
            await self._safe_source(
                "methodology",
                lambda: self.repository.methodology_projections(self.tenant.organisation_id, opportunity_ids),
            )
            if self.settings.feature_sales_methodology_enabled and opportunity_records is not None
            else ([] if opportunity_records is not None else None)
        )
        insight_rows = (
            await self._safe_source(
                "revenue_brain",
                lambda: self.repository.revenue_brain_insights(self.tenant.organisation_id, opportunity_ids),
            )
            if self.settings.feature_revenue_brain_enabled and opportunity_records is not None
            else ([] if opportunity_records is not None else None)
        )
        recommendation_rows = (
            await self._safe_source(
                "recommendations",
                lambda: self.repository.next_best_actions(self.tenant.organisation_id, opportunity_ids),
            )
            if self.settings.feature_revenue_brain_enabled and opportunity_records is not None
            else ([] if opportunity_records is not None else None)
        )

        projections = self._projection_gaps(projection_rows or [])
        brain_reasons = self._brain_reasons(insight_rows or [])
        recommendations = self._recommendations(recommendation_rows or [])
        interactions = self._interactions(interaction_records or [], end_at=end_at, methodology_gaps=projections)
        today_interactions = [item for item in interactions if item.starts_at < end_at][:5]
        next_interaction = next((item for item in interactions if item.starts_at >= generated_at), None)
        if next_interaction is None:
            next_interaction = next(
                (item for item in today_interactions if item.preparation_state in {"active", "capture_needed"}),
                None,
            )

        if action_source is None:
            action_records: list[DailyActionRecord] = []
            action_counts = DailyActionCounts(0, 0, 0, 0, 0)
        else:
            action_records, action_counts = action_source
        actions = self._actions(action_records, action_counts, generated_at, start_at, end_at)
        surfaced_action_opportunities = {item.opportunity_id for item in actions.items}
        deal_attention = self._deal_attention(
            opportunity_records or [],
            action_records,
            projections,
            brain_reasons,
            generated_at,
            local_date,
            surfaced_action_opportunities,
            recommendations,
        )
        pipeline = self._pipeline(pipeline_records)
        availability = DailyAvailability(
            interactions=interaction_records is not None,
            actions=action_source is not None and self.settings.feature_action_layer_enabled,
            deal_attention=opportunity_records is not None,
            pipeline=pipeline_records is not None,
            recommendations=recommendation_rows is not None and self.settings.feature_revenue_brain_enabled,
            methodology=projection_rows is not None and self.settings.feature_sales_methodology_enabled,
            revenue_brain=insight_rows is not None and self.settings.feature_revenue_brain_enabled,
        )
        source_failure = any(
            (
                interaction_records is None,
                self.settings.feature_action_layer_enabled and action_source is None,
                opportunity_records is None,
                pipeline_records is None,
                self.settings.feature_sales_methodology_enabled and projection_rows is None,
                self.settings.feature_revenue_brain_enabled and insight_rows is None,
                self.settings.feature_revenue_brain_enabled and recommendation_rows is None,
            )
        )
        top_priority = self._top_priority(
            interactions,
            actions.items,
            deal_attention.items,
            recommendations,
            generated_at,
        )
        caught_up = (
            not source_failure
            and top_priority is None
            and actions.attention_count == 0
            and deal_attention.attention_count == 0
            and not today_interactions
        )
        response = DailyResponse(
            generated_at=generated_at,
            local_date=local_date,
            timezone=timezone.key,
            user_display_name=display_name,
            top_priority=top_priority,
            next_interaction=next_interaction,
            today_interactions=today_interactions,
            total_today_interactions=sum(item.starts_at < end_at for item in interactions),
            actions=actions,
            deal_attention=deal_attention,
            pipeline=pipeline,
            recommendations=recommendations,
            availability=availability,
            # On a partial source failure, do not misrepresent an established user as brand new.
            has_opportunities=opportunity_records is None or bool(opportunity_records),
            caught_up=caught_up,
        )
        logger.info(
            "daily_opened",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "user_id": str(self.tenant.user_id),
                "local_date": local_date.isoformat(),
                "timezone": timezone.key,
                "top_priority_type": top_priority.kind if top_priority is not None else None,
                "today_interaction_count": response.total_today_interactions,
                "action_attention_count": actions.attention_count,
                "deal_attention_count": deal_attention.attention_count,
                "partial": source_failure,
            },
        )
        return response

    async def _safe_source(self, name: str, loader: Callable[[], Awaitable[T]]) -> T | None:
        try:
            async with self.session.begin_nested():
                return await loader()
        except SQLAlchemyError:
            logger.warning(
                "daily_source_unavailable",
                extra={
                    "organisation_id": str(self.tenant.organisation_id),
                    "user_id": str(self.tenant.user_id),
                    "source": name,
                },
            )
            return None

    @staticmethod
    def _timezone(timezone_name: str | None) -> ZoneInfo:
        candidate = timezone_name or "UTC"
        try:
            return ZoneInfo(candidate)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise PublicAPIError(
                "invalid_timezone",
                "Choose a valid timezone before loading Oryntela Daily.",
                422,
            ) from exc

    def _interactions(
        self,
        records: list[DailyInteractionRecord],
        *,
        end_at: datetime,
        methodology_gaps: dict[UUID, DailyDealReason],
    ) -> list[DailyInteraction]:
        items: list[DailyInteraction] = []
        for record in records:
            interaction = record.interaction
            raw_starts_at = interaction.actual_start_at or interaction.scheduled_start_at or interaction.created_at
            starts_at = (
                raw_starts_at.replace(tzinfo=UTC) if raw_starts_at.tzinfo is None else raw_starts_at.astimezone(UTC)
            )
            state: Literal["prepared", "not_prepared", "active", "capture_needed", "complete"]
            if interaction.lifecycle_status == "in_progress":
                state = "active"
                cta_label = "Open Companion"
                href = f"/conversations/{interaction.id}/workspace"
            elif interaction.lifecycle_status == "completed" and not record.intelligence_exists:
                state = "capture_needed"
                cta_label = "Capture what happened"
                href = f"/conversations/{interaction.id}#debrief"
            elif interaction.lifecycle_status == "completed":
                state = "complete"
                cta_label = "Open interaction"
                href = f"/conversations/{interaction.id}"
            elif record.brief_generated_at is not None:
                state = "prepared"
                cta_label = "Prepare"
                href = f"/conversations/{interaction.id}#preparation"
            else:
                state = "not_prepared"
                cta_label = "Prepare for meeting"
                href = f"/conversations/{interaction.id}#preparation"
            context = (
                methodology_gaps[interaction.opportunity_id].text
                if interaction.opportunity_id in methodology_gaps and starts_at < end_at
                else record.opportunity_name or record.company_name or "Customer context is ready to review."
            )
            items.append(
                DailyInteraction(
                    id=interaction.id,
                    title=interaction.title,
                    company_id=interaction.company_id,
                    company_name=record.company_name,
                    opportunity_id=interaction.opportunity_id,
                    opportunity_name=record.opportunity_name,
                    participant_names=list(record.participant_names),
                    interaction_type=interaction.interaction_type,
                    lifecycle_status=interaction.lifecycle_status,
                    starts_at=starts_at,
                    preparation_state=state,
                    context=context,
                    cta_label=cta_label,
                    href=href,
                )
            )
        return items

    @staticmethod
    def _actions(
        records: list[DailyActionRecord],
        counts: DailyActionCounts,
        now: datetime,
        start_at: datetime,
        end_at: datetime,
    ) -> DailyActionSection:
        def timing(record: DailyActionRecord) -> Literal["overdue", "due_today", "upcoming", "no_due_date"]:
            due_at = record.version.proposed_due_at
            if due_at is None:
                return "no_due_date"
            aware_due = due_at.replace(tzinfo=UTC) if due_at.tzinfo is None else due_at.astimezone(UTC)
            if aware_due < now:
                return "overdue"
            if start_at <= aware_due < end_at:
                return "due_today"
            return "upcoming"

        timing_rank = {"overdue": 0, "due_today": 1, "upcoming": 2, "no_due_date": 3}
        priority_rank = {"high": 0, "normal": 1, "low": 2}
        ranked = sorted(
            records,
            key=lambda item: (
                timing_rank[timing(item)],
                priority_rank[item.proposal.priority],
                item.version.proposed_due_at or datetime.max.replace(tzinfo=UTC),
                -item.proposal.generated_at.timestamp(),
                str(item.proposal.id),
            ),
        )
        items: list[DailyAction] = []
        for record in ranked[:5]:
            if record.proposal.opportunity_id is None:
                continue
            state, state_label, cta_label = RevenueOSDailyService._action_state(record)
            items.append(
                DailyAction(
                    id=record.proposal.id,
                    title=record.version.title,
                    opportunity_id=record.proposal.opportunity_id,
                    interaction_id=record.proposal.interaction_id,
                    opportunity_name=record.opportunity_name,
                    company_name=record.company_name,
                    priority=cast(Literal["high", "normal", "low"], record.proposal.priority),
                    review_status=cast(Literal["proposed", "edited", "approved"], record.proposal.status),
                    timing=timing(record),
                    due_at=record.version.proposed_due_at,
                    state=state,
                    state_label=state_label,
                    cta_label=cta_label,
                    href=(
                        f"/conversations/{record.proposal.interaction_id}#follow-up"
                        if record.proposal.interaction_id is not None
                        else "/conversations"
                    ),
                )
            )
        return DailyActionSection(
            attention_count=counts.attention,
            overdue_count=counts.overdue,
            due_today_count=counts.due_today,
            pending_review_count=counts.pending_review,
            approved_open_count=counts.approved_open,
            items=items,
            truncated=counts.attention > len(items),
        )

    @staticmethod
    def _action_state(
        record: DailyActionRecord,
    ) -> tuple[
        Literal[
            "needs_review",
            "approved_not_complete",
            "simulation_in_progress",
            "simulation_completed_action_open",
            "simulation_needs_review",
        ],
        str,
        str,
    ]:
        if record.proposal.status in {"proposed", "edited"}:
            return "needs_review", "Needs review", "Review"
        if record.execution_status in {"queued", "executing"}:
            return "simulation_in_progress", "Simulation in progress", "Review execution"
        if record.execution_status == "simulated_success":
            return (
                "simulation_completed_action_open",
                "Simulation completed — action still open",
                "Review execution",
            )
        if record.execution_status in {
            "failed_retryable",
            "failed_permanent",
            "cancelled",
            "unknown_external_state",
        }:
            return "simulation_needs_review", "Simulation needs review", "Review execution"
        return (
            "approved_not_complete",
            "Approved — not complete",
            "Complete" if record.proposal.audience == "internal" else "Review execution",
        )

    @staticmethod
    def _projection_gaps(rows: list[MethodologyProjection]) -> dict[UUID, DailyDealReason]:
        gaps: dict[UUID, DailyDealReason] = {}
        state_rank = {"conflicting": 0, "stale": 1, "unknown": 2, "partially_supported": 3}
        for row in rows:
            try:
                content = MethodologyProjectionContent.model_validate(row.content_json)
            except ValidationError:
                continue
            candidates = [item for item in content.items if item.state != "confirmed"]
            if not candidates:
                continue
            item = min(candidates, key=lambda value: (state_rank[value.state], not value.required, value.field_key))
            if item.state == "conflicting":
                gaps[row.opportunity_id] = DailyDealReason(
                    code="conflicting_evidence",
                    text=f"{item.display_name} needs clarification.",
                )
            elif item.state == "stale":
                gaps[row.opportunity_id] = DailyDealReason(
                    code="methodology_gap",
                    text=f"{item.display_name} needs revalidation.",
                )
            elif item.state == "unknown":
                gaps[row.opportunity_id] = DailyDealReason(
                    code="methodology_gap",
                    text=f"{item.display_name} is still unknown.",
                )
            else:
                gaps[row.opportunity_id] = DailyDealReason(
                    code="methodology_gap",
                    text=f"{item.display_name} needs more evidence.",
                )
        return gaps

    @staticmethod
    def _brain_reasons(rows: list[RevenueBrainInsight]) -> dict[UUID, DailyDealReason]:
        reasons: dict[UUID, DailyDealReason] = {}
        for row in rows:
            if row.opportunity_id is None:
                continue
            try:
                content = RevenueBrainInsightContent.model_validate_json(json.dumps(row.content_json))
            except ValidationError:
                continue
            ranked = sorted(
                content.changes,
                key=lambda item: (
                    {"high": 0, "medium": 1, "low": 2}[item.importance],
                    item.change_type,
                ),
            )
            for change in ranked:
                mapped = NEGATIVE_REVENUE_BRAIN_CHANGES.get(change.change_type)
                if mapped is None or change.direction in {"improved", "resolved"}:
                    continue
                reasons[row.opportunity_id] = DailyDealReason(
                    code=cast(
                        Literal[
                            "overdue_action",
                            "unresolved_risk",
                            "methodology_gap",
                            "conflicting_evidence",
                            "upcoming_close_with_blocker",
                            "interaction_stale",
                            "next_action_pending",
                        ],
                        mapped[0],
                    ),
                    text=mapped[1],
                )
                break
        return reasons

    @staticmethod
    def _recommendations(rows: list[DailyRecommendationRecord]) -> list[DailyRecommendation]:
        priority_rank = {"high": 0, "medium": 1, "low": 2}
        recommendations: list[DailyRecommendation] = []
        for row in rows:
            try:
                content = NextBestActionArtifactContent.model_validate(row.content_json)
            except ValidationError:
                continue
            recommendations.append(
                DailyRecommendation(
                    source_id=row.artifact_id,
                    opportunity_id=row.opportunity_id,
                    opportunity_name=row.opportunity_name,
                    recommendation=content.overall_recommendation,
                    priority=content.priority,
                    reason="Existing Next Best Action from final validated intelligence.",
                    href=f"/opportunities/{row.opportunity_id}#latest-next-best-action",
                )
            )
        recommendations.sort(
            key=lambda item: (priority_rank[item.priority], item.opportunity_name.casefold(), str(item.source_id))
        )
        return recommendations[:3]

    @staticmethod
    def _deal_attention(
        opportunities: list[DailyOpportunityRecord],
        action_records: list[DailyActionRecord],
        methodology_gaps: dict[UUID, DailyDealReason],
        brain_reasons: dict[UUID, DailyDealReason],
        now: datetime,
        local_date: date,
        surfaced_action_opportunities: set[UUID],
        recommendations: list[DailyRecommendation],
    ) -> DailyDealSection:
        overdue_by_opportunity: set[UUID] = set()
        high_action_by_opportunity: set[UUID] = set()
        for record in action_records:
            if record.proposal.opportunity_id is None:
                continue
            due_at = record.version.proposed_due_at
            if due_at is not None:
                aware_due = due_at.replace(tzinfo=UTC) if due_at.tzinfo is None else due_at.astimezone(UTC)
                if aware_due < now:
                    overdue_by_opportunity.add(record.proposal.opportunity_id)
            if record.proposal.priority == "high":
                high_action_by_opportunity.add(record.proposal.opportunity_id)
        recommendation_opportunities = {item.opportunity_id for item in recommendations}
        ranked: list[tuple[int, date, str, DailyDealAttention]] = []
        for opportunity_record in opportunities:
            opportunity = opportunity_record.opportunity
            reasons: list[DailyDealReason] = []
            if opportunity.id in overdue_by_opportunity and opportunity.id not in surfaced_action_opportunities:
                reasons.append(DailyDealReason(code="overdue_action", text="An Action for this deal is overdue."))
            if opportunity.id in brain_reasons:
                reasons.append(brain_reasons[opportunity.id])
            if opportunity.id in methodology_gaps and all(
                item.code != methodology_gaps[opportunity.id].code for item in reasons
            ):
                reasons.append(methodology_gaps[opportunity.id])

            stale_days = DEAL_STALENESS_DAYS.get(opportunity.stage, DEAL_STALENESS_DAYS["other"])
            freshness_anchor = opportunity_record.latest_completed_interaction_at or opportunity.created_at
            if freshness_anchor.tzinfo is None:
                freshness_anchor = freshness_anchor.replace(tzinfo=UTC)
            if freshness_anchor < now - timedelta(days=stale_days):
                reasons.append(
                    DailyDealReason(
                        code="interaction_stale",
                        text=f"No meaningful customer interaction in {stale_days} days.",
                    )
                )
            if not reasons and opportunity.id in high_action_by_opportunity:
                reasons.append(
                    DailyDealReason(code="next_action_pending", text="A high-priority Action needs attention.")
                )
            if not reasons and opportunity.id in recommendation_opportunities:
                reasons.append(
                    DailyDealReason(code="next_action_pending", text="A Next Best Action is ready to review.")
                )
            if not reasons:
                continue

            close_date = opportunity.expected_close_date
            blocker = any(
                item.code in {"unresolved_risk", "conflicting_evidence", "methodology_gap"} for item in reasons
            )
            close_soon = close_date is not None and local_date <= close_date <= local_date + DEAL_CLOSE_ATTENTION_WINDOW
            if close_soon and blocker:
                close_reason = DailyDealReason(
                    code="upcoming_close_with_blocker",
                    text="The expected close date is approaching with an unresolved gap.",
                )
                reasons = [close_reason, reasons[0]]
                priority: Literal["urgent", "needs_attention", "watch"] = "urgent"
            elif any(item.code in {"overdue_action", "unresolved_risk", "conflicting_evidence"} for item in reasons):
                priority = "needs_attention"
            else:
                priority = "watch"
            item = DailyDealAttention(
                opportunity_id=opportunity.id,
                opportunity_name=opportunity.name,
                company_name=opportunity_record.company_name,
                estimated_value=opportunity.estimated_value,
                currency=opportunity.currency,
                expected_close_date=opportunity.expected_close_date,
                priority=priority,
                reasons=reasons[:2],
                href=f"/opportunities/{opportunity.id}",
            )
            ranked.append(
                (
                    {"urgent": 0, "needs_attention": 1, "watch": 2}[priority],
                    close_date or date.max,
                    str(opportunity.id),
                    item,
                )
            )
        ranked.sort(key=lambda value: value[:3])
        return DailyDealSection(
            attention_count=len(ranked),
            items=[item[3] for item in ranked[:3]],
            truncated=len(ranked) > 3,
        )

    @staticmethod
    def _pipeline(records: DailyPipelineRecords | None) -> DailyPipelineSummary:
        if records is None:
            return DailyPipelineSummary(
                state="empty",
                open_opportunity_count=0,
                unvalued_opportunity_count=0,
                currency_count=0,
                currencies=[],
                safe_message="Pipeline is temporarily unavailable.",
            )
        currencies = [
            DailyPipelineCurrency(
                currency=item.currency,
                open_value=item.open_value,
                closing_this_month_value=item.closing_this_month_value,
                open_opportunity_count=item.open_opportunity_count,
                closing_this_month_count=item.closing_this_month_count,
            )
            for item in records.currencies
        ]
        if records.open_opportunity_count == 0:
            state: Literal["empty", "single_currency", "multiple_currencies"] = "empty"
            message = "Open pipeline will appear here when you add an opportunity."
        elif records.currency_count == 0:
            state = "empty"
            message = "Add values and currencies to see a monetary pipeline summary."
        elif records.currency_count == 1:
            state = "single_currency"
            message = "Open pipeline and opportunities closing this month."
        else:
            state = "multiple_currencies"
            message = "Pipeline is shown separately by currency; values are never silently combined."
        return DailyPipelineSummary(
            state=state,
            open_opportunity_count=records.open_opportunity_count,
            unvalued_opportunity_count=records.unvalued_opportunity_count,
            currency_count=records.currency_count,
            currencies=currencies,
            safe_message=message,
        )

    @staticmethod
    def _top_priority(
        interactions: list[DailyInteraction],
        actions: list[DailyAction],
        deals: list[DailyDealAttention],
        recommendations: list[DailyRecommendation],
        now: datetime,
    ) -> DailyPriority | None:
        active = next((item for item in interactions if item.preparation_state == "active"), None)
        if active is not None:
            return RevenueOSDailyService._interaction_priority(
                active, "active_interaction", "This interaction is in progress."
            )
        needs_prep = next(
            (
                item
                for item in interactions
                if item.preparation_state == "not_prepared"
                and now - timedelta(minutes=15) <= item.starts_at <= now + NEAR_TERM_INTERACTION_WINDOW
            ),
            None,
        )
        if needs_prep is not None:
            return RevenueOSDailyService._interaction_priority(
                needs_prep,
                "interaction_needs_preparation",
                "This customer interaction starts within four hours and has no completed brief.",
            )
        overdue_high = next((item for item in actions if item.timing == "overdue" and item.priority == "high"), None)
        if overdue_high is not None:
            return RevenueOSDailyService._action_priority(
                overdue_high,
                "overdue_high_priority_action",
                "This high-priority Action is overdue.",
            )
        capture = next((item for item in interactions if item.preparation_state == "capture_needed"), None)
        if capture is not None:
            return RevenueOSDailyService._interaction_priority(
                capture,
                "interaction_needs_capture",
                "This completed interaction still needs a deliberate capture.",
            )
        urgent_deal = next((item for item in deals if item.priority == "urgent"), None)
        if urgent_deal is not None:
            return DailyPriority(
                kind="deal",
                reason_code="time_sensitive_deal_blocker",
                title=f"Review {urgent_deal.opportunity_name}",
                context=urgent_deal.company_name or "Opportunity",
                reason=urgent_deal.reasons[0].text,
                cta_label="Review opportunity",
                href=urgent_deal.href,
                source_id=urgent_deal.opportunity_id,
            )
        high_action = next((item for item in actions if item.priority == "high"), None)
        if high_action is not None:
            return RevenueOSDailyService._action_priority(
                high_action,
                "high_priority_action",
                "This is the highest-priority current Action.",
            )
        high_recommendation = next((item for item in recommendations if item.priority == "high"), None)
        if high_recommendation is not None:
            return DailyPriority(
                kind="recommendation",
                reason_code="next_best_action",
                title=high_recommendation.recommendation,
                context=high_recommendation.opportunity_name,
                reason=high_recommendation.reason,
                cta_label="Review",
                href=high_recommendation.href,
                source_id=high_recommendation.source_id,
            )
        upcoming = next((item for item in interactions if item.starts_at >= now), None)
        if upcoming is not None:
            return RevenueOSDailyService._interaction_priority(
                upcoming,
                "next_upcoming_interaction",
                "This is your next scheduled customer interaction.",
            )
        return None

    @staticmethod
    def _interaction_priority(
        interaction: DailyInteraction,
        reason_code: Literal[
            "active_interaction",
            "interaction_needs_preparation",
            "interaction_needs_capture",
            "next_upcoming_interaction",
        ],
        reason: str,
    ) -> DailyPriority:
        return DailyPriority(
            kind="interaction",
            reason_code=reason_code,
            title=interaction.title,
            context=interaction.context,
            reason=reason,
            cta_label=interaction.cta_label,
            href=interaction.href,
            source_id=interaction.id,
            starts_at=interaction.starts_at,
        )

    @staticmethod
    def _action_priority(
        action: DailyAction,
        reason_code: Literal["overdue_high_priority_action", "high_priority_action"],
        reason: str,
    ) -> DailyPriority:
        return DailyPriority(
            kind="action",
            reason_code=reason_code,
            title=action.title,
            context=action.opportunity_name,
            reason=reason,
            cta_label=action.cta_label,
            href=action.href,
            source_id=action.id,
            due_at=action.due_at,
        )
