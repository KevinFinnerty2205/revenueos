from __future__ import annotations

from datetime import date
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    CaptureSession,
    Interaction,
    Meeting,
    RecordingChunk,
    RecordingSession,
    RecordingUsageCounter,
    Transcript,
    TranscriptSegment,
    TranscriptVersion,
)


class RecordingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_interaction(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        *,
        for_update: bool = False,
    ) -> Interaction | None:
        statement = select(Interaction).where(
            Interaction.organisation_id == organisation_id,
            Interaction.id == interaction_id,
            Interaction.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(
            Interaction | None,
            await self.session.scalar(statement),
        )

    async def get_meeting_for_interaction(self, organisation_id: UUID, interaction_id: UUID) -> Meeting | None:
        return cast(
            Meeting | None,
            await self.session.scalar(
                select(Meeting).where(
                    Meeting.organisation_id == organisation_id,
                    Meeting.interaction_id == interaction_id,
                    Meeting.deleted_at.is_(None),
                )
            ),
        )

    async def find_idempotent_recording(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        user_id: UUID,
        idempotency_key: str,
    ) -> RecordingSession | None:
        return cast(
            RecordingSession | None,
            await self.session.scalar(
                select(RecordingSession).where(
                    RecordingSession.organisation_id == organisation_id,
                    RecordingSession.interaction_id == interaction_id,
                    RecordingSession.created_by_user_id == user_id,
                    RecordingSession.idempotency_key == idempotency_key,
                )
            ),
        )

    async def get_recording(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        recording_id: UUID,
        *,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> RecordingSession | None:
        conditions = [
            RecordingSession.organisation_id == organisation_id,
            RecordingSession.interaction_id == interaction_id,
            RecordingSession.id == recording_id,
        ]
        if not include_deleted:
            conditions.append(RecordingSession.deleted_at.is_(None))
        statement = select(RecordingSession).where(*conditions)
        if for_update:
            statement = statement.with_for_update()
        return cast(RecordingSession | None, await self.session.scalar(statement))

    async def list_recordings(self, organisation_id: UUID, interaction_id: UUID) -> list[RecordingSession]:
        result = await self.session.scalars(
            select(RecordingSession)
            .where(
                RecordingSession.organisation_id == organisation_id,
                RecordingSession.interaction_id == interaction_id,
                RecordingSession.deleted_at.is_(None),
            )
            .order_by(RecordingSession.created_at.desc(), RecordingSession.id.desc())
        )
        return list(result.all())

    async def active_recording_count(self, organisation_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(RecordingSession)
                .where(
                    RecordingSession.organisation_id == organisation_id,
                    RecordingSession.lifecycle_status.in_(
                        ("created", "recording", "uploading", "uploaded", "transcribing")
                    ),
                    RecordingSession.deleted_at.is_(None),
                )
            )
            or 0
        )

    async def active_recording_for_interaction(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
    ) -> RecordingSession | None:
        return cast(
            RecordingSession | None,
            await self.session.scalar(
                select(RecordingSession)
                .where(
                    RecordingSession.organisation_id == organisation_id,
                    RecordingSession.interaction_id == interaction_id,
                    RecordingSession.lifecycle_status.in_(
                        ("created", "recording", "uploading", "uploaded", "transcribing")
                    ),
                    RecordingSession.deleted_at.is_(None),
                )
                .order_by(RecordingSession.created_at.desc(), RecordingSession.id.desc())
                .limit(1)
            ),
        )

    async def find_chunk(
        self,
        organisation_id: UUID,
        recording_id: UUID,
        sequence_number: int,
        *,
        for_update: bool = False,
    ) -> RecordingChunk | None:
        statement = select(RecordingChunk).where(
            RecordingChunk.organisation_id == organisation_id,
            RecordingChunk.recording_session_id == recording_id,
            RecordingChunk.sequence_number == sequence_number,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(RecordingChunk | None, await self.session.scalar(statement))

    async def get_chunk(
        self,
        organisation_id: UUID,
        recording_id: UUID,
        chunk_id: UUID,
        *,
        for_update: bool = False,
    ) -> RecordingChunk | None:
        statement = select(RecordingChunk).where(
            RecordingChunk.organisation_id == organisation_id,
            RecordingChunk.recording_session_id == recording_id,
            RecordingChunk.id == chunk_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(RecordingChunk | None, await self.session.scalar(statement))

    async def list_chunks(
        self,
        organisation_id: UUID,
        recording_id: UUID,
        *,
        for_update: bool = False,
    ) -> list[RecordingChunk]:
        statement = (
            select(RecordingChunk)
            .where(
                RecordingChunk.organisation_id == organisation_id,
                RecordingChunk.recording_session_id == recording_id,
            )
            .order_by(RecordingChunk.sequence_number)
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.scalars(statement)
        return list(result.all())

    async def daily_usage(
        self,
        organisation_id: UUID,
        usage_date: date,
        *,
        for_update: bool = False,
    ) -> RecordingUsageCounter | None:
        statement = select(RecordingUsageCounter).where(
            RecordingUsageCounter.organisation_id == organisation_id,
            RecordingUsageCounter.usage_date == usage_date,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(RecordingUsageCounter | None, await self.session.scalar(statement))

    async def get_capture_session(
        self,
        organisation_id: UUID,
        capture_session_id: UUID,
        *,
        for_update: bool = False,
    ) -> CaptureSession | None:
        statement = select(CaptureSession).where(
            CaptureSession.organisation_id == organisation_id,
            CaptureSession.id == capture_session_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(CaptureSession | None, await self.session.scalar(statement))

    async def get_current_transcript(
        self,
        organisation_id: UUID,
        meeting_id: UUID,
        *,
        for_update: bool = False,
    ) -> Transcript | None:
        statement = select(Transcript).where(
            Transcript.organisation_id == organisation_id,
            Transcript.meeting_id == meeting_id,
            Transcript.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(Transcript | None, await self.session.scalar(statement))

    async def find_transcript_version(
        self,
        organisation_id: UUID,
        transcript_id: UUID,
        version: int,
    ) -> TranscriptVersion | None:
        return cast(
            TranscriptVersion | None,
            await self.session.scalar(
                select(TranscriptVersion).where(
                    TranscriptVersion.organisation_id == organisation_id,
                    TranscriptVersion.transcript_id == transcript_id,
                    TranscriptVersion.version == version,
                )
            ),
        )

    async def get_recording_transcript_version(
        self,
        organisation_id: UUID,
        recording_id: UUID,
    ) -> TranscriptVersion | None:
        return cast(
            TranscriptVersion | None,
            await self.session.scalar(
                select(TranscriptVersion).where(
                    TranscriptVersion.organisation_id == organisation_id,
                    TranscriptVersion.recording_session_id == recording_id,
                    TranscriptVersion.deleted_at.is_(None),
                )
            ),
        )

    async def list_transcript_segments(
        self,
        organisation_id: UUID,
        transcript_version_id: UUID,
    ) -> list[TranscriptSegment]:
        result = await self.session.scalars(
            select(TranscriptSegment)
            .where(
                TranscriptSegment.organisation_id == organisation_id,
                TranscriptSegment.transcript_version_id == transcript_version_id,
                TranscriptSegment.deleted_at.is_(None),
            )
            .order_by(TranscriptSegment.sequence_number)
        )
        return list(result.all())

    async def transcribing_count(self, organisation_id: UUID) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(RecordingSession)
                .where(
                    RecordingSession.organisation_id == organisation_id,
                    RecordingSession.lifecycle_status == "transcribing",
                    RecordingSession.deleted_at.is_(None),
                )
            )
            or 0
        )
