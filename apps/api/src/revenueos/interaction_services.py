from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.business_repositories import PageResult
from revenueos.domain import (
    CallDirection,
    InteractionAuditAction,
    InteractionLifecycleStatus,
    InteractionType,
    OnlineMeetingPlatform,
)
from revenueos.errors import PublicAPIError
from revenueos.interaction_compatibility import (
    interaction_transition_is_allowed,
    meeting_type_for_interaction,
    project_interaction_to_meeting,
)
from revenueos.interaction_contracts import InteractionComplete, InteractionCreate, InteractionStart, InteractionUpdate
from revenueos.interaction_repositories import InteractionRecord, InteractionRepository
from revenueos.models import (
    Contact,
    Interaction,
    InteractionAuditEvent,
    LiveInteractionSession,
    Meeting,
    MeetingAuditEvent,
    OnlineMeetingMetadata,
    Opportunity,
)
from revenueos.online_meeting_provider import UnsafeMeetingReference, normalize_meeting_reference
from revenueos.tenant import TenantContext

logger = logging.getLogger("revenueos.interactions")


class InteractionService:
    def __init__(self, session: AsyncSession, tenant: TenantContext) -> None:
        self.session = session
        self.repository = InteractionRepository(session)
        self.tenant = tenant

    async def list_interactions(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        company_id: UUID | None,
        opportunity_id: UUID | None,
        interaction_type: str | None,
        lifecycle_status: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        sort_by: str,
        sort_order: str,
    ) -> PageResult[InteractionRecord]:
        if date_from and date_to and date_from > date_to:
            raise PublicAPIError("invalid_date_range", "dateFrom must be before or equal to dateTo.", 422)
        if company_id is not None:
            await self._require_company(company_id)
        if opportunity_id is not None:
            await self._require_opportunity(opportunity_id)
        return await self.repository.list_interactions(
            self.tenant.organisation_id,
            page=page,
            page_size=page_size,
            search=search,
            company_id=company_id,
            opportunity_id=opportunity_id,
            interaction_type=interaction_type,
            lifecycle_status=lifecycle_status,
            date_from=date_from,
            date_to=date_to,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    async def get_interaction(self, interaction_id: UUID) -> InteractionRecord:
        record = await self.repository.get_interaction(self.tenant.organisation_id, interaction_id)
        if record is None:
            raise self._not_found()
        return record

    async def create_interaction(self, request: InteractionCreate) -> InteractionRecord:
        self._validate_phone_metadata(
            request.interaction_type.value,
            request.contact_id,
            request.call_direction.value if request.call_direction is not None else None,
            request.call_outcome.value if request.call_outcome is not None else None,
        )
        await self._validate_relationships(request.company_id, request.opportunity_id, request.contact_id)
        self._validate_lifecycle_times(request.lifecycle_status.value, request.actual_end_at)
        interaction = Interaction(
            id=uuid4(),
            organisation_id=self.tenant.organisation_id,
            company_id=request.company_id,
            opportunity_id=request.opportunity_id,
            contact_id=request.contact_id,
            interaction_type=request.interaction_type.value,
            lifecycle_status=request.lifecycle_status.value,
            title=request.title,
            scheduled_start_at=request.scheduled_start_at,
            scheduled_end_at=request.scheduled_end_at,
            actual_start_at=request.actual_start_at,
            actual_end_at=request.actual_end_at,
            timezone=request.timezone,
            creation_origin="manual",
            call_direction=(
                (request.call_direction or CallDirection.UNKNOWN).value
                if request.interaction_type == InteractionType.PHONE_CALL
                else None
            ),
            call_outcome=request.call_outcome.value if request.call_outcome is not None else None,
            created_by_user_id=self.tenant.user_id,
        )
        self.session.add(interaction)
        if request.interaction_type == InteractionType.ONLINE_MEETING:
            platform = request.meeting_platform or OnlineMeetingPlatform.OTHER
            safe_url, meeting_host = self._safe_meeting_reference(platform, request.meeting_url)
            self.session.add_all(
                (
                    OnlineMeetingMetadata(
                        id=uuid4(),
                        organisation_id=self.tenant.organisation_id,
                        interaction_id=interaction.id,
                        meeting_platform=platform.value,
                        safe_meeting_url=safe_url,
                        meeting_host=meeting_host,
                        external_meeting_id=request.external_meeting_id,
                        ingestion_state="not_started",
                    ),
                    Meeting(
                        id=uuid4(),
                        organisation_id=self.tenant.organisation_id,
                        interaction_id=interaction.id,
                        title=interaction.title,
                        description=None,
                        meeting_date=(
                            interaction.scheduled_start_at or interaction.actual_start_at or datetime.now(UTC)
                        ),
                        meeting_type="remote",
                        status=(
                            "completed"
                            if interaction.lifecycle_status == InteractionLifecycleStatus.COMPLETED.value
                            else (
                                "cancelled"
                                if interaction.lifecycle_status == InteractionLifecycleStatus.CANCELLED.value
                                else "scheduled"
                            )
                        ),
                        company_id=interaction.company_id,
                        opportunity_id=interaction.opportunity_id,
                        owner_user_id=self.tenant.user_id,
                        created_by=self.tenant.user_id,
                        updated_by=self.tenant.user_id,
                    ),
                )
            )
        await self._flush()
        self.session.add(self._audit(interaction.id, InteractionAuditAction.CREATED, self._create_fields()))
        if request.interaction_type == InteractionType.ONLINE_MEETING:
            self.session.add(
                self._audit(
                    interaction.id,
                    InteractionAuditAction.MEETING_LINKED,
                    ["meeting_id"],
                )
            )
            linked = await self.repository.get_interaction(self.tenant.organisation_id, interaction.id)
            if linked is not None and linked.meeting_id is not None:
                self.session.add(
                    MeetingAuditEvent(
                        id=uuid4(),
                        organisation_id=self.tenant.organisation_id,
                        meeting_id=linked.meeting_id,
                        actor_user_id=self.tenant.user_id,
                        action="created",
                        entity_type="meeting",
                        entity_id=linked.meeting_id,
                        changed_fields=[
                            "company_id",
                            "meeting_date",
                            "meeting_type",
                            "opportunity_id",
                            "owner_user_id",
                            "status",
                            "title",
                        ],
                    )
                )
        await self._commit(interaction)
        logger.info(
            "phone_call_created" if interaction.interaction_type == "phone_call" else "interaction_created",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "interaction_id": str(interaction.id),
                "interaction_type": interaction.interaction_type,
                "lifecycle_status": interaction.lifecycle_status,
                "call_direction": interaction.call_direction,
                "call_outcome": interaction.call_outcome,
            },
        )
        return await self.get_interaction(interaction.id)

    async def update_interaction(self, interaction_id: UUID, request: InteractionUpdate) -> InteractionRecord:
        record = await self._get_for_update(interaction_id)
        interaction = record.interaction
        values = request.model_dump(exclude_unset=True)
        online_values = {
            field_name: values.pop(field_name)
            for field_name in ("meeting_platform", "meeting_url", "external_meeting_id")
            if field_name in values
        }
        for enum_field in ("interaction_type", "lifecycle_status", "call_direction", "call_outcome"):
            if enum_field in values and values[enum_field] is not None:
                values[enum_field] = values[enum_field].value
        if "lifecycle_status" in values:
            self._require_transition(interaction.lifecycle_status, values["lifecycle_status"])
        company_id = values.get("company_id", interaction.company_id)
        opportunity_id = values.get("opportunity_id", interaction.opportunity_id)
        contact_id = values.get("contact_id", interaction.contact_id)
        target_type = values.get("interaction_type", interaction.interaction_type)
        await self._apply_online_meeting_update(record, target_type, online_values)
        if target_type == InteractionType.PHONE_CALL.value:
            if values.get("call_direction", interaction.call_direction) is None:
                values["call_direction"] = CallDirection.UNKNOWN.value
        else:
            values.update({"contact_id": None, "call_direction": None, "call_outcome": None})
            contact_id = None
        self._validate_phone_metadata(
            target_type,
            contact_id,
            values.get("call_direction", interaction.call_direction),
            values.get("call_outcome", interaction.call_outcome),
        )
        if any(field in values for field in ("company_id", "opportunity_id", "contact_id")):
            changed = (
                company_id != interaction.company_id
                or opportunity_id != interaction.opportunity_id
                or contact_id != interaction.contact_id
            )
            if changed and await self.repository.intelligence_exists(self.tenant.organisation_id, interaction_id):
                raise PublicAPIError(
                    "interaction_intelligence_locked",
                    "Associations cannot change after final interaction intelligence has been created.",
                    409,
                )
        await self._validate_relationships(company_id, opportunity_id, contact_id)
        merged = {
            "scheduled_start_at": interaction.scheduled_start_at,
            "scheduled_end_at": interaction.scheduled_end_at,
            "actual_start_at": interaction.actual_start_at,
            "actual_end_at": interaction.actual_end_at,
            **values,
        }
        self._validate_ranges(merged)
        self._validate_lifecycle_times(
            values.get("lifecycle_status", interaction.lifecycle_status),
            merged["actual_end_at"],
        )
        if record.meeting_id is not None:
            candidate_type = values.get("interaction_type", interaction.interaction_type)
            if meeting_type_for_interaction(candidate_type) is None:
                raise PublicAPIError(
                    "incompatible_interaction_type",
                    "A Meeting-linked interaction must retain a Meeting-compatible type.",
                    422,
                )
        for field_name, value in values.items():
            setattr(interaction, field_name, value)
        now = datetime.now(UTC)
        interaction.updated_at = now
        meeting: Meeting | None = None
        if target_type == InteractionType.ONLINE_MEETING.value and record.meeting_id is None:
            meeting = Meeting(
                id=uuid4(),
                organisation_id=self.tenant.organisation_id,
                interaction_id=interaction.id,
                title=interaction.title,
                description=None,
                meeting_date=interaction.scheduled_start_at or interaction.actual_start_at or now,
                meeting_type="remote",
                status=(
                    "completed"
                    if interaction.lifecycle_status == InteractionLifecycleStatus.COMPLETED.value
                    else (
                        "cancelled"
                        if interaction.lifecycle_status == InteractionLifecycleStatus.CANCELLED.value
                        else "scheduled"
                    )
                ),
                company_id=interaction.company_id,
                opportunity_id=interaction.opportunity_id,
                owner_user_id=self.tenant.user_id,
                created_by=self.tenant.user_id,
                updated_by=self.tenant.user_id,
            )
            self.session.add(meeting)
            self.session.add(
                self._audit(
                    interaction.id,
                    InteractionAuditAction.MEETING_LINKED,
                    ["meeting_id"],
                )
            )
        elif record.meeting_id is not None:
            meeting = await self.repository.get_meeting_for_update(self.tenant.organisation_id, record.meeting_id)
            if meeting is None:
                raise PublicAPIError("compatibility_conflict", "The linked Meeting is unavailable.", 409)
        if meeting is not None:
            project_interaction_to_meeting(
                interaction,
                meeting,
                updated_by=self.tenant.user_id,
                updated_at=now,
            )
        action = (
            InteractionAuditAction.CANCELLED
            if values.get("lifecycle_status") == InteractionLifecycleStatus.CANCELLED.value
            else InteractionAuditAction.UPDATED
        )
        self.session.add(self._audit(interaction.id, action, [*values, *online_values]))
        await self._commit(interaction)
        return await self.get_interaction(interaction.id)

    async def complete_interaction(
        self,
        interaction_id: UUID,
        request: InteractionComplete,
    ) -> InteractionRecord:
        record = await self._get_for_update(interaction_id)
        interaction = record.interaction
        if interaction.lifecycle_status == InteractionLifecycleStatus.COMPLETED.value:
            return record
        self._require_transition(interaction.lifecycle_status, InteractionLifecycleStatus.COMPLETED.value)
        actual_end_at = request.actual_end_at or datetime.now(UTC)
        if interaction.actual_start_at is not None and actual_end_at < self._aware(interaction.actual_start_at):
            raise PublicAPIError("invalid_time_range", "actualEndAt cannot be before actualStartAt.", 422)
        interaction.lifecycle_status = InteractionLifecycleStatus.COMPLETED.value
        interaction.actual_end_at = actual_end_at
        if request.call_outcome is not None:
            if interaction.interaction_type != InteractionType.PHONE_CALL.value:
                raise PublicAPIError(
                    "invalid_phone_metadata",
                    "callOutcome is available only for phone-call interactions.",
                    422,
                )
            interaction.call_outcome = request.call_outcome.value
        interaction.updated_at = datetime.now(UTC)
        live_session = await self.session.scalar(
            select(LiveInteractionSession)
            .where(
                LiveInteractionSession.organisation_id == self.tenant.organisation_id,
                LiveInteractionSession.interaction_id == interaction.id,
                LiveInteractionSession.status.in_(("active", "processing")),
            )
            .with_for_update()
        )
        if live_session is not None:
            live_session.status = "stopped"
            live_session.stopped_at = interaction.updated_at
            live_session.failure_code = None
        if record.meeting_id is not None:
            meeting = await self.repository.get_meeting_for_update(self.tenant.organisation_id, record.meeting_id)
            if meeting is None:
                raise PublicAPIError("compatibility_conflict", "The linked Meeting is unavailable.", 409)
            project_interaction_to_meeting(
                interaction,
                meeting,
                updated_by=self.tenant.user_id,
                updated_at=interaction.updated_at,
            )
        self.session.add(
            self._audit(
                interaction.id,
                InteractionAuditAction.COMPLETED,
                [
                    "actual_end_at",
                    "lifecycle_status",
                    *(["call_outcome"] if request.call_outcome is not None else []),
                ],
            )
        )
        await self._commit(interaction)
        logger.info(
            "call_completed" if interaction.interaction_type == "phone_call" else "interaction_completed",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "interaction_id": str(interaction.id),
                "lifecycle_status": interaction.lifecycle_status,
                "call_outcome": interaction.call_outcome,
            },
        )
        return await self.get_interaction(interaction.id)

    async def start_interaction(
        self,
        interaction_id: UUID,
        request: InteractionStart,
    ) -> InteractionRecord:
        record = await self._get_for_update(interaction_id)
        interaction = record.interaction
        if interaction.lifecycle_status == InteractionLifecycleStatus.IN_PROGRESS.value:
            return record
        self._require_transition(interaction.lifecycle_status, InteractionLifecycleStatus.IN_PROGRESS.value)
        actual_start_at = request.actual_start_at or datetime.now(UTC)
        interaction.lifecycle_status = InteractionLifecycleStatus.IN_PROGRESS.value
        interaction.actual_start_at = interaction.actual_start_at or actual_start_at
        interaction.actual_end_at = None
        interaction.updated_at = datetime.now(UTC)
        if record.meeting_id is not None:
            meeting = await self.repository.get_meeting_for_update(self.tenant.organisation_id, record.meeting_id)
            if meeting is None:
                raise PublicAPIError("compatibility_conflict", "The linked Meeting is unavailable.", 409)
            project_interaction_to_meeting(
                interaction,
                meeting,
                updated_by=self.tenant.user_id,
                updated_at=interaction.updated_at,
            )
        self.session.add(
            self._audit(
                interaction.id,
                InteractionAuditAction.UPDATED,
                ["actual_start_at", "lifecycle_status"],
            )
        )
        await self._commit(interaction)
        logger.info(
            "call_started" if interaction.interaction_type == "phone_call" else "interaction_started",
            extra={
                "organisation_id": str(self.tenant.organisation_id),
                "interaction_id": str(interaction.id),
                "interaction_type": interaction.interaction_type,
            },
        )
        return await self.get_interaction(interaction.id)

    async def _get_for_update(self, interaction_id: UUID) -> InteractionRecord:
        record = await self.repository.get_interaction(
            self.tenant.organisation_id,
            interaction_id,
        )
        if record is None:
            raise self._not_found()
        if record.meeting_id is not None:
            meeting = await self.repository.get_meeting_for_update(
                self.tenant.organisation_id,
                record.meeting_id,
            )
            if meeting is None:
                raise PublicAPIError(
                    "compatibility_conflict",
                    "The linked Meeting is unavailable.",
                    409,
                )
        locked = await self.repository.get_interaction(
            self.tenant.organisation_id,
            interaction_id,
            for_update=True,
        )
        if locked is None:
            raise self._not_found()
        return locked

    async def _validate_relationships(
        self,
        company_id: UUID | None,
        opportunity_id: UUID | None,
        contact_id: UUID | None,
    ) -> None:
        if company_id is not None:
            await self._require_company(company_id)
        opportunity = await self._require_opportunity(opportunity_id) if opportunity_id is not None else None
        if (
            opportunity is not None
            and company_id is not None
            and opportunity.company_id is not None
            and company_id != opportunity.company_id
        ):
            raise PublicAPIError(
                "inconsistent_relationship",
                "The interaction and opportunity must refer to the same company.",
                422,
            )
        if contact_id is None:
            return
        contact = await self._require_contact(contact_id)
        relationship_company_id = company_id or (opportunity.company_id if opportunity is not None else None)
        if relationship_company_id is not None and contact.company_id != relationship_company_id:
            raise PublicAPIError(
                "inconsistent_relationship",
                "The phone-call contact, company and opportunity must refer to the same company.",
                422,
            )

    async def _require_company(self, company_id: UUID) -> None:
        if await self.repository.get_company(self.tenant.organisation_id, company_id) is None:
            raise PublicAPIError("company_not_found", "The requested company was not found.", 404)

    async def _require_opportunity(self, opportunity_id: UUID) -> Opportunity:
        opportunity = await self.repository.get_opportunity(self.tenant.organisation_id, opportunity_id)
        if opportunity is None:
            raise PublicAPIError("opportunity_not_found", "The requested opportunity was not found.", 404)
        return opportunity

    async def _require_contact(self, contact_id: UUID) -> Contact:
        contact = await self.repository.get_contact(self.tenant.organisation_id, contact_id)
        if contact is None:
            raise PublicAPIError("contact_not_found", "The requested contact was not found.", 404)
        return contact

    @staticmethod
    def _validate_phone_metadata(
        interaction_type: str,
        contact_id: UUID | None,
        call_direction: str | None,
        call_outcome: str | None,
    ) -> None:
        if interaction_type != InteractionType.PHONE_CALL.value and any(
            value is not None for value in (contact_id, call_direction, call_outcome)
        ):
            raise PublicAPIError(
                "invalid_phone_metadata",
                "Contact, call direction and call outcome are available only for phone calls.",
                422,
            )

    async def _apply_online_meeting_update(
        self,
        record: InteractionRecord,
        target_type: str,
        values: dict[str, Any],
    ) -> None:
        metadata = record.online_meeting_metadata
        if target_type != InteractionType.ONLINE_MEETING.value:
            if any(value is not None for value in values.values()):
                raise PublicAPIError(
                    "invalid_online_meeting_metadata",
                    "Online-meeting metadata is available only for online meetings.",
                    422,
                )
            if metadata is not None:
                await self.session.delete(metadata)
            return
        platform_value = values.get(
            "meeting_platform",
            metadata.meeting_platform if metadata is not None else OnlineMeetingPlatform.OTHER.value,
        )
        if hasattr(platform_value, "value"):
            platform_value = platform_value.value
        platform = OnlineMeetingPlatform(platform_value)
        meeting_url = values.get(
            "meeting_url",
            metadata.safe_meeting_url if metadata is not None else None,
        )
        safe_url, meeting_host = self._safe_meeting_reference(platform, meeting_url)
        if metadata is None:
            metadata = OnlineMeetingMetadata(
                id=uuid4(),
                organisation_id=self.tenant.organisation_id,
                interaction_id=record.interaction.id,
                meeting_platform=platform.value,
                ingestion_state="not_started",
            )
            self.session.add(metadata)
        metadata.meeting_platform = platform.value
        metadata.safe_meeting_url = safe_url
        metadata.meeting_host = meeting_host
        if "external_meeting_id" in values:
            metadata.external_meeting_id = values["external_meeting_id"]
        metadata.updated_at = datetime.now(UTC)

    @staticmethod
    def _safe_meeting_reference(
        platform: OnlineMeetingPlatform,
        meeting_url: str | None,
    ) -> tuple[str | None, str | None]:
        if meeting_url is None:
            return None, None
        try:
            normalised = normalize_meeting_reference(platform, meeting_url)
        except UnsafeMeetingReference as exc:
            raise PublicAPIError("unsafe_meeting_url", str(exc), 422) from exc
        return normalised.safe_url, normalised.host

    @staticmethod
    def _require_transition(current: str, target: str) -> None:
        if not interaction_transition_is_allowed(current, target):
            raise PublicAPIError(
                "invalid_lifecycle_transition",
                f"An interaction cannot move from {current} to {target}.",
                409,
            )

    @staticmethod
    def _validate_ranges(values: dict[str, Any]) -> None:
        scheduled_start = values["scheduled_start_at"]
        scheduled_end = values["scheduled_end_at"]
        actual_start = values["actual_start_at"]
        actual_end = values["actual_end_at"]
        if scheduled_start is not None and scheduled_end is not None:
            if InteractionService._aware(scheduled_end) < InteractionService._aware(scheduled_start):
                raise PublicAPIError("invalid_time_range", "scheduledEndAt cannot be before scheduledStartAt.", 422)
        if actual_start is not None and actual_end is not None:
            if InteractionService._aware(actual_end) < InteractionService._aware(actual_start):
                raise PublicAPIError("invalid_time_range", "actualEndAt cannot be before actualStartAt.", 422)

    @staticmethod
    def _validate_lifecycle_times(lifecycle_status: str, actual_end_at: datetime | None) -> None:
        if lifecycle_status == InteractionLifecycleStatus.IN_PROGRESS.value and actual_end_at is not None:
            raise PublicAPIError(
                "invalid_lifecycle_time",
                "An in-progress interaction cannot have an actual end time.",
                422,
            )

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    def _audit(
        self,
        interaction_id: UUID,
        action: InteractionAuditAction,
        changed_fields: list[str],
    ) -> InteractionAuditEvent:
        return InteractionAuditEvent(
            organisation_id=self.tenant.organisation_id,
            interaction_id=interaction_id,
            actor_user_id=self.tenant.user_id,
            action=action.value,
            changed_fields=sorted(changed_fields),
        )

    async def _flush(self) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PublicAPIError("conflict", "The interaction conflicts with related data.", 409) from exc

    async def _commit(self, interaction: Interaction) -> None:
        try:
            await self.session.flush()
            await self.session.refresh(interaction)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise PublicAPIError("conflict", "The interaction conflicts with related data.", 409) from exc

    @staticmethod
    def _create_fields() -> list[str]:
        return [
            "actual_end_at",
            "actual_start_at",
            "company_id",
            "contact_id",
            "call_direction",
            "call_outcome",
            "interaction_type",
            "lifecycle_status",
            "opportunity_id",
            "scheduled_end_at",
            "scheduled_start_at",
            "timezone",
            "title",
        ]

    @staticmethod
    def _not_found() -> PublicAPIError:
        return PublicAPIError("interaction_not_found", "The requested interaction was not found.", 404)
