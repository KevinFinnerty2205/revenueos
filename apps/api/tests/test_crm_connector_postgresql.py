from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.config import Settings
from revenueos.database import set_tenant_database_context
from revenueos.domain import ConnectorKey
from revenueos.errors import PublicAPIError
from revenueos.integration_services import IntegrationService
from revenueos.models import IntegrationConnection, Organisation, OrganisationMembership, User
from revenueos.tenant import TenantContext


def test_postgresql_concurrent_crm_connect_establishes_exactly_one_primary() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required for CRM connection concurrency tests.")

    organisation_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.now(UTC)

    async def scenario() -> None:
        engine = create_async_engine(database_url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = Settings(
            environment="test",
            auth_mode="mock",
            mock_auth_enabled=True,
            database_url=database_url,
        )
        tenant = TenantContext(organisation_id, user_id, "admin")
        try:
            async with factory() as session:
                session.add(
                    Organisation(
                        id=organisation_id,
                        name="CRM connection concurrency organisation",
                        slug=f"crm-connection-concurrency-{organisation_id}",
                    )
                )
                session.add(
                    User(
                        id=user_id,
                        external_auth_id=f"crm-connection-concurrency-{user_id}",
                        email=f"crm-connection-concurrency-{user_id}@example.test",
                        display_name="CRM concurrency user",
                    )
                )
                await session.flush()
                session.add(
                    OrganisationMembership(
                        organisation_id=organisation_id,
                        user_id=user_id,
                        role="admin",
                    )
                )
                await session.commit()

            async def connect(connector: ConnectorKey) -> str:
                async with factory() as session:
                    await set_tenant_database_context(session, organisation_id)
                    service = IntegrationService(session, tenant, settings)
                    await service._require_primary_external_crm_available(connector)
                    session.add(
                        IntegrationConnection(
                            id=uuid.uuid4(),
                            organisation_id=organisation_id,
                            connector_key=connector.value,
                            connection_status="active",
                            created_by_user_id=user_id,
                            connected_at=now,
                            last_verified_at=now,
                            revoked_at=None,
                            credential_reference=None,
                            capability_state_json=[],
                            external_account_id=f"external-{connector.value}-{organisation_id}",
                            external_account_name=f"Synthetic {connector.value}",
                            external_account_email=None,
                            external_tenant_id=f"tenant-{connector.value}-{organisation_id}",
                            granted_scopes_json=[],
                            metadata_version=1,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    await session.commit()
                    return connector.value

            results = await asyncio.gather(
                connect(ConnectorKey.HUBSPOT),
                connect(ConnectorKey.SALESFORCE),
                return_exceptions=True,
            )
            assert sum(isinstance(item, str) for item in results) == 1
            errors = [item for item in results if isinstance(item, PublicAPIError)]
            assert len(errors) == 1
            assert errors[0].code == "primary_crm_already_connected"

            async with factory() as session:
                await set_tenant_database_context(session, organisation_id)
                connections = list(
                    (
                        await session.scalars(
                            select(IntegrationConnection).where(
                                IntegrationConnection.organisation_id == organisation_id,
                                IntegrationConnection.connector_key.in_(("hubspot", "salesforce")),
                                IntegrationConnection.connection_status != "revoked",
                            )
                        )
                    ).all()
                )
                assert len(connections) == 1
                assert connections[0].connector_key in {"hubspot", "salesforce"}
                assert (
                    await session.scalar(
                        text(
                            """
                            SELECT relforcerowsecurity
                            FROM pg_class
                            WHERE relname = 'integration_connections'
                            """
                        )
                    )
                    is True
                )
        finally:
            async with factory() as session:
                await session.execute(
                    delete(IntegrationConnection).where(IntegrationConnection.organisation_id == organisation_id)
                )
                await session.execute(
                    delete(OrganisationMembership).where(OrganisationMembership.organisation_id == organisation_id)
                )
                await session.execute(delete(User).where(User.id == user_id))
                await session.execute(delete(Organisation).where(Organisation.id == organisation_id))
                await session.commit()
            await engine.dispose()

    asyncio.run(scenario())
