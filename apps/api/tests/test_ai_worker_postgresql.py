from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from revenueos.ai_worker_services import AIWorkerService
from revenueos.config import Settings
from revenueos.domain import AIJobStatus, AIJobType
from revenueos.models import (
    AIJob,
    Interaction,
    Meeting,
    Organisation,
    OrganisationMembership,
    Transcript,
    User,
)
from revenueos.operations import inspect_runtime_database


def test_postgresql_preflight_checks_every_worker_discovery_function() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required for worker preflight tests.")

    runtime_role = f"worker_preflight_runtime_{uuid.uuid4().hex}"
    function_signatures = (
        "public.revenueos_ai_worker_eligible_organisations(timestamptz, integer)",
        "public.revenueos_post_conversation_draft_worker_scopes(integer)",
        "public.revenueos_briefing_worker_eligible_owners(timestamptz, integer)",
    )

    async def scenario() -> None:
        admin_engine = create_async_engine(database_url)
        runtime_engine = None
        original_public_execute: dict[str, bool] = {}
        try:
            async with admin_engine.begin() as connection:
                await connection.exec_driver_sql(f'CREATE ROLE "{runtime_role}" NOLOGIN NOSUPERUSER NOBYPASSRLS')
                await connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{runtime_role}"')
                await connection.exec_driver_sql(f'GRANT SELECT ON public.alembic_version TO "{runtime_role}"')
                for signature in function_signatures:
                    original_public_execute[signature] = bool(
                        await connection.scalar(
                            text("SELECT has_function_privilege('public', to_regprocedure(:signature), 'EXECUTE')"),
                            {"signature": signature},
                        )
                    )
                    await connection.exec_driver_sql(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
                    await connection.exec_driver_sql(f'GRANT EXECUTE ON FUNCTION {signature} TO "{runtime_role}"')

            runtime_engine = create_async_engine(
                database_url,
                connect_args={"server_settings": {"role": runtime_role}},
            )
            ready_checks = await inspect_runtime_database(runtime_engine)
            assert next(check for check in ready_checks if check.name == "database_runtime_role").status == "pass"
            assert (
                next(check for check in ready_checks if check.name == "database_worker_discovery_authority").status
                == "pass"
            )

            async with admin_engine.begin() as connection:
                await connection.exec_driver_sql(
                    f'REVOKE EXECUTE ON FUNCTION {function_signatures[1]} FROM "{runtime_role}"'
                )
            blocked_checks = await inspect_runtime_database(runtime_engine)
            assert (
                next(check for check in blocked_checks if check.name == "database_worker_discovery_authority").status
                == "fail"
            )
        finally:
            if runtime_engine is not None:
                await runtime_engine.dispose()
            async with admin_engine.begin() as connection:
                await connection.exec_driver_sql(f'DROP OWNED BY "{runtime_role}"')
                await connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{runtime_role}"')
                for signature, public_could_execute in original_public_execute.items():
                    if public_could_execute:
                        await connection.exec_driver_sql(f"GRANT EXECUTE ON FUNCTION {signature} TO PUBLIC")
            await admin_engine.dispose()

    asyncio.run(scenario())


def test_postgresql_atomic_claim_and_abandoned_recovery_are_concurrency_safe() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required for worker concurrency tests.")

    organisation_id = uuid.uuid4()
    user_id = uuid.uuid4()
    meeting_id = uuid.uuid4()
    interaction_id = uuid.uuid4()
    transcript_id = uuid.uuid4()
    claim_job_id = uuid.uuid4()
    recovery_job_id = uuid.uuid4()
    discovery_owner_role = f"worker_discovery_owner_{uuid.uuid4().hex}"
    now = datetime.now(UTC)

    async def scenario() -> None:
        engine = create_async_engine(database_url)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        settings = Settings(
            environment="test",
            auth_mode="mock",
            mock_auth_enabled=True,
            database_url=database_url,
            worker_lease_duration_seconds=30,
            worker_heartbeat_interval_seconds=10,
            worker_base_retry_delay_seconds=5,
            worker_max_retry_delay_seconds=60,
        )
        try:
            async with session_factory() as session:
                session.add(
                    Organisation(
                        id=organisation_id,
                        name="Worker concurrency organisation",
                        slug=f"worker-concurrency-{organisation_id}",
                    )
                )
                session.add(
                    User(
                        id=user_id,
                        external_auth_id=f"worker_concurrency_{user_id}",
                        email=f"worker-{user_id}@example.test",
                        display_name="Worker Test User",
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
                    Interaction(
                        id=interaction_id,
                        organisation_id=organisation_id,
                        title="Worker concurrency meeting",
                        interaction_type="online_meeting",
                        lifecycle_status="planned",
                        scheduled_start_at=now,
                        creation_origin="meeting_compatibility",
                        created_by_user_id=user_id,
                    )
                )
                session.add(
                    Meeting(
                        id=meeting_id,
                        organisation_id=organisation_id,
                        interaction_id=interaction_id,
                        title="Worker concurrency meeting",
                        meeting_date=now,
                        owner_user_id=user_id,
                        created_by=user_id,
                        updated_by=user_id,
                    )
                )
                await session.flush()
                session.add(
                    Transcript(
                        id=transcript_id,
                        organisation_id=organisation_id,
                        meeting_id=meeting_id,
                        raw_text="PostgreSQL worker test content.",
                        version=1,
                    )
                )
                await session.flush()
                session.add_all(
                    [
                        AIJob(
                            id=claim_job_id,
                            organisation_id=organisation_id,
                            meeting_id=meeting_id,
                            transcript_id=transcript_id,
                            transcript_version=1,
                            job_type=AIJobType.INFRASTRUCTURE_TEST.value,
                            status=AIJobStatus.PENDING.value,
                            idempotency_key=f"claim-{claim_job_id}",
                            requested_by_user_id=user_id,
                        ),
                        AIJob(
                            id=recovery_job_id,
                            organisation_id=organisation_id,
                            meeting_id=meeting_id,
                            transcript_id=transcript_id,
                            transcript_version=1,
                            job_type=AIJobType.INFRASTRUCTURE_TEST.value,
                            status=AIJobStatus.RUNNING.value,
                            idempotency_key=f"recovery-{recovery_job_id}",
                            requested_by_user_id=user_id,
                            attempt_count=1,
                            worker_id="crashed-worker",
                            heartbeat_at=now - timedelta(minutes=2),
                            lease_expires_at=now - timedelta(minutes=1),
                        ),
                    ]
                )
                await session.commit()

            first = AIWorkerService(session_factory, settings, clock=lambda: now)
            second = AIWorkerService(session_factory, settings, clock=lambda: now)
            assert organisation_id in await first.discover_eligible_organisations()

            async with engine.begin() as connection:
                original_function_owner = await connection.scalar(
                    text(
                        """
                        SELECT owners.rolname
                        FROM pg_proc AS functions
                        JOIN pg_namespace AS namespaces
                            ON namespaces.oid = functions.pronamespace
                        JOIN pg_roles AS owners ON owners.oid = functions.proowner
                        WHERE namespaces.nspname = 'public'
                            AND functions.proname =
                                'revenueos_ai_worker_eligible_organisations'
                        """
                    )
                )
                assert isinstance(original_function_owner, str)
                original_public_execute = bool(
                    await connection.scalar(
                        text(
                            """
                            SELECT has_function_privilege('public', functions.oid, 'EXECUTE')
                            FROM pg_proc AS functions
                            JOIN pg_namespace AS namespaces
                                ON namespaces.oid = functions.pronamespace
                            WHERE namespaces.nspname = 'public'
                                AND functions.proname =
                                    'revenueos_ai_worker_eligible_organisations'
                            """
                        )
                    )
                )
                await connection.exec_driver_sql(
                    f'CREATE ROLE "{discovery_owner_role}" NOLOGIN NOSUPERUSER NOBYPASSRLS'
                )
                await connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{discovery_owner_role}"')
                await connection.exec_driver_sql(f'GRANT SELECT ON public.ai_jobs TO "{discovery_owner_role}"')
                await connection.exec_driver_sql(
                    "ALTER FUNCTION public.revenueos_ai_worker_eligible_organisations"
                    f'(timestamptz, integer) OWNER TO "{discovery_owner_role}"'
                )

            try:
                assert organisation_id not in await first.discover_eligible_organisations()
                blocked_checks = await inspect_runtime_database(engine)
                blocked_discovery_check = next(
                    check for check in blocked_checks if check.name == "database_worker_discovery_authority"
                )
                assert blocked_discovery_check.status == "fail"
                async with engine.begin() as connection:
                    await connection.exec_driver_sql(f'ALTER ROLE "{discovery_owner_role}" BYPASSRLS')
                    await connection.exec_driver_sql(
                        "REVOKE EXECUTE ON FUNCTION "
                        "public.revenueos_ai_worker_eligible_organisations(timestamptz, integer) FROM PUBLIC"
                    )
                assert organisation_id in await first.discover_eligible_organisations()
                ready_checks = await inspect_runtime_database(engine)
                ready_discovery_check = next(
                    check for check in ready_checks if check.name == "database_worker_discovery_authority"
                )
                assert ready_discovery_check.status == "pass"
            finally:
                async with engine.begin() as connection:
                    await connection.exec_driver_sql(
                        "ALTER FUNCTION public.revenueos_ai_worker_eligible_organisations"
                        f'(timestamptz, integer) OWNER TO "{original_function_owner}"'
                    )
                    await connection.exec_driver_sql(f'DROP OWNED BY "{discovery_owner_role}"')
                    await connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{discovery_owner_role}"')
                    if original_public_execute:
                        await connection.exec_driver_sql(
                            "GRANT EXECUTE ON FUNCTION "
                            "public.revenueos_ai_worker_eligible_organisations(timestamptz, integer) TO PUBLIC"
                        )

            claims = await asyncio.gather(
                first.claim_next_job(organisation_id, "worker-one"),
                second.claim_next_job(organisation_id, "worker-two"),
            )
            claimed = [claim for claim in claims if claim is not None]
            assert len(claimed) == 1
            assert claimed[0].job_id == claim_job_id

            recovery_counts = await asyncio.gather(
                first.recover_abandoned_jobs(organisation_id),
                second.recover_abandoned_jobs(organisation_id),
            )
            assert sum(recovery_counts) == 1

            async with session_factory() as session:
                claimed_job = await session.get(AIJob, claim_job_id)
                recovered_job = await session.get(AIJob, recovery_job_id)
                assert claimed_job is not None
                assert recovered_job is not None
                assert claimed_job.status == AIJobStatus.RUNNING.value
                assert claimed_job.attempt_count == 1
                assert claimed_job.worker_id in {"worker-one", "worker-two"}
                assert recovered_job.status == AIJobStatus.PENDING.value
                assert recovered_job.worker_id is None
                assert recovered_job.last_error_code == "worker_lease_expired"
                rls_state = dict(
                    (
                        await session.execute(
                            text(
                                """
                                SELECT relname, relforcerowsecurity
                                FROM pg_class
                                WHERE relname IN ('ai_jobs', 'ai_artifacts')
                                """
                            )
                        )
                    ).all()
                )
                assert rls_state == {"ai_jobs": True, "ai_artifacts": True}
                assert (
                    await session.scalar(
                        text(
                            """
                            SELECT prosecdef
                            FROM pg_proc
                            WHERE proname =
                                'revenueos_ai_worker_eligible_organisations'
                            """
                        )
                    )
                    is True
                )
        finally:
            async with session_factory() as session:
                await session.execute(delete(AIJob).where(AIJob.organisation_id == organisation_id))
                await session.execute(delete(Transcript).where(Transcript.organisation_id == organisation_id))
                await session.execute(delete(Meeting).where(Meeting.organisation_id == organisation_id))
                await session.execute(delete(Interaction).where(Interaction.organisation_id == organisation_id))
                await session.execute(
                    delete(OrganisationMembership).where(OrganisationMembership.organisation_id == organisation_id)
                )
                await session.execute(delete(User).where(User.id == user_id))
                await session.execute(delete(Organisation).where(Organisation.id == organisation_id))
                await session.commit()
            await engine.dispose()

    asyncio.run(scenario())
