from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    Interaction,
    Meeting,
    OnlineMeetingMetadata,
    OnlineMeetingTranscriptImport,
    Transcript,
    TranscriptSegment,
    TranscriptVersion,
)


class OnlineMeetingRepository:
    """Every online-meeting read carries an explicit organisation predicate."""

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
        return cast(Interaction | None, await self.session.scalar(statement))

    async def get_metadata(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        *,
        for_update: bool = False,
    ) -> OnlineMeetingMetadata | None:
        statement = select(OnlineMeetingMetadata).where(
            OnlineMeetingMetadata.organisation_id == organisation_id,
            OnlineMeetingMetadata.interaction_id == interaction_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(OnlineMeetingMetadata | None, await self.session.scalar(statement))

    async def get_meeting(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        *,
        for_update: bool = False,
    ) -> Meeting | None:
        statement = select(Meeting).where(
            Meeting.organisation_id == organisation_id,
            Meeting.interaction_id == interaction_id,
            Meeting.deleted_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(Meeting | None, await self.session.scalar(statement))

    async def get_transcript(
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

    async def find_import_by_idempotency(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        user_id: UUID,
        idempotency_key: str,
    ) -> OnlineMeetingTranscriptImport | None:
        return cast(
            OnlineMeetingTranscriptImport | None,
            await self.session.scalar(
                select(OnlineMeetingTranscriptImport).where(
                    OnlineMeetingTranscriptImport.organisation_id == organisation_id,
                    OnlineMeetingTranscriptImport.interaction_id == interaction_id,
                    OnlineMeetingTranscriptImport.imported_by_user_id == user_id,
                    OnlineMeetingTranscriptImport.idempotency_key == idempotency_key,
                )
            ),
        )

    async def find_import_by_content(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
        content_sha256: str,
    ) -> OnlineMeetingTranscriptImport | None:
        return cast(
            OnlineMeetingTranscriptImport | None,
            await self.session.scalar(
                select(OnlineMeetingTranscriptImport).where(
                    OnlineMeetingTranscriptImport.organisation_id == organisation_id,
                    OnlineMeetingTranscriptImport.interaction_id == interaction_id,
                    OnlineMeetingTranscriptImport.content_sha256 == content_sha256,
                )
            ),
        )

    async def list_imports(
        self,
        organisation_id: UUID,
        interaction_id: UUID,
    ) -> list[OnlineMeetingTranscriptImport]:
        result = await self.session.scalars(
            select(OnlineMeetingTranscriptImport)
            .where(
                OnlineMeetingTranscriptImport.organisation_id == organisation_id,
                OnlineMeetingTranscriptImport.interaction_id == interaction_id,
            )
            .order_by(
                OnlineMeetingTranscriptImport.imported_at.desc(),
                OnlineMeetingTranscriptImport.id.desc(),
            )
        )
        return list(result.all())

    async def get_version(
        self,
        organisation_id: UUID,
        transcript_version_id: UUID,
    ) -> TranscriptVersion | None:
        return cast(
            TranscriptVersion | None,
            await self.session.scalar(
                select(TranscriptVersion).where(
                    TranscriptVersion.organisation_id == organisation_id,
                    TranscriptVersion.id == transcript_version_id,
                )
            ),
        )

    async def list_segments(
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
