from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.business_repositories import PageResult
from revenueos.domain import CallDirection, InteractionAuditAction, InteractionLifecycleStatus, InteractionType
from revenueos.errors import PublicAPIError
from revenueos.interaction_compatibility import (
    interaction_transition_is_allowed,
    meeting_type_for_interaction,
    project_interaction_to_meeting,
)
from revenueos.interaction_contracts import InteractionComplete, InteractionCreate, InteractionStart, InteractionUpdate
from revenueos.interaction_repositories import InteractionRecord, InteractionRepository
from revenueos.models import Contact, Interaction, InteractionAuditEvent, Opportunity
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
        await self._flush()
        self.session.add(self._audit(interaction.id, InteractionAuditAction.CREATED, self._create_fields()))
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
        for enum_field in ("interaction_type", "lifecycle_status", "call_direction", "call_outcome"):
            if enum_field in values and values[enum_field] is not None:
                values[enum_field] = values[enum_field].value
        if "lifecycle_status" in values:
            self._require_transition(interaction.lifecycle_status, values["lifecycle_status"])
        company_id = values.get("company_id", interaction.company_id)
        opportunity_id = values.get("opportunity_id", interaction.opportunity_id)
        contact_id = values.get("contact_id", interaction.contact_id)
        target_type = values.get("interaction_type", interaction.interaction_type)
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
        if record.meeting_id is not None:
            meeting = await self.repository.get_meeting_for_update(self.tenant.organisation_id, record.meeting_id)
            if meeting is None:
                raise PublicAPIError("compatibility_conflict", "The linked Meeting is unavailable.", 409)
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
        self.session.add(self._audit(interaction.id, action, list(values)))
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
