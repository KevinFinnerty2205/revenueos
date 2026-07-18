# Application architecture

## Current scope

WO-004C1 keeps the Sprint 3 modular monolith and WO-004A1/A2/B1/B2/B3 AI baseline. The durable worker now runs both its infrastructure test and one current-transcript Executive Summary through immutable prompts/schemas, bounded validation and the no-network mock. A meeting-scoped API and Intelligence tab expose only that capability. There is no real AI provider, additional intelligence schema, recording/media pipeline, connector, billing service or mobile application.

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
              ├── AI job/artefact domain services
              │
      separate AI worker process
      claim · lease · retry · recover · cancel
              │
      prompt/schema registries
      safe render · strict parse/validate
              │
      typed provider contract/registry
      deterministic mock only · no network
              │
              ▼
       PostgreSQL / Supabase later
       identity · business records · meetings
       AI jobs/artefacts · audit metadata · RLS
```

## Repository boundaries

- `apps/web` owns web presentation, navigation and server-side access checks.
- `apps/api` owns authentication dependencies, tenant context, application policy, Pydantic contracts and persistence.
- `apps/api/src/revenueos/worker.py` is a separately deployable worker entry point; it shares domain/persistence modules but never runs inside FastAPI.
- `packages/shared` contains the deliberately small TypeScript view of stable API responses.
- `packages/ui` is reserved for primitives with a real second consumer.
- Alembic is the sole application-schema migration owner.

## Web architecture

Next.js App Router, strict TypeScript and Tailwind CSS provide the responsive web shell. Pages compose application-local components; business rules remain server-side. Protected routes resolve an authentication adapter during server rendering and redirect when it does not provide a complete user and organisation context.

Development auth returns one fixed example user/organisation, provisions that identity only in a migrated development database, and displays a warning banner. Production never provisions or falls back to the mock identity. The Clerk adapter boundary and environment path exist, but Clerk sessions are not connected.

Companies, contacts, opportunities and tasks share list and form components. Meetings use focused list, aggregate form and detail components because participant and transcript state is nested. The detail view exposes accessible Overview, Intelligence, Transcript and History tabs. Intelligence contains only the Executive Summary panel, which safely handles six lifecycle states and polls every three seconds without overlapping requests. The browser reads an explicitly selected `.txt` file into the form; no file is uploaded to object storage and no recording or transcription occurs. Components provide loading, empty, safe error and responsive mobile/desktop states. Business validation remains server-side even when HTML constraints improve feedback.

## API architecture

FastAPI exposes:

- `GET /health` for process health;
- `GET /ready` for honest configured-dependency readiness;
- `GET /api/v1/me` for the authenticated identity and active organisation context;
- CRUD collections and resources under `/api/v1/companies`, `/api/v1/contacts`, `/api/v1/opportunities` and `/api/v1/tasks`; and
- meeting, nested participant, singular transcript and audit-history resources under `/api/v1/meetings`; and
- meeting-scoped POST/GET Executive Summary intelligence at `/api/v1/meetings/{meetingId}/intelligence/executive-summary`.

Routes use Pydantic request/response models, camel-case JSON, bounded pagination, explicit filters/sorts, request IDs, structured content-redacted logs, explicit CORS and central safe error handlers. Route handlers delegate business rules to services and all SQL to repositories. Meeting, participant and transcript services share one tenant-aware repository without introducing a new persistence pattern.

The Executive Summary endpoints expose only normalized product state, safe timestamps/messages and the completed strict schema. Worker ownership, leases, prompts, raw errors and provider responses remain internal. The worker starts only through its separate process entry point; HTTP requests only queue/read work and never generate inline.

## Persistence and tenancy

SQLAlchemy 2 models Organisation, User, OrganisationMembership, Company, Contact, Opportunity, Task, Meeting, MeetingParticipant, Transcript, MeetingAuditEvent, AIJob and AIArtifact. UUIDs, UTC timestamps, allowed enum values, bounded numeric values, unique organisation slugs, unique external auth IDs and membership uniqueness are enforced in schema and migrations.

Every tenant-owned row, including meeting children and audit events, has a non-null `organisation_id`. Composite foreign keys include the organisation for company/contact/meeting/participant relationships and membership-owned user fields, so the database cannot attach a record to another tenant even if application validation regresses. Business parent deletes remain restrictive. Meetings, participants and transcripts use `deleted_at`; deleting a meeting soft-deletes its active children in one transaction.

The active organisation originates in the trusted auth adapter, never a body, path or query tenant identifier. Each request sets PostgreSQL's transaction-local `app.organisation_id`; repositories also apply an explicit organisation predicate. Companies, contacts, opportunities, tasks, all four Meeting Domain tables, AI jobs and AI artefacts enable and force RLS. Composite tenant foreign keys reject cross-tenant meeting, transcript, requester, job and artefact references. Runtime deployment must use a non-bypass application role; migration credentials remain separate.

All authenticated organisation members currently have the same entity and meeting CRUD access. Every Meeting Domain request also verifies an active local membership. This is the safest simple interpretation because no entity-level role matrix is specified. A future authorisation change requires an explicit product decision and policy tests.

One active or soft-deleted transcript row is retained per meeting. Mutations lock the meeting aggregate root; transcript corrections also lock the transcript row, compare an optimistic integer `version` and fail stale updates with `409`. Audit events record actor, action, entity identity, changed field names and transcript version, never raw transcript or participant content. The version counter is an extension seam, not transcript snapshot history.

Each AI job captures the exact current transcript version requested; it cannot silently point to a different meeting or transcript. Each AI artefact must match its job's organisation, meeting, transcript and transcript version. Logical artefact versions are unique and earlier content cannot be updated at the database layer; only a one-way `superseded_at` marker may change. The current transcript table still mutates one body in place, so a pinned version number does not yet provide historical source-text reconstruction.

`AIJobService` validates the active meeting/transcript trace and applies the explicit lifecycle matrix. Infrastructure tests retain caller-provided bounded idempotency keys. Executive Summary equivalence includes meeting, current transcript version, type, prompt version and schema version; repeated active/completed requests return the same job, while failed/cancelled work can create a new ordinal retry and transcript corrections create a new logical job. Entering `running` consumes an attempt; failed-to-pending preparation preserves the attempt count and clears stale execution metadata.

`AIArtifactService` accepts only registered strict schema-version-1 infrastructure-test or Executive Summary content, proves its trace matches the tenant-scoped job and assigns the next append-only logical version. Job creation, lifecycle changes and artefact creation commit atomically with content-minimised audit events. Audit metadata contains identifiers/type/status/version and optional prompt/schema/provider/model labels, never supplied transcript text, artefact content, prompt/model bodies, secrets or raw exceptions.

`AIWorkerService` discovers only opaque organisation IDs through a fixed PostgreSQL scheduler function, then sets one transaction-local tenant context for every queue transaction. Claims and recovery use `FOR UPDATE SKIP LOCKED`; heartbeat updates require exact worker ownership. Execution occurs without an open database transaction. The completion transaction locks the owned running job, rechecks cancellation, stages the validated artefact and commits artefact/audits/completed state atomically. Retries use persisted attempts, bounded exponential backoff and `next_attempt_at`.

`InfrastructureTestExecutor` and `ExecutiveSummaryExecutor` resolve their prompt/schema pairs and invoke the configured `mock` / `mock-infrastructure-v1` adapter. Executive Summary loads only the exact current tenant transcript pinned by the job, enforces 50,000 characters without truncation and renders transcript/title as JSON-delimited untrusted data. Only complete JSON objects that pass the registered strict Pydantic schema can reach artefact persistence. Malformed, non-object and schema-invalid output may retry within one execution up to a small configured limit; exhaustion is non-retryable, while transient provider errors continue through the durable worker retry path. The mock can process the transcript deterministically but makes no network call, so customer content does not leave the application.

Existing AI job fields persist prompt/schema/provider/model/request trace, zero mock token usage, zero integer cost and `AUD`; artefacts copy exact labels. Migration `0007_executive_summary` changes only the existing job/artefact type checks to accept `executive_summary`; table shape, forced RLS, composite keys and immutability guards remain unchanged.

The API starts without a database so developers can inspect health and the shell, but `/ready` returns `503` and marks persistence unavailable. CRUD routes return a safe service-unavailable response.

## Contracts

FastAPI Pydantic models and OpenAPI are canonical. `packages/shared` mirrors the current response shapes manually and is updated in the same pull request. Client generation remains the intended follow-up when the contract surface makes generation simpler than the manual surface.

## Deployment direction

Vercel is planned for the web application. The API requires a managed Python host that supports a long-running ASGI process, and the worker requires an independently supervised long-running process from the same release. Both need private database connectivity, secrets and rolling rollback. Select hosting in a later ADR; the current system has no production deployment.

Supabase PostgreSQL, Clerk, Supabase Storage, OpenAI and Stripe are planned managed services. Only PostgreSQL-compatible persistence and auth adapter paths exist now.

## Future extension boundaries

Future, separately authorised Meeting Intelligence work can add a real provider adapter or additional immutable prompt/schema pairs on top of the durable worker. It must define source evidence, prompt-injection controls, evaluation thresholds and privacy terms; keep vendor SDK types behind the provider port and generated content separate from supplied source text; and preserve exact trace, RLS, short-transaction and append-only artefact rules. Conversation recording/capture, storage and external systems will use narrow adapters. A React Native client may later consume the same versioned API; no mobile code is included now.

See [AI database foundation](ai-database-foundation.md), [AI worker and durable job queue](ai-worker-queue.md), [AI provider abstraction](ai-provider-abstraction.md), [prompt registry and structured output](prompt-registry-and-structured-output.md) and [Executive Summary intelligence](executive-summary-intelligence.md).
