from __future__ import annotations

import base64
import logging
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from revenueos.auth import get_current_user
from revenueos.config import Settings
from revenueos.domain import OnlineMeetingPlatform
from revenueos.main import create_app
from revenueos.online_meeting_provider import (
    DeterministicFakeOnlineMeetingProviderAdapter,
    ProviderAdapterError,
    ProviderArtifact,
    ProviderMeetingMetadata,
    ProviderParticipant,
    UnsafeMeetingReference,
    map_participants_conservatively,
    normalize_meeting_reference,
)
from revenueos.online_meeting_transcripts import UnsafeTranscript, decode_and_parse_transcript

from .conftest import TEST_DB_URL, TEST_VISUAL_STORAGE
from .test_business_api import create_company, create_opportunity
from .test_interaction_api import create_interaction
from .test_meeting_api import cast_auth_dependency, secondary_user


def _encoded(value: str) -> str:
    return base64.b64encode(value.encode()).decode()


def _complete(client: TestClient, interaction_id: str) -> dict[str, object]:
    response = client.post(f"/api/v1/interactions/{interaction_id}/complete", json={})
    assert response.status_code == 200, response.text
    return response.json()


def _transcript_payload(
    content: str,
    *,
    file_name: str = "meeting.vtt",
    provenance: str = "platform_generated",
    key: str = "online-transcript-1",
) -> dict[str, object]:
    return {
        "fileName": file_name,
        "contentBase64": _encoded(content),
        "provenance": provenance,
        "language": "en-AU",
        "userAttestedAuthority": True,
        "externalProcessingAcknowledged": True,
        "idempotencyKey": key,
    }


def test_online_meeting_links_are_normalised_without_fetching(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="revenueos.interactions")
    cases = (
        (
            "microsoft_teams",
            "https://teams.microsoft.com/l/meetup-join/19%3ameeting_demo?context=secret#fragment",
            "https://teams.microsoft.com/l/meetup-join/19%3ameeting_demo",
        ),
        ("zoom", "https://acme.zoom.us/j/12345678901?pwd=secret", "https://acme.zoom.us/j/12345678901"),
        ("google_meet", "https://meet.google.com/abc-defg-hij?authuser=0", "https://meet.google.com/abc-defg-hij"),
    )
    for platform, meeting_url, safe_url in cases:
        interaction = create_interaction(
            client,
            title=f"{platform} meeting",
            interaction_type="online_meeting",
            meeting_platform=platform,
            meeting_url=meeting_url,
            external_meeting_id=f"external-{platform}",
        )
        assert interaction["meetingPlatform"] == platform
        assert interaction["meetingUrl"] == safe_url
        assert interaction["externalMeetingId"] == f"external-{platform}"
        assert interaction["meetingId"] is not None

    unsafe = client.post(
        "/api/v1/interactions",
        json={
            "title": "Unsafe online meeting",
            "interactionType": "online_meeting",
            "meetingPlatform": "google_meet",
            "meetingUrl": "https://127.0.0.1/internal",
        },
    )
    assert unsafe.status_code == 422
    assert unsafe.json()["code"] == "unsafe_meeting_url"

    other = create_interaction(
        client,
        title="Unspecified platform meeting",
        interaction_type="online_meeting",
        meeting_platform="other",
    )
    assert other["meetingUrl"] is None
    assert "context=secret" not in caplog.text
    assert "pwd=secret" not in caplog.text
    assert "authuser=0" not in caplog.text


def test_online_meeting_capabilities_are_server_authoritative(client: TestClient) -> None:
    interaction = create_interaction(
        client,
        interaction_type="online_meeting",
        meeting_platform="zoom",
    )
    response = client.get(f"/api/v1/interactions/{interaction['id']}/online-meeting/capabilities")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "meetingPlatform": "zoom",
        "recordingImport": False,
        "transcriptImport": True,
        "nativeFetch": False,
        "aiDebrief": True,
        "voiceJournal": True,
        "nativeConnectionState": "not_configured",
        "safeMessage": (
            "Authorised recording and transcript imports are available. No meeting-platform connection is configured."
        ),
    }


def test_authorised_vtt_import_preserves_provenance_and_reuses_existing_content(
    client: TestClient,
) -> None:
    company_id = str(create_company(client, name="Online meeting account")["id"])
    opportunity_id = str(create_opportunity(client, company_id, name="Online meeting opportunity")["id"])
    interaction = create_interaction(
        client,
        title="Google Meet discovery",
        interaction_type="online_meeting",
        company_id=company_id,
        opportunity_id=opportunity_id,
        meeting_platform="google_meet",
        meeting_url="https://meet.google.com/abc-defg-hij?token=discarded",
    )
    interaction_id = str(interaction["id"])
    completed = _complete(client, interaction_id)
    meeting_id = str(completed["meetingId"])
    content = """WEBVTT

00:00:01.000 --> 00:00:03.250
<v Customer>We need security approval.

00:00:04.000 --> 00:00:07.000
Seller: I will send the review pack.
"""
    payload = _transcript_payload(content)
    imported = client.post(
        f"/api/v1/interactions/{interaction_id}/online-meeting/transcript",
        json=payload,
    )
    assert imported.status_code == 201, imported.text
    body = imported.json()
    assert body["meetingId"] == meeting_id
    assert body["provenance"] == "platform_generated"
    assert body["sourceFormat"] == "vtt"
    assert body["timestampsPresent"] is True
    assert body["speakerLabelsPresent"] is True
    assert body["segments"][0] == {
        "sequenceNumber": 0,
        "startMs": 1000,
        "endMs": 3250,
        "speakerLabel": "Customer",
        "text": "We need security approval.",
    }
    assert body["duplicate"] is False

    repeated = client.post(
        f"/api/v1/interactions/{interaction_id}/online-meeting/transcript",
        json=payload,
    )
    assert repeated.status_code == 201
    assert repeated.json()["id"] == body["id"]
    assert repeated.json()["duplicate"] is True

    content_duplicate = client.post(
        f"/api/v1/interactions/{interaction_id}/online-meeting/transcript",
        json={**payload, "idempotencyKey": "online-transcript-other-tab"},
    )
    assert content_duplicate.status_code == 201
    assert content_duplicate.json()["id"] == body["id"]
    assert content_duplicate.json()["duplicate"] is True

    provenance_conflict = client.post(
        f"/api/v1/interactions/{interaction_id}/online-meeting/transcript",
        json={
            **payload,
            "provenance": "user_uploaded",
            "idempotencyKey": "online-transcript-conflicting-provenance",
        },
    )
    assert provenance_conflict.status_code == 409
    assert provenance_conflict.json()["code"] == "transcript_provenance_conflict"

    meeting_transcript = client.get(f"/api/v1/meetings/{meeting_id}/transcript")
    assert meeting_transcript.status_code == 200, meeting_transcript.text
    assert meeting_transcript.json()["source"] == "platform_generated"
    refreshed = client.get(f"/api/v1/interactions/{interaction_id}").json()
    assert refreshed["captureSource"] == "platform_transcript"
    assert refreshed["ingestionState"] == "ready"
    assert "transcript" in refreshed["captureMethods"]
    workspace = client.get(f"/api/v1/opportunities/{opportunity_id}/workspace")
    assert workspace.status_code == 200, workspace.text
    assert workspace.json()["latestInteractionCapture"]["interactionId"] == interaction_id


def test_transcript_import_validates_lifecycle_authority_encoding_and_idempotency(
    client: TestClient,
) -> None:
    interaction = create_interaction(
        client,
        interaction_type="online_meeting",
        meeting_platform="microsoft_teams",
    )
    interaction_id = str(interaction["id"])
    payload = _transcript_payload("Customer: Approved\nSeller: Thank you", file_name="meeting.txt")
    before_completion = client.post(
        f"/api/v1/interactions/{interaction_id}/online-meeting/transcript",
        json=payload,
    )
    assert before_completion.status_code == 409
    assert before_completion.json()["code"] == "interaction_not_completed"
    _complete(client, interaction_id)

    missing_authority = client.post(
        f"/api/v1/interactions/{interaction_id}/online-meeting/transcript",
        json={**payload, "userAttestedAuthority": False},
    )
    assert missing_authority.status_code == 422
    invalid_encoding = client.post(
        f"/api/v1/interactions/{interaction_id}/online-meeting/transcript",
        json={**payload, "contentBase64": "not-base64", "idempotencyKey": "bad-encoding"},
    )
    assert invalid_encoding.status_code == 422
    assert invalid_encoding.json()["code"] == "invalid_transcript_encoding"
    malformed = client.post(
        f"/api/v1/interactions/{interaction_id}/online-meeting/transcript",
        json={
            **payload,
            "contentBase64": _encoded("WEBVTT\n\nnot a cue"),
            "fileName": "bad.vtt",
            "idempotencyKey": "malformed-vtt",
        },
    )
    assert malformed.status_code == 422
    assert malformed.json()["code"] == "malformed_transcript"

    imported = client.post(
        f"/api/v1/interactions/{interaction_id}/online-meeting/transcript",
        json=payload,
    )
    assert imported.status_code == 201, imported.text
    conflict = client.post(
        f"/api/v1/interactions/{interaction_id}/online-meeting/transcript",
        json={**payload, "contentBase64": _encoded("Different"), "fileName": "other.txt"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"


def test_online_transcript_import_is_tenant_hidden(
    app: FastAPI,
    client: TestClient,
) -> None:
    interaction = create_interaction(
        client,
        interaction_type="online_meeting",
        meeting_platform="zoom",
    )
    interaction_id = str(interaction["id"])
    _complete(client, interaction_id)
    imported = client.post(
        f"/api/v1/interactions/{interaction_id}/online-meeting/transcript",
        json=_transcript_payload("Seller: Follow up", file_name="meeting.txt"),
    )
    assert imported.status_code == 201, imported.text

    app.dependency_overrides[get_current_user] = cast_auth_dependency(secondary_user())
    hidden = client.get(f"/api/v1/interactions/{interaction_id}/online-meeting/transcripts")
    assert hidden.status_code == 404
    app.dependency_overrides.clear()


@pytest.fixture
def recording_enabled_app() -> FastAPI:
    return create_app(
        Settings(
            environment="test",
            auth_mode="mock",
            mock_auth_enabled=True,
            database_url=TEST_DB_URL,
            log_level="WARNING",
            cors_origins="http://localhost:3000",
            visual_storage_directory=str(TEST_VISUAL_STORAGE),
            feature_recording_capture_enabled=True,
        )
    )


@pytest.fixture
def recording_enabled_client(recording_enabled_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(recording_enabled_app) as test_client:
        yield test_client


def test_online_meeting_accepts_platform_recording_provenance(
    recording_enabled_client: TestClient,
) -> None:
    interaction = create_interaction(
        recording_enabled_client,
        interaction_type="online_meeting",
        meeting_platform="zoom",
    )
    interaction_id = str(interaction["id"])
    imported = recording_enabled_client.post(
        f"/api/v1/interactions/{interaction_id}/recordings",
        json={
            "recordingType": "imported_audio_recording",
            "recordingSource": "platform_recording",
            "expectedMimeType": "audio/webm",
            "noticeVersion": 1,
            "consentMethod": "contractual_authority",
            "userAttestedAuthority": True,
            "idempotencyKey": "online-platform-recording",
        },
    )
    assert imported.status_code == 201, imported.text
    assert imported.json()["recordingSource"] == "platform_recording"
    refreshed = recording_enabled_client.get(f"/api/v1/interactions/{interaction_id}").json()
    assert refreshed["captureSource"] == "platform_recording"
    assert refreshed["ingestionState"] == "uploading"


def test_provider_adapter_is_deterministic_authorised_and_conservative() -> None:
    now = datetime.now(UTC)
    metadata = ProviderMeetingMetadata(
        platform=OnlineMeetingPlatform.GOOGLE_MEET,
        external_meeting_id="conference-record-1",
        scheduled_start_at=now,
        scheduled_end_at=now,
        actual_start_at=now,
        actual_end_at=now,
    )
    artifact = ProviderArtifact("transcript-1", "transcript", now, "text/vtt", 42)
    participant = ProviderParticipant("participant-1", "Casey Customer", "CASEY@example.test")
    adapter = DeterministicFakeOnlineMeetingProviderAdapter(
        OnlineMeetingPlatform.GOOGLE_MEET,
        metadata,
        (artifact,),
        {"transcript-1": b"WEBVTT"},
        (participant,),
    )

    import asyncio

    assert asyncio.run(adapter.list_authorised_artifacts("conference-record-1")) == (artifact,)
    assert asyncio.run(adapter.retrieve_artifact("transcript-1")) == b"WEBVTT"
    mapped = map_participants_conservatively((participant,), {"casey@example.test": "contact-1"})
    assert mapped[0].contact_id == "contact-1"
    unmatched = map_participants_conservatively(
        (ProviderParticipant("participant-2", "Same name", None),),
        {"casey@example.test": "contact-1"},
    )
    assert unmatched[0].contact_id is None

    denied = DeterministicFakeOnlineMeetingProviderAdapter(
        OnlineMeetingPlatform.GOOGLE_MEET,
        metadata,
        authorised=False,
    )
    with pytest.raises(PermissionError):
        asyncio.run(denied.normalize_meeting_metadata("conference-record-1"))

    empty = DeterministicFakeOnlineMeetingProviderAdapter(
        OnlineMeetingPlatform.GOOGLE_MEET,
        metadata,
    )
    assert asyncio.run(empty.list_authorised_artifacts("conference-record-1")) == ()
    with pytest.raises(LookupError):
        asyncio.run(empty.retrieve_artifact("missing"))

    failures = DeterministicFakeOnlineMeetingProviderAdapter(
        OnlineMeetingPlatform.GOOGLE_MEET,
        metadata,
        operation_failures={
            "list_authorised_artifacts": "transient",
            "retrieve_artifact": "permanent",
        },
    )
    with pytest.raises(ProviderAdapterError) as transient:
        asyncio.run(failures.list_authorised_artifacts("conference-record-1"))
    assert transient.value.retryable is True
    with pytest.raises(ProviderAdapterError) as permanent:
        asyncio.run(failures.retrieve_artifact("transcript-1"))
    assert permanent.value.retryable is False


def test_transcript_parsers_and_meeting_reference_rejections() -> None:
    parsed = decode_and_parse_transcript(
        _encoded("1\n00:00:01,000 --> 00:00:02,500\nSpeaker: Hello"),
        "meeting.srt",
        max_bytes=1024,
        max_characters=1024,
    )
    assert parsed.source_format == "srt"
    assert parsed.segments[0].end_ms == 2500
    assert parsed.segments[0].speaker_label == "Speaker"
    with pytest.raises(UnsafeTranscript, match="valid UTF-8"):
        decode_and_parse_transcript(
            base64.b64encode(b"\xff").decode(),
            "meeting.txt",
            max_bytes=1024,
            max_characters=1024,
        )
    with pytest.raises(UnsafeTranscript, match="no larger"):
        decode_and_parse_transcript(
            _encoded("too large"),
            "meeting.txt",
            max_bytes=3,
            max_characters=1024,
        )
    with pytest.raises(UnsafeMeetingReference):
        normalize_meeting_reference(OnlineMeetingPlatform.ZOOM, "http://zoom.us/j/123456")
    with pytest.raises(UnsafeMeetingReference):
        normalize_meeting_reference(OnlineMeetingPlatform.GOOGLE_MEET, "https://example.com/internal")
