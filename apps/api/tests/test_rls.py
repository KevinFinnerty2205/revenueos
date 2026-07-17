from __future__ import annotations

import asyncio
import os
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine


def test_postgresql_rls_isolates_every_business_table() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required for the RLS integration test.")

    organisation_a = uuid.uuid4()
    organisation_b = uuid.uuid4()
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    company_a = uuid.uuid4()
    company_b = uuid.uuid4()
    contact_a = uuid.uuid4()
    contact_b = uuid.uuid4()
    opportunity_a = uuid.uuid4()
    opportunity_b = uuid.uuid4()
    task_a = uuid.uuid4()
    task_b = uuid.uuid4()
    role_name = f"revenueos_rls_test_{uuid.uuid4().hex[:12]}"

    async def scenario() -> None:
        engine = create_async_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.exec_driver_sql(f'CREATE ROLE "{role_name}" NOLOGIN')
                await connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{role_name}"')
                for table in ("companies", "contacts", "opportunities", "tasks"):
                    await connection.exec_driver_sql(
                        f'GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO "{role_name}"'
                    )
                identity_parameters = {
                    "organisation_a": organisation_a,
                    "organisation_b": organisation_b,
                    "slug_a": f"rls-a-{organisation_a.hex}",
                    "slug_b": f"rls-b-{organisation_b.hex}",
                    "user_a": user_a,
                    "user_b": user_b,
                    "external_a": f"rls_a_{user_a.hex}",
                    "external_b": f"rls_b_{user_b.hex}",
                    "email_a": f"rls-a-{user_a.hex}@example.com",
                    "email_b": f"rls-b-{user_b.hex}@example.com",
                }
                await connection.execute(
                    text(
                        """
                        INSERT INTO organisations (id, name, slug)
                        VALUES (:organisation_a, 'RLS A', :slug_a),
                               (:organisation_b, 'RLS B', :slug_b)
                        """
                    ),
                    identity_parameters,
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO users (id, external_auth_id, email, display_name)
                        VALUES (:user_a, :external_a, :email_a, 'RLS User A'),
                               (:user_b, :external_b, :email_b, 'RLS User B')
                        """
                    ),
                    identity_parameters,
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO organisation_memberships (organisation_id, user_id, role)
                        VALUES (:organisation_a, :user_a, 'admin'),
                               (:organisation_b, :user_b, 'admin')
                        """
                    ),
                    identity_parameters,
                )
                for suffix, organisation_id, user_id, company_id in (
                    ("A", organisation_a, user_a, company_a),
                    ("B", organisation_b, user_b, company_b),
                ):
                    await connection.execute(
                        text(
                            """
                            INSERT INTO companies
                                (id, organisation_id, name, status, owner_user_id)
                            VALUES (:id, :organisation_id, :name, 'prospect', :user_id)
                            """
                        ),
                        {
                            "id": company_id,
                            "organisation_id": organisation_id,
                            "name": f"RLS Company {suffix}",
                            "user_id": user_id,
                        },
                    )
                for (
                    suffix,
                    organisation_id,
                    user_id,
                    company_id,
                    contact_id,
                    opportunity_id,
                    task_id,
                ) in (
                    (
                        "A",
                        organisation_a,
                        user_a,
                        company_a,
                        contact_a,
                        opportunity_a,
                        task_a,
                    ),
                    (
                        "B",
                        organisation_b,
                        user_b,
                        company_b,
                        contact_b,
                        opportunity_b,
                        task_b,
                    ),
                ):
                    entity_parameters = {
                        "contact_id": contact_id,
                        "opportunity_id": opportunity_id,
                        "task_id": task_id,
                        "organisation_id": organisation_id,
                        "company_id": company_id,
                        "suffix": suffix,
                        "email": f"rls-{suffix.lower()}-{contact_id.hex}@example.com",
                        "user_id": user_id,
                        "name": f"RLS Opportunity {suffix}",
                        "value": Decimal("1000.00"),
                        "task_title": f"RLS Task {suffix}",
                    }
                    await connection.execute(
                        text(
                            """
                            INSERT INTO contacts
                                (id, organisation_id, company_id, first_name, last_name,
                                 email, owner_user_id)
                            VALUES
                                (:contact_id, :organisation_id, :company_id, 'RLS',
                                 :suffix, :email, :user_id)
                            """
                        ),
                        entity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO opportunities
                                (id, organisation_id, company_id, name, stage, value,
                                 currency, probability, owner_user_id)
                            VALUES
                                (:opportunity_id, :organisation_id, :company_id, :name,
                                 'discovery', :value, 'AUD', 20, :user_id)
                            """
                        ),
                        entity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO tasks
                                (id, organisation_id, company_id, contact_id, opportunity_id,
                                 title, status, priority, assigned_user_id, created_by_user_id)
                            VALUES
                                (:task_id, :organisation_id, :company_id, :contact_id,
                                 :opportunity_id, :task_title, 'open', 'medium', :user_id, :user_id)
                            """
                        ),
                        entity_parameters,
                    )

            async with engine.connect() as connection:
                transaction = await connection.begin()
                await connection.exec_driver_sql(f'SET LOCAL ROLE "{role_name}"')
                await connection.execute(
                    text("SELECT set_config('app.organisation_id', :organisation_id, true)"),
                    {"organisation_id": str(organisation_a)},
                )
                for table in ("companies", "contacts", "opportunities", "tasks"):
                    count = await connection.scalar(text(f"SELECT count(*) FROM {table}"))
                    assert count == 1
                updated = await connection.execute(
                    text("UPDATE companies SET name = 'Blocked' WHERE id = :id"),
                    {"id": company_b},
                )
                assert updated.rowcount == 0
                await transaction.commit()

                transaction = await connection.begin()
                await connection.exec_driver_sql(f'SET LOCAL ROLE "{role_name}"')
                await connection.execute(
                    text("SELECT set_config('app.organisation_id', :organisation_id, true)"),
                    {"organisation_id": str(organisation_a)},
                )
                with pytest.raises(DBAPIError):
                    await connection.execute(
                        text(
                            """
                            INSERT INTO companies
                                (id, organisation_id, name, status, owner_user_id)
                            VALUES (:id, :organisation_id, 'Cross tenant', 'prospect', :user_id)
                            """
                        ),
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": organisation_b,
                            "user_id": user_b,
                        },
                    )
                await transaction.rollback()
        finally:
            async with engine.begin() as connection:
                for table in ("tasks", "contacts", "opportunities", "companies"):
                    await connection.execute(
                        text(f"DELETE FROM {table} WHERE organisation_id IN (:organisation_a, :organisation_b)"),
                        {
                            "organisation_a": organisation_a,
                            "organisation_b": organisation_b,
                        },
                    )
                cleanup_parameters = {
                    "organisation_a": organisation_a,
                    "organisation_b": organisation_b,
                    "user_a": user_a,
                    "user_b": user_b,
                }
                await connection.execute(
                    text(
                        """
                        DELETE FROM organisation_memberships
                        WHERE organisation_id IN (:organisation_a, :organisation_b)
                        """
                    ),
                    cleanup_parameters,
                )
                await connection.execute(
                    text("DELETE FROM users WHERE id IN (:user_a, :user_b)"),
                    cleanup_parameters,
                )
                await connection.execute(
                    text("DELETE FROM organisations WHERE id IN (:organisation_a, :organisation_b)"),
                    cleanup_parameters,
                )
                await connection.exec_driver_sql(f'DROP OWNED BY "{role_name}"')
                await connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{role_name}"')
            await engine.dispose()

    asyncio.run(scenario())
