from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from revenueos.beta_maintenance import _delete_meeting_batch
from revenueos.config import Settings, get_settings
from revenueos.database import create_engine, create_session_factory, set_tenant_database_context
from revenueos.models import (
    BetaFeedback,
    BetaSystemEvent,
    Company,
    Meeting,
    Opportunity,
    OpportunityAuditEvent,
    OrganisationMembership,
    Transcript,
)

DEMO_NAMESPACE = UUID("d7838892-ce0b-434a-a8e9-445767115063")

TRANSCRIPTS = (
    """SYNTHETIC DEMO TRANSCRIPT — no real person or customer data.\nSeller: Thanks for discussing the evaluation. What outcome matters most?\nBuyer: We need a consistent handover after sales calls. The operations lead supports a pilot, but the finance approver has not reviewed the budget.\nSeller: What timing are you working towards?\nBuyer: We would like a decision by the end of the quarter. Please send the security summary and a clear pilot plan next Tuesday.\nSeller: I will send both items next Tuesday and arrange a finance review.\nBuyer: That works. The unresolved questions are data retention and implementation effort.""",
    """SYNTHETIC DEMO TRANSCRIPT — no real person or customer data.\nSeller: Since the discovery meeting, what has changed?\nBuyer: The finance approver joined and confirmed budget for a limited pilot. Security is comfortable with the proposed controls.\nSeller: Are there remaining concerns?\nBuyer: The team is comparing the internal process with another vendor. Implementation capacity is the main risk, although the operations lead remains our champion.\nSeller: What should happen next?\nBuyer: Send the final pilot scope by Friday. We will hold a decision meeting next Wednesday.\nSeller: I will own the pilot scope and include the retention settings.""",
)


def demo_ids(organisation_id: UUID) -> tuple[UUID, UUID, tuple[UUID, UUID], tuple[UUID, UUID]]:
    prefix = str(organisation_id)
    return (
        uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:company"),
        uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:opportunity"),
        (
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:meeting-discovery"),
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:meeting-evaluation"),
        ),
        (
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:transcript-discovery"),
            uuid.uuid5(DEMO_NAMESPACE, f"{prefix}:transcript-evaluation"),
        ),
    )


async def seed_demo_data(
    session_factory: async_sessionmaker[AsyncSession],
    organisation_id: UUID,
    user_id: UUID,
) -> dict[str, object]:
    company_id, opportunity_id, meeting_ids, transcript_ids = demo_ids(organisation_id)
    seeded_at = datetime.now(UTC)
    async with session_factory() as session, session.begin():
        await set_tenant_database_context(session, organisation_id)
        membership = await session.get(OrganisationMembership, (organisation_id, user_id))
        if membership is None or membership.status != "active":
            raise ValueError("Demo data requires an active member of the selected organisation.")
        company = await session.get(Company, company_id)
        if company is None:
            session.add(
                Company(
                    id=company_id,
                    organisation_id=organisation_id,
                    name="[DEMO] Southern Cross Operations",
                    website="https://example.test/demo",
                    industry="Synthetic professional services",
                    employee_count=75,
                    status="prospect",
                    owner_user_id=user_id,
                )
            )
        opportunity = await session.get(Opportunity, opportunity_id)
        if opportunity is None:
            session.add(
                Opportunity(
                    id=opportunity_id,
                    organisation_id=organisation_id,
                    company_id=company_id,
                    name="[DEMO] Revenue workflow pilot",
                    stage="evaluation",
                    status="open",
                    owner_user_id=user_id,
                    description="Synthetic private-beta opportunity. No real customer or personal data.",
                )
            )
        await session.flush()
        for index, meeting_id in enumerate(meeting_ids):
            meeting = await session.get(Meeting, meeting_id)
            if meeting is None:
                session.add(
                    Meeting(
                        id=meeting_id,
                        organisation_id=organisation_id,
                        title=(
                            "[DEMO] Discovery and evaluation goals" if index == 0 else "[DEMO] Pilot decision review"
                        ),
                        description="Synthetic demonstration meeting.",
                        meeting_date=seeded_at - timedelta(days=14 if index == 0 else 7),
                        meeting_type="remote",
                        status="completed",
                        company_id=company_id,
                        opportunity_id=opportunity_id,
                        owner_user_id=user_id,
                        created_by=user_id,
                        updated_by=user_id,
                    )
                )
            transcript = await session.get(Transcript, transcript_ids[index])
            if transcript is None:
                session.add(
                    Transcript(
                        id=transcript_ids[index],
                        organisation_id=organisation_id,
                        meeting_id=meeting_id,
                        raw_text=TRANSCRIPTS[index],
                        language="en-AU",
                        version=1,
                        source="manual",
                    )
                )
        exists = await session.scalar(
            select(BetaSystemEvent.id).where(
                BetaSystemEvent.organisation_id == organisation_id,
                BetaSystemEvent.event_type == "demo_data_seeded",
                BetaSystemEvent.subject_id == opportunity_id,
            )
        )
        if exists is None:
            session.add(
                BetaSystemEvent(
                    organisation_id=organisation_id,
                    actor_user_id=user_id,
                    event_type="demo_data_seeded",
                    subject_id=opportunity_id,
                    metadata_json={"dataset_version": 1},
                )
            )
    return {
        "status": "ready",
        "company_id": company_id,
        "opportunity_id": opportunity_id,
        "meeting_ids": meeting_ids,
        "provider_calls": 0,
    }


async def reset_demo_data(
    session_factory: async_sessionmaker[AsyncSession],
    organisation_id: UUID,
) -> dict[str, object]:
    company_id, opportunity_id, meeting_ids, _ = demo_ids(organisation_id)
    async with session_factory() as session, session.begin():
        await set_tenant_database_context(session, organisation_id)
        if session.get_bind().dialect.name == "postgresql":
            await session.execute(text("SELECT set_config('app.beta_maintenance', 'approved', true)"))
        await session.execute(
            update(BetaFeedback)
            .where(
                BetaFeedback.organisation_id == organisation_id,
                BetaFeedback.opportunity_id == opportunity_id,
            )
            .values(opportunity_id=None)
        )
        await _delete_meeting_batch(session, organisation_id, list(meeting_ids))
        await session.execute(
            delete(OpportunityAuditEvent).where(
                OpportunityAuditEvent.organisation_id == organisation_id,
                OpportunityAuditEvent.opportunity_id == opportunity_id,
            )
        )
        await session.execute(
            delete(Opportunity).where(
                Opportunity.organisation_id == organisation_id,
                Opportunity.id == opportunity_id,
            )
        )
        await session.execute(
            delete(Company).where(
                Company.organisation_id == organisation_id,
                Company.id == company_id,
            )
        )
        await session.execute(
            delete(BetaSystemEvent).where(
                BetaSystemEvent.organisation_id == organisation_id,
                BetaSystemEvent.event_type == "demo_data_seeded",
                BetaSystemEvent.subject_id == opportunity_id,
            )
        )
    return {"status": "reset", "provider_calls": 0}


async def _run_cli(arguments: argparse.Namespace) -> None:
    settings: Settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    if engine is None or session_factory is None:
        raise RuntimeError("Demo data maintenance requires API_DATABASE_URL.")
    try:
        if arguments.command == "seed":
            result = await seed_demo_data(
                session_factory,
                UUID(arguments.organisation_id),
                UUID(arguments.user_id),
            )
        else:
            result = await reset_demo_data(session_factory, UUID(arguments.organisation_id))
        print(json.dumps(result, default=str, sort_keys=True))
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Explicit tenant-scoped synthetic demo data")
    subparsers = parser.add_subparsers(dest="command", required=True)
    seed = subparsers.add_parser("seed")
    seed.add_argument("--organisation-id", required=True)
    seed.add_argument("--user-id", required=True)
    reset = subparsers.add_parser("reset")
    reset.add_argument("--organisation-id", required=True)
    asyncio.run(_run_cli(parser.parse_args()))


if __name__ == "__main__":
    main()
