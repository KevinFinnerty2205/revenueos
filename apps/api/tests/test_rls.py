from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from revenueos.ai_repositories import AIJobRepository
from revenueos.ai_services import AIArtifactService, AIJobService
from revenueos.ai_worker_repositories import AIWorkerRepository
from revenueos.domain import AIJobStatus
from revenueos.errors import PublicAPIError
from revenueos.tenant import TenantContext


def test_postgresql_rls_isolates_every_tenant_table() -> None:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql", "postgres")):
        pytest.skip("A PostgreSQL DATABASE_URL is required for the RLS integration test.")

    role_name = f"revenueos_rls_test_{uuid.uuid4().hex[:12]}"
    tenant_tables = (
        "companies",
        "contacts",
        "opportunities",
        "tasks",
        "meetings",
        "meeting_participants",
        "transcripts",
        "meeting_audit_events",
        "ai_jobs",
        "ai_artifacts",
    )
    tenant_a = {
        "suffix": "A",
        "organisation_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "company_id": uuid.uuid4(),
        "contact_id": uuid.uuid4(),
        "opportunity_id": uuid.uuid4(),
        "task_id": uuid.uuid4(),
        "meeting_id": uuid.uuid4(),
        "participant_id": uuid.uuid4(),
        "transcript_id": uuid.uuid4(),
        "audit_id": uuid.uuid4(),
        "ai_job_id": uuid.uuid4(),
        "ai_artifact_id": uuid.uuid4(),
    }
    tenant_b = {
        "suffix": "B",
        "organisation_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "company_id": uuid.uuid4(),
        "contact_id": uuid.uuid4(),
        "opportunity_id": uuid.uuid4(),
        "task_id": uuid.uuid4(),
        "meeting_id": uuid.uuid4(),
        "participant_id": uuid.uuid4(),
        "transcript_id": uuid.uuid4(),
        "audit_id": uuid.uuid4(),
        "ai_job_id": uuid.uuid4(),
        "ai_artifact_id": uuid.uuid4(),
    }

    async def scenario() -> None:
        engine = create_async_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.exec_driver_sql(f'CREATE ROLE "{role_name}" NOLOGIN')
                await connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{role_name}"')
                for table in tenant_tables:
                    await connection.exec_driver_sql(
                        f'GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO "{role_name}"'
                    )

                for tenant in (tenant_a, tenant_b):
                    suffix = str(tenant["suffix"])
                    identity_parameters = {
                        **tenant,
                        "slug": f"rls-{suffix.lower()}-{tenant['organisation_id']}",
                        "external_auth_id": f"rls_{suffix.lower()}_{tenant['user_id']}",
                        "email": f"rls-{suffix.lower()}-{tenant['user_id']}@example.test",
                    }
                    await connection.execute(
                        text(
                            """
                            INSERT INTO organisations (id, name, slug)
                            VALUES (:organisation_id, :name, :slug)
                            """
                        ),
                        {
                            **identity_parameters,
                            "name": f"RLS Organisation {suffix}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO users
                                (id, external_auth_id, email, display_name)
                            VALUES
                                (:user_id, :external_auth_id, :email, :display_name)
                            """
                        ),
                        {
                            **identity_parameters,
                            "display_name": f"RLS User {suffix}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO organisation_memberships
                                (organisation_id, user_id, role)
                            VALUES (:organisation_id, :user_id, 'admin')
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO companies
                                (id, organisation_id, name, status, owner_user_id)
                            VALUES
                                (:company_id, :organisation_id, :company_name,
                                 'prospect', :user_id)
                            """
                        ),
                        {
                            **identity_parameters,
                            "company_name": f"RLS Company {suffix}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO contacts
                                (id, organisation_id, company_id, first_name, last_name,
                                 email, owner_user_id)
                            VALUES
                                (:contact_id, :organisation_id, :company_id, 'RLS',
                                 :suffix, :contact_email, :user_id)
                            """
                        ),
                        {
                            **identity_parameters,
                            "contact_email": f"rls-contact-{suffix.lower()}-{tenant['contact_id']}@example.test",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO opportunities
                                (id, organisation_id, company_id, name, stage, value,
                                 currency, probability, owner_user_id)
                            VALUES
                                (:opportunity_id, :organisation_id, :company_id,
                                 :opportunity_name, 'discovery', :value, 'AUD', 20, :user_id)
                            """
                        ),
                        {
                            **identity_parameters,
                            "opportunity_name": f"RLS Opportunity {suffix}",
                            "value": Decimal("1000.00"),
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO tasks
                                (id, organisation_id, company_id, contact_id, opportunity_id,
                                 title, status, priority, assigned_user_id, created_by_user_id)
                            VALUES
                                (:task_id, :organisation_id, :company_id, :contact_id,
                                 :opportunity_id, :task_title, 'open', 'medium',
                                 :user_id, :user_id)
                            """
                        ),
                        {
                            **identity_parameters,
                            "task_title": f"RLS Task {suffix}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO meetings
                                (id, organisation_id, title, meeting_date, meeting_type,
                                 status, company_id, owner_user_id, created_by, updated_by)
                            VALUES
                                (:meeting_id, :organisation_id, :meeting_title, now(),
                                 'remote', 'completed', :company_id, :user_id,
                                 :user_id, :user_id)
                            """
                        ),
                        {
                            **identity_parameters,
                            "meeting_title": f"RLS Meeting {suffix}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO meeting_participants
                                (id, organisation_id, meeting_id, contact_id, display_name,
                                 email, attendance_status, role)
                            VALUES
                                (:participant_id, :organisation_id, :meeting_id, :contact_id,
                                 :participant_name, :contact_email, 'attended', 'attendee')
                            """
                        ),
                        {
                            **identity_parameters,
                            "participant_name": f"RLS Participant {suffix}",
                            "contact_email": f"rls-participant-{suffix.lower()}-{tenant['participant_id']}@example.test",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO transcripts
                                (id, organisation_id, meeting_id, raw_text, language,
                                 version, source)
                            VALUES
                                (:transcript_id, :organisation_id, :meeting_id,
                                 :raw_text, 'en', 1, 'manual')
                            """
                        ),
                        {
                            **identity_parameters,
                            "raw_text": f"RLS transcript {suffix}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO meeting_audit_events
                                (id, organisation_id, meeting_id, actor_user_id, action,
                                 entity_type, entity_id, changed_fields)
                            VALUES
                                (:audit_id, :organisation_id, :meeting_id, :user_id,
                                 'created', 'meeting', :meeting_id, '["title"]'::json)
                            """
                        ),
                        identity_parameters,
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO ai_jobs
                                (id, organisation_id, meeting_id, transcript_id,
                                 transcript_version, job_type, status, schema_version,
                                 idempotency_key, requested_by_user_id)
                            VALUES
                                (:ai_job_id, :organisation_id, :meeting_id, :transcript_id,
                                 1, 'infrastructure_test', 'pending', 1,
                                 :idempotency_key, :user_id)
                            """
                        ),
                        {
                            **identity_parameters,
                            "idempotency_key": f"rls-job-{suffix.lower()}",
                        },
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO ai_artifacts
                                (id, organisation_id, meeting_id, transcript_id,
                                 transcript_version, job_id, artifact_type,
                                 artifact_version, schema_version, content_json)
                            VALUES
                                (:ai_artifact_id, :organisation_id, :meeting_id,
                                 :transcript_id, 1, :ai_job_id, 'infrastructure_test',
                                 1, 1, '{"status":"ok"}'::json)
                            """
                        ),
                        identity_parameters,
                    )

                savepoint = await connection.begin_nested()
                with pytest.raises(DBAPIError):
                    await connection.execute(
                        text(
                            """
                            INSERT INTO ai_jobs
                                (id, organisation_id, meeting_id, transcript_id,
                                 transcript_version, requested_by_user_id)
                            VALUES
                                (:id, :organisation_id, :meeting_id, :transcript_id,
                                 1, :requested_by_user_id)
                            """
                        ),
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": tenant_a["organisation_id"],
                            "meeting_id": tenant_b["meeting_id"],
                            "transcript_id": tenant_b["transcript_id"],
                            "requested_by_user_id": tenant_a["user_id"],
                        },
                    )
                await savepoint.rollback()

                savepoint = await connection.begin_nested()
                with pytest.raises(DBAPIError):
                    await connection.execute(
                        text(
                            """
                            INSERT INTO ai_artifacts
                                (id, organisation_id, meeting_id, transcript_id,
                                 transcript_version, job_id, artifact_version,
                                 schema_version, content_json)
                            VALUES
                                (:id, :organisation_id, :meeting_id, :transcript_id,
                                 1, :job_id, 99, 1, '{"status":"ok"}'::json)
                            """
                        ),
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": tenant_a["organisation_id"],
                            "meeting_id": tenant_a["meeting_id"],
                            "transcript_id": tenant_a["transcript_id"],
                            "job_id": tenant_b["ai_job_id"],
                        },
                    )
                await savepoint.rollback()

                rls_state = {
                    row.relname: (row.relrowsecurity, row.relforcerowsecurity)
                    for row in (
                        await connection.execute(
                            text(
                                """
                                SELECT relname, relrowsecurity, relforcerowsecurity
                                FROM pg_class
                                WHERE relname IN ('ai_jobs', 'ai_artifacts')
                                """
                            )
                        )
                    )
                }
                assert rls_state == {
                    "ai_jobs": (True, True),
                    "ai_artifacts": (True, True),
                }

            async with engine.connect() as connection:
                transaction = await connection.begin()
                await connection.exec_driver_sql(f'SET LOCAL ROLE "{role_name}"')
                await connection.execute(
                    text("SELECT set_config('app.organisation_id', :organisation_id, true)"),
                    {"organisation_id": str(tenant_a["organisation_id"])},
                )
                for table in tenant_tables:
                    count = await connection.scalar(text(f"SELECT count(*) FROM {table}"))
                    assert count == 1
                company_update = await connection.execute(
                    text("UPDATE companies SET name = 'Blocked' WHERE id = :id"),
                    {"id": tenant_b["company_id"]},
                )
                assert company_update.rowcount == 0
                job_update = await connection.execute(
                    text("UPDATE ai_jobs SET status = 'cancelled' WHERE id = :id"),
                    {"id": tenant_b["ai_job_id"]},
                )
                assert job_update.rowcount == 0
                artifact_update = await connection.execute(
                    text("UPDATE ai_artifacts SET superseded_at = now() WHERE id = :id"),
                    {"id": tenant_b["ai_artifact_id"]},
                )
                assert artifact_update.rowcount == 0

                tenant_context = TenantContext(
                    organisation_id=tenant_a["organisation_id"],
                    user_id=tenant_a["user_id"],
                    role="admin",
                )
                async with AsyncSession(
                    bind=connection,
                    expire_on_commit=False,
                ) as session:
                    repository = AIJobRepository(session)
                    worker_repository = AIWorkerRepository(session)
                    assert (
                        await worker_repository.claim_next(
                            tenant_b["organisation_id"],
                            eligible_at=datetime.now(UTC),
                        )
                        is None
                    )
                    own_queue_job = await worker_repository.claim_next(
                        tenant_a["organisation_id"],
                        eligible_at=datetime.now(UTC),
                    )
                    assert own_queue_job is not None
                    assert own_queue_job.organisation_id == tenant_a["organisation_id"]
                    assert (
                        await repository.get_job(
                            tenant_a["organisation_id"],
                            tenant_b["ai_job_id"],
                        )
                        is None
                    )
                    job_service = AIJobService(
                        session,
                        tenant_context,
                        job_repository=repository,
                    )
                    with pytest.raises(PublicAPIError) as cross_tenant_job:
                        await job_service.transition_job(
                            tenant_b["ai_job_id"],
                            AIJobStatus.RUNNING,
                        )
                    assert cross_tenant_job.value.code == "ai_job_not_found"

                    service_job = await job_service.create_infrastructure_test_job(
                        meeting_id=tenant_a["meeting_id"],
                        transcript_id=tenant_a["transcript_id"],
                        transcript_version=1,
                        idempotency_key="rls-service-job-a",
                    )
                    service_artifact = await AIArtifactService(
                        session,
                        tenant_context,
                        job_repository=repository,
                    ).create_infrastructure_test_artifact(
                        job_id=service_job.id,
                        meeting_id=tenant_a["meeting_id"],
                        transcript_id=tenant_a["transcript_id"],
                        transcript_version=1,
                        schema_version=1,
                        content={
                            "status": "ok",
                            "message": "AI processing infrastructure is operational.",
                        },
                    )
                    assert service_job.organisation_id == tenant_a["organisation_id"]
                    assert service_artifact.organisation_id == tenant_a["organisation_id"]
                    assert service_artifact.artifact_version == 2
                await transaction.commit()

                cross_tenant_inserts = (
                    (
                        """
                        INSERT INTO meetings
                            (id, organisation_id, title, meeting_date, meeting_type,
                             status, owner_user_id, created_by, updated_by)
                        VALUES
                            (:id, :organisation_id, 'Cross tenant', now(), 'remote',
                             'scheduled', :user_id, :user_id, :user_id)
                        """,
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": tenant_b["organisation_id"],
                            "user_id": tenant_b["user_id"],
                        },
                    ),
                    (
                        """
                        INSERT INTO ai_jobs
                            (id, organisation_id, meeting_id, transcript_id,
                             transcript_version, requested_by_user_id)
                        VALUES
                            (:id, :organisation_id, :meeting_id, :transcript_id,
                             1, :requested_by_user_id)
                        """,
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": tenant_b["organisation_id"],
                            "meeting_id": tenant_b["meeting_id"],
                            "transcript_id": tenant_b["transcript_id"],
                            "requested_by_user_id": tenant_b["user_id"],
                        },
                    ),
                    (
                        """
                        INSERT INTO ai_artifacts
                            (id, organisation_id, meeting_id, transcript_id,
                             transcript_version, job_id, artifact_version,
                             schema_version, content_json)
                        VALUES
                            (:id, :organisation_id, :meeting_id, :transcript_id,
                             1, :job_id, 2, 1, '{"status":"ok"}'::json)
                        """,
                        {
                            "id": uuid.uuid4(),
                            "organisation_id": tenant_b["organisation_id"],
                            "meeting_id": tenant_b["meeting_id"],
                            "transcript_id": tenant_b["transcript_id"],
                            "job_id": tenant_b["ai_job_id"],
                        },
                    ),
                )
                for statement, parameters in cross_tenant_inserts:
                    transaction = await connection.begin()
                    await connection.exec_driver_sql(f'SET LOCAL ROLE "{role_name}"')
                    await connection.execute(
                        text("SELECT set_config('app.organisation_id', :organisation_id, true)"),
                        {"organisation_id": str(tenant_a["organisation_id"])},
                    )
                    with pytest.raises(DBAPIError):
                        await connection.execute(text(statement), parameters)
                    await transaction.rollback()
        finally:
            async with engine.begin() as connection:
                for table in (
                    "ai_artifacts",
                    "ai_jobs",
                    "meeting_audit_events",
                    "transcripts",
                    "meeting_participants",
                    "meetings",
                    "tasks",
                    "contacts",
                    "opportunities",
                    "companies",
                ):
                    await connection.execute(
                        text(f"DELETE FROM {table} WHERE organisation_id IN (:organisation_a, :organisation_b)"),
                        {
                            "organisation_a": tenant_a["organisation_id"],
                            "organisation_b": tenant_b["organisation_id"],
                        },
                    )
                cleanup_parameters = {
                    "organisation_a": tenant_a["organisation_id"],
                    "organisation_b": tenant_b["organisation_id"],
                    "user_a": tenant_a["user_id"],
                    "user_b": tenant_b["user_id"],
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
