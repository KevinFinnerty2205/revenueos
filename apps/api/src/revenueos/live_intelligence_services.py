from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.beta_services import BetaService
from revenueos.config import Settings
from revenueos.errors import PublicAPIError
from revenueos.live_intelligence_contracts import (
    LiveBriefItemInput,
    LiveBriefProgressDetection,
    LiveBriefProgressResponse,
    LiveBriefProgressState,
    LiveDismissRequest,
    LiveEvidenceStrength,
    LiveIntelligenceResponse,
    LivePriority,
    LiveProcessRequest,
    LiveProcessResponse,
    LiveProviderInput,
    LivePublicState,
    LiveReconcileResponse,
    LiveReconciliationSummary,
    LiveResolution,
    LiveSignalDetection,
    LiveSignalLifecycle,
    LiveSignalType,
    LiveSourceReference,
    LiveStartRequest,
    LiveStopRequest,
    LiveTranscriptSegmentInput,
    ProvisionalSignalResponse,
)
from revenueos.live_intelligence_provider import (
    DeterministicLiveSignalProvider,
    LiveSignalProvider,
)
from revenueos.live_intelligence_repositories import LiveIntelligenceRepository
from revenueos.models import (
    Interaction,
    LiveBriefProgress,
    LiveInteractionSession,
    LiveProcessingWindow,
    PreInteractionBrief,
    ProvisionalSignal,
    TranscriptSegment,
)
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.live_intelligence")

SUPPORTED_LIVE_INTERACTION_TYPES = frozenset(
    {
        "face_to_face_meeting",
        "presentation",
        "workshop",
        "site_visit",
        "online_meeting",
        "phone_call",
    }
)
LiveBriefItemType = Literal["objective", "open_question"]


class LiveInteractionIntelligenceService:
    """Bounded provisional processing isolated from final intelligence stores."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        settings: Settings,
        provider: LiveSignalProvider | None = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.settings = settings
        self.repository = LiveIntelligenceRepository(session)
        self.beta = BetaService(session, tenant, settings)
        self.provider = provider or DeterministicLiveSignalProvider()

    async def get(self, interaction_id: UUID) -> LiveIntelligenceResponse:
        interaction = await self._interaction(interaction_id)
        live_session = await self.repository.get_live_session(
            self.tenant.organisation_id,
            interaction_id,
        )
        return await self._response(interaction, live_session)

    async def start(
        self,
        interaction_id: UUID,
        request: LiveStartRequest,
    ) -> LiveIntelligenceResponse:
        self.beta.require_feature("liveInteractionIntelligence")
        interaction = await self._interaction(interaction_id, for_update=True)
        existing = await self.repository.get_live_session(
            self.tenant.organisation_id,
            interaction_id,
            for_update=True,
        )
        if existing is not None:
            if existing.status in {"active", "processing"}:
                return await self._response(interaction, existing)
            raise PublicAPIError(
                "live_intelligence_already_stopped",
                "Live Intelligence has already been stopped for this interaction.",
                409,
            )
        if interaction.lifecycle_status != "in_progress":
            raise PublicAPIError(
                "interaction_not_in_progress",
                "Live Intelligence can start only while the interaction is in progress.",
                409,
            )
        if interaction.interaction_type not in SUPPORTED_LIVE_INTERACTION_TYPES:
            raise PublicAPIError(
                "live_source_unavailable",
                "Live Intelligence is unavailable for this interaction. Use the post-interaction Debrief instead.",
                409,
            )
        transcript = await self.repository.latest_progressive_transcript(
            self.tenant.organisation_id,
            interaction_id,
        )
        if transcript is None:
            raise PublicAPIError(
                "live_source_unavailable",
                "No authorised progressive transcript source is available. Use the post-interaction Debrief instead.",
                409,
            )
        if self.settings.feature_live_interaction_external_ai_enabled:
            if not request.external_processing_acknowledged:
                raise PublicAPIError(
                    "external_processing_acknowledgement_required",
                    "Acknowledge external processing before enabling this live path.",
                    422,
                )
            raise PublicAPIError(
                "live_external_provider_unavailable",
                "The external Live Intelligence provider is not configured for this release.",
                503,
            )
        if (
            await self.repository.count_active_sessions(self.tenant.organisation_id)
            >= self.settings.private_beta_max_concurrent_live_interactions
        ):
            raise PublicAPIError(
                "live_concurrency_limit_reached",
                "This organisation already has the maximum number of active live interactions.",
                429,
            )
        brief = await self.repository.latest_brief(self.tenant.organisation_id, interaction_id)
        now = datetime.now(UTC)
        live_session = LiveInteractionSession(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction_id,
            transcript_version_id=transcript.id,
            brief_id=brief.id if brief is not None else None,
            created_by_user_id=self.tenant.user_id,
            status="active",
            source_kind="progressive_transcript",
            last_processed_sequence=-1,
            processed_character_count=0,
            processing_request_count=0,
            started_at=now,
            retention_expires_at=now + timedelta(days=self.settings.private_beta_live_retention_days),
        )
        self.session.add(live_session)
        await self.session.flush()
        for item in self._brief_items(brief):
            self.session.add(
                LiveBriefProgress(
                    id=uuid.uuid4(),
                    organisation_id=self.tenant.organisation_id,
                    live_session_id=live_session.id,
                    item_type=item.item_type,
                    item_index=item.item_index,
                    item_fingerprint=self._hash(item.text),
                    progress_status="unresolved",
                )
            )
        await self._commit("Live Intelligence could not be enabled safely.")
        logger.info(
            "live_intelligence_enabled",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "interaction_id": str(interaction_id),
                "live_session_id": str(live_session.id),
                "interaction_type": interaction.interaction_type,
            },
        )
        return await self._response(interaction, live_session)

    async def stop(
        self,
        interaction_id: UUID,
        request: LiveStopRequest,
    ) -> LiveIntelligenceResponse:
        self.beta.require_feature("liveInteractionIntelligence")
        interaction = await self._interaction(interaction_id)
        live_session = await self._require_session(interaction_id, for_update=True)
        if live_session.status in {"stopped", "completed", "expired"}:
            return await self._response(interaction, live_session)
        if live_session.status == "processing":
            raise PublicAPIError(
                "live_processing_in_progress",
                "A bounded live update is finishing. Try stopping again shortly.",
                409,
            )
        live_session.status = "stopped"
        live_session.stopped_at = datetime.now(UTC)
        live_session.failure_code = None
        await self._commit("Live Intelligence could not be stopped safely.")
        logger.info(
            "live_intelligence_disabled",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "interaction_id": str(interaction_id),
                "live_session_id": str(live_session.id),
                "stop_reason": request.reason,
            },
        )
        return await self._response(interaction, live_session)

    async def process(
        self,
        interaction_id: UUID,
        request: LiveProcessRequest,
    ) -> LiveProcessResponse:
        self.beta.require_feature("liveInteractionIntelligence")
        interaction = await self._interaction(interaction_id)
        if interaction.lifecycle_status != "in_progress":
            raise PublicAPIError(
                "interaction_not_in_progress",
                "Live processing stops when the interaction ends.",
                409,
            )
        live_session = await self._require_session(interaction_id, for_update=True)
        if live_session.status != "active":
            if live_session.status == "processing":
                return self._process_response(
                    await self._response(interaction, live_session),
                    processed=False,
                    new_segment_count=0,
                )
            raise PublicAPIError(
                "invalid_live_intelligence_transition",
                "Live processing is not active for this interaction.",
                409,
            )
        replay = await self.repository.window_by_trigger(
            self.tenant.organisation_id,
            live_session.id,
            request.idempotency_key,
        )
        if replay is not None:
            return self._process_response(
                await self._response(interaction, live_session),
                processed=replay.status in {"completed", "no_signal"},
                new_segment_count=max(0, replay.last_sequence - live_session.last_processed_sequence),
            )
        segments = await self.repository.processing_segments(
            self.tenant.organisation_id,
            live_session.transcript_version_id,
            cursor=live_session.last_processed_sequence,
            overlap=self.settings.private_beta_live_window_overlap_segments,
            limit=self.settings.private_beta_live_window_segments,
        )
        new_segments = [item for item in segments if item.sequence_number > live_session.last_processed_sequence]
        contiguous = self._contiguous_new_segments(new_segments, live_session.last_processed_sequence + 1)
        if not contiguous:
            return self._process_response(
                await self._response(interaction, live_session),
                processed=False,
                new_segment_count=0,
            )
        window = self._bounded_window(segments, contiguous[-1].sequence_number)
        new_in_window = [item for item in window if item.sequence_number > live_session.last_processed_sequence]
        if not self._cadence_ready(live_session, new_in_window):
            return self._process_response(
                await self._response(interaction, live_session),
                processed=False,
                new_segment_count=len(new_in_window),
            )
        new_character_count = sum(len(item.text) for item in new_in_window)
        await self._enforce_quotas(live_session, new_character_count)
        window_fingerprint = self._window_fingerprint(live_session.transcript_version_id, window)
        duplicate = await self.repository.window_by_fingerprint(
            self.tenant.organisation_id,
            live_session.id,
            window_fingerprint,
        )
        if duplicate is not None:
            return self._process_response(
                await self._response(interaction, live_session),
                processed=duplicate.status in {"completed", "no_signal"},
                new_segment_count=len(new_in_window),
            )

        now = datetime.now(UTC)
        processing_window = LiveProcessingWindow(
            id=uuid.uuid4(),
            organisation_id=self.tenant.organisation_id,
            live_session_id=live_session.id,
            trigger_idempotency_key=request.idempotency_key,
            window_fingerprint=window_fingerprint,
            first_sequence=window[0].sequence_number,
            last_sequence=window[-1].sequence_number,
            segment_count=len(window),
            character_count=sum(len(item.text) for item in window),
            status="processing",
            signal_count=0,
            created_at=now,
        )
        self.session.add(processing_window)
        live_session.status = "processing"
        live_session.current_window_fingerprint = window_fingerprint
        logger.info(
            "live_processing_started",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "interaction_id": str(interaction_id),
                "interaction_type": interaction.interaction_type,
                "live_session_id": str(live_session.id),
                "segment_count": len(window),
            },
        )
        try:
            if self.provider.uses_external_provider:
                await self.beta.reserve_provider_request(self.provider.provider_name)
            provider_output = await self.provider.detect(
                LiveProviderInput(
                    interaction_type=interaction.interaction_type,
                    segments=tuple(
                        LiveTranscriptSegmentInput(
                            sequence_number=item.sequence_number,
                            start_ms=item.start_ms,
                            end_ms=item.end_ms,
                            speaker_label=item.speaker_label,
                            speaker_role=cast(
                                Literal["customer", "salesperson", "unknown"],
                                item.speaker_role or "unknown",
                            ),
                            text=item.text,
                        )
                        for item in window
                    ),
                    brief_items=tuple(
                        self._brief_items(
                            await self.repository.brief_by_id(
                                self.tenant.organisation_id,
                                live_session.brief_id,
                            )
                            if live_session.brief_id is not None
                            else None
                        )
                    ),
                    existing_signal_fingerprints=tuple(
                        item.signal_fingerprint
                        for item in (
                            await self.repository.list_signals(
                                self.tenant.organisation_id,
                                live_session.id,
                            )
                        )[:100]
                    ),
                )
            )
            detected_count, updated_count, superseded_count = await self._apply_detections(
                live_session,
                provider_output.signals,
                now,
            )
            signal_count = detected_count + updated_count
            await self._apply_progress(live_session, provider_output.brief_progress)
        except Exception as exc:
            processing_window.status = "failed"
            processing_window.failure_code = "live_provider_failure"
            processing_window.completed_at = datetime.now(UTC)
            live_session.status = "failed"
            live_session.failure_code = "live_provider_failure"
            await self._commit("Live processing failed safely.")
            logger.warning(
                "live_processing_failed",
                extra={
                    "organisation_id": str(self.tenant.organisation_id),
                    "interaction_id": str(interaction_id),
                    "live_session_id": str(live_session.id),
                    "error_code": "live_provider_failure",
                },
            )
            raise PublicAPIError(
                "live_processing_failed",
                "Live Intelligence paused safely. Continue the interaction and use Debrief afterwards.",
                503,
            ) from exc

        completed_at = datetime.now(UTC)
        processing_window.status = "completed" if signal_count else "no_signal"
        processing_window.signal_count = signal_count
        processing_window.completed_at = completed_at
        live_session.status = "active"
        live_session.failure_code = None
        live_session.last_processed_sequence = new_in_window[-1].sequence_number
        live_session.last_processed_at = completed_at
        live_session.processed_character_count += new_character_count
        live_session.processing_request_count += 1
        await self._commit("The live update could not be saved safely.")
        logger.info(
            "live_processing_completed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "interaction_id": str(interaction_id),
                "live_session_id": str(live_session.id),
                "processing_window_count": 1,
                "segment_count": len(window),
                "transcript_character_count": processing_window.character_count,
                "signal_detected_count": detected_count,
                "signal_updated_count": updated_count,
                "signal_superseded_count": superseded_count,
            },
        )
        return self._process_response(
            await self._response(interaction, live_session),
            processed=True,
            new_segment_count=len(new_in_window),
        )

    async def dismiss(
        self,
        interaction_id: UUID,
        signal_id: UUID,
        request: LiveDismissRequest,
    ) -> LiveIntelligenceResponse:
        del request
        self.beta.require_feature("liveInteractionIntelligence")
        interaction = await self._interaction(interaction_id)
        live_session = await self._require_session(interaction_id, for_update=True)
        signal = await self.repository.signal_by_id(
            self.tenant.organisation_id,
            live_session.id,
            signal_id,
            for_update=True,
        )
        if signal is None:
            raise PublicAPIError("live_signal_not_found", "The requested provisional signal was not found.", 404)
        if signal.lifecycle_status == "dismissed":
            return await self._response(interaction, live_session)
        if signal.lifecycle_status in {"superseded", "expired"}:
            raise PublicAPIError(
                "live_signal_immutable",
                "That provisional signal can no longer be dismissed.",
                409,
            )
        signal.lifecycle_status = "dismissed"
        signal.last_updated_at = datetime.now(UTC)
        await self._commit("The provisional signal could not be dismissed.")
        logger.info(
            "signal_dismissed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "interaction_id": str(interaction_id),
                "live_session_id": str(live_session.id),
                "signal_id": str(signal.id),
                "signal_dismissed_count": 1,
            },
        )
        return await self._response(interaction, live_session)

    async def reconcile(self, interaction_id: UUID) -> LiveReconcileResponse:
        self.beta.require_feature("liveInteractionIntelligence")
        interaction = await self._interaction(interaction_id)
        if interaction.lifecycle_status != "completed":
            raise PublicAPIError(
                "interaction_not_completed",
                "Final reconciliation is available only after the interaction is completed.",
                409,
            )
        live_session = await self._require_session(interaction_id, for_update=True)
        final_intelligence = await self.repository.latest_final_intelligence(
            self.tenant.organisation_id,
            interaction_id,
        )
        signals = await self.repository.list_signals(
            self.tenant.organisation_id,
            live_session.id,
            for_update=True,
        )
        final_items = self._final_items(final_intelligence.content_json if final_intelligence is not None else None)
        counts = {"confirmed": 0, "revised": 0, "unsupported": 0, "unresolved": 0}
        for signal in signals:
            if signal.lifecycle_status in {"expired", "superseded"}:
                continue
            resolution = self._reconcile_signal(signal, final_items)
            signal.resolution_status = resolution
            if resolution in {"confirmed", "revised"} and signal.lifecycle_status != "dismissed":
                signal.lifecycle_status = "promoted_candidate"
            counts[resolution] += 1
        now = datetime.now(UTC)
        live_session.status = "completed"
        live_session.stopped_at = live_session.stopped_at or now
        live_session.reconciled_at = now
        live_session.final_intelligence_id = final_intelligence.id if final_intelligence is not None else None
        await self._commit("Live-to-final reconciliation could not be saved.")
        logger.info(
            "live_reconciliation_completed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "interaction_id": str(interaction_id),
                "live_session_id": str(live_session.id),
                "reconciliation_confirmed_count": counts["confirmed"],
                "reconciliation_revised_count": counts["revised"],
                "reconciliation_unsupported_count": counts["unsupported"],
                "reconciliation_unresolved_count": counts["unresolved"],
            },
        )
        response = await self._response(interaction, live_session)
        return LiveReconcileResponse(**response.model_dump(), reconciled=True)

    async def _response(
        self,
        interaction: Interaction,
        live_session: LiveInteractionSession | None,
    ) -> LiveIntelligenceResponse:
        interval = self.settings.private_beta_live_processing_interval_seconds
        if not self.settings.feature_live_interaction_intelligence_enabled:
            return LiveIntelligenceResponse(
                availability="disabled",
                state="disabled",
                safe_message="Live Intelligence is disabled for this workspace. Post-interaction Debrief remains available.",
                source_kind=None,
                session_id=None,
                signals=[],
                objectives=[],
                open_questions=[],
                reconciliation=None,
                generated_at=None,
                updated_at=None,
                next_poll_seconds=interval,
            )
        if live_session is None:
            source = await self.repository.latest_progressive_transcript(
                self.tenant.organisation_id,
                interaction.id,
            )
            available = (
                interaction.lifecycle_status in {"planned", "in_progress"}
                and interaction.interaction_type in SUPPORTED_LIVE_INTERACTION_TYPES
                and source is not None
            )
            return LiveIntelligenceResponse(
                availability="available" if available else "unavailable",
                state="available" if available else "unavailable",
                safe_message=(
                    "An authorised progressive transcript is available. Live Intelligence is optional and provisional."
                    if available
                    else "Live Intelligence is unavailable without an authorised progressive source. Use Debrief afterwards."
                ),
                source_kind="progressive_transcript" if available else None,
                session_id=None,
                signals=[],
                objectives=[],
                open_questions=[],
                reconciliation=None,
                generated_at=None,
                updated_at=None,
                next_poll_seconds=interval,
            )
        await self.session.refresh(live_session)
        signals = await self.repository.list_signals(
            self.tenant.organisation_id,
            live_session.id,
        )
        progress = await self.repository.list_progress(
            self.tenant.organisation_id,
            live_session.id,
        )
        brief = (
            await self.repository.brief_by_id(self.tenant.organisation_id, live_session.brief_id)
            if live_session.brief_id is not None
            else None
        )
        labels = {(item.item_type, item.item_index): item.text for item in self._brief_items(brief)}
        progress_responses = [
            LiveBriefProgressResponse(
                item_type=cast(LiveBriefItemType, item.item_type),
                item_index=item.item_index,
                label=labels.get(
                    (cast(LiveBriefItemType, item.item_type), item.item_index),
                    "Brief item unavailable",
                ),
                progress_status=cast(LiveBriefProgressState, item.progress_status),
            )
            for item in progress
        ]
        state_by_session_status: dict[str, LivePublicState] = {
            "active": "active",
            "processing": "processing",
            "failed": "failed",
            "stopped": "completed",
            "completed": "completed",
            "expired": "completed",
        }
        public_state = state_by_session_status[live_session.status]
        safe_message = {
            "active": "Live signals are provisional, may change and need post-interaction review.",
            "processing": "A bounded provisional update is being prepared.",
            "failed": "Live Intelligence paused safely. Continue the interaction and use Debrief afterwards.",
            "stopped": "Live Intelligence is stopped and its provisional state is frozen for final review.",
            "completed": "Final intelligence is authoritative; live signals are retained only for reconciliation.",
            "expired": "The provisional live state has expired under the workspace retention policy.",
        }[live_session.status]
        reconciliation_counts = {
            "confirmed": 0,
            "revised": 0,
            "unsupported": 0,
            "unresolved": 0,
        }
        for signal in signals:
            if signal.resolution_status in reconciliation_counts:
                reconciliation_counts[signal.resolution_status] += 1
        reconciliation = (
            LiveReconciliationSummary(**reconciliation_counts) if live_session.reconciled_at is not None else None
        )
        ordered_signals = sorted(
            signals,
            key=lambda item: (
                item.lifecycle_status in {"superseded", "expired"},
                item.priority != "high",
                item.detected_at,
                str(item.id),
            ),
        )
        return LiveIntelligenceResponse(
            availability="available",
            state=public_state,
            safe_message=safe_message,
            source_kind="progressive_transcript",
            session_id=live_session.id,
            signals=[self._signal_response(item) for item in ordered_signals],
            objectives=[item for item in progress_responses if item.item_type == "objective"],
            open_questions=[item for item in progress_responses if item.item_type == "open_question"],
            reconciliation=reconciliation,
            generated_at=live_session.last_processed_at,
            updated_at=live_session.updated_at,
            next_poll_seconds=interval,
        )

    async def _apply_detections(
        self,
        live_session: LiveInteractionSession,
        detections: tuple[LiveSignalDetection, ...],
        now: datetime,
    ) -> tuple[int, int, int]:
        detected_count = 0
        updated_count = 0
        superseded_count = 0
        for detection in detections:
            signal_fingerprint = self._hash(f"{detection.signal_type}:{self._normalise(detection.statement)}")
            existing = await self.repository.signal_by_fingerprint(
                self.tenant.organisation_id,
                live_session.id,
                signal_fingerprint,
            )
            if existing is not None:
                if existing.lifecycle_status in {"dismissed", "superseded", "expired"}:
                    continue
                existing.lifecycle_status = "updated"
                existing.last_updated_at = now
                existing.source_sequence_end = max(existing.source_sequence_end, detection.sequence_end)
                updated_count += 1
                continue
            subject_fingerprint = self._hash(f"{detection.signal_type}:{self._normalise(detection.subject_key)}")
            prior = await self.repository.active_signal_by_subject(
                self.tenant.organisation_id,
                live_session.id,
                subject_fingerprint,
            )
            signal = ProvisionalSignal(
                id=uuid.uuid4(),
                organisation_id=self.tenant.organisation_id,
                interaction_id=live_session.interaction_id,
                live_session_id=live_session.id,
                transcript_version_id=live_session.transcript_version_id,
                signal_type=detection.signal_type,
                statement=detection.statement,
                lifecycle_status="detected",
                is_provisional=True,
                priority=detection.priority,
                evidence_strength=detection.evidence_strength,
                resolution_status="pending",
                signal_fingerprint=signal_fingerprint,
                subject_fingerprint=subject_fingerprint,
                source_sequence_start=detection.sequence_start,
                source_sequence_end=detection.sequence_end,
                detected_at=now,
                last_updated_at=now,
            )
            self.session.add(signal)
            await self.session.flush([signal])
            detected_count += 1
            if prior is not None and prior.id != signal.id:
                prior.lifecycle_status = "superseded"
                prior.superseded_by_id = signal.id
                prior.last_updated_at = now
                superseded_count += 1
        return detected_count, updated_count, superseded_count

    async def _apply_progress(
        self,
        live_session: LiveInteractionSession,
        detections: tuple[LiveBriefProgressDetection, ...],
    ) -> None:
        for detection in detections:
            progress = await self.repository.progress_item(
                self.tenant.organisation_id,
                live_session.id,
                detection.item_type,
                detection.item_index,
            )
            if progress is None:
                continue
            progress.progress_status = detection.progress_status
            progress.source_sequence_end = detection.source_sequence_end

    async def _enforce_quotas(
        self,
        live_session: LiveInteractionSession,
        new_character_count: int,
    ) -> None:
        now = datetime.now(UTC)
        if live_session.processing_request_count >= self.settings.private_beta_max_live_requests_per_interaction:
            raise PublicAPIError(
                "live_interaction_request_limit_reached",
                "The live request limit for this interaction has been reached. Use Debrief afterwards.",
                429,
            )
        if (
            live_session.processed_character_count + new_character_count
            > self.settings.private_beta_max_live_characters_per_interaction
        ):
            raise PublicAPIError(
                "live_interaction_text_limit_reached",
                "The live text limit for this interaction has been reached. Use Debrief afterwards.",
                429,
            )
        minute_count = await self.repository.count_windows_since(
            self.tenant.organisation_id,
            now - timedelta(minutes=1),
        )
        if minute_count >= self.settings.private_beta_max_live_requests_per_minute:
            raise PublicAPIError(
                "live_rate_limit_reached",
                "Live updates are temporarily rate limited. The interaction can continue normally.",
                429,
            )
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_count = await self.repository.count_windows_since(self.tenant.organisation_id, day_start)
        if day_count >= self.settings.private_beta_max_live_provider_calls_per_day:
            raise PublicAPIError(
                "live_daily_limit_reached",
                "The organisation’s daily live-processing limit has been reached.",
                429,
            )

    async def _interaction(
        self,
        interaction_id: UUID,
        *,
        for_update: bool = False,
    ) -> Interaction:
        interaction = await self.repository.get_interaction(
            self.tenant.organisation_id,
            interaction_id,
            for_update=for_update,
        )
        if interaction is None:
            raise PublicAPIError("interaction_not_found", "The requested interaction was not found.", 404)
        return interaction

    async def _require_session(
        self,
        interaction_id: UUID,
        *,
        for_update: bool = False,
    ) -> LiveInteractionSession:
        live_session = await self.repository.get_live_session(
            self.tenant.organisation_id,
            interaction_id,
            for_update=for_update,
        )
        if live_session is None:
            raise PublicAPIError(
                "live_intelligence_not_started",
                "Live Intelligence has not been enabled for this interaction.",
                409,
            )
        return live_session

    def _cadence_ready(
        self,
        live_session: LiveInteractionSession,
        new_segments: list[TranscriptSegment],
    ) -> bool:
        if live_session.last_processed_at is None:
            return True
        elapsed = datetime.now(UTC) - self._aware(live_session.last_processed_at)
        return (
            elapsed.total_seconds() >= self.settings.private_beta_live_processing_interval_seconds
            or len(new_segments) >= self.settings.private_beta_live_min_new_segments
            or sum(len(item.text) for item in new_segments) >= self.settings.private_beta_live_min_new_characters
        )

    def _bounded_window(
        self,
        segments: list[TranscriptSegment],
        last_new_sequence: int,
    ) -> list[TranscriptSegment]:
        eligible = [item for item in segments if item.sequence_number <= last_new_sequence]
        bounded: list[TranscriptSegment] = []
        character_count = 0
        for item in reversed(eligible):
            next_count = character_count + len(item.text)
            if bounded and next_count > self.settings.private_beta_live_window_characters:
                break
            bounded.append(item)
            character_count = next_count
        return list(reversed(bounded))

    @staticmethod
    def _contiguous_new_segments(
        segments: list[TranscriptSegment],
        expected_sequence: int,
    ) -> list[TranscriptSegment]:
        contiguous: list[TranscriptSegment] = []
        for segment in segments:
            if segment.sequence_number != expected_sequence:
                break
            contiguous.append(segment)
            expected_sequence += 1
        return contiguous

    @staticmethod
    def _brief_items(brief: PreInteractionBrief | None) -> list[LiveBriefItemInput]:
        if brief is None:
            return []
        items: list[LiveBriefItemInput] = []
        specifications: tuple[tuple[LiveBriefItemType, tuple[str, ...], str], ...] = (
            ("objective", ("objectives",), "objective"),
            ("open_question", ("questions_to_ask", "questionsToAsk"), "question"),
        )
        for item_type, container_names, text_name in specifications:
            raw: object = []
            for container_name in container_names:
                if container_name in brief.content_json:
                    raw = brief.content_json[container_name]
                    break
            if not isinstance(raw, list):
                continue
            for index, value in enumerate(raw[:20]):
                if not isinstance(value, dict):
                    continue
                text = value.get(text_name)
                if isinstance(text, str) and text.strip():
                    items.append(
                        LiveBriefItemInput(
                            item_type=item_type,
                            item_index=index,
                            text=text.strip()[:500],
                        )
                    )
        return items

    @staticmethod
    def _window_fingerprint(
        transcript_version_id: UUID,
        segments: list[TranscriptSegment],
    ) -> str:
        source = "|".join(
            f"{item.sequence_number}:{item.start_ms}:{item.end_ms}:{item.speaker_role or 'unknown'}:{item.text}"
            for item in segments
        )
        return LiveInteractionIntelligenceService._hash(f"{transcript_version_id}:{source}")

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalise(value: str) -> str:
        return " ".join(re.sub(r"[^a-z0-9 ]+", " ", value.casefold()).split())

    @staticmethod
    def _final_items(content: dict[str, object] | None) -> list[tuple[str, str]]:
        if content is None:
            return []
        raw = content.get("items")
        if not isinstance(raw, list):
            return []
        items: list[tuple[str, str]] = []
        for value in raw:
            if not isinstance(value, dict):
                continue
            category = value.get("category")
            statement = value.get("statement")
            if isinstance(category, str) and isinstance(statement, str):
                items.append((category, statement))
        return items

    @classmethod
    def _reconcile_signal(
        cls,
        signal: ProvisionalSignal,
        final_items: list[tuple[str, str]],
    ) -> str:
        if not final_items:
            return "unresolved"
        comparable = [
            statement
            for category, statement in final_items
            if category == signal.signal_type
            or (signal.signal_type == "buying_signal" and category == "commercial_intent")
        ]
        if not comparable:
            return "unsupported"
        provisional = cls._normalise(signal.statement)
        provisional_terms = set(provisional.split())
        best = 0.0
        exact = False
        for final_statement in comparable:
            final = cls._normalise(final_statement)
            exact = exact or final == provisional
            final_terms = set(final.split())
            union = provisional_terms | final_terms
            score = len(provisional_terms & final_terms) / len(union) if union else 0.0
            best = max(best, score)
        if exact or best >= 0.8:
            return "confirmed"
        if best >= 0.35:
            return "revised"
        return "unresolved"

    @staticmethod
    def _signal_response(signal: ProvisionalSignal) -> ProvisionalSignalResponse:
        return ProvisionalSignalResponse(
            id=signal.id,
            signal_type=cast(LiveSignalType, signal.signal_type),
            statement=signal.statement,
            lifecycle_status=cast(LiveSignalLifecycle, signal.lifecycle_status),
            provisional=True,
            priority=cast(LivePriority, signal.priority),
            evidence_strength=cast(LiveEvidenceStrength, signal.evidence_strength),
            resolution_status=cast(LiveResolution, signal.resolution_status),
            source=LiveSourceReference(
                transcript_version_id=signal.transcript_version_id,
                sequence_start=signal.source_sequence_start,
                sequence_end=signal.source_sequence_end,
            ),
            detected_at=signal.detected_at,
            last_updated_at=signal.last_updated_at,
            superseded_by=signal.superseded_by_id,
        )

    @staticmethod
    def _process_response(
        response: LiveIntelligenceResponse,
        *,
        processed: bool,
        new_segment_count: int,
    ) -> LiveProcessResponse:
        return LiveProcessResponse(
            **response.model_dump(),
            processed=processed,
            new_segment_count=new_segment_count,
        )

    async def _commit(self, message: str) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PublicAPIError("live_intelligence_conflict", message, 409) from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise PublicAPIError("live_intelligence_save_failed", message, 500) from exc

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def expire_live_intelligence(
    session: AsyncSession,
    organisation_id: UUID,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> int:
    """Expire bounded provisional state while retaining metadata-only reconciliation."""

    cutoff = now or datetime.now(UTC)
    sessions = list(
        (
            await session.scalars(
                select(LiveInteractionSession)
                .where(
                    LiveInteractionSession.organisation_id == organisation_id,
                    LiveInteractionSession.retention_expires_at <= cutoff,
                    LiveInteractionSession.status != "expired",
                )
                .order_by(LiveInteractionSession.retention_expires_at, LiveInteractionSession.id)
                .limit(limit)
            )
        ).all()
    )
    for live_session in sessions:
        signals = list(
            (
                await session.scalars(
                    select(ProvisionalSignal).where(
                        ProvisionalSignal.organisation_id == organisation_id,
                        ProvisionalSignal.live_session_id == live_session.id,
                    )
                )
            ).all()
        )
        for signal in signals:
            signal.statement = "Provisional statement expired under retention policy."
            signal.lifecycle_status = "expired"
            signal.last_updated_at = cutoff
        live_session.status = "expired"
        live_session.current_window_fingerprint = None
        live_session.failure_code = None
    await session.flush()
    return len(sessions)
