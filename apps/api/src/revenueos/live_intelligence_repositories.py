from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    Interaction,
    InteractionIntelligenceSnapshot,
    LiveBriefProgress,
    LiveInteractionSession,
    LiveProcessingWindow,
    PreInteractionBrief,
    ProvisionalSignal,
    TranscriptSegment,
    TranscriptVersion,
)


class LiveIntelligenceRepository:
    """Live-intelligence persistence with an explicit trusted tenant predicate."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_interaction(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        *,
        for_update: bool = False,
    ) -> Interaction | None:
        statement = select(Interaction).where(
            Interaction.organisation_id == organisation_id,
            Interaction.id == interaction_id,
            Interaction.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(Interaction | None, await self.session.scalar(statement))

    async def latest_progressive_transcript(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
    ) -> TranscriptVersion | None:
        segment_exists = (
            select(TranscriptSegment.id)
            .where(
                TranscriptSegment.organisation_id == organisation_id,
                TranscriptSegment.transcript_version_id == TranscriptVersion.id,
                TranscriptSegment.deleted_at.is_(None),
            )
            .limit(1)
            .exists()
        )
        return cast(
            TranscriptVersion | None,
            await self.session.scalar(
                select(TranscriptVersion)
                .where(
                    TranscriptVersion.organisation_id == organisation_id,
                    TranscriptVersion.interaction_id == interaction_id,
                    TranscriptVersion.source == "progressive",
                    TranscriptVersion.status.in_(("provisional", "final")),
                    TranscriptVersion.deleted_at.is_(None),
                    segment_exists,
                )
                .order_by(TranscriptVersion.created_at.desc(), TranscriptVersion.id.desc())
                .limit(1)
            ),
        )

    async def latest_brief(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
    ) -> PreInteractionBrief | None:
        return cast(
            PreInteractionBrief | None,
            await self.session.scalar(
                select(PreInteractionBrief)
                .where(
                    PreInteractionBrief.organisation_id == organisation_id,
                    PreInteractionBrief.interaction_id == interaction_id,
                    PreInteractionBrief.status == "completed",
                )
                .order_by(PreInteractionBrief.brief_version.desc(), PreInteractionBrief.id.desc())
                .limit(1)
            ),
        )

    async def brief_by_id(
        self,
        organisation_id: UUID,
        brief_id: UUID,
    ) -> PreInteractionBrief | None:
        return cast(
            PreInteractionBrief | None,
            await self.session.scalar(
                select(PreInteractionBrief).where(
                    PreInteractionBrief.organisation_id == organisation_id,
                    PreInteractionBrief.id == brief_id,
                    PreInteractionBrief.status == "completed",
                )
            ),
        )

    async def get_live_session(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        *,
        for_update: bool = False,
    ) -> LiveInteractionSession | None:
        statement = select(LiveInteractionSession).where(
            LiveInteractionSession.organisation_id == organisation_id,
            LiveInteractionSession.interaction_id == interaction_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(LiveInteractionSession | None, await self.session.scalar(statement))

    async def count_active_sessions(self, organisation_id: UUID) -> int:
        value = await self.session.scalar(
            select(func.count())
            .select_from(LiveInteractionSession)
            .where(
                LiveInteractionSession.organisation_id == organisation_id,
                LiveInteractionSession.status.in_(("active", "processing")),
            )
        )
        return int(value or 0)

    async def processing_segments(
        self,
        organisation_id: UUID,
        transcript_version_id: UUID,
        *,
        cursor: int,
        overlap: int,
        limit: int,
    ) -> list[TranscriptSegment]:
        first_sequence = max(0, cursor - overlap + 1) if cursor >= 0 else 0
        values = await self.session.scalars(
            select(TranscriptSegment)
            .where(
                TranscriptSegment.organisation_id == organisation_id,
                TranscriptSegment.transcript_version_id == transcript_version_id,
                TranscriptSegment.sequence_number >= first_sequence,
                TranscriptSegment.deleted_at.is_(None),
            )
            .order_by(TranscriptSegment.sequence_number, TranscriptSegment.id)
            .limit(limit + overlap)
        )
        return list(values.all())

    async def list_signals(
        self,
        organisation_id: UUID,
        live_session_id: UUID,
        *,
        include_inactive: bool = True,
        for_update: bool = False,
    ) -> list[ProvisionalSignal]:
        statement = select(ProvisionalSignal).where(
            ProvisionalSignal.organisation_id == organisation_id,
            ProvisionalSignal.live_session_id == live_session_id,
        )
        if not include_inactive:
            statement = statement.where(
                ProvisionalSignal.lifecycle_status.not_in(("superseded", "expired")),
            )
        statement = statement.order_by(
            ProvisionalSignal.detected_at,
            ProvisionalSignal.id,
        )
        if for_update:
            statement = statement.with_for_update()
        values = await self.session.scalars(statement)
        return list(values.all())

    async def signal_by_id(
        self,
        organisation_id: UUID,
        live_session_id: UUID,
        signal_id: UUID,
        *,
        for_update: bool = False,
    ) -> ProvisionalSignal | None:
        statement = select(ProvisionalSignal).where(
            ProvisionalSignal.organisation_id == organisation_id,
            ProvisionalSignal.live_session_id == live_session_id,
            ProvisionalSignal.id == signal_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(ProvisionalSignal | None, await self.session.scalar(statement))

    async def signal_by_fingerprint(
        self,
        organisation_id: UUID,
        live_session_id: UUID,
        fingerprint: str,
    ) -> ProvisionalSignal | None:
        return cast(
            ProvisionalSignal | None,
            await self.session.scalar(
                select(ProvisionalSignal).where(
                    ProvisionalSignal.organisation_id == organisation_id,
                    ProvisionalSignal.live_session_id == live_session_id,
                    ProvisionalSignal.signal_fingerprint == fingerprint,
                )
            ),
        )

    async def active_signal_by_subject(
        self,
        organisation_id: UUID,
        live_session_id: UUID,
        subject_fingerprint: str,
    ) -> ProvisionalSignal | None:
        return cast(
            ProvisionalSignal | None,
            await self.session.scalar(
                select(ProvisionalSignal)
                .where(
                    ProvisionalSignal.organisation_id == organisation_id,
                    ProvisionalSignal.live_session_id == live_session_id,
                    ProvisionalSignal.subject_fingerprint == subject_fingerprint,
                    ProvisionalSignal.lifecycle_status.in_(("detected", "updated", "promoted_candidate")),
                )
                .order_by(ProvisionalSignal.last_updated_at.desc(), ProvisionalSignal.id.desc())
                .limit(1)
            ),
        )

    async def list_progress(
        self,
        organisation_id: UUID,
        live_session_id: UUID,
    ) -> list[LiveBriefProgress]:
        values = await self.session.scalars(
            select(LiveBriefProgress)
            .where(
                LiveBriefProgress.organisation_id == organisation_id,
                LiveBriefProgress.live_session_id == live_session_id,
            )
            .order_by(LiveBriefProgress.item_type, LiveBriefProgress.item_index)
        )
        return list(values.all())

    async def progress_item(
        self,
        organisation_id: UUID,
        live_session_id: UUID,
        item_type: str,
        item_index: int,
    ) -> LiveBriefProgress | None:
        return cast(
            LiveBriefProgress | None,
            await self.session.scalar(
                select(LiveBriefProgress).where(
                    LiveBriefProgress.organisation_id == organisation_id,
                    LiveBriefProgress.live_session_id == live_session_id,
                    LiveBriefProgress.item_type == item_type,
                    LiveBriefProgress.item_index == item_index,
                )
            ),
        )

    async def window_by_fingerprint(
        self,
        organisation_id: UUID,
        live_session_id: UUID,
        fingerprint: str,
    ) -> LiveProcessingWindow | None:
        return cast(
            LiveProcessingWindow | None,
            await self.session.scalar(
                select(LiveProcessingWindow).where(
                    LiveProcessingWindow.organisation_id == organisation_id,
                    LiveProcessingWindow.live_session_id == live_session_id,
                    LiveProcessingWindow.window_fingerprint == fingerprint,
                )
            ),
        )

    async def window_by_trigger(
        self,
        organisation_id: UUID,
        live_session_id: UUID,
        trigger_idempotency_key: str,
    ) -> LiveProcessingWindow | None:
        return cast(
            LiveProcessingWindow | None,
            await self.session.scalar(
                select(LiveProcessingWindow).where(
                    LiveProcessingWindow.organisation_id == organisation_id,
                    LiveProcessingWindow.live_session_id == live_session_id,
                    LiveProcessingWindow.trigger_idempotency_key == trigger_idempotency_key,
                )
            ),
        )

    async def count_windows_since(self, organisation_id: UUID, since: datetime) -> int:
        value = await self.session.scalar(
            select(func.count())
            .select_from(LiveProcessingWindow)
            .where(
                LiveProcessingWindow.organisation_id == organisation_id,
                LiveProcessingWindow.created_at >= since,
            )
        )
        return int(value or 0)

    async def latest_final_intelligence(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
    ) -> InteractionIntelligenceSnapshot | None:
        return cast(
            InteractionIntelligenceSnapshot | None,
            await self.session.scalar(
                select(InteractionIntelligenceSnapshot)
                .where(
                    InteractionIntelligenceSnapshot.organisation_id == organisation_id,
                    InteractionIntelligenceSnapshot.interaction_id == interaction_id,
                    InteractionIntelligenceSnapshot.validation_state == "validated",
                )
                .order_by(
                    InteractionIntelligenceSnapshot.version.desc(),
                    InteractionIntelligenceSnapshot.created_at.desc(),
                    InteractionIntelligenceSnapshot.id.desc(),
                )
                .limit(1)
            ),
        )
