# RevenueOS AI

RevenueOS is the AI sales teammate that remembers every customer interaction and turns conversations into action.

This repository contains the Sprint 1 foundation, Sprint 2 tenant-isolated
business entities, Sprint 3 Meeting Domain, WO-004A1/A2/B1/B2/B3 AI
infrastructure, WO-004C1–C6 capabilities, WO-005 unified Meeting Intelligence,
WO-006A Buying Signals & Deal Momentum, WO-006B Objections & Competitive
Signals, WO-006C Stakeholder Intelligence, WO-006D Next Best Action, WO-007
Opportunity Workspace, WO-008A Revenue Brain Foundation, WO-008B Revenue Brain
Longitudinal Reasoning, WO-009 Private Beta Readiness, WO-011 Interaction
Domain Foundation, WO-012 AI Companion preparation, WO-013 AI Debrief/Voice
Journal, WO-014 Visual Evidence/Presentation Mode, WO-015 Recording &
Transcription Foundation, WO-016 Browser Face-to-Face Companion, WO-017 Phone
Call Intelligence, WO-018 Online Meeting Capture, WO-019 Documents & Email
Evidence, WO-020 Live Interaction Intelligence, WO-021 Action Layer, WO-022
Integrations & Execution Foundation and WO-024 Sales Methodology Engine. Interactions, Meetings,
deliberately supplied transcripts, audit history, AI persistence/domain rules
and a separate durable worker are implemented. The Opportunity Workspace adds
a tenant-isolated opportunity list and latest-meeting view over stored,
validated intelligence, with no transcript read or new AI execution. The
Meeting Detail Intelligence tab presents independently persisted Executive
Summary, Buying Signals & Deal Momentum, Objections & Competitive Signals,
Stakeholders, Next Best Action, Key Decisions, Action Items, Risks & Blockers, Open Questions and Follow-up Email
through one derived, accessible
workspace. The default provider is a deterministic no-network mock; an optional
server-side OpenAI Responses API
adapter is configuration-selectable. Completed account-linked meeting
intelligence appends one immutable, reference-only Revenue Brain snapshot per
transcript revision. Deterministic, on-demand Revenue Brain reasoning compares
only those snapshots and their referenced validated artefacts for account and
opportunity change views; it never reads transcript text or calls a provider.
WO-012 adds immutable, versioned Pre-Interaction Briefs for all ten initial
Interaction types. Its deterministic composer uses linked metadata and validated
structured intelligence only, never transcript text, and makes no provider call.
WO-013 adds bounded post-interaction text/voice capture for completed Interactions,
strict context-aware questions and candidate extraction through the existing
structured-output provider boundary, mandatory source-aware review and additive
Opportunity Workspace/Revenue Brain updates. Voice audio is short-lived and is
never persisted. WO-014 adds explicit JPEG/PNG selection or foreground camera
capture, private tenant-scoped object storage, metadata sanitisation,
deterministic or optional strict visual analysis, complete human review, and
provenance-labelled Opportunity Workspace/Revenue Brain updates. Seller
presentation material is context only; business cards never create Contacts;
site-photo output is labelled observed.
WO-015 adds optional explicitly consented foreground browser recording,
resumable private WebM/MP4 chunk upload, durable batch transcription and immutable
transcript versions/segments. The deterministic mock makes no network call; all
recording flags default off and AI Debrief/manual capture remain first-class.
WO-016 adds a mobile-first BEFORE/DURING/AFTER Companion that deliberately
chooses recording or passive mode, reuses visual/debrief capture, stores only
controlled metadata quick markers and shows capture state in Opportunity
Workspace. Browser wake/retry is best effort and foreground-only; automatic phone
and online-meeting capture remains unavailable.
WO-017 makes `phone_call` a complete normal-phone workflow with an explicit
direction/outcome, Contact association, compact brief, manual elapsed duration,
adaptive post-call capture and authorised recording import through the existing
WO-015 pipeline. It adds no dialler, phone interception, call-log access, telephony
provider or background microphone monitoring.
WO-018 makes Teams, Zoom, Google Meet and other online meetings first-class,
browser-first Interactions. It adds safe meeting navigation, passive timing,
server-negotiated post-meeting choices, authorised TXT/VTT/SRT transcript import
and WO-015 recording import reuse. Native provider and auto-ingestion flags remain
off, and no connector, meeting bot or system-audio capture is implemented.
WO-019 adds deliberate PDF/TXT upload and plain-text email paste, bounded parsing,
strict provenance, mandatory finding review and accepted-evidence timelines in the
Opportunity Workspace and Revenue Brain. Seller documents and outbound email stay
context rather than customer confirmation. DOCX, OCR, attachments, mailbox/drive
sync, legal interpretation and automatic opportunity-field writes are not
implemented.
WO-020 adds an optional quiet Live Companion over an already authorised progressive
transcript source. Server-owned cursors process bounded overlapping windows into a
separate provisional aggregate, show possible signals and brief progress, then
reconcile against final Interaction Intelligence. The default detector is
deterministic/no-network; both live flags default off. Provisional state never writes
final Opportunity Workspace intelligence or Revenue Brain.
WO-021 adds tenant-scoped, typed and versioned Action proposals derived only from
final validated intelligence. The Opportunity Workspace supports source review,
safe revision, approval, controlled rejection and internal manual completion.
Approval itself remains `not_executed`.
WO-022 adds organisation-scoped deterministic mock email, calendar, CRM and task
connections plus a provider-neutral execution boundary. An approved Action can
produce a read-only server preview and, only after a separate final confirmation,
queue a durable simulation with idempotency, bounded retry and safe unknown-state
handling. These are visibly labelled simulations: no real provider, OAuth flow or
external action is implemented.
WO-023 documents the proposed end-to-end Sales OS, Core/add-on boundaries,
simplicity-first information architecture and conditional WO-024–045 roadmap. It
changes no production behaviour, schema, dependency or navigation.
WO-024 implements RevenueOS Core methodology projections for MEDDIC, MEDDPICC,
BANT and SPICED plus bounded versioned custom definitions. The deterministic engine
maps current validated Evidence into categorical, source-linked field states and adds
Opportunity Deal and Settings experiences. It adds no qualification score, stage
blocking, rep ranking, new top-level navigation item or external provider call.
WO-009 adds production Clerk verification, versioned consent, beta retention,
export/deletion requests, usage guardrails, feature flags, onboarding,
synthetic demo data, feedback and safe administration/operations. No predictive
scoring, forecasting, privileged browser database access, background recording
guarantees, general media ingestion beyond the reviewed visual/audio paths,
live sending/integration or billing is implemented.

## Product blueprint

The [RevenueOS master product blueprint](docs/01-product/master-product-blueprint.md) defines the Sales Brain direction through private beta. Start with the [documentation index](docs/README.md), [MVP and beta scope](docs/06-roadmap/mvp-and-beta-scope.md) and [sequenced roadmap](docs/06-roadmap/product-roadmap-to-beta.md).

The proposed direction beyond the current WO-024 baseline is defined by the
[End-to-End Sales Platform vision](docs/01-product/end-to-end-sales-platform-vision.md),
[commercial packaging](docs/01-product/revenueos-commercial-packaging.md),
[simplicity-first information architecture](docs/02-design/revenueos-information-architecture.md)
and [conditional WO-024–045 roadmap](docs/06-roadmap/end-to-end-sales-platform-roadmap.md).
WO-024 implements only the Sales Methodology slice; later roadmap items remain
unauthorised.

WO-010 defines the approved direction in the
[Interaction Intelligence vision](docs/01-product/interaction-intelligence-vision.md),
[product blueprint](docs/01-product/interaction-intelligence-product-blueprint.md)
and [roadmap](docs/06-roadmap/interaction-intelligence-roadmap.md). RevenueOS is
positioned as the AI operating system for customer interactions across Capture,
Intelligence and Action. WO-011 now implements the tenant-isolated Interaction,
Capture Session and metadata-only Evidence foundation plus one-to-one Meeting
compatibility. WO-012 implements the preparation-only AI Companion slice,
WO-013 implements reviewed post-interaction AI Debrief/Voice Journal, WO-014
implements browser-only visual evidence and bounded Presentation Mode, WO-015
implements the browser-first recording/batch-transcription foundation, and WO-016
implements the thin browser Companion orchestration and gap-fill hand-off,
WO-017 implements the browser-first phone-call path and compliant recording import,
WO-018 implements the provider-neutral online-meeting import path, WO-019
implements first-party document/email evidence without an external connector, and
WO-020 implements bounded provisional processing over an authorised progressive
source, WO-021 implements reviewed Actions, WO-022 implements simulation-only
connector/execution foundations and WO-024 implements evidence-backed Sales
Methodology. Production progressive transcription, external
live AI, native/background capture, mobile client, meeting bot, telephony provider
and production connectors remain unimplemented.

Target documents distinguish future direction from shipped functionality and do
not authorise another sprint. The current implementation boundary is Sprints 1–3
plus WO-004A1/A2/B1/B2/B3/C1/C1A/C2/C3/C4/C5/C6, WO-005, WO-006A,
WO-006B, WO-006C, WO-006D, WO-007, WO-008A, WO-008B, WO-009, WO-011, WO-012,
WO-013, WO-014, WO-015, WO-016, WO-017, WO-018, WO-019, WO-020, WO-021, WO-022 and WO-024.
WO-010 remains the Interaction Intelligence blueprint. WO-023 adds the broader
end-to-end Sales OS blueprint; all post-WO-024 roadmap work remains unauthorised.

## Prerequisites

- Node.js 22 or newer
- pnpm 11.9.0
- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- Docker Desktop or another PostgreSQL 16 instance if persistence is required

No paid-service credentials are required for default local development.

## First-time setup

From the repository root:

```bash
cp apps/web/.env.example apps/web/.env.local
cp apps/api/.env.example apps/api/.env
pnpm install
uv sync --project apps/api
```

The example files contain local-only values and empty credential placeholders. Never commit the copied environment files.

## Start PostgreSQL and migrate

Docker Compose provides one local PostgreSQL service because PostgreSQL locking and forced RLS cannot be represented faithfully by a browser-side store.

```bash
docker compose -f infra/docker/compose.yml up -d
pnpm api:migrate
pnpm api:migration:check
```

If PostgreSQL is not configured, the API still starts in limited mode. `GET /health` remains healthy and `GET /ready` returns `503` with persistence marked unavailable.

## Run locally

Start the API, web application and internal worker in separate terminals:

```bash
pnpm dev:api
```

```bash
pnpm dev:web
```

```bash
pnpm dev:worker
```

Open:

- Web application: [http://localhost:3000](http://localhost:3000)
- API health: [http://localhost:8000/health](http://localhost:8000/health)
- API readiness: [http://localhost:8000/ready](http://localhost:8000/ready)
- OpenAPI: [http://localhost:8000/docs](http://localhost:8000/docs)

Local development defaults to a clearly labelled mock identity and example organisation. Mock authentication is rejected by API configuration and route policy in production.

## Available routes

Public web routes:

- `/`
- `/sign-in`
- `/sign-up`
- `/sign-out`

Protected routes:

- `/dashboard`
- `/onboarding`
- `/select-organisation`
- `/companies`
- `/companies/new`
- `/companies/{id}/edit`
- `/contacts`
- `/contacts/new`
- `/contacts/{id}/edit`
- `/opportunities`
- `/opportunities/new`
- `/opportunities/{id}`
- `/opportunities/{id}/edit`
- `/meetings`
- `/meetings/new`
- `/meetings/{id}`
- `/meetings/{id}/edit`
- `/interactions`
- `/interactions/new`
- `/interactions/{id}`
- `/interactions/{id}/companion`
- `/tasks`
- `/tasks/new`
- `/tasks/{id}/edit`
- `/assistant`
- `/feedback`
- `/settings`

Assistant remains an honest placeholder. Company, contact and task pages use
the versioned API and provide list/create/edit states. Opportunities add an
enriched list, create/edit flows, audited meeting association and a latest-
meeting workspace. Meeting pages
provide list/search/filter/pagination, create/edit, participant management,
deliberate plain-text transcript input and Overview/Intelligence/Transcript/History
detail tabs. Intelligence is one unified workspace over eight independent
transcript extractions and two composed outputs. All use the mock by default and
need no frontend change when the
worker selects OpenAI. Company names open an account page with the reference-
only Revenue Brain snapshot timeline and deterministic adjacent comparison
summaries. Opportunity Workspace includes the same safe latest comparison.
The Interaction surface lists and filters customer events, creates manual
non-Meeting interactions, completes them and shows source-aware preparation
brief readiness, phone direction/contact/outcome/duration, capture methods and
intelligence readiness. Interaction Detail can create/reuse and review a responsive
brief for every initial Interaction type. Linked Meeting and Interaction
pages navigate to each other while the established Meeting workflow remains
unchanged. A mobile-first Companion route derives BEFORE/DURING/AFTER from the
same lifecycle, offers explicit recording or passive capture where truthful,
and hands completed interactions into gap-fill debrief. A completed phone call
shows **Capture this call while it’s fresh** with AI Debrief, Voice Journal, typed
notes, authorised recording import or a no-capture finish.

API routes:

- `GET /health` — process health
- `GET /health/live` — canonical process liveness
- `GET /ready` — configured dependency readiness
- `GET /health/ready` — canonical configured dependency readiness
- `GET /api/v1/me` — trusted authenticated user and organisation context
- beta notice, onboarding, feedback and tenant-admin operations under
  `/api/v1/beta`
- CRUD under `/api/v1/companies`
- CRUD under `/api/v1/contacts`
- CRUD under `/api/v1/opportunities`
- `GET /api/v1/opportunities/{opportunityId}/workspace` — latest associated meeting and stored product-safe intelligence
- generate/list opportunity Actions under
  `/api/v1/opportunities/{opportunityId}/actions`
- read/revise/approve/reject/manual-complete review-only proposals under
  `/api/v1/actions/{actionId}`; every approval remains not executed
- manage simulation connections under `/api/v1/integrations`, create an exact
  preview/confirmation under `/api/v1/actions/{actionId}`, and read simulation
  history under `/api/v1/executions/{executionId}`
- `PATCH /api/v1/meetings/{meetingId}/opportunity` — stale-write-safe association or disassociation
- CRUD under `/api/v1/tasks`
- CRUD under `/api/v1/meetings`
- list/create/read/update/complete under `/api/v1/interactions`
- read/create/review Pre-Interaction Briefs under
  `/api/v1/interactions/{interactionId}/companion/brief`
- `POST /api/v1/interactions/{interactionId}/start` — idempotently enter the DURING phase
- create/list/delete metadata-only markers under
  `/api/v1/interactions/{interactionId}/companion/markers`
- read/start/process/stop provisional Live Intelligence, dismiss a signal and
  reconcile after final processing under
  `/api/v1/interactions/{interactionId}/live-intelligence`
- `GET /api/v1/accounts/{accountId}/brain` — retrieve ordered immutable snapshot compositions without content
- account and opportunity `POST/GET .../brain/reasoning` — create/reuse and read deterministic longitudinal comparisons
- deliberate document/email evidence under `/api/v1/evidence`, including
  capability, create, process, complete-review, private-content, deletion,
  Opportunity Workspace and account Revenue Brain source routes
- nested participant CRUD under `/api/v1/meetings/{meetingId}/participants`
- singular transcript CRUD under `/api/v1/meetings/{meetingId}/transcript`
- `GET /api/v1/meetings/{meetingId}/history` — content-minimised audit activity
- `GET /api/v1/meetings/{meetingId}/intelligence` — retrieve the unified product-safe current-version view
- `POST /api/v1/meetings/{meetingId}/intelligence/generate` — idempotently create/reuse missing Meeting Intelligence work
- `POST /api/v1/meetings/{meetingId}/intelligence/executive-summary` — queue or return equivalent Executive Summary generation
- `GET /api/v1/meetings/{meetingId}/intelligence/executive-summary` — retrieve current safe state/result
- `POST /api/v1/meetings/{meetingId}/intelligence/buying-signals` — queue or return equivalent Buying Signals generation
- `GET /api/v1/meetings/{meetingId}/intelligence/buying-signals` — retrieve current signals and qualitative deal momentum
- `POST /api/v1/meetings/{meetingId}/intelligence/objections-competitive-signals` — queue or return equivalent objection/competitive-signal generation
- `GET /api/v1/meetings/{meetingId}/intelligence/objections-competitive-signals` — retrieve current objection pressure and supported items
- `POST /api/v1/meetings/{meetingId}/intelligence/stakeholders` — queue or return equivalent Stakeholder Intelligence generation
- `GET /api/v1/meetings/{meetingId}/intelligence/stakeholders` — retrieve current stakeholder roles, coverage and evidence
- `POST /api/v1/meetings/{meetingId}/intelligence/next-best-action` — queue or return equivalent Next Best Action generation
- `GET /api/v1/meetings/{meetingId}/intelligence/next-best-action` — retrieve current grounded recommendations
- `POST /api/v1/meetings/{meetingId}/intelligence/decisions` — queue or return equivalent Decisions generation
- `GET /api/v1/meetings/{meetingId}/intelligence/decisions` — retrieve current safe state/result
- equivalent POST/GET routes for `action-items`, `risks-blockers`, `open-questions` and `follow-up-email`

## Validation

Run the complete mock-backed validation gate:

```bash
pnpm validate
pnpm test:e2e
```

Individual commands:

```bash
pnpm audit
pnpm format
pnpm lint
pnpm typecheck
pnpm test
pnpm build:web
pnpm api:lint
pnpm api:format
pnpm api:typecheck
pnpm api:test
pnpm api:migrate
pnpm build:api
pnpm api:migration:check
```

CI runs the same checks, applies Alembic to PostgreSQL and performs the production builds. It does not deploy.

## Authentication configuration

The current authentication path provides:

- an explicit web/API authentication adapter boundary;
- server-side protected-route checks;
- Clerk middleware/session handling and API RS256 JWT verification;
- deterministic active organisation/user projection and admin/member roles;
- a clearly labelled development mock;
- fail-closed production configuration.

Production fails closed unless Clerk issuer, audience and JWKS, PostgreSQL and
explicit production settings are complete. Placeholder keys do not make Clerk
live. See the [private beta readiness guide](docs/03-engineering/private-beta-readiness.md).
Production customer data remains prohibited unless separately approved.

## AI provider configuration

`AI_PROVIDER=mock` is the default and requires no network or OpenAI key. To
exercise the optional real adapter with synthetic non-sensitive content,
configure server-only `OPENAI_API_KEY`, `OPENAI_MODEL`, set
`API_FEATURE_OPENAI_PROVIDER_ENABLED=true`, and configure
`OPENAI_TIMEOUT_SECONDS` and `OPENAI_MAX_OUTPUT_TOKENS`.

> Setting `AI_PROVIDER=openai` sends the rendered extractor instructions and
> selected meeting transcript to OpenAI for the eight extractors, including
> Buying Signals, Objections & Competitive Signals and Stakeholder Intelligence. Follow-up Email sends only validated
> Executive Summary, Decisions, Action Items and Open Questions artefacts; it
> excludes Risks & Blockers. Next Best Action sends only the eight validated
> extraction artefacts. Neither composer reads or sends transcript text. Never expose
> the key through a browser or `NEXT_PUBLIC_*` variable. Production
> customer-content use remains prohibited.

See the [OpenAI provider integration guide](docs/03-engineering/openai-provider-integration.md)
for strict output, error/retry behaviour, smoke testing and rollback.

Document/email extraction independently uses
`API_EVIDENCE_EXTRACTION_PROVIDER_NAME=mock` by
default. Optional `openai` mode requires the same server-only key plus
`API_EVIDENCE_EXTRACTION_MODEL_IDENTIFIER` and
`API_EVIDENCE_EXTRACTION_TIMEOUT_SECONDS`. Document and email flags,
upload/storage/page/text/daily quotas and processing retries are listed in
[`apps/api/.env.example`](apps/api/.env.example). No mailbox or drive credential is
accepted.

Live Interaction Intelligence uses the deterministic no-network detector in this
work order. `API_FEATURE_LIVE_INTERACTION_INTELLIGENCE_ENABLED` and
`API_FEATURE_LIVE_INTERACTION_EXTERNAL_AI_ENABLED` both default off; the external
flag does not configure a provider and fails safely if enabled. Cadence, window,
request, character, concurrency, provider-call and 30-day live-retention controls
are documented in the [product guide](docs/01-product/live-interaction-intelligence.md)
and [`apps/api/.env.example`](apps/api/.env.example).

Action generation is deterministic and makes no provider call. The Action Layer
and internal manual completion have separate feature flags, with daily and
per-opportunity caps documented in the
[Action Layer guide](docs/01-product/action-layer.md). WO-022 simulation additionally
requires the Integrations, Action Execution and Mock Connectors flags. Email,
calendar, CRM and task simulations have separate organisation/day limits, share an
organisation concurrency cap and use short-lived previews. See
[simulation mode](docs/03-engineering/simulation-mode.md). No live external
execution configuration exists.

## Private beta operations

WO-009's onboarding, notice, retention, export/deletion, quotas, feature flags,
health endpoints, feedback, demo data, admin surface and runbooks are documented
in the [private beta readiness guide](docs/03-engineering/private-beta-readiness.md).
The [launch checklist](docs/03-engineering/private-beta-launch-checklist.md) is
environment-specific and intentionally unchecked in source.

## Database migrations

Alembic is the only owner of application schema changes.

```bash
pnpm api:migrate
pnpm api:migration:check
```

Create future migrations from `apps/api` only after changing SQLAlchemy metadata, then review generated SQL and tenant implications before applying it.

## Production build commands

```bash
pnpm build:web
pnpm build:api
```

The web output is started with `pnpm --filter @revenueos/web start`. The API package is run with a production ASGI process using `revenueos.main:app`; the separately supervised worker uses `revenueos-ai-worker`. Deployment-provider configuration is intentionally deferred.

## Troubleshooting

- **`/ready` returns `503`:** start PostgreSQL, confirm `DATABASE_URL` in `apps/api/.env`, then run the migration.
- **Protected pages redirect to sign-in:** confirm `AUTH_MODE=mock` and `MOCK_AUTH_ENABLED=true` in `apps/web/.env.local` for local development.
- **API rejects mock auth:** `API_ENVIRONMENT=production` cannot use the mock. Use development locally.
- **Port already in use:** stop the existing process or change the local web/API command and update the corresponding URL/CORS variables.
- **OpenAPI or TypeScript contract changed:** update the small `packages/shared` surface in the same pull request. Pydantic/OpenAPI remains canonical.
- **Simulation connector unavailable:** confirm the Action Layer, Integrations,
  Action Execution and Mock Connectors flags are enabled together outside
  production. Mock connectors are intentionally rejected in production.

See the [documentation index](docs/README.md),
[development guide](docs/03-engineering/development-guide.md),
[deployment guide](docs/03-engineering/deployment-guide.md),
[API reference](docs/03-engineering/api.md),
[Executive Summary architecture](docs/03-engineering/executive-summary-intelligence.md),
[Meeting Decisions architecture](docs/03-engineering/meeting-decisions-intelligence.md),
[Meeting Action Items architecture](docs/03-engineering/meeting-action-items-intelligence.md),
[Meeting Risks & Blockers architecture](docs/03-engineering/meeting-risks-blockers-intelligence.md),
[Meeting Open Questions architecture](docs/03-engineering/meeting-open-questions-intelligence.md),
[Buying Signals & Deal Momentum architecture](docs/03-engineering/buying-signals-intelligence.md),
[Objections & Competitive Signals architecture](docs/03-engineering/objections-competitive-signals-intelligence.md),
[Stakeholder Intelligence architecture](docs/03-engineering/stakeholder-intelligence.md),
[Next Best Action Intelligence](docs/03-engineering/next-best-action-intelligence.md),
[Revenue Brain foundation](docs/03-engineering/revenue-brain-foundation.md),
[Revenue Brain longitudinal reasoning](docs/03-engineering/revenue-brain-reasoning.md),
[Opportunity Workspace](docs/03-engineering/opportunity-workspace.md),
[Integrations and execution foundation](docs/01-product/integrations-execution-foundation.md),
[Connector architecture](docs/03-engineering/connector-architecture.md),
[Execution preview and confirmation](docs/03-engineering/execution-preview-confirmation.md),
[Follow-up Email Composer](docs/03-engineering/follow-up-email-composer.md),
[Unified Meeting Intelligence workspace](docs/03-engineering/unified-meeting-intelligence.md),
[OpenAI provider guide](docs/03-engineering/openai-provider-integration.md),
[prompt/output architecture](docs/03-engineering/prompt-registry-and-structured-output.md),
[WO-006A record](docs/07-sprints/wo-006a-buying-signals-deal-momentum.md),
[WO-006B record](docs/07-sprints/wo-006b-objections-competitive-signals.md),
[WO-006C record](docs/07-sprints/wo-006c-stakeholder-intelligence.md),
[WO-006D record](docs/07-sprints/wo-006d-next-best-action-intelligence.md),
[WO-007 record](docs/07-sprints/wo-007-opportunity-workspace.md),
[WO-008A record](docs/07-sprints/wo-008a-revenue-brain-foundation.md)
and [WO-008B record](docs/07-sprints/wo-008b-revenue-brain-longitudinal-reasoning.md).
