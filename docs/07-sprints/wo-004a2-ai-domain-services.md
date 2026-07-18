# WO-004A2 — AI Repository, Service, Lifecycle and Audit Foundation

## Objective

Add the internal, tenant-isolated application layer needed to create and manage infrastructure-test AI jobs and validated versioned artefacts without executing AI or exposing a product surface.

## Delivered

- tenant-scoped `AIJobRepository` and `AIArtifactRepository`;
- pending infrastructure-test job creation with required service idempotency;
- safe concurrent duplicate recovery;
- explicit lifecycle transition policy and timestamp/error handling;
- Pydantic infrastructure-test artefact schema version 1;
- exact job/meeting/transcript/version trace validation;
- append-only logical artefact version assignment with bounded conflict recovery;
- atomic metadata-only AI audit events on the existing meeting history table;
- migration `0005_ai_domain_services`;
- SQLite repository/service/migration regression tests and forced-RLS PostgreSQL coverage; and
- architecture, security, API, roadmap and ADR updates.

## Security and tenancy

Organisation and actor identity come only from `TenantContext`. Every repository operation includes an organisation predicate. Existing forced RLS and composite tenant foreign keys remain active. Cross-tenant resource IDs return safe not-found errors, preventing existence disclosure. Audit metadata excludes transcript/artefact content, prompt/model bodies, provider secrets, participant-sensitive data and raw exceptions.

## Validation

The repository gate covers Ruff, formatting, mypy, pytest, PostgreSQL migrations and RLS, Alembic drift, web lint/type/unit/browser tests, production builds, dependency/secret scanning and scope scanning.

Local pre-PR results: Ruff, formatting and mypy passed; pytest reported 98 passed and one PostgreSQL-only test skipped because no local PostgreSQL server was available; Vitest reported 21 passed; Playwright reported 6 passed; SQLite migration upgrade/check/downgrade/re-upgrade passed; secret/scope audit passed; and API/web production builds passed. The draft PR CI is the authoritative PostgreSQL migration, forced-RLS and drift result.

## Explicitly out of scope

No worker, claiming/locking, retry scheduler, provider abstraction, mock provider, OpenAI call, prompt registry, API endpoint, UI, polling, meeting intelligence, recording, transcription, integration, embedding, memory, notification, automation, billing or autonomous agent was added.

## Known limitations

- Internal services have no user-accessible route.
- Retry preparation exists, but scheduling and execution do not.
- Lifecycle transitions are not worker claims and do not lock rows.
- Transcript version pinning does not preserve historical transcript bodies.
- Production customer data remains prohibited until production identity and operational privacy controls are complete.

See [AI domain services](../03-engineering/ai-domain-services.md) and [ADR 0006](../08-decisions/0006-ai-domain-service-boundaries.md).
