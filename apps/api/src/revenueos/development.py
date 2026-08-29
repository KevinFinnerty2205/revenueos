from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.database import set_tenant_database_context
from revenueos.models import (
    IntegrationConnection,
    Organisation,
    OrganisationMembership,
    OrganisationModuleEntitlement,
    OutreachPolicy,
    User,
)

DEVELOPMENT_USER_ID = UUID("00000000-0000-4000-8000-000000000001")
DEVELOPMENT_ORGANISATION_ID = UUID("00000000-0000-4000-8000-000000000002")


async def ensure_development_identity(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Provision only the fixed, clearly labelled local mock identity."""

    async with session_factory() as session:
        await set_tenant_database_context(session, DEVELOPMENT_ORGANISATION_ID)
        organisation = await session.get(Organisation, DEVELOPMENT_ORGANISATION_ID)
        if organisation is None:
            session.add(
                Organisation(
                    id=DEVELOPMENT_ORGANISATION_ID,
                    name="Example Revenue Team",
                    slug="example-revenue-team",
                )
            )
        user = await session.get(User, DEVELOPMENT_USER_ID)
        if user is None:
            session.add(
                User(
                    id=DEVELOPMENT_USER_ID,
                    external_auth_id="user_dev_001",
                    email="alex@example.test",
                    display_name="Alex Morgan",
                )
            )
        membership = await session.get(
            OrganisationMembership,
            (DEVELOPMENT_ORGANISATION_ID, DEVELOPMENT_USER_ID),
        )
        if membership is None:
            session.add(
                OrganisationMembership(
                    organisation_id=DEVELOPMENT_ORGANISATION_ID,
                    user_id=DEVELOPMENT_USER_ID,
                    role="admin",
                )
            )
        await session.flush()
        for module_key in ("prospect", "engage", "create", "crm"):
            entitlement = await session.get(
                OrganisationModuleEntitlement,
                (DEVELOPMENT_ORGANISATION_ID, module_key),
            )
            if entitlement is None:
                session.add(
                    OrganisationModuleEntitlement(
                        organisation_id=DEVELOPMENT_ORGANISATION_ID,
                        module_key=module_key,
                        enabled=True,
                        source="manual_private_beta",
                        configured_by_user_id=DEVELOPMENT_USER_ID,
                        enabled_at=datetime.now(UTC),
                    )
                )
        policy = await session.get(OutreachPolicy, DEVELOPMENT_ORGANISATION_ID)
        if policy is None:
            session.add(
                OutreachPolicy(
                    organisation_id=DEVELOPMENT_ORGANISATION_ID,
                    configured=True,
                    outbound_enabled=True,
                    provider_supplied_email_allowed=True,
                    cooldown_hours=72,
                    max_daily_sends_user=25,
                    max_daily_sends_org=100,
                    require_opt_out_mechanism=False,
                    offering_name="Multi-site Access Management",
                    value_proposition=(
                        "RevenueOS helps growing teams coordinate secure access across locations without adding manual work."
                    ),
                    approved_cta="Would a short conversation next week be useful?",
                    configured_by_user_id=DEVELOPMENT_USER_ID,
                )
            )
        mock_email = await session.get(
            IntegrationConnection,
            UUID("00000000-0000-4000-8000-000000000029"),
        )
        if mock_email is None:
            session.add(
                IntegrationConnection(
                    id=UUID("00000000-0000-4000-8000-000000000029"),
                    organisation_id=DEVELOPMENT_ORGANISATION_ID,
                    connector_key="mock_email",
                    connection_status="active",
                    created_by_user_id=DEVELOPMENT_USER_ID,
                    connected_at=datetime.now(UTC),
                    last_verified_at=datetime.now(UTC),
                    capability_state_json=["send_email"],
                    metadata_version=1,
                )
            )
        await session.commit()
