from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    ActionExecution,
    Base,
    Contact,
    EngageCampaign,
    EngageCampaignAudience,
    EngageCampaignEnrollment,
    EngageCampaignVersion,
    EngageEnrollmentStep,
    EngageSequenceStep,
    EventAttendee,
    EventCampaignLink,
    IntegrationConnection,
    OutreachMessage,
    SalesEvent,
)


@dataclass(frozen=True)
class CampaignRecord:
    campaign: EngageCampaign
    version: EngageCampaignVersion


@dataclass(frozen=True)
class EnrollmentStepRecord:
    enrollment: EngageCampaignEnrollment
    step_instance: EngageEnrollmentStep
    sequence_step: EngageSequenceStep
    execution: ActionExecution | None


class CampaignRepository:
    """Tenant-explicit Campaign persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def campaigns(self, organisation_id: UUID) -> list[CampaignRecord]:
        rows = (
            await self.session.execute(
                select(EngageCampaign, EngageCampaignVersion)
                .join(
                    EngageCampaignVersion,
                    and_(
                        EngageCampaignVersion.organisation_id == EngageCampaign.organisation_id,
                        EngageCampaignVersion.campaign_id == EngageCampaign.id,
                        EngageCampaignVersion.version == EngageCampaign.current_version,
                    ),
                )
                .where(EngageCampaign.organisation_id == organisation_id)
                .order_by(EngageCampaign.updated_at.desc(), EngageCampaign.id)
            )
        ).all()
        return [CampaignRecord(campaign, version) for campaign, version in rows]

    async def campaign(
        self,
        organisation_id: UUID,
        campaign_id: UUID,
        *,
        for_update: bool = False,
    ) -> CampaignRecord | None:
        statement = (
            select(EngageCampaign, EngageCampaignVersion)
            .join(
                EngageCampaignVersion,
                and_(
                    EngageCampaignVersion.organisation_id == EngageCampaign.organisation_id,
                    EngageCampaignVersion.campaign_id == EngageCampaign.id,
                    EngageCampaignVersion.version == EngageCampaign.current_version,
                ),
            )
            .where(EngageCampaign.organisation_id == organisation_id, EngageCampaign.id == campaign_id)
        )
        if for_update:
            statement = statement.with_for_update(of=EngageCampaign)
        row = (await self.session.execute(statement)).one_or_none()
        return CampaignRecord(row[0], row[1]) if row is not None else None

    async def steps(self, organisation_id: UUID, campaign_version_id: UUID) -> list[EngageSequenceStep]:
        values = await self.session.scalars(
            select(EngageSequenceStep)
            .where(
                EngageSequenceStep.organisation_id == organisation_id,
                EngageSequenceStep.campaign_version_id == campaign_version_id,
                EngageSequenceStep.enabled.is_(True),
            )
            .order_by(EngageSequenceStep.step_order, EngageSequenceStep.id)
        )
        return list(values.all())

    async def audience(self, organisation_id: UUID, campaign_version_id: UUID) -> list[EngageCampaignAudience]:
        values = await self.session.scalars(
            select(EngageCampaignAudience)
            .where(
                EngageCampaignAudience.organisation_id == organisation_id,
                EngageCampaignAudience.campaign_version_id == campaign_version_id,
            )
            .order_by(EngageCampaignAudience.recipient_name, EngageCampaignAudience.id)
        )
        return list(values.all())

    async def contacts(self, organisation_id: UUID, contact_ids: list[UUID]) -> list[Contact]:
        values = await self.session.scalars(
            select(Contact)
            .where(Contact.organisation_id == organisation_id, Contact.id.in_(contact_ids))
            .order_by(Contact.first_name, Contact.last_name, Contact.id)
        )
        return list(values.all())

    async def event_accepts_contacts(self, organisation_id: UUID, event_id: UUID, contact_ids: list[UUID]) -> bool:
        event_exists = int(
            await self.session.scalar(
                select(func.count())
                .select_from(SalesEvent)
                .where(SalesEvent.organisation_id == organisation_id, SalesEvent.id == event_id)
            )
            or 0
        )
        if event_exists != 1:
            return False
        linked_count = int(
            await self.session.scalar(
                select(func.count(func.distinct(EventAttendee.contact_id))).where(
                    EventAttendee.organisation_id == organisation_id,
                    EventAttendee.event_id == event_id,
                    EventAttendee.contact_id.in_(contact_ids),
                )
            )
            or 0
        )
        return linked_count == len(contact_ids)

    async def event_campaign_link(self, organisation_id: UUID, campaign_id: UUID) -> EventCampaignLink | None:
        return cast(
            EventCampaignLink | None,
            await self.session.scalar(
                select(EventCampaignLink).where(
                    EventCampaignLink.organisation_id == organisation_id,
                    EventCampaignLink.campaign_id == campaign_id,
                )
            ),
        )

    async def delete_event_campaign_link(self, organisation_id: UUID, campaign_id: UUID) -> None:
        await self.session.execute(
            delete(EventCampaignLink).where(
                EventCampaignLink.organisation_id == organisation_id,
                EventCampaignLink.campaign_id == campaign_id,
            )
        )

    async def enrollments(self, organisation_id: UUID, campaign_id: UUID) -> list[EngageCampaignEnrollment]:
        values = await self.session.scalars(
            select(EngageCampaignEnrollment)
            .where(
                EngageCampaignEnrollment.organisation_id == organisation_id,
                EngageCampaignEnrollment.campaign_id == campaign_id,
            )
            .order_by(EngageCampaignEnrollment.recipient_name, EngageCampaignEnrollment.id)
        )
        return list(values.all())

    async def enrollment(
        self,
        organisation_id: UUID,
        enrollment_id: UUID,
        *,
        for_update: bool = False,
    ) -> EngageCampaignEnrollment | None:
        statement = select(EngageCampaignEnrollment).where(
            EngageCampaignEnrollment.organisation_id == organisation_id,
            EngageCampaignEnrollment.id == enrollment_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return cast(EngageCampaignEnrollment | None, await self.session.scalar(statement))

    async def enrollment_steps(
        self, organisation_id: UUID, enrollment_id: UUID
    ) -> list[tuple[EngageEnrollmentStep, EngageSequenceStep, ActionExecution | None]]:
        rows = (
            await self.session.execute(
                select(EngageEnrollmentStep, EngageSequenceStep, ActionExecution)
                .join(
                    EngageSequenceStep,
                    and_(
                        EngageSequenceStep.organisation_id == EngageEnrollmentStep.organisation_id,
                        EngageSequenceStep.id == EngageEnrollmentStep.sequence_step_id,
                    ),
                )
                .outerjoin(
                    OutreachMessage,
                    and_(
                        OutreachMessage.organisation_id == EngageEnrollmentStep.organisation_id,
                        OutreachMessage.id == EngageEnrollmentStep.outreach_message_id,
                    ),
                )
                .outerjoin(
                    ActionExecution,
                    and_(
                        ActionExecution.organisation_id == OutreachMessage.organisation_id,
                        ActionExecution.action_id == OutreachMessage.action_id,
                    ),
                )
                .where(
                    EngageEnrollmentStep.organisation_id == organisation_id,
                    EngageEnrollmentStep.enrollment_id == enrollment_id,
                )
                .order_by(EngageSequenceStep.step_order, ActionExecution.created_at.desc())
            )
        ).all()
        selected: dict[UUID, tuple[EngageEnrollmentStep, EngageSequenceStep, ActionExecution | None]] = {}
        for step_instance, sequence_step, execution in rows:
            selected.setdefault(step_instance.id, (step_instance, sequence_step, execution))
        return list(selected.values())

    async def active_campaign_collision(
        self,
        organisation_id: UUID,
        contact_id: UUID,
        *,
        excluding_campaign_id: UUID | None = None,
    ) -> bool:
        statement = (
            select(func.count())
            .select_from(EngageCampaignEnrollment)
            .join(
                EngageCampaign,
                and_(
                    EngageCampaign.organisation_id == EngageCampaignEnrollment.organisation_id,
                    EngageCampaign.id == EngageCampaignEnrollment.campaign_id,
                ),
            )
            .where(
                EngageCampaignEnrollment.organisation_id == organisation_id,
                EngageCampaignEnrollment.contact_id == contact_id,
                EngageCampaignEnrollment.state.in_(("ready", "active", "paused", "needs_attention")),
                EngageCampaign.state.in_(("active", "paused", "needs_attention")),
            )
        )
        if excluding_campaign_id is not None:
            statement = statement.where(EngageCampaignEnrollment.campaign_id != excluding_campaign_id)
        return int(await self.session.scalar(statement) or 0) > 0

    async def active_campaign_counts(self, organisation_id: UUID, owner_user_id: UUID) -> tuple[int, int]:
        active_states = ("active", "paused", "needs_attention")
        organisation_count = int(
            await self.session.scalar(
                select(func.count())
                .select_from(EngageCampaign)
                .where(EngageCampaign.organisation_id == organisation_id, EngageCampaign.state.in_(active_states))
            )
            or 0
        )
        owner_count = int(
            await self.session.scalar(
                select(func.count())
                .select_from(EngageCampaign)
                .where(
                    EngageCampaign.organisation_id == organisation_id,
                    EngageCampaign.owner_user_id == owner_user_id,
                    EngageCampaign.state.in_(active_states),
                )
            )
            or 0
        )
        return owner_count, organisation_count

    async def campaign_counts(self, organisation_id: UUID, campaign_id: UUID) -> dict[str, int]:
        enrollment_rows = (
            await self.session.execute(
                select(EngageCampaignEnrollment.state, EngageCampaignEnrollment.outcome, func.count())
                .where(
                    EngageCampaignEnrollment.organisation_id == organisation_id,
                    EngageCampaignEnrollment.campaign_id == campaign_id,
                )
                .group_by(EngageCampaignEnrollment.state, EngageCampaignEnrollment.outcome)
            )
        ).all()
        result = {
            "recipients": 0,
            "active": 0,
            "completed": 0,
            "stopped": 0,
            "blocked": 0,
            "needs_attention": 0,
            "messages_sent": 0,
            "messages_ready_for_review": 0,
            "messages_failed": 0,
            "replies_reported": 0,
            "meetings_reported": 0,
        }
        for state, outcome, count in enrollment_rows:
            value = int(count)
            result["recipients"] += value
            if state in {"ready", "active", "paused"}:
                result["active"] += value
            elif state in result:
                result[state] += value
            if outcome == "replied":
                result["replies_reported"] += value
            elif outcome == "meeting_booked":
                result["meetings_reported"] += value
        step_rows = (
            await self.session.execute(
                select(EngageEnrollmentStep.state, func.count())
                .join(
                    EngageCampaignEnrollment,
                    and_(
                        EngageCampaignEnrollment.organisation_id == EngageEnrollmentStep.organisation_id,
                        EngageCampaignEnrollment.id == EngageEnrollmentStep.enrollment_id,
                    ),
                )
                .where(
                    EngageEnrollmentStep.organisation_id == organisation_id,
                    EngageCampaignEnrollment.campaign_id == campaign_id,
                )
                .group_by(EngageEnrollmentStep.state)
            )
        ).all()
        for state, count in step_rows:
            if state == "sent":
                result["messages_sent"] += int(count)
            elif state == "ready_for_review":
                result["messages_ready_for_review"] += int(count)
            elif state in {"blocked", "unknown_delivery_state"}:
                result["messages_failed"] += int(count)
        return result

    async def prepared_drafts_since(self, organisation_id: UUID, since: datetime) -> int:
        return int(
            await self.session.scalar(
                select(func.count())
                .select_from(EngageEnrollmentStep)
                .where(
                    EngageEnrollmentStep.organisation_id == organisation_id,
                    EngageEnrollmentStep.prepared_at.is_not(None),
                    EngageEnrollmentStep.prepared_at >= since,
                )
            )
            or 0
        )

    async def active_email_connection_for_user(
        self, organisation_id: UUID, user_id: UUID
    ) -> IntegrationConnection | None:
        return cast(
            IntegrationConnection | None,
            await self.session.scalar(
                select(IntegrationConnection)
                .where(
                    IntegrationConnection.organisation_id == organisation_id,
                    IntegrationConnection.connector_key == "mock_email",
                    IntegrationConnection.connection_status == "active",
                    IntegrationConnection.created_by_user_id == user_id,
                )
                .limit(1)
            ),
        )

    async def delete_draft_children(self, organisation_id: UUID, campaign_version_id: UUID) -> None:
        await self.session.execute(
            delete(EngageCampaignAudience).where(
                EngageCampaignAudience.organisation_id == organisation_id,
                EngageCampaignAudience.campaign_version_id == campaign_version_id,
            )
        )
        await self.session.execute(
            delete(EngageSequenceStep).where(
                EngageSequenceStep.organisation_id == organisation_id,
                EngageSequenceStep.campaign_version_id == campaign_version_id,
            )
        )

    async def next_due_step(self, organisation_id: UUID, now: datetime) -> EngageEnrollmentStep | None:
        return cast(
            EngageEnrollmentStep | None,
            await self.session.scalar(
                select(EngageEnrollmentStep)
                .join(
                    EngageCampaignEnrollment,
                    and_(
                        EngageCampaignEnrollment.organisation_id == EngageEnrollmentStep.organisation_id,
                        EngageCampaignEnrollment.id == EngageEnrollmentStep.enrollment_id,
                    ),
                )
                .join(
                    EngageCampaign,
                    and_(
                        EngageCampaign.organisation_id == EngageCampaignEnrollment.organisation_id,
                        EngageCampaign.id == EngageCampaignEnrollment.campaign_id,
                    ),
                )
                .where(
                    EngageEnrollmentStep.organisation_id == organisation_id,
                    EngageCampaign.state == "active",
                    EngageCampaignEnrollment.state.in_(("ready", "active")),
                    or_(
                        and_(
                            EngageEnrollmentStep.state.in_(("pending", "deferred")),
                            EngageEnrollmentStep.prepare_at <= now,
                        ),
                        and_(
                            EngageEnrollmentStep.state == "prepared",
                            EngageEnrollmentStep.scheduled_at <= now,
                        ),
                        EngageEnrollmentStep.state.in_(("queued", "ready_for_review")),
                    ),
                )
                .order_by(
                    EngageEnrollmentStep.prepare_at,
                    EngageEnrollmentStep.scheduled_at,
                    EngageEnrollmentStep.created_at,
                    EngageEnrollmentStep.id,
                )
                .with_for_update(skip_locked=True)
                .limit(1)
            ),
        )

    def add(self, entity: Base) -> None:
        self.session.add(entity)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
