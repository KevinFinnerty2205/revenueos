from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.errors import PublicAPIError
from revenueos.recording_contracts import RecordingLifecycleStatus
from revenueos.recording_repositories import RecordingRepository

ALLOWED_RECORDING_TRANSITIONS: dict[RecordingLifecycleStatus, frozenset[RecordingLifecycleStatus]] = {
    "created": frozenset({"recording", "uploading", "cancelled", "deleting"}),
    "recording": frozenset({"uploading", "failed", "cancelled", "deleting"}),
    "uploading": frozenset({"uploaded", "failed", "cancelled", "deleting"}),
    "uploaded": frozenset({"transcribing", "failed", "deleting"}),
    "transcribing": frozenset({"uploaded", "completed", "failed", "deleting"}),
    "completed": frozenset({"deleting"}),
    "failed": frozenset({"uploading", "uploaded", "deleting"}),
    "cancelled": frozenset({"deleting"}),
    "deleting": frozenset({"deleted"}),
    "deleted": frozenset(),
}


async def require_live_recording_finished(
    session: AsyncSession,
    organisation_id: UUID,
    interaction_id: UUID,
) -> None:
    """Check for live capture under the caller's Interaction row lock."""
    if await RecordingRepository(session).has_live_recording_in_progress(
        organisation_id, interaction_id, datetime.now(UTC)
    ):
        raise PublicAPIError(
            "live_recording_in_progress",
            "Finish recording in its original tab or cancel the interrupted recording before ending this conversation.",
            409,
        )


def transition_recording(
    current: str,
    target: RecordingLifecycleStatus,
) -> RecordingLifecycleStatus:
    if current not in ALLOWED_RECORDING_TRANSITIONS:
        raise PublicAPIError("invalid_recording_state", "The recording lifecycle state is invalid.", 409)
    resolved: RecordingLifecycleStatus = current
    if resolved == target:
        return resolved
    if target not in ALLOWED_RECORDING_TRANSITIONS[resolved]:
        raise PublicAPIError(
            "invalid_recording_transition",
            f"A recording cannot move from {current} to {target}.",
            409,
        )
    return target
