from __future__ import annotations

from datetime import datetime
from uuid import UUID

from revenueos.models import Interaction, Meeting

MEETING_TO_INTERACTION_TYPE = {
    "remote": "online_meeting",
    "phone": "phone_call",
    "in_person": "face_to_face_meeting",
    "other": "manual_interaction",
}
INTERACTION_TO_MEETING_TYPE = {value: key for key, value in MEETING_TO_INTERACTION_TYPE.items()}
MEETING_TO_INTERACTION_STATUS = {
    "scheduled": "planned",
    "completed": "completed",
    "cancelled": "cancelled",
}
INTERACTION_TO_MEETING_STATUS = {
    "planned": "scheduled",
    "in_progress": "scheduled",
    "completed": "completed",
    "cancelled": "cancelled",
}
INTERACTION_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "planned": frozenset({"in_progress", "completed", "cancelled"}),
    "in_progress": frozenset({"completed", "cancelled"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
}


def interaction_type_for_meeting(meeting_type: str) -> str:
    return MEETING_TO_INTERACTION_TYPE[meeting_type]


def interaction_status_for_meeting(meeting_status: str) -> str:
    return MEETING_TO_INTERACTION_STATUS[meeting_status]


def meeting_type_for_interaction(interaction_type: str) -> str | None:
    return INTERACTION_TO_MEETING_TYPE.get(interaction_type)


def meeting_status_for_interaction(lifecycle_status: str) -> str:
    return INTERACTION_TO_MEETING_STATUS[lifecycle_status]


def interaction_transition_is_allowed(current: str, target: str) -> bool:
    return target == current or target in INTERACTION_ALLOWED_TRANSITIONS[current]


def project_meeting_to_interaction(meeting: Meeting, interaction: Interaction) -> None:
    """Apply Meeting API writes to the authoritative shared Interaction fields."""

    interaction.title = meeting.title
    interaction.company_id = meeting.company_id
    interaction.opportunity_id = meeting.opportunity_id
    interaction.interaction_type = interaction_type_for_meeting(meeting.meeting_type)
    interaction.lifecycle_status = interaction_status_for_meeting(meeting.status)
    interaction.scheduled_start_at = meeting.meeting_date
    if meeting.status == "completed":
        interaction.actual_start_at = interaction.actual_start_at or meeting.meeting_date
        interaction.actual_end_at = interaction.actual_end_at or meeting.meeting_date
    interaction.deleted_at = meeting.deleted_at


def project_interaction_to_meeting(
    interaction: Interaction,
    meeting: Meeting,
    *,
    updated_by: UUID,
    updated_at: datetime,
) -> None:
    """Maintain the stable Meeting compatibility projection in the same transaction."""

    meeting_type = meeting_type_for_interaction(interaction.interaction_type)
    if meeting_type is None:
        raise ValueError("The linked Interaction type is not Meeting-compatible.")
    meeting.title = interaction.title
    meeting.company_id = interaction.company_id
    meeting.opportunity_id = interaction.opportunity_id
    meeting.meeting_type = meeting_type
    meeting.status = meeting_status_for_interaction(interaction.lifecycle_status)
    if interaction.scheduled_start_at is not None:
        meeting.meeting_date = interaction.scheduled_start_at
    meeting.updated_by = updated_by
    meeting.updated_at = updated_at
    meeting.deleted_at = interaction.deleted_at
