from __future__ import annotations

import argparse
import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, async_sessionmaker, create_async_engine

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
from revenueos.operations import (
    WORKER_DISCOVERY_FUNCTIONS,
    _parse_database_role_name,
    _parser,
    deployment_database_preflight,
    inspect_runtime_database,
)

WORKER_DISCOVERY_FUNCTION_SIGNATURES = tuple(signature for _, signature in WORKER_DISCOVERY_FUNCTIONS)
KNOWLEDGE_DISCOVERY_FUNCTION_SIGNATURE = WORKER_DISCOVERY_FUNCTION_SIGNATURES[1]
_WORKER_FUNCTION_MUTATION_LOCK_KEY = 7_310_628_475_091_147


@dataclass(frozen=True)
class _WorkerFunctionState:
    signature: str
    owner: str
    security_definer: bool
    configuration: tuple[str, ...] | None
    definition: str
    public_has_execute: bool
    public_execute_grantable: bool
    public_can_execute: bool
    runtime_has_execute: bool
    runtime_execute_grantable: bool
    runtime_can_execute: bool


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


async def _snapshot_worker_function_states(
    connection: AsyncConnection,
    runtime_role: str,
) -> tuple[_WorkerFunctionState, ...]:
    states: list[_WorkerFunctionState] = []
    for signature in WORKER_DISCOVERY_FUNCTION_SIGNATURES:
        row = (
            (
                await connection.execute(
                    text(
                        """
                        SELECT
                            owners.rolname AS owner,
                            functions.prosecdef AS security_definer,
                            functions.proconfig AS configuration,
                            pg_get_functiondef(functions.oid) AS definition,
                            EXISTS (
                                SELECT 1
                                FROM aclexplode(
                                    COALESCE(functions.proacl, acldefault('f', functions.proowner))
                                ) AS privilege
                                WHERE privilege.grantee = 0
                                    AND privilege.privilege_type = 'EXECUTE'
                            ) AS public_has_execute,
                            COALESCE(
                                (
                                    SELECT bool_or(privilege.is_grantable)
                                    FROM aclexplode(
                                        COALESCE(functions.proacl, acldefault('f', functions.proowner))
                                    ) AS privilege
                                    WHERE privilege.grantee = 0
                                        AND privilege.privilege_type = 'EXECUTE'
                                ),
                                false
                            ) AS public_execute_grantable,
                            has_function_privilege(
                                'public', functions.oid, 'EXECUTE'
                            ) AS public_can_execute,
                            EXISTS (
                                SELECT 1
                                FROM aclexplode(
                                    COALESCE(functions.proacl, acldefault('f', functions.proowner))
                                ) AS privilege
                                WHERE privilege.grantee = runtime.oid
                                    AND privilege.privilege_type = 'EXECUTE'
                            ) AS runtime_has_execute,
                            COALESCE(
                                (
                                    SELECT bool_or(privilege.is_grantable)
                                    FROM aclexplode(
                                        COALESCE(functions.proacl, acldefault('f', functions.proowner))
                                    ) AS privilege
                                    WHERE privilege.grantee = runtime.oid
                                        AND privilege.privilege_type = 'EXECUTE'
                                ),
                                false
                            ) AS runtime_execute_grantable,
                            has_function_privilege(
                                runtime.oid, functions.oid, 'EXECUTE'
                            ) AS runtime_can_execute
                        FROM pg_proc AS functions
                        JOIN pg_roles AS owners
                            ON owners.oid = functions.proowner
                        JOIN pg_roles AS runtime
                            ON runtime.rolname = :runtime_role
                        WHERE functions.oid = to_regprocedure(:signature)
                        """
                    ),
                    {"runtime_role": runtime_role, "signature": signature},
                )
            )
            .mappings()
            .one()
        )
        configuration = row["configuration"]
        states.append(
            _WorkerFunctionState(
                signature=signature,
                owner=str(row["owner"]),
                security_definer=bool(row["security_definer"]),
                configuration=None if configuration is None else tuple(configuration),
                definition=str(row["definition"]),
                public_has_execute=bool(row["public_has_execute"]),
                public_execute_grantable=bool(row["public_execute_grantable"]),
                public_can_execute=bool(row["public_can_execute"]),
                runtime_has_execute=bool(row["runtime_has_execute"]),
                runtime_execute_grantable=bool(row["runtime_execute_grantable"]),
                runtime_can_execute=bool(row["runtime_can_execute"]),
            )
        )
    return tuple(states)


async def _restore_execute_privilege(
    connection: AsyncConnection,
    *,
    signature: str,
    grantee: str,
    current_has_execute: bool,
    current_grantable: bool,
    expected_has_execute: bool,
    expected_grantable: bool,
) -> None:
    if (current_has_execute, current_grantable) == (expected_has_execute, expected_grantable):
        return
    if not expected_has_execute:
        await connection.exec_driver_sql(f"REVOKE EXECUTE ON FUNCTION {signature} FROM {grantee}")
    elif not current_has_execute:
        grant_option = " WITH GRANT OPTION" if expected_grantable else ""
        await connection.exec_driver_sql(f"GRANT EXECUTE ON FUNCTION {signature} TO {grantee}{grant_option}")
    elif expected_grantable:
        await connection.exec_driver_sql(f"GRANT EXECUTE ON FUNCTION {signature} TO {grantee} WITH GRANT OPTION")
    else:
        await connection.exec_driver_sql(f"REVOKE GRANT OPTION FOR EXECUTE ON FUNCTION {signature} FROM {grantee}")


async def _restore_worker_function_states(
    engine: AsyncEngine,
    runtime_role: str,
    expected_states: tuple[_WorkerFunctionState, ...],
) -> None:
    async with engine.begin() as connection:
        current_states = {
            state.signature: state for state in await _snapshot_worker_function_states(connection, runtime_role)
        }
        for expected in expected_states:
            current = current_states[expected.signature]
            if current.owner != expected.owner:
                await connection.exec_driver_sql(
                    f"ALTER FUNCTION {expected.signature} OWNER TO {_quote_identifier(expected.owner)}"
                )
            if current.security_definer != expected.security_definer or current.configuration != expected.configuration:
                await connection.exec_driver_sql(expected.definition)

        current_states = {
            state.signature: state for state in await _snapshot_worker_function_states(connection, runtime_role)
        }
        runtime_grantee = _quote_identifier(runtime_role)
        for expected in expected_states:
            current = current_states[expected.signature]
            await _restore_execute_privilege(
                connection,
                signature=expected.signature,
                grantee="PUBLIC",
                current_has_execute=current.public_has_execute,
                current_grantable=current.public_execute_grantable,
                expected_has_execute=expected.public_has_execute,
                expected_grantable=expected.public_execute_grantable,
            )
            await _restore_execute_privilege(
                connection,
                signature=expected.signature,
                grantee=runtime_grantee,
                current_has_execute=current.runtime_has_execute,
                current_grantable=current.runtime_execute_grantable,
                expected_has_execute=expected.runtime_has_execute,
                expected_grantable=expected.runtime_execute_grantable,
            )

    async with engine.connect() as connection:
        restored_states = await _snapshot_worker_function_states(connection, runtime_role)
    assert restored_states == expected_states


@asynccontextmanager
async def _preserve_worker_function_states(
    engine: AsyncEngine,
    runtime_role: str,
) -> AsyncIterator[None]:
    async with engine.connect() as lock_connection:
        await lock_connection.execute(
            text("SELECT pg_advisory_lock(CAST(:lock_key AS bigint))"),
            {"lock_key": _WORKER_FUNCTION_MUTATION_LOCK_KEY},
        )
        await lock_connection.commit()
        try:
            expected_states = await _snapshot_worker_function_states(lock_connection, runtime_role)
            await lock_connection.commit()
            try:
                yield
            finally:
                await _restore_worker_function_states(engine, runtime_role, expected_states)
        finally:
            if lock_connection.in_transaction():
                await lock_connection.rollback()
            unlocked = await lock_connection.scalar(
                text("SELECT pg_advisory_unlock(CAST(:lock_key AS bigint))"),
                {"lock_key": _WORKER_FUNCTION_MUTATION_LOCK_KEY},
            )
            await lock_connection.commit()
            assert unlocked is True


def test_deployment_database_preflight_accepts_only_restricted_runtime_role_names() -> None:
    arguments = _parser().parse_args(["deployment-database-preflight", "--runtime-role", "revenueos_runtime"])
    assert arguments.runtime_role == "revenueos_runtime"
    with pytest.raises(SystemExit):
        _parser().parse_args(
            [
                "deployment-database-preflight",
                "--runtime-role",
                "revenueos_runtime",
                "--runtime-role",
                "revenueos_runtime",
            ]
        )

    for unsafe_role in (
        "RevenueOS_Runtime",
        "revenueos-runtime",
        "revenueos_runtime;select",
        "a" * 64,
        "",
    ):
        with pytest.raises(argparse.ArgumentTypeError):
            _parse_database_role_name(unsafe_role)


def test_postgresql_preflight_checks_every_worker_discovery_function() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required for worker preflight tests.")

    runtime_role = f"worker_preflight_runtime_{uuid.uuid4().hex}"

    async def scenario() -> None:
        admin_engine = create_async_engine(database_url)
        runtime_engine = None
        role_created = False
        try:
            async with admin_engine.begin() as connection:
                await connection.exec_driver_sql(f'CREATE ROLE "{runtime_role}" NOLOGIN NOSUPERUSER NOBYPASSRLS')
                await connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{runtime_role}"')
                await connection.exec_driver_sql(f'GRANT SELECT ON public.alembic_version TO "{runtime_role}"')
            role_created = True

            runtime_engine = create_async_engine(
                database_url,
                connect_args={"server_settings": {"role": runtime_role}},
            )
            async with _preserve_worker_function_states(admin_engine, runtime_role):
                async with admin_engine.begin() as connection:
                    for signature in WORKER_DISCOVERY_FUNCTION_SIGNATURES:
                        await connection.exec_driver_sql(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
                        await connection.exec_driver_sql(f'GRANT EXECUTE ON FUNCTION {signature} TO "{runtime_role}"')

                ready_checks = await inspect_runtime_database(runtime_engine)
                assert next(check for check in ready_checks if check.name == "database_runtime_role").status == "pass"
                assert (
                    next(check for check in ready_checks if check.name == "database_worker_discovery_authority").status
                    == "pass"
                )

                async with admin_engine.begin() as connection:
                    await connection.exec_driver_sql(
                        f'REVOKE EXECUTE ON FUNCTION {KNOWLEDGE_DISCOVERY_FUNCTION_SIGNATURE} FROM "{runtime_role}"'
                    )
                blocked_checks = await inspect_runtime_database(runtime_engine)
                assert (
                    next(
                        check for check in blocked_checks if check.name == "database_worker_discovery_authority"
                    ).status
                    == "fail"
                )
        finally:
            if runtime_engine is not None:
                await runtime_engine.dispose()
            if role_created:
                async with admin_engine.begin() as connection:
                    await connection.exec_driver_sql(f'DROP OWNED BY "{runtime_role}"')
                    await connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{runtime_role}"')
            await admin_engine.dispose()

    asyncio.run(scenario())


def test_postgresql_deployment_database_preflight_enforces_worker_authority() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required for deployment preflight tests.")

    runtime_role = f"deployment_preflight_{uuid.uuid4().hex}"
    wrong_owner_role = f"deployment_owner_{uuid.uuid4().hex}"

    async def scenario() -> None:
        admin_engine = create_async_engine(database_url)
        runtime_engine = None
        role_created = False
        wrong_owner_created = False
        privileged_membership_granted = False
        try:
            async with admin_engine.begin() as connection:
                await connection.exec_driver_sql(f'CREATE ROLE "{runtime_role}" LOGIN NOSUPERUSER NOBYPASSRLS')
                await connection.exec_driver_sql(f'CREATE ROLE "{wrong_owner_role}" NOLOGIN NOSUPERUSER BYPASSRLS')
                await connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{runtime_role}"')
                await connection.exec_driver_sql(f'GRANT SELECT ON public.alembic_version TO "{runtime_role}"')
                await connection.exec_driver_sql(f'GRANT CREATE ON SCHEMA public TO "{wrong_owner_role}"')
            role_created = True
            wrong_owner_created = True
            runtime_engine = create_async_engine(
                database_url,
                connect_args={"server_settings": {"role": runtime_role}},
            )

            async with _preserve_worker_function_states(admin_engine, runtime_role):
                async with admin_engine.begin() as connection:
                    for signature in WORKER_DISCOVERY_FUNCTION_SIGNATURES:
                        await connection.exec_driver_sql(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
                        await connection.exec_driver_sql(f'GRANT EXECUTE ON FUNCTION {signature} TO "{runtime_role}"')

                ready = await deployment_database_preflight(admin_engine, runtime_role)
                assert ready["status"] == "ready"
                assert {check["name"]: check["status"] for check in ready["checks"]} == {
                    "database_migration_head": "pass",
                    "database_runtime_role": "pass",
                    "database_worker_discovery_authority": "pass",
                }

                async with admin_engine.begin() as connection:
                    await connection.exec_driver_sql(f'GRANT "{wrong_owner_role}" TO "{runtime_role}"')
                privileged_membership_granted = True
                inherited_privilege = await deployment_database_preflight(admin_engine, runtime_role)
                assert inherited_privilege["status"] == "blocked"
                assert (
                    next(check for check in inherited_privilege["checks"] if check["name"] == "database_runtime_role")[
                        "status"
                    ]
                    == "fail"
                )
                inherited_runtime_checks = await inspect_runtime_database(runtime_engine)
                assert (
                    next(check for check in inherited_runtime_checks if check.name == "database_runtime_role").status
                    == "fail"
                )

                async with admin_engine.begin() as connection:
                    await connection.exec_driver_sql(f'REVOKE "{wrong_owner_role}" FROM "{runtime_role}"')
                privileged_membership_granted = False
                restored_runtime_checks = await inspect_runtime_database(runtime_engine)
                assert (
                    next(check for check in restored_runtime_checks if check.name == "database_runtime_role").status
                    == "pass"
                )

                async with admin_engine.begin() as connection:
                    await connection.exec_driver_sql(
                        f'REVOKE EXECUTE ON FUNCTION {KNOWLEDGE_DISCOVERY_FUNCTION_SIGNATURE} FROM "{runtime_role}"'
                    )
                missing_execute = await deployment_database_preflight(admin_engine, runtime_role)
                assert missing_execute["status"] == "blocked"
                assert (
                    next(
                        check
                        for check in missing_execute["checks"]
                        if check["name"] == "database_worker_discovery_authority"
                    )["status"]
                    == "fail"
                )

                async with admin_engine.begin() as connection:
                    await connection.exec_driver_sql(
                        f'GRANT EXECUTE ON FUNCTION {KNOWLEDGE_DISCOVERY_FUNCTION_SIGNATURE} TO "{runtime_role}"'
                    )
                    await connection.exec_driver_sql(
                        f"GRANT EXECUTE ON FUNCTION {KNOWLEDGE_DISCOVERY_FUNCTION_SIGNATURE} TO PUBLIC"
                    )
                public_execute = await deployment_database_preflight(admin_engine, runtime_role)
                assert public_execute["status"] == "blocked"
                assert (
                    next(
                        check
                        for check in public_execute["checks"]
                        if check["name"] == "database_worker_discovery_authority"
                    )["status"]
                    == "fail"
                )

                async with admin_engine.begin() as connection:
                    await connection.exec_driver_sql(
                        f"REVOKE EXECUTE ON FUNCTION {KNOWLEDGE_DISCOVERY_FUNCTION_SIGNATURE} FROM PUBLIC"
                    )
                    await connection.exec_driver_sql(f'ALTER ROLE "{runtime_role}" BYPASSRLS')
                elevated_runtime = await deployment_database_preflight(admin_engine, runtime_role)
                assert elevated_runtime["status"] == "blocked"
                assert (
                    next(check for check in elevated_runtime["checks"] if check["name"] == "database_runtime_role")[
                        "status"
                    ]
                    == "fail"
                )

                async with admin_engine.begin() as connection:
                    await connection.exec_driver_sql(f'ALTER ROLE "{runtime_role}" NOBYPASSRLS NOLOGIN')
                non_login_runtime = await deployment_database_preflight(admin_engine, runtime_role)
                assert non_login_runtime["status"] == "blocked"
                assert (
                    next(check for check in non_login_runtime["checks"] if check["name"] == "database_runtime_role")[
                        "status"
                    ]
                    == "fail"
                )

                async with admin_engine.begin() as connection:
                    await connection.exec_driver_sql(f'ALTER ROLE "{runtime_role}" LOGIN')
                    await connection.exec_driver_sql(
                        f"ALTER FUNCTION {KNOWLEDGE_DISCOVERY_FUNCTION_SIGNATURE} SECURITY INVOKER"
                    )
                unsafe_definition = await deployment_database_preflight(admin_engine, runtime_role)
                assert unsafe_definition["status"] == "blocked"
                assert (
                    next(
                        check
                        for check in unsafe_definition["checks"]
                        if check["name"] == "database_worker_discovery_authority"
                    )["status"]
                    == "fail"
                )

                async with admin_engine.begin() as connection:
                    await connection.exec_driver_sql(
                        f"ALTER FUNCTION {KNOWLEDGE_DISCOVERY_FUNCTION_SIGNATURE} SECURITY DEFINER"
                    )
                    await connection.exec_driver_sql(
                        f"ALTER FUNCTION {KNOWLEDGE_DISCOVERY_FUNCTION_SIGNATURE} SET search_path = public"
                    )
                unsafe_search_path = await deployment_database_preflight(admin_engine, runtime_role)
                assert unsafe_search_path["status"] == "blocked"
                assert (
                    next(
                        check
                        for check in unsafe_search_path["checks"]
                        if check["name"] == "database_worker_discovery_authority"
                    )["status"]
                    == "fail"
                )

                async with admin_engine.begin() as connection:
                    await connection.exec_driver_sql(
                        f"ALTER FUNCTION {KNOWLEDGE_DISCOVERY_FUNCTION_SIGNATURE} SET search_path = pg_catalog, public"
                    )
                    await connection.exec_driver_sql(
                        f'ALTER FUNCTION {KNOWLEDGE_DISCOVERY_FUNCTION_SIGNATURE} OWNER TO "{wrong_owner_role}"'
                    )
                wrong_owner = await deployment_database_preflight(admin_engine, runtime_role)
                assert wrong_owner["status"] == "blocked"
                assert (
                    next(
                        check
                        for check in wrong_owner["checks"]
                        if check["name"] == "database_worker_discovery_authority"
                    )["status"]
                    == "fail"
                )
        finally:
            if runtime_engine is not None:
                await runtime_engine.dispose()
            if role_created or wrong_owner_created:
                async with admin_engine.begin() as connection:
                    if privileged_membership_granted and role_created and wrong_owner_created:
                        await connection.exec_driver_sql(f'REVOKE "{wrong_owner_role}" FROM "{runtime_role}"')
                    if role_created:
                        await connection.exec_driver_sql(f'DROP OWNED BY "{runtime_role}"')
                        await connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{runtime_role}"')
                    if wrong_owner_created:
                        await connection.exec_driver_sql(f'REVOKE CREATE ON SCHEMA public FROM "{wrong_owner_role}"')
                        await connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{wrong_owner_role}"')
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
        discovery_owner_created = False
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

            async with engine.begin() as connection:
                runtime_role = await connection.scalar(text("SELECT current_user"))
                assert isinstance(runtime_role, str)
                await connection.exec_driver_sql(
                    f'CREATE ROLE "{discovery_owner_role}" NOLOGIN NOSUPERUSER NOBYPASSRLS'
                )
                await connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{discovery_owner_role}"')
                await connection.exec_driver_sql(f'GRANT SELECT ON public.ai_jobs TO "{discovery_owner_role}"')
            discovery_owner_created = True

            async with _preserve_worker_function_states(engine, runtime_role):
                assert organisation_id in await first.discover_eligible_organisations()
                async with engine.begin() as connection:
                    await connection.exec_driver_sql(
                        "ALTER FUNCTION public.revenueos_ai_worker_eligible_organisations"
                        f'(timestamptz, integer) OWNER TO "{discovery_owner_role}"'
                    )
                assert organisation_id not in await first.discover_eligible_organisations()
                blocked_checks = await inspect_runtime_database(engine)
                blocked_discovery_check = next(
                    check for check in blocked_checks if check.name == "database_worker_discovery_authority"
                )
                assert blocked_discovery_check.status == "fail"
                async with engine.begin() as connection:
                    await connection.exec_driver_sql(f'ALTER ROLE "{discovery_owner_role}" BYPASSRLS')
                    for signature in WORKER_DISCOVERY_FUNCTION_SIGNATURES:
                        await connection.exec_driver_sql(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")
                assert organisation_id in await first.discover_eligible_organisations()
                ready_checks = await inspect_runtime_database(engine)
                ready_discovery_check = next(
                    check for check in ready_checks if check.name == "database_worker_discovery_authority"
                )
                assert ready_discovery_check.status == "pass"

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
            if discovery_owner_created:
                async with engine.begin() as connection:
                    await connection.exec_driver_sql(f'REVOKE USAGE ON SCHEMA public FROM "{discovery_owner_role}"')
                    await connection.exec_driver_sql(f'REVOKE SELECT ON public.ai_jobs FROM "{discovery_owner_role}"')
                    await connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{discovery_owner_role}"')
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
