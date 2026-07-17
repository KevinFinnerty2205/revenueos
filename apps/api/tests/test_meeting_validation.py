from datetime import datetime

import pytest
from pydantic import ValidationError

from revenueos.meeting_contracts import (
    MeetingCreate,
    MeetingParticipantCreate,
    MeetingUpdate,
    TranscriptCreate,
    TranscriptUpdate,
)


@pytest.mark.parametrize(
    ("contract", "payload"),
    [
        (MeetingCreate, {"title": " ", "meetingDate": "2026-08-01T00:00:00Z"}),
        (MeetingCreate, {"title": "Meeting"}),
        (MeetingCreate, {"title": "Meeting", "meetingDate": datetime(2026, 8, 1, 10, 0)}),
        (MeetingParticipantCreate, {}),
        (MeetingParticipantCreate, {"displayName": "Guest", "email": "invalid"}),
        (TranscriptCreate, {"rawText": " ", "language": "en"}),
        (TranscriptCreate, {"rawText": "Text", "language": "invalid_language_code"}),
        (TranscriptUpdate, {"rawText": "Text", "version": 0}),
    ],
)
def test_meeting_contract_validation_rejects_invalid_models(
    contract: type[object],
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        contract.model_validate(payload)  # type: ignore[attr-defined]


def test_meeting_contracts_forbid_unrecognised_fields_and_empty_updates() -> None:
    with pytest.raises(ValidationError):
        MeetingCreate.model_validate(
            {
                "title": "Discovery",
                "meetingDate": "2026-08-01T00:00:00Z",
                "organisationId": "00000000-0000-4000-8000-000000000099",
            }
        )
    with pytest.raises(ValidationError):
        MeetingUpdate.model_validate({})
    with pytest.raises(ValidationError):
        TranscriptUpdate.model_validate({"version": 1})
