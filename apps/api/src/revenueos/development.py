from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.database import set_tenant_database_context
from revenueos.models import Organisation, OrganisationMembership, User

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
        await session.commit()
