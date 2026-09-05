from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    CreditActionPriceVersion,
    CreditExecutionControl,
    CreditLedgerEntry,
    CreditLot,
    CreditOperation,
    CreditOrganisationPolicy,
    CreditPackVersion,
    CreditQuote,
    CreditReservationAllocation,
    OrganisationCreditBalance,
)


class CreditRepository:
    """Tenant predicates stay explicit even when PostgreSQL RLS is also active."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def balance(self, organisation_id: UUID, *, lock: bool = False) -> OrganisationCreditBalance | None:
        statement = select(OrganisationCreditBalance).where(
            OrganisationCreditBalance.organisation_id == organisation_id
        )
        if lock:
            statement = statement.with_for_update()
        return cast(OrganisationCreditBalance | None, await self.session.scalar(statement))

    async def policy(self, organisation_id: UUID, *, lock: bool = False) -> CreditOrganisationPolicy | None:
        statement = select(CreditOrganisationPolicy).where(CreditOrganisationPolicy.organisation_id == organisation_id)
        if lock:
            statement = statement.with_for_update()
        return cast(CreditOrganisationPolicy | None, await self.session.scalar(statement))

    async def lots_for_consumption(self, organisation_id: UUID, *, lock: bool = False) -> list[CreditLot]:
        statement = (
            select(CreditLot)
            .where(CreditLot.organisation_id == organisation_id, CreditLot.available_credits > 0)
            .order_by(
                case((CreditLot.credit_type == "promotional", 0), else_=1),
                case((CreditLot.expires_at.is_(None), 1), else_=0),
                CreditLot.expires_at,
                CreditLot.created_at,
                CreditLot.id,
            )
        )
        if lock:
            statement = statement.with_for_update()
        return list((await self.session.scalars(statement)).all())

    async def expired_lots(self, organisation_id: UUID, now: datetime, *, lock: bool = False) -> list[CreditLot]:
        statement = (
            select(CreditLot)
            .where(
                CreditLot.organisation_id == organisation_id,
                CreditLot.credit_type == "promotional",
                CreditLot.available_credits > 0,
                CreditLot.expires_at.is_not(None),
                CreditLot.expires_at <= now,
            )
            .order_by(CreditLot.expires_at, CreditLot.id)
        )
        if lock:
            statement = statement.with_for_update()
        return list((await self.session.scalars(statement)).all())

    async def lot(self, organisation_id: UUID, lot_id: UUID, *, lock: bool = False) -> CreditLot | None:
        statement = select(CreditLot).where(CreditLot.organisation_id == organisation_id, CreditLot.id == lot_id)
        if lock:
            statement = statement.with_for_update()
        return cast(CreditLot | None, await self.session.scalar(statement))

    async def trial_lot(self, organisation_id: UUID) -> CreditLot | None:
        return cast(
            CreditLot | None,
            await self.session.scalar(
                select(CreditLot).where(
                    CreditLot.organisation_id == organisation_id,
                    CreditLot.trial_grant.is_(True),
                )
            ),
        )

    async def ledger_by_key(self, organisation_id: UUID, idempotency_key: str) -> CreditLedgerEntry | None:
        return cast(
            CreditLedgerEntry | None,
            await self.session.scalar(
                select(CreditLedgerEntry).where(
                    CreditLedgerEntry.organisation_id == organisation_id,
                    CreditLedgerEntry.idempotency_key == idempotency_key,
                )
            ),
        )

    async def ledger_entry(self, organisation_id: UUID, entry_id: UUID) -> CreditLedgerEntry | None:
        return cast(
            CreditLedgerEntry | None,
            await self.session.scalar(
                select(CreditLedgerEntry).where(
                    CreditLedgerEntry.organisation_id == organisation_id,
                    CreditLedgerEntry.id == entry_id,
                )
            ),
        )

    async def recent_ledger(self, organisation_id: UUID, *, limit: int = 30) -> list[CreditLedgerEntry]:
        return list(
            (
                await self.session.scalars(
                    select(CreditLedgerEntry)
                    .where(CreditLedgerEntry.organisation_id == organisation_id)
                    .order_by(CreditLedgerEntry.created_at.desc(), CreditLedgerEntry.id.desc())
                    .limit(limit)
                )
            ).all()
        )

    async def quote(self, organisation_id: UUID, quote_id: UUID, *, lock: bool = False) -> CreditQuote | None:
        statement = select(CreditQuote).where(
            CreditQuote.organisation_id == organisation_id, CreditQuote.id == quote_id
        )
        if lock:
            statement = statement.with_for_update()
        return cast(CreditQuote | None, await self.session.scalar(statement))

    async def operation_by_key(
        self, organisation_id: UUID, idempotency_key: str, *, lock: bool = False
    ) -> CreditOperation | None:
        statement = select(CreditOperation).where(
            CreditOperation.organisation_id == organisation_id,
            CreditOperation.idempotency_key == idempotency_key,
        )
        if lock:
            statement = statement.with_for_update()
        return cast(CreditOperation | None, await self.session.scalar(statement))

    async def operation(
        self, organisation_id: UUID, operation_id: UUID, *, lock: bool = False
    ) -> CreditOperation | None:
        statement = select(CreditOperation).where(
            CreditOperation.organisation_id == organisation_id,
            CreditOperation.id == operation_id,
        )
        if lock:
            statement = statement.with_for_update()
        return cast(CreditOperation | None, await self.session.scalar(statement))

    async def allocations(
        self, organisation_id: UUID, operation_id: UUID, *, lock: bool = False
    ) -> list[CreditReservationAllocation]:
        statement = (
            select(CreditReservationAllocation)
            .where(
                CreditReservationAllocation.organisation_id == organisation_id,
                CreditReservationAllocation.operation_id == operation_id,
            )
            .order_by(CreditReservationAllocation.allocation_order)
        )
        if lock:
            statement = statement.with_for_update()
        return list((await self.session.scalars(statement)).all())

    async def active_price(self, action_code: str, environment: str) -> CreditActionPriceVersion | None:
        status = "production_active" if environment == "production" else "test_active"
        return cast(
            CreditActionPriceVersion | None,
            await self.session.scalar(
                select(CreditActionPriceVersion)
                .where(
                    CreditActionPriceVersion.action_code == action_code,
                    CreditActionPriceVersion.environment == environment,
                    CreditActionPriceVersion.status == status,
                    CreditActionPriceVersion.effective_from <= func.now(),
                )
                .order_by(CreditActionPriceVersion.version.desc())
                .limit(1)
            ),
        )

    async def price(self, price_id: UUID) -> CreditActionPriceVersion | None:
        return await self.session.get(CreditActionPriceVersion, price_id)

    async def active_test_packs(self) -> list[CreditPackVersion]:
        return list(
            (
                await self.session.scalars(
                    select(CreditPackVersion)
                    .where(
                        CreditPackVersion.environment == "test",
                        CreditPackVersion.status == "test_active",
                        CreditPackVersion.effective_from <= func.now(),
                    )
                    .order_by(CreditPackVersion.price_minor_units, CreditPackVersion.pack_code)
                )
            ).all()
        )

    async def control(self, scope: str, key: str) -> CreditExecutionControl | None:
        return cast(
            CreditExecutionControl | None,
            await self.session.scalar(
                select(CreditExecutionControl).where(
                    CreditExecutionControl.control_scope == scope,
                    CreditExecutionControl.control_key == key,
                )
            ),
        )

    async def consumed_since(self, organisation_id: UUID, since: datetime) -> int:
        value = await self.session.scalar(
            select(func.coalesce(func.sum(-CreditLedgerEntry.reserved_delta), 0)).where(
                CreditLedgerEntry.organisation_id == organisation_id,
                CreditLedgerEntry.event_type == "consumption",
                CreditLedgerEntry.created_at >= since,
            )
        )
        return int(value or 0)

    async def provider_cost_since(self, organisation_id: UUID, since: datetime) -> int:
        value = await self.session.scalar(
            select(func.coalesce(func.sum(CreditOperation.provider_cost_micros), 0)).where(
                CreditOperation.organisation_id == organisation_id,
                CreditOperation.outcome_recorded_at.is_not(None),
                CreditOperation.outcome_recorded_at >= since,
            )
        )
        return int(value or 0)

    async def reservations_since(self, organisation_id: UUID, since: datetime) -> int:
        value = await self.session.scalar(
            select(func.count())
            .select_from(CreditOperation)
            .where(
                CreditOperation.organisation_id == organisation_id,
                CreditOperation.created_at >= since,
            )
        )
        return int(value or 0)

    async def active_exposure(self, organisation_id: UUID) -> tuple[int, int]:
        row = (
            await self.session.execute(
                select(
                    func.coalesce(func.sum(CreditOperation.reserved_credits), 0),
                    func.coalesce(func.sum(CreditQuote.maximum_provider_cost_micros), 0),
                )
                .join(
                    CreditQuote,
                    (CreditQuote.organisation_id == CreditOperation.organisation_id)
                    & (CreditQuote.id == CreditOperation.quote_id),
                )
                .where(
                    CreditOperation.organisation_id == organisation_id,
                    CreditOperation.status.in_(("reserved", "executing", "unknown")),
                )
            )
        ).one()
        return int(row[0]), int(row[1])

    async def ledger_totals(self, organisation_id: UUID) -> tuple[int, int, int, int]:
        row = (
            await self.session.execute(
                select(
                    func.coalesce(func.sum(CreditLedgerEntry.purchased_available_delta), 0),
                    func.coalesce(func.sum(CreditLedgerEntry.promotional_available_delta), 0),
                    func.coalesce(
                        func.sum(
                            case(
                                (CreditLedgerEntry.credit_type == "purchased", CreditLedgerEntry.reserved_delta),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                    func.coalesce(
                        func.sum(
                            case(
                                (CreditLedgerEntry.credit_type == "promotional", CreditLedgerEntry.reserved_delta),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                ).where(CreditLedgerEntry.organisation_id == organisation_id)
            )
        ).one()
        return int(row[0]), int(row[1]), int(row[2]), int(row[3])

    async def lot_totals(self, organisation_id: UUID) -> tuple[int, int, int, int]:
        row = (
            await self.session.execute(
                select(
                    func.coalesce(
                        func.sum(case((CreditLot.credit_type == "purchased", CreditLot.available_credits), else_=0)),
                        0,
                    ),
                    func.coalesce(
                        func.sum(case((CreditLot.credit_type == "promotional", CreditLot.available_credits), else_=0)),
                        0,
                    ),
                    func.coalesce(
                        func.sum(case((CreditLot.credit_type == "purchased", CreditLot.reserved_credits), else_=0)),
                        0,
                    ),
                    func.coalesce(
                        func.sum(case((CreditLot.credit_type == "promotional", CreditLot.reserved_credits), else_=0)),
                        0,
                    ),
                ).where(CreditLot.organisation_id == organisation_id)
            )
        ).one()
        return int(row[0]), int(row[1]), int(row[2]), int(row[3])
