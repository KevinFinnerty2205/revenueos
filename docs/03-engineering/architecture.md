# Application architecture

## Create trust boundary (WO-039B)

The modular monolith now treats every uploaded PPTX as an untrusted ZIP/XML package
and every generated PPTX as untrusted until a second bounded parse proves the render
expectations. Migration `0049_create_trust` stores versioned compatibility/output-
validation state and forced-RLS, one-time download grants. The API remains the only
download boundary: it rechecks membership, approval and checksum, then reads private
storage server-side. No Office process, new service, datastore, provider or direct
browser storage access was added. See the
[Create trust architecture](create-pptx-trust-architecture.md) and
[ADR 0063](../08-decisions/0063-create-versioned-pptx-validation-and-download-grants.md).

## Native CRM Foundation (WO-034)

The modular monolith now treats existing Company, Contact and Opportunity as the
only native CRM records. Migration `0043_native_crm` adds one tenant setting, bounded
typed custom-field definitions/values, field-change history, strong dedupe indexes
and archive/core-field extensions. Existing activity tables are composed into a
bounded read model; there is no CRM Activity/Task/Note/Lead or service. Native and
external HubSpot modes share canonical IDs and the WO-025C authority model. See
[Native CRM architecture](native-crm-architecture.md).

## Engage Events (WO-031)

The modular monolith adds six tenant-owned Event tables and a nullable Event link on
Interaction. Engage services own manual Event CRUD, safe attendee preview/import,
planning, encounters, promotion and outreach handoff; existing Core, Prospect,
Outreach and Campaign services keep their own truth and execution policy. Set-based
matching and bounded synchronous CSV processing require no queue, provider or new
datastore. Migration `0040_event_intelligence` enforces composite tenant keys and
forced RLS. See [Event domain architecture](event-domain-architecture.md).

## Engage Campaigns & Sequences (WO-030)

The modular monolith adds six tenant-owned Campaign tables and a bounded Campaign
scheduler inside the existing durable worker. Campaign services own explicit
audience/version/lifecycle policy; WO-029 owns exact Outreach composition/versioning;
WO-021/022 own approval, preview, execution idempotency and adapter receipts. No
microservice, broker, datastore, AI provider call or direct mail adapter was added.

Migration `0039_campaign_sequences` enforces composite tenant relationships, forced
RLS, table caps and published audience/sequence/version immutability. PostgreSQL
worker discovery returns opaque organisation IDs; claims/recovery execute under
trusted tenant context. Production and missing sender-bound mailbox conditions fail
closed. See [Campaign domain architecture](campaign-domain-architecture.md) and
[scheduler architecture](campaign-scheduling-architecture.md).

## Engage personalised outreach (WO-029)

The modular monolith now contains an entitled, Contact-scoped one-to-one outreach
slice. Five tenant tables persist organisation policy, outreach aggregates, immutable
versions, immutable source references and HMAC-addressed suppressions. Every table
uses composite tenant relationships, explicit repository predicates and forced
PostgreSQL RLS. Migration `0038_personalized_outreach` owns the schema.

The slice reuses canonical Contact/Company/User, eligible Prospect provenance,
versioned Action review and the Execution Foundation. Sender/recipient/content are
server-pinned; approval remains distinct from exact preview and confirmation. Mock
Email is deterministic and unavailable in production. No mailbox OAuth/provider or
tracking exists. WO-030 now reuses these records for bounded Campaign sequences and
the existing worker process. See the
[architecture guide](personalised-outreach-architecture.md).

## Prospect Person Intelligence (WO-027)

The modular monolith now includes a company-scoped Prospect Person research slice.
It reuses the FastAPI Prospect module, PostgreSQL-compatible Prospect worker and
immutable run/source/observation pipeline. Five new tenant tables use composite
organisation relationships and forced RLS. A provider-neutral typed interface is
implemented with deterministic mock data only; there is no live provider, scraper,
new datastore or queue.

Prospect Person remains outside Core Contact until an explicit duplicate-safe
promotion transaction. That transaction writes only Contact and field provenance.
Evidence, Methodology, Stakeholder Intelligence, Revenue Brain, Ask RevenueOS and
outreach do not consume WO-027 research.

## Current scope

WO-011 adds Interaction as the authoritative source for shared customer-event
metadata while retaining Meeting as a stable one-to-one compatibility projection.
It adds tenant-owned Capture Session, metadata-only Evidence and Interaction audit
tables, a minimal API and small web timeline. That work order added no capture
execution, new AI job, prompt, provider path, recording or transcription.

WO-012 adds immutable deterministic Pre-Interaction Briefs. WO-013 adds the first
executed post-interaction Capture Session slice: bounded AI Debrief and foreground
Voice Journal, strict foreground question/extraction requests through the existing
structured-output provider abstraction, a separate narrow transcription boundary,
reviewed salesperson-reported Evidence and additive source-aware Interaction/Revenue
Brain snapshots. Raw audio is never persisted and existing Meeting Intelligence is
unchanged. See [AI Debrief](ai-debrief.md) and
[ADR 0028](../08-decisions/0028-bounded-foreground-debrief-reasoning.md).

WO-014 adds private visual-evidence capture/review and WO-015 adds optional,
consent-gated browser audio chunks plus batch transcription through the existing
worker. WO-016 composes those capabilities with the brief and debrief on one
responsive Companion route, adds metadata-only Interaction markers and projects the
latest capture state into Opportunity Workspace. It adds no service, broker,
datastore, native/PWA client or new AI provider path.

WO-021 adds review-only Action proposals. WO-022 adds organisation connections,
server-authoritative connector capabilities, fingerprinted execution previews and
immutable confirmed execution intent. The existing worker also claims these rows
and invokes deterministic mock `ActionExecutor` adapters. No service, broker,
production connector, OAuth exchange or live external request was added. See
[connector architecture](connector-architecture.md) and
[ADR 0034](../08-decisions/0034-simulation-first-execution-boundary.md).

WO-006A/WO-006B/WO-006C/WO-006D/WO-007/WO-008A/WO-008B keep the Sprint 3 modular monolith and
WO-004A1/A2/B1/B2/B3/C1/C1A/C2/C3/C4/C5/C6 and WO-005 baseline. The durable worker runs
its infrastructure test plus current-transcript Executive Summary, Decisions,
Action Items, Risks & Blockers, Open Questions, Buying Signals, Objections &
Competitive Signals and Stakeholder Intelligence through
immutable prompts/schemas and bounded validation. It composes Next Best Action
from all eight validated extraction artefacts and Follow-up Email from the four
validated customer-safe artefacts other than Risks & Blockers; that path never
queries or transmits transcript text. Neither composer queries or transmits
transcript text. The selected provider is either the
default no-network mock or a server-only OpenAI Responses API adapter. Meeting-
scoped APIs and one derived Meeting Intelligence workspace expose those
independent capabilities without combining their persistence. Buying Signals
derives evidence-backed qualitative momentum, Objections derives qualitative
pressure and Stakeholder Intelligence derives cautious roles and coverage for
the current meeting only. Next Best Action adds grounded recommendations
without operational authority; none predicts outcomes or scores the deal.
After a completed account-linked meeting has all nine validated current-
revision artefacts, the same worker atomically appends one Revenue Brain
composition that stores their IDs only. The account page exposes an ordered
meeting-date snapshot timeline. WO-008B deterministically compares bounded
adjacent eligible snapshots on demand for account or opportunity scope, stores
the controlled evidence-backed result immutably and never reads a transcript or
calls a provider.
WO-007 derives an Opportunity Workspace from manually managed opportunity
metadata and the latest associated meeting's stored current-version artefacts.
That path selects transcript identity/version metadata only, performs no AI
work and labels every result as latest-meeting evidence. Revenue Brain records
the meeting's explicit opportunity association when present and never infers
one. There is no email-send integration, later intelligence schema, question-answering
workflow, connector, billing service or mobile application. Browser media capture
is foreground-only and private binary storage continues through narrow adapters.

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
              ├── Action execution service
              │     approved version · preview · explicit confirmation
              │
              ├── Interaction/debrief domain services
              │     bounded foreground prompt/schema/provider requests
              │     narrow ephemeral voice transcription
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
      mock (default) or server-side OpenAI
              │
      ActionExecutor registry
      deterministic mock email/calendar/CRM/task only
              │
              ▼
       PostgreSQL / Supabase later
       identity · business records · interactions · meetings
       AI jobs/artefacts · Revenue Brain snapshots/insights
       audit metadata · RLS
```

## Repository boundaries

- `apps/web` owns web presentation, navigation and server-side access checks.
- `apps/api` owns authentication dependencies, tenant context, application policy, Pydantic contracts and persistence.
- `apps/api/src/revenueos/worker.py` is a separately deployable worker entry point; it shares domain/persistence modules, processes both AI jobs and confirmed simulations, and never runs inside FastAPI.
- `packages/shared` contains the deliberately small TypeScript view of stable API responses.
- `packages/ui` is reserved for primitives with a real second consumer.
- Alembic is the sole application-schema migration owner.

## Web architecture

Next.js App Router, strict TypeScript and Tailwind CSS provide the responsive web shell. Pages compose application-local components; business rules remain server-side. Protected routes resolve an authentication adapter during server rendering and redirect when it does not provide a complete user and organisation context.

Development auth returns one fixed example user/organisation, provisions that
identity only in a migrated development database, and displays a warning
banner. Production never provisions or falls back to the mock identity. Clerk
middleware resolves the server session and active organisation; the API
verifies the RS256 JWT issuer, audience, lifetime and organisation claim, then
deterministically projects active users, organisations and admin/member
memberships. Client-supplied organisation IDs never establish tenant context.

WO-025 adds a thin Home client over one FastAPI Daily aggregate. Application policy
combines bounded set-based repository reads; optional sources degrade independently
through savepoints. The aggregate performs no AI/provider work, raw Evidence load,
new persistence or cache. Browser focus and local-midnight refresh replace polling.

WO-009 keeps beta controls inside the modular monolith. Seven focused
tenant-owned tables store retention, notice acknowledgement, onboarding, UTC
usage counters, feedback, data requests and safe events. Explicit predicates,
composite relationships and forced RLS apply. Retention/export/deletion remain
separately invoked bounded maintenance commands; no scheduler or service was
added. See [ADR 0025](../08-decisions/0025-private-beta-operational-controls.md).

Companies, contacts, opportunities and tasks share form conventions.
Opportunities use a focused enriched list and workspace that reuse product-safe
intelligence renderers; Meeting Detail links back to its associated opportunity.
A company account page exposes the Revenue Brain snapshot timeline and bounded
adjacent comparison summaries. Both account and opportunity surfaces can
explicitly request deterministic reasoning and render dates, qualitative
changes and source labels without raw evidence IDs, graphs or scores. Meetings
use focused list, aggregate form and detail components because participant and
transcript state is nested. The detail view exposes accessible Overview,
Intelligence, Transcript and History tabs. Intelligence is one ordered,
responsive workspace over Executive Summary, Buying Signals & Deal Momentum,
Objections & Competitive Signals, Stakeholders, Next Best Action, Key
Decisions, Action Items, Risks & Blockers, Open Questions and Follow-up Email.
One non-overlapping three-second aggregate polling chain terminates when idle or
on unmount, resumes after generation/retry and uses sequence guards against
stale responses. Shared section treatment covers unavailable, not-generated,
queued, processing, completed/valid-empty, failed and cancelled states while
preserving completed content during partial failures. Stakeholders uses textual
coverage and cautious role labels, with no graph or score. Next Best Action is
read-only; Follow-up Email retains tone, plain-text Copy and deliberate
Regenerate, but no Send. The browser reads an explicitly selected `.txt` file
into the meeting form; no file is uploaded to object storage. Completed
Interactions can use one deliberately started, foreground-only bounded voice
segment with pause/resume/stop/cancel and typed fallback. The API discards raw
audio after transcription. Components provide loading, empty, safe error and
responsive mobile/desktop states. Business validation remains server-side even
when HTML constraints improve feedback.

The Interaction pages add accessible list/search/type/status filters, manual
creation, detail and idempotent completion. Meeting pages add only an
`Interaction record` link; their routes, tabs and intelligence experience remain
unchanged.

## API architecture

FastAPI exposes:

- `GET /health` for process health;
- `GET /ready` for honest configured-dependency readiness;
- `GET /api/v1/me` for the authenticated identity and active organisation context;
- `GET /api/v1/daily` for the bounded tenant/user-scoped RevenueOS Daily Home projection;
- CRUD collections and resources under `/api/v1/companies`, `/api/v1/contacts`, `/api/v1/opportunities` and `/api/v1/tasks`;
- an enriched opportunity list, aggregate read at `/api/v1/opportunities/{opportunityId}/workspace` and stale-write-safe meeting association at `/api/v1/meetings/{meetingId}/opportunity`;
- meeting, nested participant, singular transcript and audit-history resources under `/api/v1/meetings`;
- list/create/read/update/complete resources under `/api/v1/interactions`;
- meeting-scoped POST/GET for Executive Summary, Buying Signals, Objections & Competitive Signals, Stakeholder Intelligence, Next Best Action, Decisions, Action Items, Risks & Blockers, Open Questions and Follow-up Email;
- aggregate current-version GET at `/api/v1/meetings/{meetingId}/intelligence`; and
- idempotent generation orchestration POST at `/api/v1/meetings/{meetingId}/intelligence/generate`; and
- reference-only Revenue Brain timeline GET at `/api/v1/accounts/{accountId}/brain`; and
- account/opportunity POST/GET Revenue Brain reasoning endpoints under
  `/brain/reasoning`.

Routes use Pydantic request/response models, camel-case JSON, bounded pagination, explicit filters/sorts, request IDs, structured content-redacted logs, explicit CORS and central safe error handlers. Route handlers delegate business rules to services and all SQL to repositories. Meeting, participant and transcript services share one tenant-aware repository without introducing a new persistence pattern.

The intelligence endpoints expose only normalised product state, safe timestamps/messages and the completed strict schema. Worker ownership, leases, prompts, raw errors and provider responses remain internal. The worker starts only through its separate process entry point; HTTP requests only queue/read work and never generate inline.

## Persistence and tenancy

SQLAlchemy 2 models Organisation, User, OrganisationMembership, Company,
Contact, Opportunity, OpportunityAuditEvent, Task, Meeting,
MeetingParticipant, Transcript, MeetingAuditEvent, Interaction, CaptureSession,
Evidence, InteractionAuditEvent, AIJob, AIArtifact, RevenueBrainSnapshot and
RevenueBrainInsight. UUIDs, UTC timestamps, allowed
enum values, bounded numeric values, unique organisation slugs, unique external
auth IDs and membership uniqueness are enforced in schema and migrations.

Every tenant-owned row, including meeting children and audit events, has a non-null `organisation_id`. Composite foreign keys include the organisation for company/contact/meeting/participant/opportunity relationships and membership-owned user fields, so the database cannot attach a record to another tenant even if application validation regresses. A meeting has one nullable `opportunity_id`; association writes lock the row, compare its timestamp and audit both aggregates. Business parent deletes remain restrictive. Meetings, participants and transcripts use `deleted_at`; deleting a meeting soft-deletes its active children in one transaction.

The active organisation originates in the trusted auth adapter, never a body,
path or query tenant identifier. Each request sets PostgreSQL's
transaction-local `app.organisation_id`; repositories also apply an explicit
organisation predicate. Companies, contacts, opportunities, tasks, all four
Meeting Domain tables, all four WO-011 Interaction foundation tables, AI jobs,
AI artefacts, Revenue Brain snapshots and Revenue Brain insights enable and force
RLS. Composite tenant foreign keys reject cross-tenant Interaction, Meeting,
Evidence, Capture Session, transcript, requester, job, artefact, snapshot and
insight references. Runtime deployment must use a non-bypass application role;
migration credentials remain separate.

All authenticated organisation members currently have the same entity,
Interaction and Meeting mutation access. Every Interaction and Meeting request
also verifies an active local membership. This is the safest simple interpretation
because no entity-level role matrix is specified. A future authorisation change
requires an explicit product decision and policy tests.

One active or soft-deleted transcript row is retained per meeting. Mutations lock the meeting aggregate root; transcript corrections also lock the transcript row, compare an optimistic integer `version` and fail stale updates with `409`. Audit events record actor, action, entity identity, changed field names and transcript version, never raw transcript or participant content. The version counter is an extension seam, not transcript snapshot history.

Each AI job captures the exact current transcript version requested; it cannot silently point to a different meeting or transcript. Each AI artefact must match its job's organisation, meeting, transcript and transcript version. Logical artefact versions are unique and earlier content cannot be updated at the database layer; only a one-way `superseded_at` marker may change. The current transcript table still mutates one body in place, so a pinned version number does not yet provide historical source-text reconstruction.

`AIJobService` validates the active meeting/transcript trace and applies the explicit lifecycle matrix. Infrastructure tests retain caller-provided bounded idempotency keys. Executive Summary, Buying Signals, Objections & Competitive Signals, Stakeholder Intelligence, Decisions, Action Items, Risks & Blockers and Open Questions each use meeting, current transcript version, job type, prompt version and schema version for equivalence; repeated active/completed requests return the same capability job, while failed/cancelled work can create a new ordinal retry and transcript corrections create new logical work. Next Best Action additionally pins the complete eight-artefact source trace and reuses equivalent active/completed work. Follow-up Email uses the validated source artefact version, type, prompt/schema and tone for active-work equivalence; completed work can be deliberately regenerated into a new append-only job. Entering `running` consumes an attempt; failed-to-pending preparation preserves the attempt count and clears stale execution metadata.

`MeetingIntelligenceService` derives the aggregate view in bounded tenant-scoped
queries and invokes those existing request methods for unified generation. It
restores the transaction-local tenant setting across service commits and relies
on the existing meeting lock plus unique idempotency keys for concurrency. The
overall state is never stored. The browser calls the same safe orchestration
endpoint when the aggregate state proves composer prerequisites are ready; no
workflow engine or synchronous provider path is introduced.

`AIArtifactService` accepts only registered strict schema-version-1 infrastructure-test, Executive Summary, Buying Signals, Objections & Competitive Signals, Stakeholder Intelligence, Next Best Action, Decisions, Action Items, Risks & Blockers, Open Questions or Follow-up Email content, proves its trace matches the tenant-scoped job and assigns the next append-only logical version. Job creation, lifecycle changes and artefact creation commit atomically with content-minimised audit events. Audit metadata contains identifiers/type/status/version, optional prompt/schema/provider/model/tone labels and content-free item/count flags, never supplied transcript text, generated recommendation/reasoning/signal/objection/competitor/stakeholder/email/question/risk/task/owner/evidence content, artefact content, prompt/model bodies, secrets or raw exceptions.

`AIWorkerService` discovers only opaque organisation IDs through a fixed PostgreSQL scheduler function, then sets one transaction-local tenant context for every queue transaction. Claims and recovery use `FOR UPDATE SKIP LOCKED`; heartbeat updates require exact worker ownership. Execution occurs without an open database transaction. The completion transaction locks the owned running job, rechecks cancellation, stages the validated artefact and commits artefact/audits/completed state atomically. Required intelligence completions also lock the meeting and attempt one Revenue Brain composition in that transaction; missing/invalid/failed/cancelled prerequisites create nothing. Retries use persisted attempts, bounded exponential backoff and `next_attempt_at`.

`InfrastructureTestExecutor`, `ExecutiveSummaryExecutor`, `DecisionsExecutor`,
`ActionItemsExecutor`, `RisksBlockersExecutor`, `OpenQuestionsExecutor`,
`BuyingSignalsExecutor`, `ObjectionsCompetitiveSignalsExecutor`,
`StakeholderIntelligenceExecutor`, `NextBestActionComposer` and
`FollowUpEmailComposer` resolve their prompt/schema pairs and invoke exactly the
configured provider. Transcript intelligence loads only the exact current
tenant transcript pinned by the job,
enforces 50,000 characters without truncation and renders transcript/title as
JSON-delimited untrusted data. The provider request carries the registry-derived
strict JSON Schema. Only complete JSON objects that pass the registered strict
Pydantic schema can reach artefact persistence. Malformed, non-object and
schema-invalid output may retry within one execution up to a small configured
limit; exhaustion is non-retryable, while transient provider errors continue
through the durable worker retry path.

The Next Best Action Composer checks content-free transcript audit metadata and
loads all eight validated current-version extraction artefacts. Its typed
provider input has no transcript field, Follow-up Email is excluded and an
exact-reference grounding check verifies all reasoning and dependencies before
persistence.

The Follow-up Email Composer instead checks content-free transcript audit
version metadata and loads only the pinned validated Executive Summary,
Decisions, Action Items and Open Questions artefacts. Its typed provider input
has no transcript field. Risks & Blockers are excluded, and post-provider
grounding requires every factual field and tone to match the source projection
exactly before persistence.

The mock processes the transcript deterministically with no network call. The
OpenAI adapter uses the official asynchronous Responses API with strict
`json_schema`, `store=false`, no tools and no streaming. Enabling it sends the
rendered instructions and selected transcript to OpenAI for the eight
transcript-grounded extractors. Next Best Action sends only its eight validated
extraction artefacts; Follow-up Email sends only its validated customer-safe
source projection and tone. SDK types remain inside the adapter
and SDK retries are disabled so the durable worker remains the retry authority.

Existing AI job fields persist prompt/schema/provider/model/request trace,
available token usage, integer cost and `AUD`; artefacts copy exact labels.
OpenAI estimated cost remains zero/not calculated because no approved pricing
source exists. Migration `0032_integration_execution` is the current head migration.
Migration `0026_face_to_face_companion` added forced-RLS, tenant-isolated,
metadata-only Interaction markers and their
append-only/soft-delete guard. Migration `0025_recording_transcription` added
forced-RLS recording/consent/chunk/usage and immutable transcript version/segment
tables, after `0024_visual_evidence` added forced-RLS visual asset/candidate
metadata, review guards, storage lifecycle state and the `observed` evidence support
class. `0024` follows
`0023_ai_debrief_voice_journal`, which
follows `0021_interaction_foundation` and adds immutable, forced-RLS
Pre-Interaction Brief persistence with composite tenant keys and source-fingerprint
idempotency. `0021` follows `0020_private_beta_readiness`, adds the four Interaction
foundation tables and deterministic Meeting link/backfill. `0020` adds the focused tenant-owned
private-beta control tables, identity/status metadata and approved maintenance
deletion path described above. `0019_revenue_brain_reasoning` follows
`0017_opportunity_workspace`, which expands Opportunity metadata and indexes,
adds the nullable organisation-safe meeting association and creates metadata-
only Opportunity audit events with forced RLS. `0018_revenue_brain` adds the
immutable, forced-RLS Revenue Brain composition table and its append-only
guards. `0019_revenue_brain_reasoning` adds immutable account/opportunity
comparison records with a versioned idempotency key, forced RLS and append-only
guards. `0016_next_best_action` widened job/artefact type checks for Next Best
Action; `0015_stakeholders` added
Stakeholder Intelligence, and `0014_objections` added
Objections & Competitive Signals, `0013_buying_signals` added Buying Signals and `0012_follow_up_email` added the
guarded nullable composition-tone column.
Forced RLS, composite tenant keys and indexes remain unchanged.

The API starts without a database so developers can inspect health and the shell, but `/ready` returns `503` and marks persistence unavailable. CRUD routes return a safe service-unavailable response.

## Contracts

FastAPI Pydantic models and OpenAPI are canonical. `packages/shared` mirrors the current response shapes manually and is updated in the same pull request. Client generation remains the intended follow-up when the contract surface makes generation simpler than the manual surface.

## Deployment direction

Vercel is planned for the web application. The API requires a managed Python host that supports a long-running ASGI process, and the worker requires an independently supervised long-running process from the same release. Both need private database connectivity, secrets and rolling rollback. Select hosting in a later ADR; the current system has no production deployment.

Supabase PostgreSQL, Clerk, Supabase Storage, OpenAI and Stripe are planned
managed services. PostgreSQL-compatible persistence, auth adapter paths and the
server-side OpenAI provider exist now. Production hosting and customer-content
enablement are not approved.

## Future extension boundaries

## WO-014 visual evidence extension

The modular monolith now includes a `VisualEvidenceService`, tenant-explicit
repository, private storage adapter and strict visual provider adapter. Local
and CI bytes use private filesystem storage; production configuration requires
private S3-compatible storage. The API owns upload grants, sanitisation,
analysis state, review and deletion. The browser never receives object-store
credentials and does not write directly to the database.

Migration `0024_visual_evidence` adds metadata/candidate tables with forced RLS
and composite tenant relationships. Image bytes remain outside the application
database. A separate media service, queue or datastore was not introduced.

## WO-015 recording and transcription extension

The modular monolith now includes a Recording Service/repository, private chunk
storage through the established binary adapter, a focused Transcription Provider
port and Recording Worker stages in the existing worker. Recording Session state is
the durable queue input; no broker or second worker service was added. Audio remains
outside PostgreSQL and is streamed to bounded temporary disk during assembly.
Immutable transcript versions and segments feed the current Meeting transcript/read
model without duplicating Meeting Intelligence.

## WO-016 browser Companion extension

The web app adds a thin `/interactions/{id}/companion` orchestrator over existing
services. Phase is derived from Interaction lifecycle rather than persisted as a
second state machine. `CompanionService` owns marker policy and tenant-explicit
persistence; the core Interaction service owns idempotent start/complete changes.
The recording client retains stable per-chunk idempotency keys during bounded retry,
reports interruption and connectivity state, and blocks Interaction completion while
recording or queued chunks remain. The Wake Lock API is best effort only.

Migration `0026_face_to_face_companion` adds only metadata marker persistence.
Marker text is not accepted: the contract permits a controlled marker type,
Interaction timestamp, optional recording offset and idempotency key. Markers are
included in export and approved deletion/reset paths but excluded from content logs.
See the [Companion lifecycle](companion-state-lifecycle-guide.md),
[recording UX](mobile-browser-recording-ux-guide.md) and
[security review](companion-security-review.md).

## WO-020 Live Interaction Intelligence extension

The modular monolith now includes a separate tenant-owned live aggregate and focused
repository/service/provider boundary. The browser polls bounded endpoints; the API
owns the progressive-segment cursor, overlap, dedupe, quotas and lifecycle. The
detector is deterministic and no-network. No broker, WebSocket platform, cache or
second worker was introduced.

Live sessions/signals/progress are separate from immutable final Interaction
Intelligence and Revenue Brain models. Completion freezes the live session and final
reconciliation annotates only that live history. See the
[provisional/final architecture](live-intelligence-provisional-final-architecture.md)
and [ADR 0032](../08-decisions/0032-separate-polled-live-intelligence-aggregate.md).

WO-010 defines the target direction and WO-011 implements the first additive
foundation: Interaction is the source-neutral logical parent and Meeting remains a
compatible projection. Capture Session and metadata-only Evidence separate customer
events from future recording, AI Debrief, Voice Journal, visual and document/email
acquisition. Migration is additive:
existing Meeting IDs/APIs, AI artefacts, Opportunity Workspace and immutable Revenue
Brain history remain unchanged. See the
[Interaction domain architecture](interaction-domain-architecture.md),
[evidence and provenance model](evidence-and-provenance-model.md) and
[migration strategy](interaction-intelligence-migration-strategy.md). Later generic
Interaction Intelligence breadth and external/live provider integrations remain
future work.

Future, separately authorised Meeting or Interaction Intelligence work can add additional
immutable prompt/schema pairs or providers on top of the durable worker. It must
define source evidence, prompt-injection controls, evaluation thresholds and
privacy terms; keep vendor SDK types behind the provider port and generated
content separate from supplied source text; and preserve exact trace, RLS,
short-transaction and append-only artefact rules. Conversation
recording/capture, storage and external systems will use narrow adapters. A
React Native client may later consume the same versioned API; no mobile code is
included now.

See [AI database foundation](ai-database-foundation.md),
[AI worker and durable job queue](ai-worker-queue.md),
[AI provider abstraction](ai-provider-abstraction.md),
[OpenAI provider integration](openai-provider-integration.md),
[prompt registry and structured output](prompt-registry-and-structured-output.md),
[Executive Summary intelligence](executive-summary-intelligence.md),
[Meeting Decisions intelligence](meeting-decisions-intelligence.md),
[Meeting Action Items intelligence](meeting-action-items-intelligence.md),
[Meeting Risks & Blockers intelligence](meeting-risks-blockers-intelligence.md),
[Meeting Open Questions intelligence](meeting-open-questions-intelligence.md),
[Buying Signals & Deal Momentum intelligence](buying-signals-intelligence.md),
[Objections & Competitive Signals intelligence](objections-competitive-signals-intelligence.md),
[Stakeholder Intelligence](stakeholder-intelligence.md),
[Next Best Action Intelligence](next-best-action-intelligence.md),
[Revenue Brain foundation](revenue-brain-foundation.md),
[Revenue Brain longitudinal reasoning](revenue-brain-reasoning.md)
and [Follow-up Email Composer](follow-up-email-composer.md), plus the
[Unified Meeting Intelligence workspace](unified-meeting-intelligence.md) and
[Opportunity Workspace](opportunity-workspace.md).
The future Interaction direction is governed by
[ADR 0026](../08-decisions/0026-interaction-intelligence-platform.md). The
current provider-free preparation path is documented in the
[Pre-Interaction Brief guide](pre-interaction-brief.md) and
[ADR 0027](../08-decisions/0027-deterministic-pre-interaction-briefs.md).

## WO-021 Action Layer

The modular monolith now includes tenant-scoped Action routes, a deterministic
service and repositories over `action_proposals`, immutable
`action_proposal_versions` and metadata-only `action_audit_events`. The service
reads final validated sources only. It does not call a provider or external
system. See [Action proposal architecture](action-proposal-architecture.md) and
[ADR 0033](../08-decisions/0033-versioned-review-only-action-layer.md).

## WO-022 simulation execution

Six tenant tables store connections, previews, execution intent, immutable attempts,
metadata-only audit and mock external state. The API creates previews and confirmed
queued rows; the existing worker claims only after setting trusted tenant context.
The server registry and strict `ActionExecutor` implementations keep capabilities,
risk classes and result semantics provider-neutral. See
[connector architecture](connector-architecture.md) and
[simulation mode](simulation-mode.md).

## WO-023 end-to-end Sales OS direction

WO-023 changes no runtime architecture. It proposes additional modules inside the
same web/API/PostgreSQL modular monolith, centred on canonical Evidence, Revenue
Brain, review-first Actions and provider adapters. The future methodology, analytics,
research, outreach, Create, CRM and entitlement boundaries are indexed from the
[WO-023 sprint record](../07-sprints/wo-023-end-to-end-sales-platform-blueprint.md).
[ADR 0035](../08-decisions/0035-end-to-end-sales-os-architecture.md) governs Core/
add-on and information-architecture boundaries. No schema, endpoint, worker,
provider or navigation described there exists until a separate work order implements it.

## WO-032 Create extension

WO-032 realises the PPTX presentation subset inside the existing modular monolith.
Migration `0041_create_studio` adds tenant templates, immutable versions, slide policy,
approved content, presentations and immutable presentation versions with forced RLS
and composite tenant relationships. Thin `/api/v1/create` routes call one explicit
service/repository boundary. The existing worker claims template processing and
presentation rendering with trusted transaction-local tenant context; no second
service, queue or datastore was introduced.

Private object storage holds source/generated PPTX. The in-process bounded ZIP/XML
processor and deterministic renderer never execute Office or call an AI provider.
Typed context, exact claim provenance, revalidation and human approval form the
customer-facing trust boundary. See the
[Create architecture](presentation-proposal-template-architecture.md) and
[ADR 0050](../08-decisions/0050-deterministic-pptx-rendering.md).

WO-024 is the first realised post-blueprint module. It remains inside the same
web/API/PostgreSQL modular monolith: standard definition registry, tenant custom
definition repository, deterministic projection service and Opportunity/Settings UI.
Migration `0033_sales_methodology` introduced that domain. Later work orders advance
the single head through Prospect, CRM and Engage to
`0039_campaign_sequences`. Campaign scheduling remains in the same durable worker;
no second service, queue, provider or datastore was added.

WO-025B adds strict Ask contracts, a tenant-scoped repository and a deterministic
service/router inside that same API. It composes current Methodology, Revenue Brain,
accepted Evidence, Daily and Action records without adding a service, queue,
datastore, vector index, provider call or schema migration. The web exposes it through
the existing Search route and contextual workspace links. See
[ADR 0036](../08-decisions/0036-ephemeral-deterministic-ask-revenueos.md).

## WO-047 commercial authority and WO-048 test billing

Migration `0052_commercial_plans_trial` adds immutable global plan versions,
tenant-owned commercial state and immutable tenant commercial events inside the
existing API/PostgreSQL modular monolith. The existing module-entitlement table now
records `none`, retained `read` or active `write` access with plan/trial/add-on
provenance. `CommercialService` owns plan translation, one-time trial/grace
boundaries, active-seat limits, optimistic operator changes and safe downgrade;
business services and workers consume that authority.

WO-047 added an administrator read model and kept commercial support mutation behind
explicit CLI operations. Forced RLS protects tenant commercial rows and database
triggers protect catalogue/history immutability.

WO-048 migration `0053_billing_subscriptions` adds tenant-owned billing accounts,
subscriptions, safe invoice projections, idempotent operations and immutable
provider-event receipts. A provider-neutral service consumes the WO-047 catalogue;
the deterministic provider is the CI path and an unactivated Stripe test adapter is
the first external implementation. Verified current-provider reconciliation feeds
facts into `CommercialService`, while the commercial domain remains entitlement
authority. It stays in the existing API/web/PostgreSQL modular monolith with no new
service, broker or datastore. Export v32 includes safe projections and offboarding
fails closed on unresolved accounting retention. There is no live billing, Credit
ledger or public signup. See [Commercial authority](commercial-authority.md),
[Billing operations](billing-subscription-operations.md) and
[ADR 0069](../08-decisions/0069-versioned-commercial-authority.md).

## WO-026 Prospect Account Research extension

WO-026 adds a separate tenant-owned Prospect Research Target, immutable Research
Run, source metadata, observation and citation graph. It reuses the existing API,
PostgreSQL persistence and worker process; there is no new service, queue or
datastore. An organisation module entitlement and atomic daily/concurrent counters
gate the path. Forced RLS, composite tenant foreign keys and explicit repository
predicates apply to every new row.

Research Targets do not become Companies until explicit duplicate-safe promotion.
Public research remains separate from customer Evidence and cannot mutate
Methodology, Revenue Brain or Ask RevenueOS. The current provider is a deterministic
no-network adapter; production mock configuration fails closed and no public-page
fetcher or AI synthesis exists. See the
[Prospect architecture](prospect-account-research-architecture.md) and
[ADR 0038](../08-decisions/0038-separate-prospect-research-domain.md).

## WO-033 Value Model and Business Case modules

The modular monolith now includes tenant-scoped Value Model and Business Case
repositories/services in the API and guided Create pages in the web app. PostgreSQL
RLS, composite tenant foreign keys and forced tenant policies protect all four new
tables. Approved model definitions and approved Business Case versions are immutable.
A bounded parser produces a canonical AST; evaluation uses Decimal arithmetic and
never invokes Python evaluation, JavaScript, a spreadsheet runtime or an AI provider.
See the [domain architecture](value-model-domain-architecture.md) and
[engine decision](../08-decisions/0051-bounded-deterministic-value-model-engine.md).

## WO-035 Native Pipeline module

Migration `0044_native_pipeline` adds stable tenant-owned pipeline/stage definitions,
canonical Opportunity assignment/outcome fields and immutable stage events within the
existing API/PostgreSQL modular monolith. `PipelineService` owns optimistic,
idempotent movement/closure/reopen; a bounded set-based read model powers the existing
web route. Forced RLS and composite tenant foreign keys apply. No service, broker,
datastore, provider or AI capability was added. See the
[architecture](native-pipeline-architecture.md) and
[ADR 0055](../08-decisions/0055-native-pipeline-history-and-authority.md).

## WO-036 Sales Analytics read model

Migration `0045_sales_analytics` adds four tenant/date query indexes without copying
facts. A code-owned versioned metric registry, tenant-scoped repository and
`SalesAnalyticsService` compute Overview, one-pipeline Funnel, Activity and Win/Loss
from canonical Opportunity, immutable stage-event, completed Interaction, Meeting
participant and confirmed-live Action-execution records. `SalesMetricService` is the
strict WO-037 handoff. Requests are bounded to five local years and accept only typed
date/timezone/pipeline/owner/currency filters. There is no warehouse, analytics job,
generic query language, AI provider or mutation dependency. See the
[architecture](sales-analytics-architecture.md), [metric catalogue](sales-analytics-metric-catalog.md)
and [ADR 0056](../08-decisions/0056-deterministic-canonical-sales-analytics.md).

## WO-037 Sales Targets

Migration `0046_sales_targets` adds the canonical organisation timezone plus
tenant-owned target identity/configuration and append-only revision tables. Both are
forced-RLS with composite tenant relationships; PostgreSQL triggers protect identity
and revision history. A small code-owned policy selects exactly five targetable
WO-036 metrics. `SalesTargetService` owns permission/period/value policy and delegates
every actual observation to `SalesMetricService`; no actual, counter, pacing state,
job or formula is stored. Insights renders a bounded Overview summary and dedicated
Targets tab. See the [architecture](sales-targets-architecture.md),
[security review](sales-targets-security-privacy-review.md) and
[ADR 0057](../08-decisions/0057-explicit-canonical-sales-targets.md).

## WO-038 Transparent Forecasting

Migration `0047_transparent_forecast` adds tenant calendar-period identities,
Opportunity judgment identities and immutable context-rich revisions. A bounded
tenant repository and `SalesForecastService` compose canonical current Opportunities,
WO-035 reliable exact-stage final outcomes, WO-036 `SalesMetricService` Actual and
WO-037 Target records. The primary range is explicit seller Commit/Likely/Possible;
the 730-day, 10-sample historical baseline remains separate and uses no fallback.
Insights adds Forecast and Opportunity Workspace links to it. There is no provider,
worker, probability field, fixed stage table, AI/ML, FX, manager override or mutation
of Opportunity/Evidence/Methodology/Revenue Brain. See the
[domain architecture](sales-forecast-architecture.md) and
[ADR 0058](../08-decisions/0058-separate-seller-forecast-and-system-baseline.md).

## WO-039 Manager Intelligence & Coaching

Migration `0048_manager_intelligence` adds a separate manager/reviewer Forecast
identity and append-only revision stream without altering seller rows. Forced RLS,
composite tenant relationships and immutable triggers match WO-038. The derived
`ManagerIntelligenceService` composes open-deal conditions, source references, safe
recent changes and discussion questions from canonical Pipeline, Action, Methodology,
Revenue Brain and Forecast reads. Organisation summary delegates to the existing
Forecast service and therefore reuses Sales Analytics Actual and Target services.

Home, Pipeline, Opportunity, Forecast and Insights consume the same bounded manager
contracts. V1 uses the existing admin capability; there is no hierarchy, people/deal
score, ranking, surveillance telemetry, coaching dossier, AI/provider, blended final
forecast, background worker or source-domain mutation. See the
[architecture](manager-intelligence-architecture.md),
[security review](manager-intelligence-security-privacy-review.md) and
[ADR 0062](../08-decisions/0062-deal-centric-manager-intelligence.md).
