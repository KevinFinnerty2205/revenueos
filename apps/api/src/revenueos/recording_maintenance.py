from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.models import (
    BetaSystemEvent,
    CaptureSession,
    Evidence,
    RecordingChunk,
    RecordingSession,
    Transcript,
    TranscriptSegment,
    TranscriptVersion,
)
from revenueos.recording_lifecycle import transition_recording
from revenueos.recording_storage import (
    PrivateObjectStorage,
    PrivateObjectStorageError,
    create_recording_storage,
)


@dataclass(frozen=True)
class RawRecordingRetentionResult:
    organisation_id: UUID
    dry_run: bool
    eligible_recordings: int
    eligible_objects: int
    removed_objects: int
    retry_required: int


@dataclass(frozen=True)
class RecordingReconciliationResult:
    organisation_id: UUID
    repaired: bool
    database_objects: int
    storage_objects: int
    missing_objects: tuple[str, ...]
    orphaned_objects: tuple[str, ...]
    abandoned_sessions: int
    deletion_retries: int
    repaired_missing_objects: int
    removed_orphaned_objects: int
    cleaned_abandoned_sessions: int
    completed_deletion_retries: int


async def delete_recording_objects(
    session: AsyncSession,
    settings: Settings,
    organisation_id: UUID,
    interaction_ids: list[UUID],
) -> None:
    """Delete tenant recording objects before a destructive database cascade."""
    if not interaction_ids:
        return
    keys = list(
        (
            await session.scalars(
                select(RecordingChunk.storage_key)
                .join(
                    RecordingSession,
                    (RecordingSession.organisation_id == RecordingChunk.organisation_id)
                    & (RecordingSession.id == RecordingChunk.recording_session_id),
                )
                .where(
                    RecordingChunk.organisation_id == organisation_id,
                    RecordingSession.interaction_id.in_(interaction_ids),
                    RecordingChunk.upload_state != "deleted",
                )
            )
        ).all()
    )
    storage = create_recording_storage(settings)
    try:
        for key in keys:
            await storage.delete(key)
    except PrivateObjectStorageError as exc:
        raise RuntimeError("Recording object deletion did not complete; database deletion was stopped.") from exc


async def purge_expired_recording_audio(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    organisation_id: UUID,
    *,
    dry_run: bool,
    batch_size: int,
) -> RawRecordingRetentionResult:
    """Remove verified raw audio only after a final transcript has survived its safety window."""
    bounded_batch_size = min(max(batch_size, 1), 1_000)
    cutoff = datetime.now(UTC) - timedelta(days=settings.private_beta_raw_recording_retention_days)
    storage = create_recording_storage(settings)
    async with session_factory() as session, session.begin():
        await set_tenant_database_context(session, organisation_id)
        recordings = list(
            (
                await session.scalars(
                    select(RecordingSession)
                    .where(
                        RecordingSession.organisation_id == organisation_id,
                        RecordingSession.lifecycle_status == "completed",
                        RecordingSession.transcription_completed_at.is_not(None),
                        RecordingSession.transcription_completed_at < cutoff,
                        RecordingSession.deleted_at.is_(None),
                        RecordingSession.id.in_(
                            select(RecordingChunk.recording_session_id).where(
                                RecordingChunk.organisation_id == organisation_id,
                                RecordingChunk.upload_state.in_(("uploaded", "verified", "delete_failed")),
                            )
                        ),
                    )
                    .order_by(RecordingSession.transcription_completed_at, RecordingSession.id)
                    .limit(bounded_batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        recording_ids = [item.id for item in recordings]
        chunks = (
            list(
                (
                    await session.scalars(
                        select(RecordingChunk)
                        .where(
                            RecordingChunk.organisation_id == organisation_id,
                            RecordingChunk.recording_session_id.in_(recording_ids),
                            RecordingChunk.upload_state != "deleted",
                        )
                        .order_by(RecordingChunk.recording_session_id, RecordingChunk.sequence_number)
                        .with_for_update(skip_locked=True)
                    )
                ).all()
            )
            if recording_ids
            else []
        )
        if dry_run:
            return RawRecordingRetentionResult(
                organisation_id,
                True,
                len(recordings),
                len(chunks),
                0,
                0,
            )
        chunks_by_recording: dict[UUID, list[RecordingChunk]] = {}
        for chunk in chunks:
            chunks_by_recording.setdefault(chunk.recording_session_id, []).append(chunk)
        removed_objects = 0
        retry_required = 0
        now = datetime.now(UTC)
        for recording in recordings:
            failed = False
            for chunk in chunks_by_recording.get(recording.id, []):
                chunk.upload_state = "deletion_pending"
                try:
                    await storage.delete(chunk.storage_key)
                except PrivateObjectStorageError:
                    chunk.upload_state = "delete_failed"
                    failed = True
                else:
                    chunk.upload_state = "deleted"
                    removed_objects += 1
            if failed:
                recording.failure_code = "recording_storage_delete_failed"
                retry_required += 1
                continue
            recording.failure_code = None
            source = await session.scalar(
                select(Evidence).where(
                    Evidence.organisation_id == organisation_id,
                    Evidence.id == recording.source_evidence_id,
                )
            )
            if source is not None:
                source.lifecycle_status = "deleted"
                source.deleted_at = now
            session.add(
                BetaSystemEvent(
                    organisation_id=organisation_id,
                    actor_user_id=None,
                    event_type="recording_raw_audio_purged",
                    metadata_json={
                        "recording_id": str(recording.id),
                        "object_count": len(chunks_by_recording.get(recording.id, [])),
                    },
                )
            )
        return RawRecordingRetentionResult(
            organisation_id,
            False,
            len(recordings),
            len(chunks),
            removed_objects,
            retry_required,
        )


async def reconcile_recording_storage(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    organisation_id: UUID,
    *,
    repair: bool,
) -> RecordingReconciliationResult:
    """Reconcile manifests, private objects, abandoned sessions and deletion retries."""
    storage = create_recording_storage(settings)
    prefix = f"recordings/{organisation_id}/"
    now = datetime.now(UTC)
    async with session_factory() as session, session.begin():
        await set_tenant_database_context(session, organisation_id)
        chunks = list(
            (
                await session.scalars(
                    select(RecordingChunk).where(
                        RecordingChunk.organisation_id == organisation_id,
                        RecordingChunk.upload_state != "deleted",
                    )
                )
            ).all()
        )
        database_keys = {chunk.storage_key for chunk in chunks}
        storage_keys = set(await storage.list_keys(prefix))
        missing = tuple(sorted(database_keys - storage_keys))
        orphaned = tuple(sorted(storage_keys - database_keys))
        abandoned = list(
            (
                await session.scalars(
                    select(RecordingSession).where(
                        RecordingSession.organisation_id == organisation_id,
                        RecordingSession.lifecycle_status.in_(
                            ("created", "recording", "uploading", "failed", "cancelled")
                        ),
                        RecordingSession.session_expires_at <= now,
                        RecordingSession.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        deletion_retries = list(
            (
                await session.scalars(
                    select(RecordingSession).where(
                        RecordingSession.organisation_id == organisation_id,
                        RecordingSession.lifecycle_status == "deleting",
                        RecordingSession.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        repaired_missing = 0
        removed_orphans = 0
        cleaned_abandoned = 0
        completed_retries = 0
        if repair:
            chunk_by_key = {chunk.storage_key: chunk for chunk in chunks}
            for key in missing:
                chunk = chunk_by_key[key]
                chunk.upload_state = "delete_failed"
                recording = await session.scalar(
                    select(RecordingSession).where(
                        RecordingSession.organisation_id == organisation_id,
                        RecordingSession.id == chunk.recording_session_id,
                    )
                )
                if recording is not None:
                    recording.failure_code = "recording_object_missing"
                repaired_missing += 1
            for key in orphaned:
                await storage.delete(key)
                removed_orphans += 1
            for recording in abandoned:
                if await _delete_session_objects(session, storage, organisation_id, recording.id):
                    await _mark_abandoned_deleted(session, organisation_id, recording, now)
                    cleaned_abandoned += 1
                else:
                    recording.lifecycle_status = "deleting"
                    recording.failure_code = "recording_storage_delete_failed"
            for recording in deletion_retries:
                if await _delete_session_objects(session, storage, organisation_id, recording.id):
                    await _complete_soft_deletion(session, organisation_id, recording, now)
                    completed_retries += 1
            session.add(
                BetaSystemEvent(
                    organisation_id=organisation_id,
                    actor_user_id=None,
                    event_type="recording_storage_reconciled",
                    metadata_json={
                        "missing_objects": len(missing),
                        "orphaned_objects": len(orphaned),
                        "abandoned_sessions": len(abandoned),
                        "deletion_retries": len(deletion_retries),
                        "storage_backend": storage.backend_name,
                    },
                )
            )
        return RecordingReconciliationResult(
            organisation_id=organisation_id,
            repaired=repair,
            database_objects=len(database_keys),
            storage_objects=len(storage_keys),
            missing_objects=missing,
            orphaned_objects=orphaned,
            abandoned_sessions=len(abandoned),
            deletion_retries=len(deletion_retries),
            repaired_missing_objects=repaired_missing,
            removed_orphaned_objects=removed_orphans,
            cleaned_abandoned_sessions=cleaned_abandoned,
            completed_deletion_retries=completed_retries,
        )


async def _delete_session_objects(
    session: AsyncSession,
    storage: PrivateObjectStorage,
    organisation_id: UUID,
    recording_id: UUID,
) -> bool:
    chunks = list(
        (
            await session.scalars(
                select(RecordingChunk).where(
                    RecordingChunk.organisation_id == organisation_id,
                    RecordingChunk.recording_session_id == recording_id,
                    RecordingChunk.upload_state != "deleted",
                )
            )
        ).all()
    )
    succeeded = True
    for chunk in chunks:
        chunk.upload_state = "deletion_pending"
        try:
            await storage.delete(chunk.storage_key)
        except PrivateObjectStorageError:
            chunk.upload_state = "delete_failed"
            succeeded = False
        else:
            chunk.upload_state = "deleted"
    return succeeded


async def _mark_abandoned_deleted(
    session: AsyncSession,
    organisation_id: UUID,
    recording: RecordingSession,
    now: datetime,
) -> None:
    if recording.lifecycle_status in {"created", "recording", "uploading"}:
        recording.lifecycle_status = transition_recording(recording.lifecycle_status, "cancelled")
    recording.lifecycle_status = transition_recording(recording.lifecycle_status, "deleting")
    await _complete_soft_deletion(session, organisation_id, recording, now)
    capture = await session.scalar(
        select(CaptureSession).where(
            CaptureSession.organisation_id == organisation_id,
            CaptureSession.id == recording.capture_session_id,
        )
    )
    if capture is not None:
        capture.status = "abandoned"
        capture.completed_at = now
    session.add(
        BetaSystemEvent(
            organisation_id=organisation_id,
            actor_user_id=None,
            event_type="abandoned_recording_cleaned",
            metadata_json={"recording_id": str(recording.id)},
        )
    )


async def _complete_soft_deletion(
    session: AsyncSession,
    organisation_id: UUID,
    recording: RecordingSession,
    now: datetime,
) -> None:
    version = await session.scalar(
        select(TranscriptVersion).where(
            TranscriptVersion.organisation_id == organisation_id,
            TranscriptVersion.recording_session_id == recording.id,
        )
    )
    if version is not None and version.deleted_at is None:
        version.status = "deleted"
        version.deleted_at = now
        segments = list(
            (
                await session.scalars(
                    select(TranscriptSegment).where(
                        TranscriptSegment.organisation_id == organisation_id,
                        TranscriptSegment.transcript_version_id == version.id,
                        TranscriptSegment.deleted_at.is_(None),
                    )
                )
            ).all()
        )
        for segment in segments:
            segment.deleted_at = now
        if version.transcript_id is not None:
            transcript = await session.scalar(
                select(Transcript).where(
                    Transcript.organisation_id == organisation_id,
                    Transcript.id == version.transcript_id,
                )
            )
            if transcript is not None and transcript.version == version.version:
                transcript.deleted_at = now
    evidence_ids = [recording.source_evidence_id]
    if recording.transcript_evidence_id is not None:
        evidence_ids.append(recording.transcript_evidence_id)
    evidence = list(
        (
            await session.scalars(
                select(Evidence).where(
                    Evidence.organisation_id == organisation_id,
                    Evidence.id.in_(evidence_ids),
                )
            )
        ).all()
    )
    for item in evidence:
        item.lifecycle_status = "deleted"
        item.deleted_at = now
    recording.lifecycle_status = transition_recording(recording.lifecycle_status, "deleted")
    recording.deleted_at = now
    recording.failure_code = None
