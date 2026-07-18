# Application architecture

## Current scope

WO-004A2 keeps the Sprint 3 modular monolith and builds on WO-004A1 with an internal application layer for tenant-owned `infrastructure_test` jobs and append-oriented artefacts. Tenant-scoped repositories, idempotent job creation, lifecycle validation, strict schema validation and metadata-only auditing now exist. It does not add an AI runtime, worker, provider, prompt, API route, UI, recording/media pipeline, connector, billing service or mobile application.

```text
Browser
  │
  ├── Next.js App Router ── server-side route protection
  │
  └── HTTPS /api/v1
              │
              ▼
        FastAPI application
        auth · tenant context · domain services
              │
              ├── AI job/artefact repositories and services
              │   (internal infrastructure_test only)
              │
              ▼
       PostgreSQL / Supabase later
       identity · business records · meetings
       AI jobs/artefacts · audit metadata · RLS
```

## Repository boundaries

- `apps/web` owns web presentation, navigation and server-side access checks.
- `apps/api` owns authentication dependencies, tenant context, application policy, Pydantic contracts and persistence.
- `packages/shared` contains the deliberately small TypeScript view of stable API responses.
- `packages/ui` is reserved for primitives with a real second consumer.
- Alembic is the sole application-schema migration owner.

## Web architecture

Next.js App Router, strict TypeScript and Tailwind CSS provide the responsive web shell. Pages compose application-local components; business rules remain server-side. Protected routes resolve an authentication adapter during server rendering and redirect when it does not provide a complete user and organisation context.

Development auth returns one fixed example user/organisation, provisions that identity only in a migrated development database, and displays a warning banner. Production never provisions or falls back to the mock identity. The Clerk adapter boundary and environment path exist, but Clerk sessions are not connected.

Companies, contacts, opportunities and tasks share list and form components. Meetings use focused list, aggregate form and detail components because participant and transcript state is nested. The detail view exposes accessible Overview, Transcript and History tabs. The browser reads an explicitly selected `.txt` file into the form; no file is uploaded to object storage and no recording or transcription occurs. Components provide loading, empty, safe error and responsive mobile/desktop states. Business validation remains server-side even when HTML constraints improve feedback.

## API architecture

FastAPI exposes:

- `GET /health` for process health;
- `GET /ready` for honest configured-dependency readiness;
- `GET /api/v1/me` for the authenticated identity and active organisation context;
- CRUD collections and resources under `/api/v1/companies`, `/api/v1/contacts`, `/api/v1/opportunities` and `/api/v1/tasks`; and
- meeting, nested participant, singular transcript and audit-history resources under `/api/v1/meetings`.

Routes use Pydantic request/response models, camel-case JSON, bounded pagination, explicit filters/sorts, request IDs, structured content-redacted logs, explicit CORS and central safe error handlers. Route handlers delegate business rules to services and all SQL to repositories. Meeting, participant and transcript services share one tenant-aware repository without introducing a new persistence pattern.

WO-004A2 does not expose AI jobs or artefacts through the API. Its repositories and services are internal seams only and do not start background work.

## Persistence and tenancy

SQLAlchemy 2 models Organisation, User, OrganisationMembership, Company, Contact, Opportunity, Task, Meeting, MeetingParticipant, Transcript, MeetingAuditEvent, AIJob and AIArtifact. UUIDs, UTC timestamps, allowed enum values, bounded numeric values, unique organisation slugs, unique external auth IDs and membership uniqueness are enforced in schema and migrations.

Every tenant-owned row, including meeting children and audit events, has a non-null `organisation_id`. Composite foreign keys include the organisation for company/contact/meeting/participant relationships and membership-owned user fields, so the database cannot attach a record to another tenant even if application validation regresses. Business parent deletes remain restrictive. Meetings, participants and transcripts use `deleted_at`; deleting a meeting soft-deletes its active children in one transaction.

The active organisation originates in the trusted auth adapter, never a body, path or query tenant identifier. Each request sets PostgreSQL's transaction-local `app.organisation_id`; repositories also apply an explicit organisation predicate. Companies, contacts, opportunities, tasks, all four Meeting Domain tables, AI jobs and AI artefacts enable and force RLS. Composite tenant foreign keys reject cross-tenant meeting, transcript, requester, job and artefact references. Runtime deployment must use a non-bypass application role; migration credentials remain separate.

All authenticated organisation members currently have the same entity and meeting CRUD access. Every Meeting Domain request also verifies an active local membership. This is the safest simple interpretation because no entity-level role matrix is specified. A future authorisation change requires an explicit product decision and policy tests.

One active or soft-deleted transcript row is retained per meeting. Mutations lock the meeting aggregate root; transcript corrections also lock the transcript row, compare an optimistic integer `version` and fail stale updates with `409`. Audit events record actor, action, entity identity, changed field names and transcript version, never raw transcript or participant content. The version counter is an extension seam, not transcript snapshot history.

Each AI job captures the exact current transcript version requested; it cannot silently point to a different meeting or transcript. Each AI artefact must match its job's organisation, meeting, transcript and transcript version. Logical artefact versions are unique and earlier content cannot be updated at the database layer; only a one-way `superseded_at` marker may change. The current transcript table still mutates one body in place, so a pinned version number does not yet provide historical source-text reconstruction.

`AIJobService` validates the active meeting/transcript trace, requires a bounded idempotency key, creates a pending infrastructure-test job and applies an explicit lifecycle matrix. Identical requests return the existing job, including after a concurrent unique-key race. Entering `running` consumes an attempt; failed-to-pending preparation preserves the attempt count and clears stale execution metadata. Completed and cancelled jobs are terminal.

`AIArtifactService` accepts only strict schema-version-1 infrastructure-test content, proves its trace matches the tenant-scoped job and assigns the next append-only logical version. A bounded retry resolves one concurrent version race. Job creation, lifecycle changes and artefact creation commit atomically with content-minimised audit events. Audit metadata contains identifiers/type/status/version and optional provider/model labels, never supplied transcript text, artefact content, prompt/model bodies, secrets or raw exceptions.

The API starts without a database so developers can inspect health and the shell, but `/ready` returns `503` and marks persistence unavailable. CRUD routes return a safe service-unavailable response.

## Contracts

FastAPI Pydantic models and OpenAPI are canonical. `packages/shared` mirrors the current response shapes manually and is updated in the same pull request. Client generation remains the intended follow-up when the contract surface makes generation simpler than the manual surface.

## Deployment direction

Vercel is planned for the web application. The API requires a managed Python host that supports a long-running ASGI process, private database connectivity, health/readiness probes, secrets and rolling rollback. Select it in a later ADR; the current system has no production deployment.

Supabase PostgreSQL, Clerk, Supabase Storage, OpenAI and Stripe are planned managed services. Only PostgreSQL-compatible persistence and auth adapter paths exist now.

## Future extension boundaries

Future, separately authorised Meeting Intelligence work can add durable job claiming, provider and prompt abstractions, additional validated structured-output schemas and API/UI lifecycle visibility on top of these internal services. It must keep generated content separate from supplied source text and preserve the exact trace and append-only artefact rules. Conversation recording/capture, storage and external systems will use narrow adapters; long-running work will run outside HTTP requests. A React Native client may later consume the same versioned API; no mobile code is included now.

See [AI database foundation](ai-database-foundation.md) for the schema contract and [AI domain services](ai-domain-services.md) for the current application-layer rules.
