from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.business_repositories import PageResult
from revenueos.domain import MeetingAuditAction, MeetingAuditEntityType
from revenueos.errors import PublicAPIError
from revenueos.meeting_contracts import (
    MeetingCreate,
    MeetingParticipantCreate,
    MeetingParticipantUpdate,
    MeetingUpdate,
    TranscriptCreate,
    TranscriptUpdate,
)
from revenueos.meeting_repositories import MeetingRepository
from revenueos.models import (
    Base,
    Meeting,
    MeetingAuditEvent,
    MeetingParticipant,
    Transcript,
)
from revenueos.tenant import TenantContext


class _MeetingDomainService:
    def __init__(self, session: AsyncSession, tenant: TenantContext) -> None:
        self.repository = MeetingRepository(session)
        self.tenant = tenant

    async def _get_meeting(self, meeting_id: UUID) -> Meeting:
        meeting = await self.repository.get_meeting(self.tenant.organisation_id, meeting_id)
        if meeting is None:
            raise self._not_found("meeting")
        return meeting

    async def _get_meeting_for_update(self, meeting_id: UUID) -> Meeting:
        meeting = await self.repository.get_meeting(
            self.tenant.organisation_id,
            meeting_id,
            for_update=True,
        )
        if meeting is None:
            raise self._not_found("meeting")
        return meeting

    async def _require_company(self, company_id: UUID) -> None:
        if await self.repository.get_company(self.tenant.organisation_id, company_id) is None:
            raise self._not_found("company")

    async def _require_contact(self, contact_id: UUID) -> None:
        if await self.repository.get_contact(self.tenant.organisation_id, contact_id) is None:
            raise self._not_found("contact")

    async def _require_opportunity(self, opportunity_id: UUID) -> UUID | None:
        opportunity = await self.repository.get_opportunity(
            self.tenant.organisation_id,
            opportunity_id,
        )
        if opportunity is None:
            raise self._not_found("opportunity")
        return opportunity.company_id

    @staticmethod
    def _require_consistent_company(
        meeting_company_id: UUID | None,
        opportunity_company_id: UUID | None,
    ) -> None:
        if (
            meeting_company_id is not None
            and opportunity_company_id is not None
            and meeting_company_id != opportunity_company_id
        ):
            raise PublicAPIError(
                "inconsistent_relationship",
                "The meeting and opportunity must refer to the same company.",
                422,
            )

    async def _require_member(self, user_id: UUID, field_name: str) -> None:
        if not await self.repository.membership_exists(self.tenant.organisation_id, user_id):
            raise PublicAPIError(
                "invalid_relationship",
                f"{field_name} must identify a member of the current organisation.",
                422,
            )

    def _audit(
        self,
        *,
        meeting_id: UUID,
        entity_id: UUID,
        action: MeetingAuditAction,
        entity_type: MeetingAuditEntityType,
        changed_fields: list[str],
        version: int | None = None,
    ) -> MeetingAuditEvent:
        return MeetingAuditEvent(
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            actor_user_id=self.tenant.user_id,
            action=action.value,
            entity_type=entity_type.value,
            entity_id=entity_id,
            changed_fields=sorted(changed_fields),
            version=version,
        )

    async def _commit(self, entity: Base | None = None) -> None:
        try:
            await self.repository.flush()
            if entity is not None:
                await self.repository.refresh(entity)
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "conflict",
                "The record conflicts with existing or related data.",
                409,
            ) from exc

    async def _flush(self) -> None:
        try:
            await self.repository.flush()
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "conflict",
                "The record conflicts with existing or related data.",
                409,
            ) from exc

    @staticmethod
    def _apply_values(entity: Base, values: dict[str, Any]) -> None:
        for field_name, value in values.items():
            if hasattr(value, "value"):
                value = value.value
            elif field_name == "email" and value is not None:
                value = str(value)
            setattr(entity, field_name, value)

    @staticmethod
    def _not_found(entity_name: str) -> PublicAPIError:
        return PublicAPIError(
            f"{entity_name}_not_found",
            f"The requested {entity_name} was not found.",
            404,
        )


class MeetingService(_MeetingDomainService):
    """Tenant-aware Meeting aggregate rules and audit history."""

    async def list_meetings(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        company_id: UUID | None,
        status: str | None,
        meeting_type: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        sort_by: str,
        sort_order: str,
    ) -> PageResult[Meeting]:
        if date_from and date_to and date_from > date_to:
            raise PublicAPIError(
                "invalid_date_range",
                "dateFrom must be before or equal to dateTo.",
                422,
            )
        if company_id is not None:
            await self._require_company(company_id)
        return await self.repository.list_meetings(
            self.tenant.organisation_id,
            page=page,
            page_size=page_size,
            search=search,
            company_id=company_id,
            status=status,
            meeting_type=meeting_type,
            date_from=date_from,
            date_to=date_to,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    async def get_meeting(self, meeting_id: UUID) -> Meeting:
        return await self._get_meeting(meeting_id)

    async def create_meeting(self, request: MeetingCreate) -> Meeting:
        owner_user_id = request.owner_user_id or self.tenant.user_id
        await self._require_member(owner_user_id, "ownerUserId")
        if request.company_id is not None:
            await self._require_company(request.company_id)
        if request.opportunity_id is not None:
            opportunity_company_id = await self._require_opportunity(request.opportunity_id)
            self._require_consistent_company(request.company_id, opportunity_company_id)
        for participant_request in request.participants:
            if participant_request.contact_id is not None:
                await self._require_contact(participant_request.contact_id)

        meeting = Meeting(
            organisation_id=self.tenant.organisation_id,
            title=request.title,
            description=request.description,
            meeting_date=request.meeting_date,
            meeting_type=request.meeting_type.value,
            status=request.status.value,
            company_id=request.company_id,
            opportunity_id=request.opportunity_id,
            owner_user_id=owner_user_id,
            created_by=self.tenant.user_id,
            updated_by=self.tenant.user_id,
        )
        self.repository.add(meeting)
        try:
            await self.repository.flush()
            participants = [
                self._participant_from_create(meeting.id, participant_request)
                for participant_request in request.participants
            ]
            if participants:
                self.repository.add_all(participants)
            transcript = (
                self._transcript_from_create(meeting.id, request.transcript) if request.transcript is not None else None
            )
            if transcript is not None:
                self.repository.add(transcript)
            await self.repository.flush()

            audit_events: list[Base] = [
                self._audit(
                    meeting_id=meeting.id,
                    entity_id=meeting.id,
                    action=MeetingAuditAction.CREATED,
                    entity_type=MeetingAuditEntityType.MEETING,
                    changed_fields=[
                        "title",
                        "description",
                        "meeting_date",
                        "meeting_type",
                        "status",
                        "company_id",
                        "opportunity_id",
                        "owner_user_id",
                    ],
                )
            ]
            audit_events.extend(
                self._audit(
                    meeting_id=meeting.id,
                    entity_id=participant.id,
                    action=MeetingAuditAction.CREATED,
                    entity_type=MeetingAuditEntityType.PARTICIPANT,
                    changed_fields=[
                        "contact_id",
                        "display_name",
                        "email",
                        "attendance_status",
                        "role",
                    ],
                )
                for participant in participants
            )
            if transcript is not None:
                audit_events.append(
                    self._audit(
                        meeting_id=meeting.id,
                        entity_id=transcript.id,
                        action=MeetingAuditAction.CREATED,
                        entity_type=MeetingAuditEntityType.TRANSCRIPT,
                        changed_fields=["raw_text", "language", "source"],
                        version=transcript.version,
                    )
                )
            self.repository.add_all(audit_events)
            await self.repository.flush()
            await self.repository.refresh(meeting)
            await self.repository.commit()
        except IntegrityError as exc:
            await self.repository.rollback()
            raise PublicAPIError(
                "conflict",
                "The meeting conflicts with existing or related data.",
                409,
            ) from exc
        return meeting

    async def update_meeting(self, meeting_id: UUID, request: MeetingUpdate) -> Meeting:
        meeting = await self._get_meeting_for_update(meeting_id)
        values = request.model_dump(exclude_unset=True)
        if "company_id" in values and values["company_id"] is not None:
            await self._require_company(values["company_id"])
        opportunity_company_id = None
        opportunity_id = values.get("opportunity_id", meeting.opportunity_id)
        if opportunity_id is not None:
            opportunity_company_id = await self._require_opportunity(opportunity_id)
        self._require_consistent_company(
            values.get("company_id", meeting.company_id),
            opportunity_company_id,
        )
        if "owner_user_id" in values:
            await self._require_member(values["owner_user_id"], "ownerUserId")
        meeting.updated_by = self.tenant.user_id
        self._apply_values(meeting, values)
        self.repository.add(
            self._audit(
                meeting_id=meeting.id,
                entity_id=meeting.id,
                action=MeetingAuditAction.UPDATED,
                entity_type=MeetingAuditEntityType.MEETING,
                changed_fields=[*values, "updated_by"],
            )
        )
        await self._commit(meeting)
        return meeting

    async def delete_meeting(self, meeting_id: UUID) -> None:
        meeting = await self._get_meeting_for_update(meeting_id)
        deleted_at = datetime.now(UTC)
        meeting.deleted_at = deleted_at
        meeting.updated_by = self.tenant.user_id
        participants = await self.repository.list_participants(
            self.tenant.organisation_id,
            meeting.id,
        )
        transcript = await self.repository.get_transcript(
            self.tenant.organisation_id,
            meeting.id,
        )
        for participant in participants:
            participant.deleted_at = deleted_at
            self.repository.add(
                self._audit(
                    meeting_id=meeting.id,
                    entity_id=participant.id,
                    action=MeetingAuditAction.DELETED,
                    entity_type=MeetingAuditEntityType.PARTICIPANT,
                    changed_fields=["deleted_at"],
                )
            )
        if transcript is not None:
            transcript.deleted_at = deleted_at
            self.repository.add(
                self._audit(
                    meeting_id=meeting.id,
                    entity_id=transcript.id,
                    action=MeetingAuditAction.DELETED,
                    entity_type=MeetingAuditEntityType.TRANSCRIPT,
                    changed_fields=["deleted_at"],
                    version=transcript.version,
                )
            )
        self.repository.add(
            self._audit(
                meeting_id=meeting.id,
                entity_id=meeting.id,
                action=MeetingAuditAction.DELETED,
                entity_type=MeetingAuditEntityType.MEETING,
                changed_fields=["deleted_at", "updated_by"],
            )
        )
        await self._commit()

    async def list_history(self, meeting_id: UUID) -> list[MeetingAuditEvent]:
        await self._get_meeting(meeting_id)
        return await self.repository.list_history(self.tenant.organisation_id, meeting_id)

    def _participant_from_create(
        self,
        meeting_id: UUID,
        request: MeetingParticipantCreate,
    ) -> MeetingParticipant:
        return MeetingParticipant(
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            contact_id=request.contact_id,
            display_name=request.display_name,
            email=str(request.email) if request.email else None,
            attendance_status=request.attendance_status.value,
            role=request.role.value,
        )

    def _transcript_from_create(
        self,
        meeting_id: UUID,
        request: TranscriptCreate,
    ) -> Transcript:
        return Transcript(
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting_id,
            raw_text=request.raw_text,
            language=request.language,
            version=1,
            source=request.source.value,
        )


class ParticipantService(_MeetingDomainService):
    """Tenant-aware participant rules nested under an active meeting."""

    async def list_participants(self, meeting_id: UUID) -> list[MeetingParticipant]:
        await self._get_meeting(meeting_id)
        return await self.repository.list_participants(self.tenant.organisation_id, meeting_id)

    async def get_participant(
        self,
        meeting_id: UUID,
        participant_id: UUID,
    ) -> MeetingParticipant:
        await self._get_meeting(meeting_id)
        participant = await self.repository.get_participant(
            self.tenant.organisation_id,
            meeting_id,
            participant_id,
        )
        if participant is None:
            raise self._not_found("participant")
        return participant

    async def create_participant(
        self,
        meeting_id: UUID,
        request: MeetingParticipantCreate,
    ) -> MeetingParticipant:
        meeting = await self._get_meeting_for_update(meeting_id)
        if request.contact_id is not None:
            await self._require_contact(request.contact_id)
        participant = MeetingParticipant(
            organisation_id=self.tenant.organisation_id,
            meeting_id=meeting.id,
            contact_id=request.contact_id,
            display_name=request.display_name,
            email=str(request.email) if request.email else None,
            attendance_status=request.attendance_status.value,
            role=request.role.value,
        )
        self.repository.add(participant)
        await self._flush()
        self.repository.add(
            self._audit(
                meeting_id=meeting.id,
                entity_id=participant.id,
                action=MeetingAuditAction.CREATED,
                entity_type=MeetingAuditEntityType.PARTICIPANT,
                changed_fields=[
                    "contact_id",
                    "display_name",
                    "email",
                    "attendance_status",
                    "role",
                ],
            )
        )
        await self._commit(participant)
        return participant

    async def update_participant(
        self,
        meeting_id: UUID,
        participant_id: UUID,
        request: MeetingParticipantUpdate,
    ) -> MeetingParticipant:
        await self._get_meeting_for_update(meeting_id)
        participant = await self.repository.get_participant(
            self.tenant.organisation_id,
            meeting_id,
            participant_id,
            for_update=True,
        )
        if participant is None:
            raise self._not_found("participant")
        values = request.model_dump(exclude_unset=True)
        contact_id = values.get("contact_id", participant.contact_id)
        display_name = values.get("display_name", participant.display_name)
        email = values.get("email", participant.email)
        if contact_id is None and display_name is None and email is None:
            raise PublicAPIError(
                "invalid_participant",
                "A participant must have a contact, display name or email.",
                422,
            )
        if contact_id is not None:
            await self._require_contact(contact_id)
        self._apply_values(participant, values)
        self.repository.add(
            self._audit(
                meeting_id=meeting_id,
                entity_id=participant.id,
                action=MeetingAuditAction.UPDATED,
                entity_type=MeetingAuditEntityType.PARTICIPANT,
                changed_fields=list(values),
            )
        )
        await self._commit(participant)
        return participant

    async def delete_participant(self, meeting_id: UUID, participant_id: UUID) -> None:
        await self._get_meeting_for_update(meeting_id)
        participant = await self.repository.get_participant(
            self.tenant.organisation_id,
            meeting_id,
            participant_id,
            for_update=True,
        )
        if participant is None:
            raise self._not_found("participant")
        participant.deleted_at = datetime.now(UTC)
        self.repository.add(
            self._audit(
                meeting_id=meeting_id,
                entity_id=participant.id,
                action=MeetingAuditAction.DELETED,
                entity_type=MeetingAuditEntityType.PARTICIPANT,
                changed_fields=["deleted_at"],
            )
        )
        await self._commit()


class TranscriptService(_MeetingDomainService):
    """Tenant-aware singular transcript rules with optimistic versioning."""

    async def get_transcript(self, meeting_id: UUID) -> Transcript:
        await self._get_meeting(meeting_id)
        transcript = await self.repository.get_transcript(self.tenant.organisation_id, meeting_id)
        if transcript is None:
            raise self._not_found("transcript")
        return transcript

    async def create_transcript(self, meeting_id: UUID, request: TranscriptCreate) -> Transcript:
        meeting = await self._get_meeting_for_update(meeting_id)
        existing = await self.repository.get_transcript(
            self.tenant.organisation_id,
            meeting_id,
            include_deleted=True,
            for_update=True,
        )
        if existing is not None and existing.deleted_at is None:
            raise PublicAPIError(
                "transcript_exists",
                "The meeting already has a transcript.",
                409,
            )
        if existing is None:
            transcript = Transcript(
                organisation_id=self.tenant.organisation_id,
                meeting_id=meeting.id,
                raw_text=request.raw_text,
                language=request.language,
                version=1,
                source=request.source.value,
            )
            action = MeetingAuditAction.CREATED
            self.repository.add(transcript)
            await self._flush()
        else:
            transcript = existing
            transcript.raw_text = request.raw_text
            transcript.language = request.language
            transcript.source = request.source.value
            transcript.version += 1
            transcript.deleted_at = None
            action = MeetingAuditAction.RESTORED
        self.repository.add(
            self._audit(
                meeting_id=meeting.id,
                entity_id=transcript.id,
                action=action,
                entity_type=MeetingAuditEntityType.TRANSCRIPT,
                changed_fields=["raw_text", "language", "source", "deleted_at"],
                version=transcript.version,
            )
        )
        await self._commit(transcript)
        return transcript

    async def update_transcript(
        self,
        meeting_id: UUID,
        request: TranscriptUpdate,
    ) -> Transcript:
        await self._get_meeting_for_update(meeting_id)
        transcript = await self.repository.get_transcript(
            self.tenant.organisation_id,
            meeting_id,
            for_update=True,
        )
        if transcript is None:
            raise self._not_found("transcript")
        if transcript.version != request.version:
            raise PublicAPIError(
                "transcript_version_conflict",
                "The transcript changed since it was loaded. Refresh and try again.",
                409,
            )
        values = request.model_dump(exclude={"version"}, exclude_unset=True)
        self._apply_values(transcript, values)
        transcript.version += 1
        self.repository.add(
            self._audit(
                meeting_id=meeting_id,
                entity_id=transcript.id,
                action=MeetingAuditAction.UPDATED,
                entity_type=MeetingAuditEntityType.TRANSCRIPT,
                changed_fields=[*values, "version"],
                version=transcript.version,
            )
        )
        await self._commit(transcript)
        return transcript

    async def delete_transcript(self, meeting_id: UUID) -> None:
        await self._get_meeting_for_update(meeting_id)
        transcript = await self.repository.get_transcript(
            self.tenant.organisation_id,
            meeting_id,
            for_update=True,
        )
        if transcript is None:
            raise self._not_found("transcript")
        transcript.deleted_at = datetime.now(UTC)
        self.repository.add(
            self._audit(
                meeting_id=meeting_id,
                entity_id=transcript.id,
                action=MeetingAuditAction.DELETED,
                entity_type=MeetingAuditEntityType.TRANSCRIPT,
                changed_fields=["deleted_at"],
                version=transcript.version,
            )
        )
        await self._commit()
