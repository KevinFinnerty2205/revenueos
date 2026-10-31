from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import Evidence, InteractionIntelligenceSnapshot


async def eligible_interaction_snapshot_ids(
    session: AsyncSession,
    organisation_id: UUID,
    snapshots: Sequence[InteractionIntelligenceSnapshot],
) -> set[UUID]:
    """Return validated-snapshot IDs whose complete Evidence lineage is still live."""

    required_by_snapshot: dict[UUID, tuple[UUID, UUID, set[UUID]]] = {}
    all_evidence_ids: set[UUID] = set()
    for snapshot in snapshots:
        try:
            evidence_ids = {UUID(value) for value in snapshot.source_evidence_ids}
        except (TypeError, ValueError):
            continue
        if not evidence_ids:
            continue
        required_by_snapshot[snapshot.id] = (
            snapshot.interaction_id,
            snapshot.session_id,
            evidence_ids,
        )
        all_evidence_ids.update(evidence_ids)
    if not all_evidence_ids:
        return set()

    rows = (
        await session.execute(
            select(
                Evidence.id,
                Evidence.interaction_id,
                Evidence.capture_session_id,
            ).where(
                Evidence.organisation_id == organisation_id,
                Evidence.id.in_(all_evidence_ids),
                Evidence.validation_state == "verified",
                Evidence.lifecycle_status == "available",
                Evidence.deleted_at.is_(None),
            )
        )
    ).all()
    available_by_scope: dict[tuple[UUID, UUID], set[UUID]] = {}
    for evidence_id, interaction_id, capture_session_id in rows:
        if interaction_id is None or capture_session_id is None:
            continue
        available_by_scope.setdefault((interaction_id, capture_session_id), set()).add(evidence_id)

    return {
        snapshot_id
        for snapshot_id, (interaction_id, session_id, required_ids) in required_by_snapshot.items()
        if required_ids.issubset(available_by_scope.get((interaction_id, session_id), set()))
    }
