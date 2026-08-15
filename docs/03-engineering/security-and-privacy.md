# Security and privacy

This is the engineering baseline through WO-009, not legal advice or a
certification claim.

## Authentication and authorisation

Clerk is the approved production identity/organisation provider. WO-009 connects
Next.js Clerk middleware/session handling to RS256 API JWT verification with
required issuer, audience, lifetime, subject and active organisation claims.
Development mock auth is non-production only, visibly labelled and backed by
one deterministic example membership.

Every request derives its user and organisation from the auth adapter. Client-supplied organisation identifiers do not select a tenant and are forbidden from create/update contracts. Tenant dependencies recheck that the trusted user has an active local membership before setting the database tenant context. Private-beta roles are limited to `admin` and `member`; administration and destructive-request routes enforce `admin` server-side, while active members retain the existing product access.

## Tenant isolation

- Organisation-owned queries include explicit organisation predicates.
- PostgreSQL RLS policies use transaction-local trusted organisation context.
- Companies, contacts, opportunities, tasks, meetings, participants,
  transcripts, meeting audit events, AI jobs, AI artefacts, Revenue Brain
  snapshots, Revenue Brain insights and all seven private-beta control tables
  have non-null organisation ownership and forced RLS.
- Composite foreign keys prevent cross-tenant company, contact, opportunity, meeting, owner, assignee, creator, audit-actor, AI requester, transcript trace and job/artefact references.
- Services validate every referenced record in the trusted tenant before writing.
- Runtime application roles must not bypass RLS.
- Migration/admin credentials are separate from web/API runtime credentials.
- Missing membership or tenant context fails closed.

API tests exercise cross-tenant list, read, update, delete and relationship
denial, including nested participants, inherited transcript permissions and
both Revenue Brain scopes. PostgreSQL 16 integration tests assume a restricted
role and prove RLS visibility and write checks across every tenant table,
including AI jobs, artefacts, snapshots and insights. Database tests separately
prove cross-tenant and mismatched AI trace relationships fail.

WO-004A2 repositories retain an explicit organisation predicate even under RLS. Services accept only trusted `TenantContext`, validate meeting/transcript/job trace ownership and map foreign identifiers to safe not-found errors so another tenant's record existence is not disclosed. Restricted-role PostgreSQL tests execute the new repositories and services while forced RLS is active.

WO-004B1 worker transactions also require an explicit organisation predicate and set transaction-local tenant context before tenant-owned reads/writes. A fixed security-definer scheduler function returns only opaque IDs for organisations with eligible work; it cannot return arbitrary rows or content. Claim, heartbeat, recovery, cancellation and completion operate under forced RLS. PostgreSQL tests cover wrong-tenant worker queries, concurrent claim/recovery and continuing forced-RLS state.

WO-004B2 provider requests copy their organisation/job identifiers from the
claimed immutable job snapshot and cannot load database records. Provider
execution has no open database transaction. Output persistence re-enters the
claimed organisation context, locks with the explicit organisation/job/worker
predicate and remains protected by forced RLS and tenant composite keys. A
mismatched organisation cannot persist provider output.

WO-004B3 prompts and schemas are immutable application configuration, not
tenant-controlled records. Rendering accepts only validated scalar variables
and no expression language. The executor strictly validates complete JSON
objects before persistence and checks cancellation in a separate short
tenant-bound transaction between bounded output retries. Completion preserves
the existing tenant context, ownership lock, cancellation recheck and atomic
artefact/job commit.

WO-004C1 Executive Summary requests inherit the meeting membership dependency
and trusted tenant context. Service/repository reads require the tenant's active
meeting and current transcript; worker source loading additionally requires the
claimed organisation, meeting, transcript ID and version to match in one
tenant-bound transaction. The API returns safe not-found for cross-tenant
meeting access. Existing forced RLS and composite keys continue to cover
meeting, transcript, job and artefact rows.

WO-004C2 Decisions requests use the same membership, current-transcript and
tenant-bound worker source checks. Decisions and Executive Summary are separate
job/artefact types, so neither can satisfy the other's idempotency or artefact
lookup. Only validated Decisions content is persisted; decision, owner and
evidence text is excluded from logs and audit metadata.

WO-004C3 Action Items requests preserve that boundary. Task, owner, evidence
and due-date source language are excluded from logs and audits; only
content-free item, owner and due-date counts are allowed. Relative dates use
the stored meeting date rather than system time, ambiguous wording remains
null, and forced RLS covers the new job/artefact type without a policy
exception.

WO-004C4 Risks & Blockers requests reuse the exact tenant, transcript-version,
worker and persistence checks. Risk, owner and evidence text is excluded from
logs and audits; only risk count, empty-result flag and counts by normalised
severity/category are allowed. Probability and mitigation fields are rejected
by the strict schema. OpenAI receives the bounded transcript only when selected.

WO-004C5 Open Questions requests retain the same tenant, transcript-version,
worker and persistence checks. Question, owner and evidence text is excluded
from logs and audits; only question count, empty-result flag, counts by
normalised importance and owner count are allowed. Answer, due-date, severity
and other later fields are rejected by the strict schema. OpenAI receives the
bounded transcript only when selected.

WO-004C6 Follow-up Email requests load only same-tenant validated Executive
Summary, Decisions, Action Items and Open Questions artefacts. The request and
worker use transcript audit version metadata plus source prompt/schema versions
to prove currency but never query transcript content. Risks & Blockers are excluded, and the typed provider input
has no transcript field. Email/source text is excluded from logs/audits; only
tone, counts and ordinary trace metadata are allowed. A post-provider grounding
check rejects changed or invented facts before persistence. OpenAI receives
only the validated customer-safe projection and tone when selected.

WO-005 aggregate read and generation routes inherit the same verified meeting
membership dependency, explicit organisation predicates and forced RLS. The
aggregator is not privileged and returns only product-safe state/content for the
current transcript. Orchestration logs only overall/capability counts and
created/reused metadata; it never logs generated content. Cross-tenant aggregate
read and generation return not found.

WO-006A Buying Signals requests retain the same tenant, transcript-version,
worker and persistence checks. Signal summary and evidence text are excluded
from logs and audits; only signal count, empty-result flag and counts by
normalised type, polarity and strength are allowed. The strict schema rejects
unknown scoring/probability fields and contradictory momentum. OpenAI receives
the same bounded transcript only when explicitly selected.

WO-006B Objections & Competitive Signals retains the same tenant,
transcript-version, worker and persistence checks. Objection, competitor,
summary and evidence text is excluded from logs and audits; only bounded counts
by category/status/strength, competitor count, pressure and empty-result flags
are allowed. Strict validation rejects predictive fields and contradictory
pressure/summary output. OpenAI receives the same bounded transcript only when
explicitly selected.

WO-006C Stakeholder Intelligence retains the same tenant, transcript-version,
worker and persistence checks. Stakeholder names, organisations, summary and
evidence are excluded from logs and audits; only bounded counts by role,
influence, stance, meeting engagement and coverage state plus an empty flag are
allowed. Strict validation rejects invented names/roles/relationships, graphs,
CRM fields and predictive scores. OpenAI receives the same bounded transcript
only when explicitly selected.

WO-006D Next Best Action loads only the eight same-tenant, current-version
validated extraction artefacts. The request, worker and typed provider input do
not query or carry transcript text, and Follow-up Email is excluded. Exact
source-reference grounding rejects unsupported reasoning or dependencies.
Recommendation and reasoning content stays out of logs/audits; only safe
counts and ordinary trace metadata are allowed. Priority and confidence also
remain out of telemetry and audits. The result
has no CRM, email, task, automation or integration authority.

WO-004C1A changes only provider execution after the tenant-bound source
transaction closes. OpenAI selection does not receive a client-supplied tenant
identifier and does not change repository predicates, worker ownership,
completion locks, composite tenant keys or forced RLS. The provider adapter has
no database access. Cross-tenant API, worker and PostgreSQL tests remain
authoritative.

WO-007 Opportunity Workspace derives all organisation context from verified
authentication. Opportunity, company, meeting, job and artefact reads retain
explicit organisation predicates and forced RLS; composite foreign keys prevent
cross-tenant company or meeting association even if service validation regresses.
Association writes lock the meeting and reject stale timestamps. The workspace
selects transcript ID/version metadata only, never transcript text, and performs
no provider call or job creation.

Opportunity audits and telemetry are metadata only. They may contain tenant,
opportunity and meeting identifiers, action, changed-field names, counts and
timestamps. They must not contain opportunity names or descriptions,
stakeholder names, objections, decisions, action text, risks, questions, email
content, transcript content, prompts or provider output. The aggregate response
also excludes prompt/schema/provider/model labels and operational job fields.
See [Opportunity Workspace](opportunity-workspace.md).

WO-008A snapshots contain ownership and exact artefact references only.
WO-008B reasoning loads only those same-tenant snapshots, their nine exact
referenced artefacts and completed, non-deleted meeting metadata. Its repository
has no transcript dependency and never selects `raw_text`, re-runs extraction,
renders a prompt or calls a provider. Opportunity scope requires the exact
opportunity association on both snapshots and both meetings; account scope
requires the exact company. Malformed or mixed-trace compositions fail closed.

Every generated change uses a controlled taxonomy and evidence tuple validated
against the selected pair before persistence. Stable entity keys hash
stakeholder names and free-text identities. Missing later content never proves
resolution, disappearance, completion or deterioration. Insight idempotency is
tenant- and scope-bound; composite keys, forced RLS and database triggers
prevent cross-tenant relationships, updates and deletes.

Reasoning logs and audit events contain only tenant/scope IDs, version, bounded
counts and controlled enums. They exclude summaries, descriptions, evidence
values, names, raw artefact content and transcript content. The UI renders
meeting links and capability labels but no raw evidence IDs. See
[Revenue Brain longitudinal reasoning](revenue-brain-reasoning.md).

## Secrets

Environment examples contain names and local-only placeholders. Real credentials belong in environment-specific managed secret stores. Production startup rejects mock auth or incomplete Clerk verification configuration.

`OPENAI_API_KEY` is accepted only by server settings, represented as a secret
value and required only when `AI_PROVIDER=openai`. It has no browser or
`NEXT_PUBLIC_*` variable, safe-configuration output, database column, audit
field or API response. Enabling OpenAI must inject the key through a managed
secret service and must never place it in build arguments or frontend
environments.

Secrets, tokens, authorisation headers, database URLs, signed URLs and provider payloads must not enter responses, logs or traces.

## API and browser controls

- Explicit environment-based CORS allowlists; wildcard production origins are rejected.
- Server-side protection for private routes.
- Central safe JSON errors with request IDs.
- Structured logs containing method, path, status and latency, not request bodies or exception messages.
- Private data access through the API, never privileged browser database credentials.
- Bounded page sizes, typed filters/sorts and Pydantic field constraints.
- Restrictive relationship deletes return safe `409` errors.
- Meeting deletion is soft-only and cascades the soft-delete timestamp to active participants and transcripts.
- Transcript writes are bounded to one million characters and stale versions fail safely.
- Meeting audit events contain changed field names and identifiers only, not transcript or participant content.
- AI jobs contain bounded safe failure metadata, prompt/schema trace, usage counts and integer minor-unit cost estimates; they contain no raw transcript, rendered prompt, secret or full provider response.
- AI artefact content is validated-data storage for future use, protected from overwrite by a database trigger and separated from the supplied transcript.
- Revenue Brain insights are strict, versioned, append-only deterministic
  derivatives; they contain controlled changes and evidence references but no
  transcript body, prompt, provider output, probability, forecast or deal
  score.
- AI job, lifecycle and artefact writes commit atomically with metadata-only audit events.
- AI audits may identify job/artefact/type/status/version, prompt/schema/provider/model labels and structured-output attempt count, but exclude transcript/artefact bodies, prompt templates/rendered messages, raw/invalid output, provider secrets, participant-sensitive values and raw exceptions.
- Infrastructure-test, Executive Summary, Buying Signals, Objections &
  Competitive Signals, Stakeholder Intelligence, Decisions, Action
  Items, Risks & Blockers, Open Questions, Next Best Action and Follow-up Email JSON are strict, versioned and
  rejected before persistence when malformed or extended unexpectedly.
- Worker claims use PostgreSQL row locks, bounded leases and exact worker ownership; no in-memory queue can override persisted state.
- Retry/cancellation/recovery and artefact completion use short atomic transactions and store only bounded safe errors.
- Worker logs allow safe IDs, attempts, status, duration and error codes only; they exclude content, participant data, secrets, database URLs and raw exception messages.
- Provider logs allow only safe provider/model/request labels, latency, usage,
  integer cost, currency, finish reason and bounded error classification; they
  exclude full request/response payloads, raw SDK exceptions and artefact
  content.
- The selected provider receives only job-specific ordered messages and the
  registry-derived output schema. The mock processes the bounded
  JSON-delimited transcript in-process and makes no network call. OpenAI
  selection sends the rendered extractor instructions and selected transcript
  to OpenAI through the server-side Responses API. Next Best Action sends only
  the eight validated extraction artefacts; Follow-up Email sends only its
  validated source projection and tone. Neither composer reads or sends
  transcript text.
- OpenAI requests use strict structured output, `store=false`, no tools, no
  streaming and zero SDK retries. The application Pydantic validator remains
  authoritative.
- Provider timeouts are bounded and retryable. Unsupported provider/model,
  invalid request and configuration fail without inline retry.
- Only malformed JSON, non-object JSON and schema-invalid output receive a
  small bounded within-execution retry; exhaustion is non-retryable.
- Prompt rendering uses simple named scalar substitution only. Missing,
  unknown or expression-like variables fail closed.
- Provider output must be one complete JSON object that validates through the
  registered strict Pydantic schema; markdown extraction, `eval` and broad
  repair are prohibited.
- Executive Summary, Buying Signals, Objections & Competitive Signals,
  Stakeholder Intelligence, Decisions, Action Items, Risks & Blockers and Open Questions input is limited
  to 50,000 trimmed characters, is never
  silently truncated, and is excluded from logs, audits, safe errors and
  product-status responses. Prompt-injection instructions in transcript data
  have no tool or write authority.
- Locked dependencies and automated format, lint, type, test and build checks.

## Interaction and evidence metadata

WO-011 adds `interactions`, `capture_sessions`, `evidence` and
`interaction_audit_events`. Every table has non-null tenant ownership, composite
same-tenant relationships, explicit repository predicates and forced PostgreSQL
RLS. The Meeting/Interaction link is non-null and one-to-one inside a tenant.

Interaction audit/log data is content-minimised. Evidence contains controlled
type, origin, support, validation, lifecycle, retention and time/member metadata
only—no transcript copy, customer body, blob, storage URL, prompt or AI artefact.
Origin is immutable in meaning: verification cannot turn salesperson-reported
material into customer-direct evidence. Export version 2, retention and confirmed
organisation deletion include the new metadata. See the
[Interaction domain security review](interaction-domain-security-review.md).

## Recording consent and privacy

Sprint 3 accepts only transcript text deliberately pasted by a user or read from an explicitly selected `.txt` file. The file is read in the browser and its text is sent through the ordinary API; there is no object-storage upload, microphone access, recording, listening, media processing or transcription. The form tells users to provide only content they are authorised to store.

WO-014 separately permits deliberately selected JPEG/PNG visual evidence. It
uses private tenant-prefixed storage and short-lived resource grants; validates
actual MIME, checksums, dimensions and pixel count; removes unsafe PNG/JPEG
metadata; and rejects polyglots and malformed structure. Provider and audit
logs retain metadata only. Derived candidates remain `ai_inferred` and
unreviewed until the user makes a complete accept/edit/reject decision. Seller
material cannot become a customer signal, business cards cannot create Contacts
and site-photo claims remain explicitly observed. See the
[visual security review](visual-evidence-security-review.md).

WO-009 adds a server-authoritative versioned notice before transcript writes or
intelligence requests. It stores only user/organisation/version/timestamp and
requires re-acknowledgement after a version change. This safeguard is not proof
of lawful authority or a legal determination. Future conversation capture must:

- start only after a deliberate user action;
- show a visible armed/active state;
- capture event-specific authority/consent evidence;
- support stop/pause and fail closed when permission is ambiguous;
- disclose processing providers, purpose, retention and deletion;
- never use customer content for training without a separate explicit opt-in.

WO-020 grants no new capture authority. Live start requires an existing authorised
progressive transcript source and an explicit per-Interaction user action. The panel
is visibly provisional and stoppable. The deterministic detector is no-network;
external live AI has a separate default-off flag and acknowledgement boundary. Logs
allow only tenant/Interaction/session IDs, controlled states, counts and safe error
codes—never statements, source text, names, brief text or provider payloads. See the
[Live Intelligence security review](live-intelligence-security-review.md).

Normal Meeting deletion remains soft deletion and also soft-deletes its linked
Interaction. The separate beta retention command hard-deletes eligible
Meeting/transcript/intelligence/Revenue Brain dependencies and eligible standalone
completed/cancelled Interactions in an approved tenant context. Admin export and confirmed
organisation deletion workflows exist, but backups and Clerk lifecycle require
documented operator action and legal hold is not implemented.

## Open risks before production use

- The production non-bypass database role and grants are not provisioned by this repository; CI tests the required RLS behaviour with a temporary restricted role.
- Clerk sign-up/invitation/organisation policy and external identity deletion
  are target-environment operator responsibilities.
- OpenAI output is available when explicitly configured, but provider
  privacy/retention/residency approval, network policy, quality evaluation,
  accurate cost/budget controls and production enablement are incomplete.
- The scheduler function necessarily reveals opaque eligible organisation UUIDs to the database worker role; deployment grants and role separation require production review.
- Transcript version counters do not preserve historical transcript bodies, so version traceability is not yet source snapshot retention.
- Hosting, secret management, central monitoring and backup providers are not
  selected; deployment/runbook requirements are documented for operators.
- Recording wording, residency and deletion commitments require product/legal approval before conversation features.

Do not use this system with production customer data. Enabling OpenAI changes
the data-flow boundary and externally transmits selected transcript content.
Technical production identity verification and beta consent/retention/export/
deletion controls are implemented. Provider/privacy approval, target-environment
operational evidence and production audit/legal policy are not complete. See
[the WO-009 security review](private-beta-security-review.md).
