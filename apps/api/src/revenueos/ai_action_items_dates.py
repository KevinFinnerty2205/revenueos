from __future__ import annotations

import re
from datetime import date, datetime, timedelta

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def normalise_action_item_due_date(
    expression: str | None,
    meeting_date: date | datetime,
) -> str | None:
    """Normalise a narrow due-date vocabulary using the supplied meeting date.

    ``this <weekday>`` stays within the meeting's ISO week and is rejected if it
    has already passed. ``next <weekday>`` always means the following ISO week.
    End of week means Friday in RevenueOS's Monday-to-Friday business calendar.
    Unknown or ambiguous wording is deliberately returned as ``None``.
    """

    if expression is None:
        return None
    normalised = " ".join(expression.lower().strip().split())
    if not normalised:
        return None
    if normalised.startswith("by "):
        normalised = normalised[3:]
    reference = meeting_date.date() if isinstance(meeting_date, datetime) else meeting_date

    try:
        parsed = date.fromisoformat(normalised)
    except ValueError:
        parsed = None
    if parsed is not None and parsed.isoformat() == normalised:
        return parsed.isoformat()

    if normalised == "today":
        return reference.isoformat()
    if normalised == "tomorrow":
        return (reference + timedelta(days=1)).isoformat()

    weekday_match = re.fullmatch(
        r"(this|next) (monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
        normalised,
    )
    if weekday_match is not None:
        qualifier, weekday_name = weekday_match.groups()
        week_start = reference - timedelta(days=reference.weekday())
        week_offset = 7 if qualifier == "next" else 0
        candidate = week_start + timedelta(days=week_offset + _WEEKDAYS[weekday_name])
        return candidate.isoformat() if candidate >= reference else None

    if normalised in {"end of this week", "the end of this week"}:
        candidate = reference + timedelta(days=4 - reference.weekday())
        return candidate.isoformat() if candidate >= reference else None
    if normalised in {"end of next week", "the end of next week"}:
        week_start = reference - timedelta(days=reference.weekday())
        return (week_start + timedelta(days=11)).isoformat()
    return None
