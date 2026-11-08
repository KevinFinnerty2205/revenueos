from __future__ import annotations

from typing import Protocol
from uuid import UUID


class ProgressiveTranscriptionRegistry(Protocol):
    """Narrow process-local boundary used by durable authority lifecycle services."""

    async def retire_interaction_sessions(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
    ) -> int: ...

    async def retire_recording_session(
        self,
        organisation_id: UUID,
        recording_session_id: UUID,
    ) -> bool: ...

    async def retire_user_sessions(
        self,
        organisation_id: UUID,
        user_id: UUID,
    ) -> int: ...
