from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import AIJob, Organisation


class AIWorkerRepository:
    """Queue queries whose callers establish one tenant context per transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def discover_eligible_organisations(
        self,
        *,
        eligible_at: datetime,
        limit: int,
    ) -> list[UUID]:
        bind = self.session.get_bind()
        if bind.dialect.name == "postgresql":
            result = await self.session.scalars(
                text(
                    """
                    SELECT organisation_id
                    FROM public.revenueos_ai_worker_eligible_organisations(
                        :eligible_at,
                        :result_limit
                    )
                    """
                ),
                {"eligible_at": eligible_at, "result_limit": limit},
            )
            return [UUID(str(value)) for value in result.all()]

        result = await self.session.scalars(
            select(Organisation.id)
            .where(
                Organisation.id.in_(
                    select(AIJob.organisation_id).where(
                        or_(
                            (
                                (AIJob.status == "pending")
                                & (
                                    AIJob.cancellation_requested_at.is_not(None)
                                    | (
                                        (AIJob.attempt_count < AIJob.max_attempts)
                                        & (AIJob.next_attempt_at.is_(None) | (AIJob.next_attempt_at <= eligible_at))
                                    )
                                )
                            ),
                            (
                                (AIJob.status == "running")
                                & AIJob.lease_expires_at.is_not(None)
                                & (AIJob.lease_expires_at <= eligible_at)
                            ),
                        )
                    )
                )
            )
            .order_by(Organisation.id)
            .limit(limit)
        )
        return list(result.all())

    async def lock_pending_cancellations(
        self,
        organisation_id: UUID,
        *,
        limit: int,
    ) -> list[AIJob]:
        result = await self.session.scalars(
            select(AIJob)
            .where(
                AIJob.organisation_id == organisation_id,
                AIJob.status == "pending",
                AIJob.cancellation_requested_at.is_not(None),
            )
            .order_by(AIJob.created_at, AIJob.id)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        return list(result.all())

    async def lock_stale_running(
        self,
        organisation_id: UUID,
        *,
        stale_at: datetime,
        limit: int,
    ) -> list[AIJob]:
        result = await self.session.scalars(
            select(AIJob)
            .where(
                AIJob.organisation_id == organisation_id,
                AIJob.status == "running",
                AIJob.lease_expires_at.is_not(None),
                AIJob.lease_expires_at <= stale_at,
            )
            .order_by(AIJob.lease_expires_at, AIJob.created_at, AIJob.id)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        return list(result.all())

    async def claim_next(
        self,
        organisation_id: UUID,
        *,
        eligible_at: datetime,
    ) -> AIJob | None:
        return cast(
            AIJob | None,
            await self.session.scalar(
                select(AIJob)
                .where(
                    AIJob.organisation_id == organisation_id,
                    AIJob.status == "pending",
                    AIJob.cancellation_requested_at.is_(None),
                    AIJob.attempt_count < AIJob.max_attempts,
                    or_(
                        AIJob.next_attempt_at.is_(None),
                        AIJob.next_attempt_at <= eligible_at,
                    ),
                )
                .order_by(
                    func.coalesce(AIJob.next_attempt_at, AIJob.created_at),
                    AIJob.created_at,
                    AIJob.id,
                )
                .with_for_update(skip_locked=True)
                .limit(1)
            ),
        )

    async def lock_owned_running(
        self,
        organisation_id: UUID,
        job_id: UUID,
        worker_id: str,
        *,
        owned_at: datetime,
    ) -> AIJob | None:
        return cast(
            AIJob | None,
            await self.session.scalar(
                select(AIJob)
                .where(
                    AIJob.organisation_id == organisation_id,
                    AIJob.id == job_id,
                    AIJob.status == "running",
                    AIJob.worker_id == worker_id,
                    AIJob.lease_expires_at.is_not(None),
                    AIJob.lease_expires_at > owned_at,
                )
                .with_for_update()
            ),
        )

    async def refresh_heartbeat(
        self,
        organisation_id: UUID,
        job_id: UUID,
        worker_id: str,
        *,
        heartbeat_at: datetime,
        lease_expires_at: datetime,
    ) -> bool:
        result = await self.session.execute(
            update(AIJob)
            .where(
                AIJob.organisation_id == organisation_id,
                AIJob.id == job_id,
                AIJob.status == "running",
                AIJob.worker_id == worker_id,
                AIJob.lease_expires_at.is_not(None),
                AIJob.lease_expires_at > heartbeat_at,
            )
            .values(
                heartbeat_at=heartbeat_at,
                lease_expires_at=lease_expires_at,
            )
            .returning(AIJob.id)
        )
        return result.scalar_one_or_none() is not None
