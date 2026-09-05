from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.models import (
    BillingAccount,
    BillingInvoiceProjection,
    BillingOperation,
    BillingProviderEventReceipt,
    BillingSubscription,
)


class BillingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def account(self, organisation_id: UUID, provider: str, mode: str) -> BillingAccount | None:
        return cast(
            BillingAccount | None,
            await self.session.scalar(
                select(BillingAccount).where(
                    BillingAccount.organisation_id == organisation_id,
                    BillingAccount.provider == provider,
                    BillingAccount.provider_mode == mode,
                )
            ),
        )

    async def subscription(self, organisation_id: UUID, *, lock: bool = False) -> BillingSubscription | None:
        statement = (
            select(BillingSubscription)
            .where(BillingSubscription.organisation_id == organisation_id)
            .order_by(BillingSubscription.created_at.desc(), BillingSubscription.id.desc())
            .limit(1)
        )
        if lock:
            statement = statement.with_for_update()
        return cast(BillingSubscription | None, await self.session.scalar(statement))

    async def subscription_by_provider_id(
        self,
        organisation_id: UUID,
        billing_account_id: UUID,
        provider_subscription_id: str,
        *,
        lock: bool = False,
    ) -> BillingSubscription | None:
        statement = select(BillingSubscription).where(
            BillingSubscription.organisation_id == organisation_id,
            BillingSubscription.billing_account_id == billing_account_id,
            BillingSubscription.provider_subscription_id == provider_subscription_id,
        )
        if lock:
            statement = statement.with_for_update()
        return cast(BillingSubscription | None, await self.session.scalar(statement))

    async def invoices(self, organisation_id: UUID) -> list[BillingInvoiceProjection]:
        return list(
            (
                await self.session.scalars(
                    select(BillingInvoiceProjection)
                    .where(BillingInvoiceProjection.organisation_id == organisation_id)
                    .order_by(BillingInvoiceProjection.invoice_date.desc(), BillingInvoiceProjection.id.desc())
                )
            ).all()
        )

    async def invoice_by_provider_id(
        self, organisation_id: UUID, provider_invoice_id: str
    ) -> BillingInvoiceProjection | None:
        return cast(
            BillingInvoiceProjection | None,
            await self.session.scalar(
                select(BillingInvoiceProjection).where(
                    BillingInvoiceProjection.organisation_id == organisation_id,
                    BillingInvoiceProjection.provider_invoice_id == provider_invoice_id,
                )
            ),
        )

    async def operation(
        self,
        organisation_id: UUID,
        operation_type: str,
        idempotency_key: str,
        *,
        lock: bool = False,
    ) -> BillingOperation | None:
        statement = select(BillingOperation).where(
            BillingOperation.organisation_id == organisation_id,
            BillingOperation.operation_type == operation_type,
            BillingOperation.idempotency_key == idempotency_key,
        )
        if lock:
            statement = statement.with_for_update()
        return cast(BillingOperation | None, await self.session.scalar(statement))

    async def provider_event_receipt(
        self,
        organisation_id: UUID,
        provider: str,
        mode: str,
        provider_event_id: str,
    ) -> BillingProviderEventReceipt | None:
        return cast(
            BillingProviderEventReceipt | None,
            await self.session.scalar(
                select(BillingProviderEventReceipt).where(
                    BillingProviderEventReceipt.organisation_id == organisation_id,
                    BillingProviderEventReceipt.provider == provider,
                    BillingProviderEventReceipt.provider_mode == mode,
                    BillingProviderEventReceipt.provider_event_id == provider_event_id,
                )
            ),
        )
