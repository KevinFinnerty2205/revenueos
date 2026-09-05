from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.commercial_services import PLAN_CATALOGUE, ensure_plan_catalogue
from revenueos.config import Settings
from revenueos.credit_contracts import CreditOperationResponse
from revenueos.credit_services import TEST_ACTION_CODE, TEST_PACK_ID, CreditService
from revenueos.database import set_tenant_database_context
from revenueos.errors import PublicAPIError
from revenueos.models import (
    BillingOperation,
    CreditLedgerEntry,
    Organisation,
    OrganisationCommercialState,
    OrganisationMembership,
    OrganisationModuleEntitlement,
    User,
)


def test_postgresql_credit_contention_idempotency_and_rls_are_concurrency_safe() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required for Credit concurrency and RLS tests.")

    async def scenario() -> None:
        engine = create_async_engine(database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = Settings(
            environment="test",
            auth_mode="mock",
            mock_auth_enabled=True,
            database_url=database_url,
            feature_credits_enabled=True,
        )
        organisation_id, user_id = uuid.uuid4(), uuid.uuid4()
        try:
            async with factory() as session:
                session.add(
                    Organisation(
                        id=organisation_id,
                        name="Credit contention organisation",
                        slug=f"credit-contention-{organisation_id}",
                    )
                )
                session.add(
                    User(
                        id=user_id,
                        external_auth_id=f"credit-contention-{user_id}",
                        email=f"credit-contention-{user_id}@example.test",
                        display_name="Credit Contention User",
                    )
                )
                await session.flush()
                session.add(OrganisationMembership(organisation_id=organisation_id, user_id=user_id, role="admin"))
                await session.commit()
                await ensure_plan_catalogue(session)
                complete_plan = next(item for item in PLAN_CATALOGUE if item.code == "complete")
                session.add(
                    OrganisationCommercialState(
                        organisation_id=organisation_id,
                        plan_version_id=complete_plan.id,
                        status="active",
                        billing_interval="monthly",
                        add_on_modules_json=[],
                        seat_limit_status="within_limit",
                        effective_at=datetime.now(UTC),
                        source="migration",
                        actor_reference="credit-concurrency-test",
                        reason="Synthetic Credit contention state.",
                    )
                )
                session.add(
                    OrganisationModuleEntitlement(
                        organisation_id=organisation_id,
                        module_key="prospect",
                        enabled=True,
                        access_level="write",
                        source="commercial_plan",
                        configured_by_actor="credit-concurrency-test",
                        enabled_at=datetime.now(UTC),
                    )
                )
                await session.commit()
                await set_tenant_database_context(session, organisation_id)
                service = CreditService(session, settings)
                await service.ensure_test_catalogue()
                await service.set_execution_control(
                    scope="global",
                    key="metered_actions",
                    enabled=True,
                    actor_reference="credit-concurrency-test",
                    reason="Enable deterministic Credit contention testing.",
                )
                await service.set_execution_control(
                    scope="action",
                    key=TEST_ACTION_CODE,
                    enabled=True,
                    actor_reference="credit-concurrency-test",
                    reason="Enable deterministic action contention testing.",
                )
                await set_tenant_database_context(session, organisation_id)
                await service.configure_policy(
                    organisation_id,
                    metered_actions_enabled=True,
                    max_credits_per_operation=100,
                    max_credits_per_day=1_000,
                    max_provider_cost_micros_per_day=100_000_000,
                    trial_max_credits_per_day=100,
                    max_operations_per_minute=100,
                    actor_reference="credit-concurrency-test",
                    reason="Bound deterministic Credit contention exposure.",
                )
                await service.grant_promotional(
                    organisation_id,
                    credits=10,
                    idempotency_key="initial-contention-grant",
                    source_reference=f"initial-contention-{organisation_id}",
                    actor_reference="credit-concurrency-test",
                    reason="Fund simultaneous reservations.",
                )
                quote_a = await service.create_quote(organisation_id, user_id, action_code=TEST_ACTION_CODE, quantity=2)
                quote_b = await service.create_quote(organisation_id, user_id, action_code=TEST_ACTION_CODE, quantity=2)
                billing_operation_id = uuid.uuid4()
                session.add(
                    BillingOperation(
                        id=billing_operation_id,
                        organisation_id=organisation_id,
                        requested_by_user_id=user_id,
                        operation_type="credit_purchase",
                        idempotency_key="concurrent-purchase-operation",
                        request_fingerprint="a" * 64,
                        status="succeeded",
                        credit_pack_version_id=TEST_PACK_ID,
                        amount=Decimal("20.00"),
                        currency="AUD",
                    )
                )
                await session.commit()

            async def reserve(quote_id: uuid.UUID, key: str) -> CreditOperationResponse | PublicAPIError:
                async with factory() as session:
                    await set_tenant_database_context(session, organisation_id)
                    try:
                        return await CreditService(session, settings).reserve(
                            organisation_id, user_id, quote_id=quote_id, idempotency_key=key
                        )
                    except PublicAPIError as exc:
                        return exc

            attempts = await asyncio.gather(
                reserve(quote_a.quote_id, "contention-reservation-a"),
                reserve(quote_b.quote_id, "contention-reservation-b"),
            )
            successes = [item for item in attempts if isinstance(item, CreditOperationResponse)]
            failures = [item for item in attempts if isinstance(item, PublicAPIError)]
            assert len(successes) == 1 and len(failures) == 1
            assert failures[0].code == "insufficient_credits"
            winning = successes[0]

            async def settle() -> CreditOperationResponse:
                async with factory() as session:
                    await set_tenant_database_context(session, organisation_id)
                    return await CreditService(session, settings).settle(
                        organisation_id,
                        winning.operation_id,
                        successful_units=1,
                        provider_cost_micros=300_000,
                        provider_cost_currency="AUD",
                        idempotency_key="duplicate-worker-settlement",
                    )

            settlements = await asyncio.gather(settle(), settle())
            assert settlements[0] == settlements[1]
            assert settlements[0].settled_credits == 5
            assert settlements[0].released_credits == 5

            async def purchase() -> uuid.UUID:
                async with factory() as session:
                    await set_tenant_database_context(session, organisation_id)
                    lot = await CreditService(session, settings).grant_verified_purchase(
                        organisation_id,
                        billing_operation_id=billing_operation_id,
                        provider_event_id="concurrent-verified-purchase-event",
                    )
                    return lot.id

            purchase_lots = await asyncio.gather(purchase(), purchase())
            assert purchase_lots[0] == purchase_lots[1]

            async with factory() as session:
                await set_tenant_database_context(session, organisation_id)
                service = CreditService(session, settings)
                quote = await service.create_quote(organisation_id, user_id, action_code=TEST_ACTION_CODE, quantity=1)
                release_operation = await service.reserve(
                    organisation_id,
                    user_id,
                    quote_id=quote.quote_id,
                    idempotency_key="concurrent-release-reservation",
                )

            async def release() -> CreditOperationResponse:
                async with factory() as session:
                    await set_tenant_database_context(session, organisation_id)
                    return await CreditService(session, settings).release(
                        organisation_id,
                        release_operation.operation_id,
                        idempotency_key="duplicate-worker-release",
                        reason="Provider failed before executing any billable work.",
                    )

            releases = await asyncio.gather(release(), release())
            assert releases[0] == releases[1]
            assert releases[0].released_credits == 5

            async def correct() -> int:
                async with factory() as session:
                    await set_tenant_database_context(session, organisation_id)
                    result = await CreditService(session, settings).correct_balance(
                        organisation_id,
                        credits=3,
                        direction="increase",
                        credit_type="promotional",
                        reference="concurrent-correction",
                        idempotency_key="concurrent-correction-key",
                        actor_reference="credit-concurrency-test",
                        reason="Exercise concurrent correction idempotency.",
                    )
                    return result.available

            corrections = await asyncio.gather(correct(), correct())
            assert corrections[0] == corrections[1] == 108

            async with factory() as session:
                await set_tenant_database_context(session, organisation_id)
                consumption_entry_id = await session.scalar(
                    select(CreditLedgerEntry.id).where(
                        CreditLedgerEntry.organisation_id == organisation_id,
                        CreditLedgerEntry.operation_id == winning.operation_id,
                        CreditLedgerEntry.event_type == "consumption",
                    )
                )
                assert consumption_entry_id is not None

            async def refund(key: str) -> uuid.UUID | PublicAPIError:
                async with factory() as session:
                    await set_tenant_database_context(session, organisation_id)
                    try:
                        lot = await CreditService(session, settings).refund_consumption(
                            organisation_id,
                            consumption_entry_id=consumption_entry_id,
                            credits=4,
                            idempotency_key=key,
                            actor_reference="credit-concurrency-test",
                            reason="Prove concurrent refunds cannot exceed one consumption.",
                        )
                        return lot.id
                    except PublicAPIError as exc:
                        return exc

            refunds = await asyncio.gather(
                refund("concurrent-refund-a"),
                refund("concurrent-refund-b"),
            )
            assert len([item for item in refunds if isinstance(item, uuid.UUID)]) == 1
            refund_failures = [item for item in refunds if isinstance(item, PublicAPIError)]
            assert len(refund_failures) == 1
            assert refund_failures[0].code == "credit_refund_exceeds_consumption"

            async with factory() as session:
                await set_tenant_database_context(session, organisation_id)
                service = CreditService(session, settings)
                await service.configure_policy(
                    organisation_id,
                    metered_actions_enabled=True,
                    max_credits_per_operation=100,
                    max_credits_per_day=14,
                    max_provider_cost_micros_per_day=100_000_000,
                    trial_max_credits_per_day=100,
                    max_operations_per_minute=100,
                    actor_reference="credit-concurrency-test",
                    reason="Bound concurrent in-flight daily Credit exposure.",
                )
                cap_quote_a = await service.create_quote(
                    organisation_id, user_id, action_code=TEST_ACTION_CODE, quantity=1
                )
                cap_quote_b = await service.create_quote(
                    organisation_id, user_id, action_code=TEST_ACTION_CODE, quantity=1
                )

            cap_attempts = await asyncio.gather(
                reserve(cap_quote_a.quote_id, "concurrent-cap-reservation-a"),
                reserve(cap_quote_b.quote_id, "concurrent-cap-reservation-b"),
            )
            assert len([item for item in cap_attempts if isinstance(item, CreditOperationResponse)]) == 1
            cap_failures = [item for item in cap_attempts if isinstance(item, PublicAPIError)]
            assert len(cap_failures) == 1
            assert cap_failures[0].code == "credit_daily_cap_exceeded"

            async with factory() as session:
                await set_tenant_database_context(session, organisation_id)
                service = CreditService(session, settings)
                assert (await service.reconcile_balance(organisation_id)).consistent is True
                for event_type in ("purchase", "correction", "refund"):
                    count = await session.scalar(
                        select(func.count())
                        .select_from(CreditLedgerEntry)
                        .where(
                            CreditLedgerEntry.organisation_id == organisation_id,
                            CreditLedgerEntry.event_type == event_type,
                        )
                    )
                    assert count == 1
                rows = await session.execute(
                    text(
                        """SELECT relname, relforcerowsecurity FROM pg_class
                        WHERE relname = ANY(:tables)"""
                    ),
                    {
                        "tables": [
                            "organisation_credit_balances",
                            "credit_organisation_policies",
                            "credit_lots",
                            "credit_quotes",
                            "credit_operations",
                            "credit_reservation_allocations",
                            "credit_ledger_entries",
                        ]
                    },
                )
                rls = dict(rows.all())
                assert len(rls) == 7 and all(rls.values())
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_postgresql_credit_rls_hides_every_tenant_owned_credit_row() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required for Credit RLS tests.")

    role_name = f"revenueos_credit_rls_{uuid.uuid4().hex[:12]}"
    action_price_id = uuid.uuid4()
    tenant_a = {"organisation_id": uuid.uuid4(), "user_id": uuid.uuid4()}
    tenant_b = {"organisation_id": uuid.uuid4(), "user_id": uuid.uuid4()}
    tenant_tables = (
        "organisation_credit_balances",
        "credit_organisation_policies",
        "credit_lots",
        "credit_quotes",
        "credit_operations",
        "credit_reservation_allocations",
        "credit_ledger_entries",
    )

    async def scenario() -> None:
        engine = create_async_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.exec_driver_sql(f'CREATE ROLE "{role_name}" NOLOGIN')
                await connection.exec_driver_sql('GRANT USAGE ON SCHEMA public TO "' + role_name + '"')
                for table_name in tenant_tables:
                    await connection.exec_driver_sql(
                        f'GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO "{role_name}"'
                    )
                await connection.execute(
                    text(
                        """
                        INSERT INTO credit_action_price_versions
                            (id, action_code, display_name, required_module_code, version,
                             credit_charge_per_unit, customer_charge_basis,
                             max_units_per_operation,
                             customer_revenue_micros_per_unit, customer_currency, cost_basis,
                             provider_cost_minor_units, provider_currency, fx_rate_to_aud,
                             fx_source, fx_observed_at, other_variable_cost_micros,
                             expected_variable_cost_micros_per_unit,
                             maximum_variable_cost_micros_per_unit,
                             gross_margin_basis_points, approved_margin_floor_basis_points,
                             owner_approval_reference, environment, status, pricing_note,
                             effective_from, created_by_actor)
                        VALUES
                            (:id, :action_code, 'Credit RLS fixture', 'prospect', 1,
                             5, 'successful_unit', 10, 1000000, 'AUD', 'successful_unit',
                             20, 'USD', 1.50000000, 'deterministic RLS fixture', now(),
                             0, 300000, 400000, 6000, 1000, NULL, 'test', 'test_active',
                             'TEST ONLY / NOT CUSTOMER PRICING', now(), 'credit-rls-test')
                        """
                    ),
                    {"id": action_price_id, "action_code": f"CREDIT_RLS_{action_price_id.hex}"},
                )
                for label, tenant in (("a", tenant_a), ("b", tenant_b)):
                    fixture = {
                        **tenant,
                        "organisation_name": f"Credit RLS {label.upper()}",
                        "slug": f"credit-rls-{label}-{tenant['organisation_id']}",
                        "external_auth_id": f"credit-rls-{label}-{tenant['user_id']}",
                        "email": f"credit-rls-{label}-{tenant['user_id']}@example.test",
                        "lot_id": uuid.uuid4(),
                        "quote_id": uuid.uuid4(),
                        "operation_id": uuid.uuid4(),
                        "allocation_id": uuid.uuid4(),
                        "ledger_id": uuid.uuid4(),
                        "action_price_id": action_price_id,
                        "source_reference": f"credit-rls-source-{label}-{tenant['organisation_id']}",
                        "idempotency_key": f"credit-rls-reservation-{label}-{tenant['organisation_id']}",
                    }
                    fixture_statements = """
                            INSERT INTO organisations (id, name, slug)
                            VALUES (:organisation_id, :organisation_name, :slug);
                            INSERT INTO users (id, external_auth_id, email, display_name)
                            VALUES (:user_id, :external_auth_id, :email, :organisation_name);
                            INSERT INTO organisation_memberships (organisation_id, user_id, role)
                            VALUES (:organisation_id, :user_id, 'admin');
                            INSERT INTO organisation_credit_balances
                                (organisation_id, promotional_available, promotional_reserved, lock_version)
                            VALUES (:organisation_id, 5, 5, 1);
                            INSERT INTO credit_organisation_policies
                                (organisation_id, metered_actions_enabled, max_credits_per_operation,
                                 max_credits_per_day, max_provider_cost_micros_per_day,
                                 trial_max_credits_per_day, max_operations_per_minute,
                                 actor_reference, reason)
                            VALUES (:organisation_id, true, 100, 1000, 100000000, 100, 10,
                                    'credit-rls-test', 'Bound the synthetic RLS fixture.');
                            INSERT INTO credit_lots
                                (id, organisation_id, credit_type, source_reference,
                                 original_credits, available_credits, reserved_credits,
                                 consumed_credits, original_revenue_micros,
                                 remaining_revenue_micros, grant_actor_reference, grant_reason)
                            VALUES (:lot_id, :organisation_id, 'promotional', :source_reference,
                                    10, 5, 5, 0, 0, 0, 'credit-rls-test',
                                    'Populate every tenant-owned Credit table.');
                            INSERT INTO credit_quotes
                                (id, organisation_id, created_by_user_id, action_price_version_id,
                                 action_code, quantity, required_credits,
                                 maximum_provider_cost_micros, quote_fingerprint, status, expires_at)
                            VALUES (:quote_id, :organisation_id, :user_id, :action_price_id,
                                    'CREDIT_RLS_FIXTURE', 1, 5, 400000, :fingerprint,
                                    'reserved', now() + interval '10 minutes');
                            INSERT INTO credit_operations
                                (id, organisation_id, requested_by_user_id, quote_id,
                                 action_price_version_id, action_code, quantity, idempotency_key,
                                 request_fingerprint, status, outcome, reserved_credits)
                            VALUES (:operation_id, :organisation_id, :user_id, :quote_id,
                                    :action_price_id, 'CREDIT_RLS_FIXTURE', 1, :idempotency_key,
                                    :fingerprint, 'reserved', 'pending', 5);
                            INSERT INTO credit_reservation_allocations
                                (id, organisation_id, operation_id, lot_id, allocation_order,
                                 reserved_credits)
                            VALUES (:allocation_id, :organisation_id, :operation_id, :lot_id, 1, 5);
                            INSERT INTO credit_ledger_entries
                                (id, organisation_id, event_type, credit_type,
                                 promotional_available_delta, reserved_delta, lot_id, operation_id,
                                 action_code, quantity, idempotency_key, request_fingerprint,
                                 actor_reference, reason)
                            VALUES (:ledger_id, :organisation_id, 'reservation', 'promotional',
                                    -5, 5, :lot_id, :operation_id, 'CREDIT_RLS_FIXTURE', 1,
                                    :idempotency_key, :fingerprint, 'credit-rls-test',
                                    'Populate an immutable tenant-owned ledger row.');
                            """
                    for statement in fixture_statements.split(";"):
                        if statement.strip():
                            await connection.execute(
                                text(statement),
                                {**fixture, "fingerprint": label * 64},
                            )

            async with engine.connect() as connection:
                transaction = await connection.begin()
                await connection.exec_driver_sql(f'SET LOCAL ROLE "{role_name}"')
                await connection.execute(
                    text("SELECT set_config('app.organisation_id', :organisation_id, true)"),
                    {"organisation_id": str(tenant_a["organisation_id"])},
                )
                for table_name in tenant_tables:
                    assert await connection.scalar(text(f"SELECT count(*) FROM {table_name}")) == 1
                    assert (
                        await connection.scalar(
                            text(f"SELECT count(*) FROM {table_name} WHERE organisation_id = :organisation_id"),
                            {"organisation_id": tenant_b["organisation_id"]},
                        )
                        == 0
                    )
                savepoint = await connection.begin_nested()
                with pytest.raises(DBAPIError):
                    await connection.execute(
                        text(
                            """
                            INSERT INTO credit_lots
                                (id, organisation_id, credit_type, source_reference,
                                 original_credits, available_credits, reserved_credits,
                                 consumed_credits, original_revenue_micros,
                                 remaining_revenue_micros, grant_actor_reference, grant_reason)
                            VALUES (:id, :organisation_id, 'promotional', :source_reference,
                                    1, 1, 0, 0, 0, 0, 'credit-rls-test',
                                    'Cross-tenant insertion must fail.')
                            """
                        ),
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": tenant_b["organisation_id"],
                            "source_reference": f"credit-rls-denied-{uuid.uuid4()}",
                        },
                    )
                await savepoint.rollback()
                await transaction.rollback()
        finally:
            async with engine.begin() as connection:
                await connection.exec_driver_sql(
                    "ALTER TABLE credit_ledger_entries DISABLE TRIGGER credit_ledger_entries_immutable"
                )
                for table_name in (
                    "credit_ledger_entries",
                    "credit_reservation_allocations",
                    "credit_operations",
                    "credit_quotes",
                    "credit_lots",
                    "credit_organisation_policies",
                    "organisation_credit_balances",
                ):
                    await connection.execute(
                        text(f"DELETE FROM {table_name} WHERE organisation_id IN (:organisation_a, :organisation_b)"),
                        {
                            "organisation_a": tenant_a["organisation_id"],
                            "organisation_b": tenant_b["organisation_id"],
                        },
                    )
                await connection.exec_driver_sql(
                    "ALTER TABLE credit_ledger_entries ENABLE TRIGGER credit_ledger_entries_immutable"
                )
                identity_parameters = {
                    "organisation_a": tenant_a["organisation_id"],
                    "organisation_b": tenant_b["organisation_id"],
                    "user_a": tenant_a["user_id"],
                    "user_b": tenant_b["user_id"],
                }
                for statement in (
                    "DELETE FROM organisation_memberships WHERE organisation_id IN (:organisation_a, :organisation_b)",
                    "DELETE FROM organisations WHERE id IN (:organisation_a, :organisation_b)",
                    "DELETE FROM users WHERE id IN (:user_a, :user_b)",
                ):
                    await connection.execute(text(statement), identity_parameters)
                await connection.exec_driver_sql(
                    "ALTER TABLE credit_action_price_versions DISABLE TRIGGER credit_action_price_versions_immutable"
                )
                await connection.execute(
                    text("DELETE FROM credit_action_price_versions WHERE id = :id"),
                    {"id": action_price_id},
                )
                await connection.exec_driver_sql(
                    "ALTER TABLE credit_action_price_versions ENABLE TRIGGER credit_action_price_versions_immutable"
                )
                role_exists = await connection.scalar(
                    text("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :role_name)"),
                    {"role_name": role_name},
                )
                if role_exists:
                    await connection.exec_driver_sql(f'DROP OWNED BY "{role_name}"')
                    await connection.exec_driver_sql(f'DROP ROLE "{role_name}"')
            await engine.dispose()

    asyncio.run(scenario())
