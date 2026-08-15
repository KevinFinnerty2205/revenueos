from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    LiveBriefProgress,
    LiveInteractionSession,
    LiveProcessingWindow,
    ProvisionalSignal,
)


async def delete_live_intelligence(
    session: AsyncSession,
    organisation_id: UUID,
    *,
    interaction_ids: Sequence[UUID] = (),
    transcript_version_ids: Sequence[UUID] = (),
) -> None:
    """Delete one tenant's provisional aggregate before its parent source rows."""

    if not interaction_ids and not transcript_version_ids:
        return
    predicates = []
    if interaction_ids:
        predicates.append(LiveInteractionSession.interaction_id.in_(interaction_ids))
    if transcript_version_ids:
        predicates.append(LiveInteractionSession.transcript_version_id.in_(transcript_version_ids))
    session_ids = select(LiveInteractionSession.id).where(
        LiveInteractionSession.organisation_id == organisation_id,
        *predicates,
    )
    await session.execute(
        update(ProvisionalSignal)
        .where(
            ProvisionalSignal.organisation_id == organisation_id,
            ProvisionalSignal.live_session_id.in_(session_ids),
        )
        .values(superseded_by_id=None)
    )
    await session.execute(
        delete(LiveBriefProgress).where(
            LiveBriefProgress.organisation_id == organisation_id,
            LiveBriefProgress.live_session_id.in_(session_ids),
        )
    )
    await session.execute(
        delete(ProvisionalSignal).where(
            ProvisionalSignal.organisation_id == organisation_id,
            ProvisionalSignal.live_session_id.in_(session_ids),
        )
    )
    await session.execute(
        delete(LiveProcessingWindow).where(
            LiveProcessingWindow.organisation_id == organisation_id,
            LiveProcessingWindow.live_session_id.in_(session_ids),
        )
    )
    await session.execute(
        delete(LiveInteractionSession).where(
            LiveInteractionSession.organisation_id == organisation_id,
            *predicates,
        )
    )
