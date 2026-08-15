from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from urllib.parse import SplitResult, urlsplit, urlunsplit

from revenueos.domain import OnlineMeetingPlatform

ArtifactKind = Literal["recording", "transcript"]
ProviderFailureKind = Literal["transient", "permanent"]

_GOOGLE_MEET_CODE = re.compile(r"^/[a-z]{3}-[a-z]{4}-[a-z]{3}/?$")
_ZOOM_PATH = re.compile(r"^/(?:j/\d{6,20}|s/\d{6,20}|wc/join/\d{6,20}|my/[A-Za-z0-9._-]{1,128})/?$")


class UnsafeMeetingReference(ValueError):
    """Raised when a meeting reference is not safe for storage or browser navigation."""


class ProviderAdapterError(RuntimeError):
    """Typed provider failure used by adapter contract tests and future orchestration."""

    def __init__(self, operation: str, *, retryable: bool) -> None:
        super().__init__(f"The fake provider {operation} operation failed.")
        self.operation = operation
        self.retryable = retryable


@dataclass(frozen=True)
class NormalizedMeetingReference:
    platform: OnlineMeetingPlatform
    safe_url: str
    host: str


@dataclass(frozen=True)
class ProviderMeetingMetadata:
    platform: OnlineMeetingPlatform
    external_meeting_id: str | None
    scheduled_start_at: datetime | None
    scheduled_end_at: datetime | None
    actual_start_at: datetime | None
    actual_end_at: datetime | None


@dataclass(frozen=True)
class ProviderArtifact:
    artifact_id: str
    kind: ArtifactKind
    created_at: datetime
    media_type: str
    byte_size: int | None = None


@dataclass(frozen=True)
class ProviderParticipant:
    external_participant_id: str
    display_name: str | None
    email: str | None


@dataclass(frozen=True)
class MappedParticipant:
    external_participant_id: str
    contact_id: str | None
    display_label: str | None


class OnlineMeetingProviderAdapter(Protocol):
    """Provider-neutral boundary for deliberately authorised meeting artefacts."""

    platform: OnlineMeetingPlatform

    def validate_meeting_reference(self, value: str) -> NormalizedMeetingReference: ...

    async def normalize_meeting_metadata(self, external_meeting_id: str) -> ProviderMeetingMetadata: ...

    async def list_authorised_artifacts(self, external_meeting_id: str) -> tuple[ProviderArtifact, ...]: ...

    async def retrieve_artifact(self, artifact_id: str) -> bytes: ...

    async def list_participants(self, external_meeting_id: str) -> tuple[ProviderParticipant, ...]: ...


def normalize_meeting_reference(
    platform: OnlineMeetingPlatform,
    value: str,
) -> NormalizedMeetingReference:
    """Return a query/fragment-free approved meeting URL; never performs a fetch."""

    candidate = value.strip()
    if len(candidate) > 1_000:
        raise UnsafeMeetingReference("The meeting link is too long.")
    try:
        parsed = urlsplit(candidate)
    except ValueError as exc:
        raise UnsafeMeetingReference("The meeting link is malformed.") from exc
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise UnsafeMeetingReference("Use an HTTPS meeting link.")
    if parsed.username is not None or parsed.password is not None or parsed.port not in {None, 443}:
        raise UnsafeMeetingReference("The meeting link contains unsupported credentials or a port.")
    host = parsed.hostname.rstrip(".").lower()
    path = _normalised_path(parsed)
    if platform == OnlineMeetingPlatform.MICROSOFT_TEAMS:
        if host not in {"teams.microsoft.com", "teams.live.com"}:
            raise UnsafeMeetingReference("Use a Microsoft Teams meeting link.")
        if not (path.startswith("/l/meetup-join/") or path.startswith("/meet/")):
            raise UnsafeMeetingReference("The Microsoft Teams meeting path is not supported.")
    elif platform == OnlineMeetingPlatform.ZOOM:
        if host != "zoom.us" and not host.endswith(".zoom.us"):
            raise UnsafeMeetingReference("Use a Zoom meeting link.")
        if _ZOOM_PATH.fullmatch(path) is None:
            raise UnsafeMeetingReference("The Zoom meeting path is not supported.")
    elif platform == OnlineMeetingPlatform.GOOGLE_MEET:
        if host != "meet.google.com" or _GOOGLE_MEET_CODE.fullmatch(path) is None:
            raise UnsafeMeetingReference("Use a Google Meet meeting link.")
    else:
        raise UnsafeMeetingReference("Store an external meeting reference instead of an unapproved link.")
    safe = urlunsplit(("https", host, path.rstrip("/") or "/", "", ""))
    return NormalizedMeetingReference(platform=platform, safe_url=safe, host=host)


def map_participants_conservatively(
    participants: tuple[ProviderParticipant, ...],
    authorised_contacts_by_email: dict[str, str],
) -> tuple[MappedParticipant, ...]:
    """Map only exact authorised email matches; names never create or merge Contacts."""

    normalised_contacts = {
        email.strip().lower(): contact_id for email, contact_id in authorised_contacts_by_email.items()
    }
    return tuple(
        MappedParticipant(
            external_participant_id=participant.external_participant_id,
            contact_id=(
                normalised_contacts.get(participant.email.strip().lower()) if participant.email is not None else None
            ),
            display_label=participant.display_name,
        )
        for participant in participants
    )


class DeterministicFakeOnlineMeetingProviderAdapter:
    """Test-only adapter with no network, OAuth, webhook or production registration."""

    def __init__(
        self,
        platform: OnlineMeetingPlatform,
        metadata: ProviderMeetingMetadata,
        artifacts: tuple[ProviderArtifact, ...] = (),
        artifact_content: dict[str, bytes] | None = None,
        participants: tuple[ProviderParticipant, ...] = (),
        *,
        authorised: bool = True,
        operation_failures: dict[str, ProviderFailureKind] | None = None,
    ) -> None:
        self.platform = platform
        self._metadata = metadata
        self._artifacts = artifacts
        self._artifact_content = artifact_content or {}
        self._participants = participants
        self._authorised = authorised
        self._operation_failures = operation_failures or {}

    def validate_meeting_reference(self, value: str) -> NormalizedMeetingReference:
        return normalize_meeting_reference(self.platform, value)

    async def normalize_meeting_metadata(self, external_meeting_id: str) -> ProviderMeetingMetadata:
        self._require_authorised()
        self._maybe_fail("normalize_meeting_metadata")
        self._require_meeting(external_meeting_id)
        return self._metadata

    async def list_authorised_artifacts(self, external_meeting_id: str) -> tuple[ProviderArtifact, ...]:
        self._require_authorised()
        self._maybe_fail("list_authorised_artifacts")
        self._require_meeting(external_meeting_id)
        return self._artifacts

    async def retrieve_artifact(self, artifact_id: str) -> bytes:
        self._require_authorised()
        self._maybe_fail("retrieve_artifact")
        try:
            return self._artifact_content[artifact_id]
        except KeyError as exc:
            raise LookupError("The fake artefact was not found.") from exc

    async def list_participants(self, external_meeting_id: str) -> tuple[ProviderParticipant, ...]:
        self._require_authorised()
        self._maybe_fail("list_participants")
        self._require_meeting(external_meeting_id)
        return self._participants

    def _require_authorised(self) -> None:
        if not self._authorised:
            raise PermissionError("The fake provider connection is not authorised.")

    def _require_meeting(self, external_meeting_id: str) -> None:
        if external_meeting_id != self._metadata.external_meeting_id:
            raise LookupError("The fake meeting was not found.")

    def _maybe_fail(self, operation: str) -> None:
        failure = self._operation_failures.get(operation)
        if failure is not None:
            raise ProviderAdapterError(operation, retryable=failure == "transient")


def _normalised_path(parsed: SplitResult) -> str:
    if not parsed.path.startswith("/") or "\\" in parsed.path or "\x00" in parsed.path:
        raise UnsafeMeetingReference("The meeting link path is malformed.")
    if any(part in {".", ".."} for part in parsed.path.split("/")):
        raise UnsafeMeetingReference("The meeting link path is malformed.")
    return parsed.path
