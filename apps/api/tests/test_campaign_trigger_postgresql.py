from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from revenueos.database import set_tenant_database_context
from revenueos.models import (
    Company,
    Contact,
    EngageCampaign,
    EngageCampaignAudience,
    EngageCampaignVersion,
    EngageSequenceStep,
    Organisation,
    OrganisationMembership,
    User,
)


def test_postgresql_published_campaign_guard_handles_each_trigger_relation() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required for campaign trigger tests.")

    suffix = uuid.uuid4().hex
    organisation_id = uuid.uuid4()
    user_id = uuid.uuid4()
    company_id = uuid.uuid4()
    contact_id = uuid.uuid4()
    campaign_id = uuid.uuid4()
    version_id = uuid.uuid4()
    audience_id = uuid.uuid4()
    sequence_id = uuid.uuid4()

    async def scenario() -> None:
        engine = create_async_engine(database_url, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async def assert_update_rejected(statement: object, message: str) -> None:
            async with factory() as session:
                await set_tenant_database_context(session, organisation_id)
                with pytest.raises(DBAPIError) as caught:
                    await session.execute(statement)  # type: ignore[arg-type]
                    await session.commit()
                await session.rollback()
            assert message in str(caught.value.orig)

        try:
            async with factory() as session, session.begin():
                await set_tenant_database_context(session, organisation_id)
                session.add(
                    Organisation(
                        id=organisation_id,
                        name="Synthetic campaign trigger team",
                        slug=f"campaign-trigger-{suffix}",
                    )
                )
                session.add(
                    User(
                        id=user_id,
                        external_auth_id=f"campaign-trigger-{suffix}",
                        email=f"campaign-trigger-{suffix}@example.test",
                        display_name="Synthetic campaign trigger owner",
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
                await session.flush()
                session.add(
                    Company(
                        id=company_id,
                        organisation_id=organisation_id,
                        owner_user_id=user_id,
                        name="Synthetic campaign customer",
                    )
                )
                await session.flush()
                session.add(
                    Contact(
                        id=contact_id,
                        organisation_id=organisation_id,
                        company_id=company_id,
                        owner_user_id=user_id,
                        first_name="Casey",
                        last_name="Contact",
                        email=f"casey-{suffix}@example.test",
                    )
                )
                session.add(
                    EngageCampaign(
                        id=campaign_id,
                        organisation_id=organisation_id,
                        owner_user_id=user_id,
                        state="ready",
                    )
                )
                await session.flush()
                session.add(
                    EngageCampaignVersion(
                        id=version_id,
                        organisation_id=organisation_id,
                        campaign_id=campaign_id,
                        version=1,
                        status="published",
                        name="Synthetic published campaign",
                        purpose="Prove the relation-safe trigger guard.",
                        approval_mode="review_each_send",
                        sender_user_id=user_id,
                        sender_timezone="Australia/Sydney",
                        created_by_user_id=user_id,
                    )
                )
                await session.flush()
                session.add_all(
                    (
                        EngageCampaignAudience(
                            id=audience_id,
                            organisation_id=organisation_id,
                            campaign_version_id=version_id,
                            contact_id=contact_id,
                            company_id=company_id,
                            recipient_name="Casey Contact",
                            recipient_email=f"casey-{suffix}@example.test",
                            recipient_trust="verified",
                            eligible=True,
                            eligibility_code="eligible",
                            eligibility_reason="Eligible synthetic business Person.",
                        ),
                        EngageSequenceStep(
                            id=sequence_id,
                            organisation_id=organisation_id,
                            campaign_version_id=version_id,
                            step_order=1,
                            delay_days=0,
                            objective="introduction",
                            content_strategy="source_backed_value",
                        ),
                    )
                )

            await assert_update_rejected(
                update(EngageCampaignAudience)
                .where(
                    EngageCampaignAudience.organisation_id == organisation_id,
                    EngageCampaignAudience.id == audience_id,
                )
                .values(id=uuid.uuid4(), contact_id=None),
                "Published campaign audience and sequence are immutable",
            )

            async with factory() as session, session.begin():
                await set_tenant_database_context(session, organisation_id)
                await session.execute(
                    update(EngageCampaignAudience)
                    .where(
                        EngageCampaignAudience.organisation_id == organisation_id,
                        EngageCampaignAudience.id == audience_id,
                    )
                    .values(contact_id=None)
                )

            async with factory() as session, session.begin():
                await set_tenant_database_context(session, organisation_id)
                detached_contact = await session.scalar(
                    select(EngageCampaignAudience.contact_id).where(
                        EngageCampaignAudience.organisation_id == organisation_id,
                        EngageCampaignAudience.id == audience_id,
                    )
                )
                assert detached_contact is None

            await assert_update_rejected(
                update(EngageCampaignAudience)
                .where(
                    EngageCampaignAudience.organisation_id == organisation_id,
                    EngageCampaignAudience.id == audience_id,
                )
                .values(eligibility_reason="Changed after publication."),
                "Published campaign audience and sequence are immutable",
            )
            await assert_update_rejected(
                update(EngageSequenceStep)
                .where(
                    EngageSequenceStep.organisation_id == organisation_id,
                    EngageSequenceStep.id == sequence_id,
                )
                .values(delay_days=1),
                "Published campaign audience and sequence are immutable",
            )
            await assert_update_rejected(
                update(EngageCampaignVersion)
                .where(
                    EngageCampaignVersion.organisation_id == organisation_id,
                    EngageCampaignVersion.id == version_id,
                )
                .values(name="Changed after publication"),
                "Published campaign versions are immutable",
            )
        finally:
            async with factory() as session, session.begin():
                await set_tenant_database_context(session, organisation_id)
                await session.execute(delete(Organisation).where(Organisation.id == organisation_id))
                await session.execute(delete(User).where(User.id == user_id))
            await engine.dispose()

    asyncio.run(scenario())
