from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from revenueos.commercial_contracts import ModuleCode
from revenueos.commercial_services import CommercialService
from revenueos.config import Settings
from revenueos.credit_contracts import (
    CreditActivityResponse,
    CreditBalanceResponse,
    CreditOperationOutcome,
    CreditOperationResponse,
    CreditPackResponse,
    CreditQuoteResponse,
    CreditReconciliationResponse,
    CreditsProjectionResponse,
    MarginValidationResponse,
)
from revenueos.credit_repositories import CreditRepository
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import (
    BetaSystemEvent,
    BillingOperation,
    CreditActionPriceVersion,
    CreditControlEvent,
    CreditExecutionControl,
    CreditLedgerEntry,
    CreditLot,
    CreditOperation,
    CreditOrganisationPolicy,
    CreditPackVersion,
    CreditQuote,
    CreditReservationAllocation,
    OrganisationCommercialState,
    OrganisationCreditBalance,
)

MAX_CREDITS = 9_000_000_000_000
TEST_PACK_ID = UUID("00000000-0000-4000-9000-000000000049")
TEST_PRICE_ID = UUID("00000000-0000-4000-9000-000000000149")
TEST_GLOBAL_CONTROL_ID = UUID("00000000-0000-4000-9000-000000000249")
TEST_ACTION_CONTROL_ID = UUID("00000000-0000-4000-9000-000000000349")
TEST_PROVIDER_CONTROL_ID = UUID("00000000-0000-4000-9000-000000000449")
TEST_ACTION_CODE = "PROSPECT_COMPANY_RESEARCH"
TEST_PROVIDER_CAPABILITY = "deterministic:company_research"
TEST_PRICING_NOTICE = "TEST ONLY / NOT CUSTOMER PRICING"


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _fingerprint(payload: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _event_key(phase: str, supplied_key: str, discriminator: object) -> str:
    digest = hashlib.sha256(f"{phase}:{supplied_key}:{discriminator}".encode()).hexdigest()
    return f"{phase}:{digest}"


def _require_actor_reason(actor_reference: str, reason: str) -> tuple[str, str]:
    actor = actor_reference.strip()
    resolved_reason = reason.strip()
    if not actor or len(actor) > 200 or any(ord(character) < 32 for character in actor):
        raise PublicAPIError("credit_actor_invalid", "A valid internal actor reference is required.", 422)
    if (
        len(resolved_reason) < 8
        or len(resolved_reason) > 500
        or any(ord(character) < 32 for character in resolved_reason)
    ):
        raise PublicAPIError("credit_reason_invalid", "A meaningful adjustment reason is required.", 422)
    return actor, resolved_reason


class CreditService:
    """Provider-neutral commercial boundary; providers never mutate balances directly."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.repository = CreditRepository(session)
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def catalogue_environment(self) -> Literal["test", "production"]:
        return "production" if self.settings.environment == "production" else "test"

    async def projection(self, organisation_id: UUID) -> CreditsProjectionResponse:
        if self.catalogue_environment == "test":
            await self.ensure_test_catalogue()
        balance = await self.repository.balance(organisation_id, lock=True)
        if balance is not None:
            await self._expire_promotional_lots(organisation_id, balance)
        await self._commit(organisation_id)
        rows = await self.repository.recent_ledger(organisation_id)
        packs = await self.repository.active_test_packs() if self.catalogue_environment == "test" else []
        response_balance = self._balance_response(balance)
        return CreditsProjectionResponse(
            unit_name="Oryntela Credit",
            balance=response_balance,
            recent_activity=[self._activity_response(item) for item in rows],
            test_packs=[
                CreditPackResponse(
                    id=pack.id,
                    pack_code=pack.pack_code,
                    display_name=pack.display_name,
                    version=pack.version,
                    credit_quantity=pack.credit_quantity,
                    amount_minor_units=pack.price_minor_units,
                    currency="AUD",
                    test_only=True,
                    purchase_available=False,
                    pricing_note=pack.pricing_note,
                )
                for pack in packs
            ],
            low_balance=response_balance.available == 0,
            auto_top_up=False,
            production_prices_available=False,
            message=(
                "Credits cover meaningful metered external services. Ordinary Oryntela software use is not metered. "
                "Test catalogue values are not customer pricing."
            ),
        )

    async def ensure_test_catalogue(self) -> None:
        if self.catalogue_environment != "test":
            return
        now = _aware(self._clock()) - timedelta(seconds=1)
        if await self.session.get(CreditPackVersion, TEST_PACK_ID) is None:
            self.session.add(
                CreditPackVersion(
                    id=TEST_PACK_ID,
                    pack_code="TEST_100",
                    display_name="100 test Credits",
                    version=1,
                    credit_quantity=100,
                    price_minor_units=2_000,
                    currency="AUD",
                    environment="test",
                    status="test_active",
                    pricing_note=TEST_PRICING_NOTICE,
                    effective_from=now,
                    created_by_actor="wo-049-deterministic-catalogue",
                )
            )
        if await self.session.get(CreditActionPriceVersion, TEST_PRICE_ID) is None:
            margin = self.validate_margin(1_000_000, 400_000, 1_000)
            self.session.add(
                CreditActionPriceVersion(
                    id=TEST_PRICE_ID,
                    action_code=TEST_ACTION_CODE,
                    display_name="Research this company",
                    required_module_code="prospect",
                    version=1,
                    credit_charge_per_unit=5,
                    customer_charge_basis="successful_unit",
                    max_units_per_operation=40,
                    customer_revenue_micros_per_unit=1_000_000,
                    customer_currency="AUD",
                    cost_basis="successful_unit",
                    provider_cost_minor_units=20,
                    provider_currency="USD",
                    fx_rate_to_aud=Decimal("1.50000000"),
                    fx_source="deterministic test assumption",
                    fx_observed_at=now,
                    other_variable_cost_micros=50_000,
                    expected_variable_cost_micros_per_unit=350_000,
                    maximum_variable_cost_micros_per_unit=400_000,
                    gross_margin_basis_points=margin.gross_margin_basis_points,
                    approved_margin_floor_basis_points=1_000,
                    owner_approval_reference=None,
                    environment="test",
                    status="test_active",
                    pricing_note=TEST_PRICING_NOTICE,
                    effective_from=now,
                    created_by_actor="wo-049-deterministic-catalogue",
                )
            )
        controls = (
            (TEST_GLOBAL_CONTROL_ID, "global", "metered_actions"),
            (TEST_ACTION_CONTROL_ID, "action", TEST_ACTION_CODE),
            (TEST_PROVIDER_CONTROL_ID, "provider_capability", TEST_PROVIDER_CAPABILITY),
        )
        for control_id, scope, key in controls:
            if await self.session.get(CreditExecutionControl, control_id) is None:
                self.session.add(
                    CreditExecutionControl(
                        id=control_id,
                        control_scope=scope,
                        control_key=key,
                        enabled=self.settings.feature_credits_enabled,
                        actor_reference="wo-049-deterministic-catalogue",
                        reason=f"{TEST_PRICING_NOTICE}; execution follows the server feature flag.",
                    )
                )
        await self.session.flush()

    async def configure_policy(
        self,
        organisation_id: UUID,
        *,
        metered_actions_enabled: bool,
        max_credits_per_operation: int,
        max_credits_per_day: int,
        max_provider_cost_micros_per_day: int,
        trial_max_credits_per_day: int | None,
        max_operations_per_minute: int,
        actor_reference: str,
        reason: str,
    ) -> CreditOrganisationPolicy:
        actor, resolved_reason = _require_actor_reason(actor_reference, reason)
        values = (
            max_credits_per_operation,
            max_credits_per_day,
            max_provider_cost_micros_per_day,
            max_operations_per_minute,
        )
        if any(value <= 0 or value > MAX_CREDITS for value in values):
            raise PublicAPIError("credit_policy_invalid", "Credit exposure limits must be positive and bounded.", 422)
        if trial_max_credits_per_day is not None and not 0 < trial_max_credits_per_day <= MAX_CREDITS:
            raise PublicAPIError("credit_policy_invalid", "The trial exposure limit must be positive and bounded.", 422)
        policy = await self.repository.policy(organisation_id, lock=True)
        if policy is None:
            policy = CreditOrganisationPolicy(
                organisation_id=organisation_id,
                metered_actions_enabled=metered_actions_enabled,
                max_credits_per_operation=max_credits_per_operation,
                max_credits_per_day=max_credits_per_day,
                max_provider_cost_micros_per_day=max_provider_cost_micros_per_day,
                trial_max_credits_per_day=trial_max_credits_per_day,
                max_operations_per_minute=max_operations_per_minute,
                actor_reference=actor,
                reason=resolved_reason,
            )
            self.session.add(policy)
        else:
            policy.metered_actions_enabled = metered_actions_enabled
            policy.max_credits_per_operation = max_credits_per_operation
            policy.max_credits_per_day = max_credits_per_day
            policy.max_provider_cost_micros_per_day = max_provider_cost_micros_per_day
            policy.trial_max_credits_per_day = trial_max_credits_per_day
            policy.max_operations_per_minute = max_operations_per_minute
            policy.actor_reference = actor
            policy.reason = resolved_reason
        self.session.add(
            BetaSystemEvent(
                id=uuid.uuid4(),
                organisation_id=organisation_id,
                actor_user_id=None,
                event_type="credit_exposure_policy_configured",
                subject_id=organisation_id,
                metadata_json={
                    "actorReference": actor,
                    "reason": resolved_reason,
                    "meteredActionsEnabled": metered_actions_enabled,
                    "maxCreditsPerOperation": max_credits_per_operation,
                    "maxCreditsPerDay": max_credits_per_day,
                    "maxProviderCostMicrosPerDay": max_provider_cost_micros_per_day,
                    "trialMaxCreditsPerDay": trial_max_credits_per_day,
                    "maxOperationsPerMinute": max_operations_per_minute,
                },
            )
        )
        await self._commit(organisation_id)
        return policy

    async def set_execution_control(
        self,
        *,
        scope: Literal["global", "action", "provider_capability"],
        key: str,
        enabled: bool,
        actor_reference: str,
        reason: str,
    ) -> CreditExecutionControl:
        actor, resolved_reason = _require_actor_reason(actor_reference, reason)
        if not key.strip() or len(key) > 120:
            raise PublicAPIError("credit_control_invalid", "A valid control key is required.", 422)
        control = await self.repository.control(scope, key)
        if control is None:
            control = CreditExecutionControl(
                id=uuid.uuid4(),
                control_scope=scope,
                control_key=key,
                enabled=enabled,
                actor_reference=actor,
                reason=resolved_reason,
            )
            self.session.add(control)
        else:
            control.enabled = enabled
            control.actor_reference = actor
            control.reason = resolved_reason
        self.session.add(
            CreditControlEvent(
                id=uuid.uuid4(),
                control_scope=scope,
                control_key=key,
                enabled=enabled,
                actor_reference=actor,
                reason=resolved_reason,
            )
        )
        await self.session.commit()
        return control

    async def create_action_price_version(
        self,
        *,
        action_code: str,
        display_name: str,
        required_module_code: ModuleCode,
        version: int,
        credit_charge_per_unit: int,
        customer_charge_basis: Literal["successful_unit", "requested_unit"],
        max_units_per_operation: int,
        customer_revenue_micros_per_unit: int,
        cost_basis: Literal["fixed_operation", "successful_unit", "provider_unit", "message_segment", "minute"],
        provider_cost_minor_units: int,
        provider_currency: str,
        fx_rate_to_aud: Decimal,
        fx_source: str,
        fx_observed_at: datetime,
        other_variable_cost_micros: int,
        expected_variable_cost_micros_per_unit: int,
        maximum_variable_cost_micros_per_unit: int,
        status: Literal["draft", "test_active", "production_active"],
        pricing_note: str,
        actor_reference: str,
    ) -> CreditActionPriceVersion:
        actor, _ = _require_actor_reason(actor_reference, pricing_note)
        if version <= 0 or max_units_per_operation <= 0 or max_units_per_operation > 1_000_000:
            raise PublicAPIError(
                "credit_action_price_invalid", "Action price version and quantity cap are invalid.", 422
            )
        self._validate_credits(credit_charge_per_unit)
        if customer_charge_basis not in {"successful_unit", "requested_unit"}:
            raise PublicAPIError("credit_action_price_invalid", "Customer charge basis is invalid.", 422)
        if (
            customer_revenue_micros_per_unit <= 0
            or provider_cost_minor_units < 0
            or other_variable_cost_micros < 0
            or expected_variable_cost_micros_per_unit < 0
            or maximum_variable_cost_micros_per_unit < expected_variable_cost_micros_per_unit
            or fx_rate_to_aud <= 0
            or len(provider_currency) != 3
            or not provider_currency.isalpha()
            or not fx_source.strip()
        ):
            raise PublicAPIError(
                "credit_action_price_invalid", "Complete exact provider-cost assumptions are required.", 422
            )
        environment = self.catalogue_environment
        floor = self.settings.credits_margin_floor_basis_points if status == "production_active" else 1_000
        approval = self.settings.credits_margin_policy_reference if status == "production_active" else None
        margin = self.validate_margin(
            customer_revenue_micros_per_unit,
            maximum_variable_cost_micros_per_unit,
            floor,
        )
        if status == "production_active" and (
            environment != "production" or approval is None or not margin.production_eligible
        ):
            raise PublicAPIError(
                "credit_production_price_not_approved",
                "Production action pricing requires complete economics and an owner-approved margin policy.",
                409,
            )
        if status == "test_active" and environment != "test":
            raise PublicAPIError("credit_test_price_invalid", "Test prices cannot be activated in production.", 409)
        price = CreditActionPriceVersion(
            id=uuid.uuid4(),
            action_code=action_code,
            display_name=display_name,
            required_module_code=required_module_code,
            version=version,
            credit_charge_per_unit=credit_charge_per_unit,
            customer_charge_basis=customer_charge_basis,
            max_units_per_operation=max_units_per_operation,
            customer_revenue_micros_per_unit=customer_revenue_micros_per_unit,
            customer_currency="AUD",
            cost_basis=cost_basis,
            provider_cost_minor_units=provider_cost_minor_units,
            provider_currency=provider_currency.upper(),
            fx_rate_to_aud=fx_rate_to_aud,
            fx_source=fx_source.strip(),
            fx_observed_at=_aware(fx_observed_at),
            other_variable_cost_micros=other_variable_cost_micros,
            expected_variable_cost_micros_per_unit=expected_variable_cost_micros_per_unit,
            maximum_variable_cost_micros_per_unit=maximum_variable_cost_micros_per_unit,
            gross_margin_basis_points=margin.gross_margin_basis_points,
            approved_margin_floor_basis_points=floor,
            owner_approval_reference=approval,
            environment=environment,
            status=status,
            pricing_note=pricing_note.strip(),
            effective_from=_aware(self._clock()) - timedelta(seconds=1),
            created_by_actor=actor,
        )
        self.session.add(price)
        await self.session.commit()
        return price

    async def grant_promotional(
        self,
        organisation_id: UUID,
        *,
        credits: int,
        idempotency_key: str,
        source_reference: str,
        actor_reference: str,
        reason: str,
        expires_at: datetime | None = None,
        trial_only: bool = False,
    ) -> CreditLot:
        actor, resolved_reason = _require_actor_reason(actor_reference, reason)
        self._validate_credits(credits)
        expiry = _aware(expires_at) if expires_at is not None else None
        now = _aware(self._clock())
        if expiry is not None and expiry <= now:
            raise PublicAPIError("credit_grant_expired", "Promotional Credits require a future expiry.", 422)
        if trial_only:
            commercial = await self.session.get(OrganisationCommercialState, organisation_id)
            if commercial is None or commercial.status != "trial":
                raise PublicAPIError("credit_trial_inactive", "Trial Credits require an active trial.", 409)
            if expiry is None:
                expiry = commercial.trial_ends_at
            if expiry is None or commercial.trial_ends_at is None or expiry > _aware(commercial.trial_ends_at):
                raise PublicAPIError(
                    "credit_trial_expiry_invalid", "Trial Credits cannot outlive the active trial.", 422
                )
        fingerprint = _fingerprint(
            {
                "credits": credits,
                "source_reference": source_reference,
                "expires_at": expiry,
                "trial_only": trial_only,
            }
        )
        ledger_key = _event_key("promotional-grant", idempotency_key, source_reference)
        existing = await self.repository.ledger_by_key(organisation_id, ledger_key)
        if existing is not None:
            self._require_fingerprint(existing.request_fingerprint, fingerprint)
            lot = await self.repository.lot(organisation_id, existing.lot_id)
            assert lot is not None
            return lot
        balance = await self._locked_balance(organisation_id)
        existing = await self.repository.ledger_by_key(organisation_id, ledger_key)
        if existing is not None:
            self._require_fingerprint(existing.request_fingerprint, fingerprint)
            lot = await self.repository.lot(organisation_id, existing.lot_id)
            assert lot is not None
            return lot
        lot = CreditLot(
            id=uuid.uuid4(),
            organisation_id=organisation_id,
            credit_type="promotional",
            source_reference=source_reference,
            original_credits=credits,
            available_credits=credits,
            original_revenue_micros=0,
            remaining_revenue_micros=0,
            expires_at=expiry,
            grant_actor_reference=actor,
            grant_reason=resolved_reason,
        )
        self.session.add(lot)
        await self.session.flush()
        self.session.add(
            self._ledger_entry(
                organisation_id,
                event_type="promotional_grant",
                credit_type="promotional",
                lot=lot,
                promotional_delta=credits,
                idempotency_key=ledger_key,
                fingerprint=fingerprint,
                actor=actor,
                reason=resolved_reason,
            )
        )
        balance.promotional_available += credits
        balance.lock_version += 1
        await self._commit(organisation_id)
        return lot

    async def grant_verified_purchase(
        self,
        organisation_id: UUID,
        *,
        billing_operation_id: UUID,
        provider_event_id: str,
        commit: bool = True,
    ) -> CreditLot:
        operation = await self.session.scalar(
            select(BillingOperation)
            .where(
                BillingOperation.organisation_id == organisation_id,
                BillingOperation.id == billing_operation_id,
            )
            .with_for_update()
        )
        if (
            operation is None
            or operation.operation_type != "credit_purchase"
            or operation.status != "succeeded"
            or operation.credit_pack_version_id is None
            or operation.amount is None
            or operation.currency != "AUD"
        ):
            raise PublicAPIError(
                "credit_purchase_unverified",
                "Credits can be granted only after verified payment confirmation.",
                409,
            )
        pack = await self.session.get(CreditPackVersion, operation.credit_pack_version_id)
        if pack is None or pack.status != "test_active" or pack.environment != "test":
            raise PublicAPIError("credit_pack_mismatch", "The paid Credit pack could not be verified.", 409)
        paid_minor = int(operation.amount * 100)
        if paid_minor != pack.price_minor_units:
            raise PublicAPIError("credit_purchase_amount_mismatch", "The paid Credit-pack amount did not match.", 409)
        fingerprint = _fingerprint(
            {
                "billing_operation_id": billing_operation_id,
                "pack_version_id": pack.id,
                "amount_minor": paid_minor,
                "currency": operation.currency,
            }
        )
        ledger_key = _event_key("purchase", provider_event_id, billing_operation_id)
        existing = await self.repository.ledger_by_key(organisation_id, ledger_key)
        if existing is not None:
            self._require_fingerprint(existing.request_fingerprint, fingerprint)
            lot = await self.repository.lot(organisation_id, existing.lot_id)
            assert lot is not None
            return lot
        balance = await self._locked_balance(organisation_id)
        revenue_micros = paid_minor * 10_000
        lot = CreditLot(
            id=uuid.uuid4(),
            organisation_id=organisation_id,
            credit_type="purchased",
            source_reference=f"billing:{billing_operation_id}",
            original_credits=pack.credit_quantity,
            available_credits=pack.credit_quantity,
            original_revenue_micros=revenue_micros,
            remaining_revenue_micros=revenue_micros,
            expires_at=None,
            pack_version_id=pack.id,
            billing_operation_id=billing_operation_id,
            grant_actor_reference="verified-billing-event",
            grant_reason="Verified test-mode Credit-pack payment.",
        )
        self.session.add(lot)
        await self.session.flush()
        self.session.add(
            self._ledger_entry(
                organisation_id,
                event_type="purchase",
                credit_type="purchased",
                lot=lot,
                purchased_delta=pack.credit_quantity,
                idempotency_key=ledger_key,
                fingerprint=fingerprint,
                actor="verified-billing-event",
                reason="Verified test-mode Credit-pack payment.",
                customer_revenue_micros=revenue_micros,
            )
        )
        balance.purchased_available += pack.credit_quantity
        balance.lock_version += 1
        if commit:
            await self._commit(organisation_id)
        else:
            await self.session.flush()
        return lot

    async def create_quote(
        self,
        organisation_id: UUID,
        user_id: UUID,
        *,
        action_code: str,
        quantity: int,
    ) -> CreditQuoteResponse:
        self._require_feature_enabled()
        await self.ensure_test_catalogue()
        price = await self.repository.active_price(action_code, self.catalogue_environment)
        if price is None:
            raise PublicAPIError("credit_action_price_unavailable", "That metered action is not available.", 409)
        if quantity <= 0 or quantity > price.max_units_per_operation:
            raise PublicAPIError(
                "credit_quantity_out_of_range",
                f"Choose between 1 and {price.max_units_per_operation} units for this action.",
                422,
            )
        await CommercialService(self.session, self.settings).require_module_write(
            organisation_id, cast(ModuleCode, price.required_module_code)
        )
        await self._require_new_execution_enabled(organisation_id, price.action_code)
        balance = await self._locked_balance(organisation_id)
        await self._expire_promotional_lots(organisation_id, balance)
        required = self._checked_multiply(price.credit_charge_per_unit, quantity)
        maximum_cost = self._checked_multiply(price.maximum_variable_cost_micros_per_unit, quantity)
        now = _aware(self._clock())
        quote = CreditQuote(
            id=uuid.uuid4(),
            organisation_id=organisation_id,
            created_by_user_id=user_id,
            action_price_version_id=price.id,
            action_code=price.action_code,
            quantity=quantity,
            required_credits=required,
            maximum_provider_cost_micros=maximum_cost,
            quote_fingerprint=_fingerprint(
                {"price_id": price.id, "action_code": price.action_code, "quantity": quantity, "credits": required}
            ),
            status="open",
            expires_at=now + timedelta(seconds=self.settings.credits_quote_ttl_seconds),
        )
        self.session.add(quote)
        await self._commit(organisation_id)
        available = balance.purchased_available + balance.promotional_available
        return CreditQuoteResponse(
            quote_id=quote.id,
            action_price_version_id=price.id,
            action_code=price.action_code,
            action_name=price.display_name,
            quantity=quantity,
            credit_cost_per_unit=price.credit_charge_per_unit,
            maximum_credit_cost=required,
            current_balance=available,
            sufficient_balance=available >= required,
            expires_at=quote.expires_at,
            pricing_notice=price.pricing_note,
        )

    async def reserve(
        self,
        organisation_id: UUID,
        user_id: UUID,
        *,
        quote_id: UUID,
        idempotency_key: str,
    ) -> CreditOperationResponse:
        self._require_feature_enabled()
        fingerprint = _fingerprint({"quote_id": quote_id, "user_id": user_id})
        existing = await self.repository.operation_by_key(organisation_id, idempotency_key, lock=True)
        if existing is not None:
            self._require_fingerprint(existing.request_fingerprint, fingerprint)
            return self._operation_response(existing)
        balance = await self._locked_balance(organisation_id)
        existing = await self.repository.operation_by_key(organisation_id, idempotency_key, lock=True)
        if existing is not None:
            self._require_fingerprint(existing.request_fingerprint, fingerprint)
            return self._operation_response(existing)
        await self._expire_promotional_lots(organisation_id, balance)
        quote = await self.repository.quote(organisation_id, quote_id, lock=True)
        if quote is None:
            raise PublicAPIError("credit_quote_not_found", "That Credit quote is unavailable.", 404)
        now = _aware(self._clock())
        if _aware(quote.expires_at) <= now:
            quote.status = "expired"
            await self._commit(organisation_id)
            raise PublicAPIError(
                "credit_quote_expired", "That Credit quote expired. Refresh the cost before continuing.", 409
            )
        if quote.status != "open":
            raise PublicAPIError("credit_quote_already_used", "That Credit quote was already used.", 409)
        price = await self.repository.price(quote.action_price_version_id)
        if price is None or price.action_code != quote.action_code:
            raise PublicAPIError("credit_quote_invalid", "That Credit quote cannot be verified.", 409)
        expected_fingerprint = _fingerprint(
            {
                "price_id": price.id,
                "action_code": price.action_code,
                "quantity": quote.quantity,
                "credits": quote.required_credits,
            }
        )
        self._require_fingerprint(quote.quote_fingerprint, expected_fingerprint, code="credit_quote_tampered")
        await CommercialService(self.session, self.settings).require_module_write(
            organisation_id, cast(ModuleCode, price.required_module_code)
        )
        policy = await self._require_new_execution_enabled(organisation_id, quote.action_code)
        await self._enforce_exposure_limits(organisation_id, policy, quote)
        available = balance.purchased_available + balance.promotional_available
        if available < quote.required_credits:
            raise PublicAPIError(
                "insufficient_credits",
                f"You need {quote.required_credits} Credits. Your balance is {available}.",
                409,
            )
        operation = CreditOperation(
            id=uuid.uuid4(),
            organisation_id=organisation_id,
            requested_by_user_id=user_id,
            quote_id=quote.id,
            action_price_version_id=price.id,
            action_code=quote.action_code,
            quantity=quote.quantity,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            status="reserved",
            outcome="pending",
            reserved_credits=quote.required_credits,
        )
        self.session.add(operation)
        await self.session.flush()
        remaining = quote.required_credits
        lots = await self.repository.lots_for_consumption(organisation_id, lock=True)
        for index, lot in enumerate(lots):
            if remaining == 0:
                break
            amount = min(lot.available_credits, remaining)
            if amount <= 0:
                continue
            lot.available_credits -= amount
            lot.reserved_credits += amount
            if lot.credit_type == "promotional":
                balance.promotional_available -= amount
                balance.promotional_reserved += amount
            else:
                balance.purchased_available -= amount
                balance.purchased_reserved += amount
            allocation = CreditReservationAllocation(
                id=uuid.uuid4(),
                organisation_id=organisation_id,
                operation_id=operation.id,
                lot_id=lot.id,
                allocation_order=index + 1,
                reserved_credits=amount,
            )
            self.session.add(allocation)
            self.session.add(
                self._ledger_entry(
                    organisation_id,
                    event_type="reservation",
                    credit_type=cast(Literal["purchased", "promotional"], lot.credit_type),
                    lot=lot,
                    operation=operation,
                    purchased_delta=-amount if lot.credit_type == "purchased" else 0,
                    promotional_delta=-amount if lot.credit_type == "promotional" else 0,
                    reserved_delta=amount,
                    idempotency_key=_event_key("reservation", idempotency_key, index),
                    fingerprint=fingerprint,
                    actor=str(user_id),
                    reason="Server-authorised reservation before metered provider execution.",
                    action_code=operation.action_code,
                    quantity=operation.quantity,
                )
            )
            remaining -= amount
        if remaining != 0:
            raise PublicAPIError("credit_balance_inconsistent", "Credit balance requires reconciliation.", 409)
        quote.status = "reserved"
        balance.lock_version += 1
        await self._commit(organisation_id)
        return self._operation_response(operation)

    async def mark_executing(
        self,
        organisation_id: UUID,
        operation_id: UUID,
        *,
        provider_request_id: str,
        provider_capability: str,
    ) -> CreditOperationResponse:
        operation = await self._required_operation(organisation_id, operation_id, lock=True)
        if operation.status == "executing":
            if operation.provider_request_id != provider_request_id:
                raise PublicAPIError("credit_provider_request_conflict", "The provider request reference changed.", 409)
            return self._operation_response(operation)
        if operation.status != "reserved":
            raise PublicAPIError(
                "credit_operation_state_invalid", "Provider execution cannot start in this state.", 409
            )
        await self._require_controls_enabled(operation.action_code, provider_capability=provider_capability)
        if not provider_request_id.strip() or len(provider_request_id) > 255:
            raise PublicAPIError(
                "credit_provider_request_invalid", "A valid provider request reference is required.", 422
            )
        operation.status = "executing"
        operation.provider_request_id = provider_request_id
        operation.execution_started_at = _aware(self._clock())
        await self._commit(organisation_id)
        return self._operation_response(operation)

    async def mark_unknown(self, organisation_id: UUID, operation_id: UUID) -> CreditOperationResponse:
        operation = await self._required_operation(organisation_id, operation_id, lock=True)
        if operation.status == "unknown":
            return self._operation_response(operation)
        if operation.status != "executing":
            raise PublicAPIError(
                "credit_operation_state_invalid", "Only in-flight work can have an unknown outcome.", 409
            )
        operation.status = "unknown"
        operation.outcome = "unknown"
        operation.outcome_recorded_at = _aware(self._clock())
        await self._commit(organisation_id)
        return self._operation_response(operation)

    async def settle(
        self,
        organisation_id: UUID,
        operation_id: UUID,
        *,
        successful_units: int,
        provider_cost_micros: int,
        provider_cost_currency: str,
        idempotency_key: str,
        reconciled: bool = False,
    ) -> CreditOperationResponse:
        operation = await self._required_operation(organisation_id, operation_id, lock=True)
        price = await self.repository.price(operation.action_price_version_id)
        if price is None:
            raise PublicAPIError("credit_action_price_unavailable", "The historical action price is unavailable.", 409)
        if successful_units < 0 or successful_units > operation.quantity:
            raise PublicAPIError(
                "credit_settlement_invalid", "Successful units are outside the reserved operation.", 422
            )
        if provider_cost_micros < 0 or provider_cost_micros > MAX_CREDITS * 1_000_000:
            raise PublicAPIError("credit_provider_cost_invalid", "Provider cost must be non-negative and bounded.", 422)
        if len(provider_cost_currency) != 3 or not provider_cost_currency.isalpha():
            raise PublicAPIError(
                "credit_provider_cost_invalid", "Provider cost currency must be a three-letter code.", 422
            )
        charge_units = successful_units if price.customer_charge_basis == "successful_unit" else operation.quantity
        charge = self._checked_multiply(price.credit_charge_per_unit, charge_units) if charge_units else 0
        if charge > operation.reserved_credits:
            raise PublicAPIError(
                "credit_settlement_exceeds_reservation",
                "The approved reservation cannot cover that settlement. No surprise charge was made.",
                409,
            )
        fingerprint = _fingerprint(
            {
                "operation_id": operation_id,
                "successful_units": successful_units,
                "provider_cost_micros": provider_cost_micros,
                "provider_cost_currency": provider_cost_currency.upper(),
                "reconciled": reconciled,
            }
        )
        existing_key = _event_key("settlement", idempotency_key, operation_id)
        existing = await self.repository.ledger_by_key(organisation_id, existing_key)
        if existing is not None:
            self._require_fingerprint(existing.request_fingerprint, fingerprint)
            return self._operation_response(operation)
        if operation.status == "unknown" and not reconciled:
            raise PublicAPIError(
                "credit_reconciliation_required",
                "The provider outcome is unknown. Keep the reservation until reconciliation completes.",
                409,
            )
        if operation.status not in {"reserved", "executing", "unknown"}:
            raise PublicAPIError("credit_operation_state_invalid", "That operation can no longer be settled.", 409)
        balance = await self._locked_balance(organisation_id)
        allocations = await self.repository.allocations(organisation_id, operation_id, lock=True)
        remaining_to_consume = charge
        revenue_total = 0
        consumption_index = 0
        provider_cost_recorded = False
        for allocation in allocations:
            lot = await self.repository.lot(organisation_id, allocation.lot_id, lock=True)
            if lot is None:
                raise PublicAPIError("credit_balance_inconsistent", "Credit balance requires reconciliation.", 409)
            unprocessed = allocation.reserved_credits - allocation.consumed_credits - allocation.released_credits
            consumed = min(unprocessed, remaining_to_consume)
            if consumed > 0:
                revenue = self._consume_lot_revenue(lot, consumed)
                revenue_total += revenue
                allocation.consumed_credits += consumed
                lot.reserved_credits -= consumed
                lot.consumed_credits += consumed
                if lot.credit_type == "promotional":
                    balance.promotional_reserved -= consumed
                else:
                    balance.purchased_reserved -= consumed
                entry_key = (
                    existing_key
                    if consumption_index == 0
                    else _event_key("settlement-allocation", idempotency_key, consumption_index)
                )
                entry_provider_cost = provider_cost_micros if not provider_cost_recorded else 0
                provider_cost_recorded = True
                self.session.add(
                    self._ledger_entry(
                        organisation_id,
                        event_type="consumption",
                        credit_type=cast(Literal["purchased", "promotional"], lot.credit_type),
                        lot=lot,
                        operation=operation,
                        reserved_delta=-consumed,
                        idempotency_key=entry_key,
                        fingerprint=fingerprint,
                        actor="metered-operation-settlement",
                        reason="Settled successful units against the approved reservation.",
                        action_code=operation.action_code,
                        quantity=successful_units,
                        customer_revenue_micros=revenue,
                        provider_cost_micros=entry_provider_cost,
                    )
                )
                remaining_to_consume -= consumed
                consumption_index += 1
            released = unprocessed - consumed
            if released > 0:
                allocation.released_credits += released
                lot.reserved_credits -= released
                lot.available_credits += released
                if lot.credit_type == "promotional":
                    balance.promotional_reserved -= released
                    balance.promotional_available += released
                else:
                    balance.purchased_reserved -= released
                    balance.purchased_available += released
                self.session.add(
                    self._ledger_entry(
                        organisation_id,
                        event_type="release",
                        credit_type=cast(Literal["purchased", "promotional"], lot.credit_type),
                        lot=lot,
                        operation=operation,
                        purchased_delta=released if lot.credit_type == "purchased" else 0,
                        promotional_delta=released if lot.credit_type == "promotional" else 0,
                        reserved_delta=-released,
                        idempotency_key=_event_key("settlement-release", idempotency_key, allocation.id),
                        fingerprint=fingerprint,
                        actor="metered-operation-settlement",
                        reason="Released the unused remainder of the approved reservation.",
                        action_code=operation.action_code,
                        quantity=operation.quantity - successful_units,
                    )
                )
        if remaining_to_consume:
            raise PublicAPIError("credit_balance_inconsistent", "Credit balance requires reconciliation.", 409)
        if charge == 0:
            # A release entry is the stable settlement marker for zero-success operations.
            marker = next(
                (
                    item
                    for item in self.session.new
                    if isinstance(item, CreditLedgerEntry) and item.operation_id == operation.id
                ),
                None,
            )
            if marker is None:
                raise PublicAPIError("credit_balance_inconsistent", "Credit balance requires reconciliation.", 409)
            marker.idempotency_key = existing_key
            marker.provider_cost_micros = provider_cost_micros
        operation.settled_credits = charge
        operation.released_credits = operation.reserved_credits - charge
        operation.successful_units = successful_units
        operation.customer_revenue_micros = revenue_total
        operation.provider_cost_micros = provider_cost_micros
        operation.provider_cost_currency = provider_cost_currency.upper()
        operation.status = "settled"
        operation.outcome = (
            "reconciled_success" if reconciled else "success" if successful_units == operation.quantity else "partial"
        )
        operation.outcome_recorded_at = _aware(self._clock())
        operation.completed_at = _aware(self._clock())
        balance.lock_version += 1
        await self._commit(organisation_id)
        return self._operation_response(operation)

    async def release(
        self,
        organisation_id: UUID,
        operation_id: UUID,
        *,
        idempotency_key: str,
        reason: str,
        reconciled: bool = False,
    ) -> CreditOperationResponse:
        operation = await self._required_operation(organisation_id, operation_id, lock=True)
        fingerprint = _fingerprint({"operation_id": operation_id, "reason": reason.strip(), "reconciled": reconciled})
        marker_key = _event_key("release", idempotency_key, operation_id)
        existing = await self.repository.ledger_by_key(organisation_id, marker_key)
        if existing is not None:
            self._require_fingerprint(existing.request_fingerprint, fingerprint)
            return self._operation_response(operation)
        if operation.status == "unknown" and not reconciled:
            raise PublicAPIError(
                "credit_reconciliation_required",
                "The provider outcome is unknown. Keep the reservation until reconciliation completes.",
                409,
            )
        if operation.status not in {"reserved", "executing", "unknown"}:
            raise PublicAPIError("credit_operation_state_invalid", "That reservation can no longer be released.", 409)
        if len(reason.strip()) < 8 or len(reason) > 500:
            raise PublicAPIError("credit_reason_invalid", "A meaningful release reason is required.", 422)
        balance = await self._locked_balance(organisation_id)
        allocations = await self.repository.allocations(organisation_id, operation_id, lock=True)
        for index, allocation in enumerate(allocations):
            amount = allocation.reserved_credits - allocation.consumed_credits - allocation.released_credits
            if amount <= 0:
                continue
            lot = await self.repository.lot(organisation_id, allocation.lot_id, lock=True)
            if lot is None:
                raise PublicAPIError("credit_balance_inconsistent", "Credit balance requires reconciliation.", 409)
            allocation.released_credits += amount
            lot.reserved_credits -= amount
            lot.available_credits += amount
            if lot.credit_type == "promotional":
                balance.promotional_reserved -= amount
                balance.promotional_available += amount
            else:
                balance.purchased_reserved -= amount
                balance.purchased_available += amount
            self.session.add(
                self._ledger_entry(
                    organisation_id,
                    event_type="release",
                    credit_type=cast(Literal["purchased", "promotional"], lot.credit_type),
                    lot=lot,
                    operation=operation,
                    purchased_delta=amount if lot.credit_type == "purchased" else 0,
                    promotional_delta=amount if lot.credit_type == "promotional" else 0,
                    reserved_delta=-amount,
                    idempotency_key=marker_key
                    if index == 0
                    else _event_key("release-allocation", idempotency_key, index),
                    fingerprint=fingerprint,
                    actor="metered-operation-release",
                    reason=reason.strip(),
                    action_code=operation.action_code,
                    quantity=operation.quantity,
                )
            )
        operation.released_credits = operation.reserved_credits - operation.settled_credits
        operation.status = "released"
        operation.outcome = "reconciled_failure" if reconciled else "failure"
        operation.outcome_recorded_at = _aware(self._clock())
        operation.completed_at = _aware(self._clock())
        balance.lock_version += 1
        await self._commit(organisation_id)
        return self._operation_response(operation)

    async def reconcile_unknown(
        self,
        organisation_id: UUID,
        operation_id: UUID,
        *,
        provider_definitely_executed: bool,
        successful_units: int = 0,
        provider_cost_micros: int = 0,
        provider_cost_currency: str = "AUD",
        idempotency_key: str,
    ) -> CreditOperationResponse:
        operation = await self._required_operation(organisation_id, operation_id, lock=True)
        if operation.status not in {"unknown", "settled", "released"}:
            raise PublicAPIError(
                "credit_reconciliation_invalid", "Only an unknown provider outcome can reconcile.", 409
            )
        if operation.status in {"settled", "released"}:
            return self._operation_response(operation)
        if provider_definitely_executed:
            return await self.settle(
                organisation_id,
                operation_id,
                successful_units=successful_units,
                provider_cost_micros=provider_cost_micros,
                provider_cost_currency=provider_cost_currency,
                idempotency_key=idempotency_key,
                reconciled=True,
            )
        return await self.release(
            organisation_id,
            operation_id,
            idempotency_key=idempotency_key,
            reason="Provider reconciliation confirmed that no billable execution occurred.",
            reconciled=True,
        )

    async def refund_consumption(
        self,
        organisation_id: UUID,
        *,
        consumption_entry_id: UUID,
        credits: int,
        idempotency_key: str,
        actor_reference: str,
        reason: str,
    ) -> CreditLot:
        actor, resolved_reason = _require_actor_reason(actor_reference, reason)
        self._validate_credits(credits)
        original = await self.repository.ledger_entry(organisation_id, consumption_entry_id)
        if original is None or original.event_type != "consumption":
            raise PublicAPIError("credit_refund_reference_invalid", "Refunds must reference a consumption event.", 409)
        fingerprint = _fingerprint({"entry_id": consumption_entry_id, "credits": credits})
        ledger_key = _event_key("refund", idempotency_key, consumption_entry_id)
        existing = await self.repository.ledger_by_key(organisation_id, ledger_key)
        if existing is not None:
            self._require_fingerprint(existing.request_fingerprint, fingerprint)
            lot = await self.repository.lot(organisation_id, existing.lot_id)
            assert lot is not None
            return lot
        already_refunded = int(
            await self.session.scalar(
                select(func.coalesce(func.sum(CreditLedgerEntry.purchased_available_delta), 0)).where(
                    CreditLedgerEntry.organisation_id == organisation_id,
                    CreditLedgerEntry.event_type == "refund",
                    CreditLedgerEntry.referenced_entry_id == consumption_entry_id,
                    CreditLedgerEntry.credit_type == "purchased",
                )
            )
            or 0
        ) + int(
            await self.session.scalar(
                select(func.coalesce(func.sum(CreditLedgerEntry.promotional_available_delta), 0)).where(
                    CreditLedgerEntry.organisation_id == organisation_id,
                    CreditLedgerEntry.event_type == "refund",
                    CreditLedgerEntry.referenced_entry_id == consumption_entry_id,
                    CreditLedgerEntry.credit_type == "promotional",
                )
            )
            or 0
        )
        consumed = -original.reserved_delta
        if credits > consumed - already_refunded:
            raise PublicAPIError(
                "credit_refund_exceeds_consumption", "Refund cannot exceed the original consumption.", 409
            )
        source_lot = await self.repository.lot(organisation_id, original.lot_id)
        if source_lot is None:
            raise PublicAPIError("credit_refund_reference_invalid", "The original Credit lot is unavailable.", 409)
        revenue = (original.customer_revenue_micros * credits) // consumed if consumed else 0
        balance = await self._locked_balance(organisation_id)
        lot = CreditLot(
            id=uuid.uuid4(),
            organisation_id=organisation_id,
            credit_type=original.credit_type,
            source_reference=f"refund:{ledger_key}",
            original_credits=credits,
            available_credits=credits,
            original_revenue_micros=revenue,
            remaining_revenue_micros=revenue,
            expires_at=None,
            pack_version_id=source_lot.pack_version_id,
            grant_actor_reference=actor,
            grant_reason=resolved_reason,
        )
        self.session.add(lot)
        await self.session.flush()
        purchased_delta = credits if original.credit_type == "purchased" else 0
        promotional_delta = credits if original.credit_type == "promotional" else 0
        self.session.add(
            self._ledger_entry(
                organisation_id,
                event_type="refund",
                credit_type=cast(Literal["purchased", "promotional"], original.credit_type),
                lot=lot,
                purchased_delta=purchased_delta,
                promotional_delta=promotional_delta,
                referenced_entry_id=original.id,
                idempotency_key=ledger_key,
                fingerprint=fingerprint,
                actor=actor,
                reason=resolved_reason,
                customer_revenue_micros=revenue,
            )
        )
        balance.purchased_available += purchased_delta
        balance.promotional_available += promotional_delta
        balance.lock_version += 1
        await self._commit(organisation_id)
        return lot

    async def correct_balance(
        self,
        organisation_id: UUID,
        *,
        credits: int,
        direction: Literal["increase", "decrease"],
        credit_type: Literal["purchased", "promotional"],
        reference: str,
        idempotency_key: str,
        actor_reference: str,
        reason: str,
    ) -> CreditBalanceResponse:
        actor, resolved_reason = _require_actor_reason(actor_reference, reason)
        self._validate_credits(credits)
        if not reference.strip() or len(reference) > 200:
            raise PublicAPIError("credit_correction_reference_invalid", "A correction reference is required.", 422)
        fingerprint = _fingerprint(
            {"credits": credits, "direction": direction, "credit_type": credit_type, "reference": reference}
        )
        marker_key = _event_key("correction", idempotency_key, reference)
        existing = await self.repository.ledger_by_key(organisation_id, marker_key)
        if existing is not None:
            self._require_fingerprint(existing.request_fingerprint, fingerprint)
            return self._balance_response(await self.repository.balance(organisation_id))
        balance = await self._locked_balance(organisation_id)
        existing = await self.repository.ledger_by_key(organisation_id, marker_key)
        if existing is not None:
            self._require_fingerprint(existing.request_fingerprint, fingerprint)
            return self._balance_response(balance)
        if direction == "increase":
            revenue = 0
            lot = CreditLot(
                id=uuid.uuid4(),
                organisation_id=organisation_id,
                credit_type=credit_type,
                source_reference=f"correction:{reference}:{idempotency_key}",
                original_credits=credits,
                available_credits=credits,
                original_revenue_micros=revenue,
                remaining_revenue_micros=revenue,
                grant_actor_reference=actor,
                grant_reason=resolved_reason,
            )
            self.session.add(lot)
            await self.session.flush()
            self.session.add(
                self._ledger_entry(
                    organisation_id,
                    event_type="correction",
                    credit_type=credit_type,
                    lot=lot,
                    purchased_delta=credits if credit_type == "purchased" else 0,
                    promotional_delta=credits if credit_type == "promotional" else 0,
                    idempotency_key=marker_key,
                    fingerprint=fingerprint,
                    actor=actor,
                    reason=resolved_reason,
                )
            )
            if credit_type == "purchased":
                balance.purchased_available += credits
            else:
                balance.promotional_available += credits
        else:
            available = balance.purchased_available if credit_type == "purchased" else balance.promotional_available
            if available < credits:
                raise PublicAPIError(
                    "insufficient_credits", "A correction cannot make the Credit balance negative.", 409
                )
            remaining = credits
            lots = [
                lot
                for lot in await self.repository.lots_for_consumption(organisation_id, lock=True)
                if lot.credit_type == credit_type
            ]
            for index, lot in enumerate(lots):
                amount = min(remaining, lot.available_credits)
                if not amount:
                    continue
                self._consume_lot_revenue(lot, amount)
                lot.available_credits -= amount
                lot.consumed_credits += amount
                self.session.add(
                    self._ledger_entry(
                        organisation_id,
                        event_type="correction",
                        credit_type=credit_type,
                        lot=lot,
                        purchased_delta=-amount if credit_type == "purchased" else 0,
                        promotional_delta=-amount if credit_type == "promotional" else 0,
                        idempotency_key=marker_key
                        if index == 0
                        else _event_key("correction-allocation", idempotency_key, index),
                        fingerprint=fingerprint,
                        actor=actor,
                        reason=resolved_reason,
                    )
                )
                remaining -= amount
                if remaining == 0:
                    break
            if remaining:
                raise PublicAPIError("credit_balance_inconsistent", "Credit balance requires reconciliation.", 409)
            if credit_type == "purchased":
                balance.purchased_available -= credits
            else:
                balance.promotional_available -= credits
        balance.lock_version += 1
        await self._commit(organisation_id)
        return self._balance_response(balance)

    async def reconcile_balance(self, organisation_id: UUID) -> CreditReconciliationResponse:
        balance = await self.repository.balance(organisation_id)
        purchased, promotional, reserved = await self.repository.ledger_totals(organisation_id)
        lot_available, lot_reserved = await self.repository.lot_totals(organisation_id)
        projection = self._balance_response(balance)
        return CreditReconciliationResponse(
            consistent=(
                projection.purchased_available == purchased
                and projection.promotional_available == promotional
                and projection.reserved == reserved
                and projection.available == lot_available
                and projection.reserved == lot_reserved
            ),
            projection_purchased_available=projection.purchased_available,
            ledger_purchased_available=purchased,
            projection_promotional_available=projection.promotional_available,
            ledger_promotional_available=promotional,
            projection_reserved=projection.reserved,
            ledger_reserved=reserved,
            lot_available=lot_available,
            lot_reserved=lot_reserved,
        )

    @staticmethod
    def validate_margin(
        customer_revenue_micros: int,
        maximum_variable_cost_micros: int,
        required_margin_basis_points: int | None,
    ) -> MarginValidationResponse:
        if customer_revenue_micros <= 0 or maximum_variable_cost_micros < 0:
            raise PublicAPIError("credit_margin_input_invalid", "Margin inputs must use positive exact revenue.", 422)
        profit = customer_revenue_micros - maximum_variable_cost_micros
        margin = (profit * 10_000) // customer_revenue_micros
        positive = profit > 0
        meets = required_margin_basis_points is not None and margin >= required_margin_basis_points
        return MarginValidationResponse(
            customer_revenue_micros=customer_revenue_micros,
            maximum_variable_cost_micros=maximum_variable_cost_micros,
            gross_profit_micros=profit,
            gross_margin_basis_points=margin,
            required_margin_basis_points=required_margin_basis_points,
            positive_margin=positive,
            meets_required_margin=meets,
            production_eligible=positive and meets and required_margin_basis_points is not None,
        )

    async def _require_new_execution_enabled(self, organisation_id: UUID, action_code: str) -> CreditOrganisationPolicy:
        await self._require_controls_enabled(action_code)
        policy = await self.repository.policy(organisation_id, lock=True)
        if policy is None or not policy.metered_actions_enabled:
            raise PublicAPIError(
                "credit_exposure_policy_unavailable",
                "Metered execution is disabled until bounded organisation exposure controls are configured.",
                409,
            )
        return policy

    async def _require_controls_enabled(self, action_code: str, *, provider_capability: str | None = None) -> None:
        global_control = await self.repository.control("global", "metered_actions")
        action_control = await self.repository.control("action", action_code)
        if global_control is None or not global_control.enabled or action_control is None or not action_control.enabled:
            raise PublicAPIError("credit_action_disabled", "That metered action is temporarily disabled.", 409)
        if provider_capability is not None:
            provider_control = await self.repository.control("provider_capability", provider_capability)
            if provider_control is None or not provider_control.enabled:
                raise PublicAPIError(
                    "credit_provider_capability_disabled",
                    "That metered provider capability is temporarily disabled.",
                    409,
                )

    async def _enforce_exposure_limits(
        self, organisation_id: UUID, policy: CreditOrganisationPolicy, quote: CreditQuote
    ) -> None:
        now = _aware(self._clock())
        day_start = datetime(now.year, now.month, now.day, tzinfo=UTC)
        if quote.required_credits > policy.max_credits_per_operation:
            raise PublicAPIError(
                "credit_operation_cap_exceeded", "This operation exceeds the organisation safety cap.", 409
            )
        consumed = await self.repository.consumed_since(organisation_id, day_start)
        if consumed + quote.required_credits > policy.max_credits_per_day:
            raise PublicAPIError(
                "credit_daily_cap_exceeded", "The organisation daily Credit safety cap is reached.", 409
            )
        provider_cost = await self.repository.provider_cost_since(organisation_id, day_start)
        if provider_cost + quote.maximum_provider_cost_micros > policy.max_provider_cost_micros_per_day:
            raise PublicAPIError(
                "credit_provider_cost_cap_exceeded", "The organisation daily provider-cost safety cap is reached.", 409
            )
        commercial = await self.session.get(OrganisationCommercialState, organisation_id)
        if commercial is not None and commercial.status == "trial":
            if policy.trial_max_credits_per_day is None:
                raise PublicAPIError("credit_trial_cap_unavailable", "Trial metered execution is disabled.", 409)
            if consumed + quote.required_credits > policy.trial_max_credits_per_day:
                raise PublicAPIError("credit_trial_cap_exceeded", "The trial Credit safety cap is reached.", 409)
        minute_start = now - timedelta(minutes=1)
        if await self.repository.reservations_since(organisation_id, minute_start) >= policy.max_operations_per_minute:
            raise PublicAPIError("credit_rate_limit_exceeded", "Metered actions are temporarily rate limited.", 429)

    async def _expire_promotional_lots(self, organisation_id: UUID, balance: OrganisationCreditBalance) -> None:
        now = _aware(self._clock())
        for lot in await self.repository.expired_lots(organisation_id, now, lock=True):
            amount = lot.available_credits
            fingerprint = _fingerprint({"lot_id": lot.id, "expires_at": lot.expires_at, "credits": amount})
            key = _event_key("expiry", str(lot.id), lot.expires_at)
            if await self.repository.ledger_by_key(organisation_id, key) is not None:
                continue
            lot.available_credits = 0
            balance.promotional_available -= amount
            balance.lock_version += 1
            self.session.add(
                self._ledger_entry(
                    organisation_id,
                    event_type="expiry",
                    credit_type="promotional",
                    lot=lot,
                    promotional_delta=-amount,
                    idempotency_key=key,
                    fingerprint=fingerprint,
                    actor="credit-expiry-policy",
                    reason="Explicitly dated promotional Credits expired.",
                )
            )

    async def _locked_balance(self, organisation_id: UUID) -> OrganisationCreditBalance:
        balance = await self.repository.balance(organisation_id, lock=True)
        if balance is not None:
            return balance
        dialect_name = self.session.bind.dialect.name if self.session.bind is not None else ""
        if dialect_name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as postgresql_insert

            await self.session.execute(
                postgresql_insert(OrganisationCreditBalance)
                .values(organisation_id=organisation_id)
                .on_conflict_do_nothing()
            )
        elif dialect_name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            await self.session.execute(
                sqlite_insert(OrganisationCreditBalance)
                .values(organisation_id=organisation_id)
                .on_conflict_do_nothing()
            )
        else:
            await self.session.execute(insert(OrganisationCreditBalance).values(organisation_id=organisation_id))
        await self.session.flush()
        balance = await self.repository.balance(organisation_id, lock=True)
        if balance is None:
            raise PublicAPIError("credit_balance_unavailable", "Credit balance is temporarily unavailable.", 503)
        return balance

    async def _required_operation(self, organisation_id: UUID, operation_id: UUID, *, lock: bool) -> CreditOperation:
        operation = await self.repository.operation(organisation_id, operation_id, lock=lock)
        if operation is None:
            raise PublicAPIError("credit_operation_not_found", "That Credit operation is unavailable.", 404)
        return operation

    @staticmethod
    def _consume_lot_revenue(lot: CreditLot, credits: int) -> int:
        remaining_credits = lot.available_credits + lot.reserved_credits
        if remaining_credits <= 0 or credits > remaining_credits:
            raise PublicAPIError("credit_balance_inconsistent", "Credit balance requires reconciliation.", 409)
        revenue = (
            lot.remaining_revenue_micros
            if credits == remaining_credits
            else (lot.remaining_revenue_micros * credits) // remaining_credits
        )
        lot.remaining_revenue_micros -= revenue
        return revenue

    @staticmethod
    def _validate_credits(credits: int) -> None:
        if credits <= 0 or credits > MAX_CREDITS:
            raise PublicAPIError("credit_amount_invalid", "Credit amounts must be positive and bounded.", 422)

    @staticmethod
    def _checked_multiply(left: int, right: int) -> int:
        value = left * right
        if value <= 0 or value > MAX_CREDITS:
            raise PublicAPIError("credit_amount_invalid", "Credit amount exceeds the supported range.", 422)
        return value

    def _require_feature_enabled(self) -> None:
        if not self.settings.feature_credits_enabled or self.settings.environment == "production":
            raise PublicAPIError(
                "credit_execution_unavailable",
                "Metered Credit execution is not enabled in this environment.",
                503,
            )

    @staticmethod
    def _require_fingerprint(actual: str, expected: str, *, code: str = "credit_idempotency_conflict") -> None:
        if actual != expected:
            raise PublicAPIError(code, "That retry key or server-owned quote was used for different values.", 409)

    @staticmethod
    def _ledger_entry(
        organisation_id: UUID,
        *,
        event_type: str,
        credit_type: Literal["purchased", "promotional"],
        lot: CreditLot,
        idempotency_key: str,
        fingerprint: str,
        actor: str,
        reason: str,
        purchased_delta: int = 0,
        promotional_delta: int = 0,
        reserved_delta: int = 0,
        operation: CreditOperation | None = None,
        referenced_entry_id: UUID | None = None,
        action_code: str | None = None,
        quantity: int | None = None,
        customer_revenue_micros: int = 0,
        provider_cost_micros: int = 0,
    ) -> CreditLedgerEntry:
        return CreditLedgerEntry(
            id=uuid.uuid4(),
            organisation_id=organisation_id,
            event_type=event_type,
            credit_type=credit_type,
            purchased_available_delta=purchased_delta,
            promotional_available_delta=promotional_delta,
            reserved_delta=reserved_delta,
            lot_id=lot.id,
            operation_id=operation.id if operation is not None else None,
            referenced_entry_id=referenced_entry_id,
            action_code=action_code,
            quantity=quantity,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            actor_reference=actor,
            reason=reason,
            customer_revenue_micros=customer_revenue_micros,
            provider_cost_micros=provider_cost_micros,
        )

    @staticmethod
    def _balance_response(balance: OrganisationCreditBalance | None) -> CreditBalanceResponse:
        if balance is None:
            return CreditBalanceResponse(
                available=0,
                purchased_available=0,
                promotional_available=0,
                reserved=0,
                purchased_reserved=0,
                promotional_reserved=0,
                total_held=0,
            )
        available = balance.purchased_available + balance.promotional_available
        reserved = balance.purchased_reserved + balance.promotional_reserved
        return CreditBalanceResponse(
            available=available,
            purchased_available=balance.purchased_available,
            promotional_available=balance.promotional_available,
            reserved=reserved,
            purchased_reserved=balance.purchased_reserved,
            promotional_reserved=balance.promotional_reserved,
            total_held=available + reserved,
        )

    @staticmethod
    def _activity_response(entry: CreditLedgerEntry) -> CreditActivityResponse:
        return CreditActivityResponse(
            id=entry.id,
            event_type=cast(
                Literal[
                    "purchase",
                    "promotional_grant",
                    "reservation",
                    "consumption",
                    "release",
                    "refund",
                    "correction",
                    "expiry",
                ],
                entry.event_type,
            ),
            credit_type=cast(Literal["purchased", "promotional"], entry.credit_type),
            available_change=entry.purchased_available_delta + entry.promotional_available_delta,
            reserved_change=entry.reserved_delta,
            action_code=entry.action_code,
            operation_id=entry.operation_id,
            reason=entry.reason,
            created_at=entry.created_at,
        )

    @staticmethod
    def _operation_response(operation: CreditOperation) -> CreditOperationResponse:
        return CreditOperationResponse(
            operation_id=operation.id,
            quote_id=operation.quote_id,
            action_price_version_id=operation.action_price_version_id,
            action_code=operation.action_code,
            quantity=operation.quantity,
            reserved_credits=operation.reserved_credits,
            settled_credits=operation.settled_credits,
            released_credits=operation.released_credits,
            successful_units=operation.successful_units,
            status=cast(Literal["reserved", "executing", "unknown", "settled", "released"], operation.status),
            outcome=cast(CreditOperationOutcome, operation.outcome),
            provider_execution_authorised=operation.status in {"reserved", "executing"},
        )

    async def _commit(self, organisation_id: UUID) -> None:
        try:
            await self.session.commit()
            await set_tenant_database_context(self.session, organisation_id)
        except (IntegrityError, SQLAlchemyError) as exc:
            await self.session.rollback()
            raise PublicAPIError(
                "credit_state_conflict",
                "Credit state changed concurrently. Check the balance before retrying.",
                409,
            ) from exc
