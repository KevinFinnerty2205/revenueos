from __future__ import annotations

from revenueos.errors import PublicAPIError
from revenueos.recording_contracts import RecordingLifecycleStatus

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
