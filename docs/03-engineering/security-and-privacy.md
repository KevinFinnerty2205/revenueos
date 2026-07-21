# Security and privacy

This is the WO-004C6 engineering baseline, not legal advice or a certification claim.

## Authentication and authorisation

Clerk is the approved production identity/organisation provider. Sprint 3 still provides only adapter boundaries, configuration validation and server-side protected-route checks. Development mock auth is non-production only, visibly labelled and backed by one deterministic example membership.

Every request derives its user and organisation from the auth adapter. Client-supplied organisation identifiers do not select a tenant and are forbidden from create/update contracts. Meeting dependencies recheck that the trusted user has an active local membership before setting the database tenant context. Roles are `admin`, `manager` and `member`; Sprint 3 grants organisation members equal CRUD access because no narrower role policy is specified.

## Tenant isolation

- Organisation-owned queries include explicit organisation predicates.
- PostgreSQL RLS policies use transaction-local trusted organisation context.
- Companies, contacts, opportunities, tasks, meetings, participants, transcripts, meeting audit events, AI jobs and AI artefacts have non-null organisation ownership and forced RLS.
- Composite foreign keys prevent cross-tenant company, contact, opportunity, meeting, owner, assignee, creator, audit-actor, AI requester, transcript trace and job/artefact references.
- Services validate every referenced record in the trusted tenant before writing.
- Runtime application roles must not bypass RLS.
- Migration/admin credentials are separate from web/API runtime credentials.
- Missing membership or tenant context fails closed.

API tests exercise cross-tenant list, read, update, delete and relationship denial, including nested participants and inherited transcript permissions. PostgreSQL 16 integration tests assume a restricted role and prove RLS visibility and write checks across every tenant table, including AI jobs and artefacts. Database tests separately prove cross-tenant and mismatched AI trace relationships fail.

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

WO-004C1A changes only provider execution after the tenant-bound source
transaction closes. OpenAI selection does not receive a client-supplied tenant
identifier and does not change repository predicates, worker ownership,
completion locks, composite tenant keys or forced RLS. The provider adapter has
no database access. Cross-tenant API, worker and PostgreSQL tests remain
authoritative.

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
- AI job, lifecycle and artefact writes commit atomically with metadata-only audit events.
- AI audits may identify job/artefact/type/status/version, prompt/schema/provider/model labels and structured-output attempt count, but exclude transcript/artefact bodies, prompt templates/rendered messages, raw/invalid output, provider secrets, participant-sensitive values and raw exceptions.
- Infrastructure-test, Executive Summary, Buying Signals, Decisions, Action
  Items, Risks & Blockers, Open Questions and Follow-up Email JSON are strict, versioned and
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
  to OpenAI through the server-side Responses API. Follow-up Email instead
  sends only its validated source projection and tone; it never reads or sends
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
- Executive Summary, Buying Signals, Decisions, Action Items, Risks & Blockers and Open Questions input is limited to 50,000 trimmed characters, is never
  silently truncated, and is excluded from logs, audits, safe errors and
  product-status responses. Prompt-injection instructions in transcript data
  have no tool or write authority.
- Locked dependencies and automated format, lint, type, test and build checks.

## Recording consent and privacy

Sprint 3 accepts only transcript text deliberately pasted by a user or read from an explicitly selected `.txt` file. The file is read in the browser and its text is sent through the ordinary API; there is no object-storage upload, microphone access, recording, listening, media processing or transcription. The form tells users to provide only content they are authorised to store.

This notice is a product safeguard, not proof of consent or a legal determination. Production use still requires approved consent wording, provenance, retention, export and deletion policy. Future conversation capture must:

- start only after a deliberate user action;
- show a visible armed/active state;
- capture event-specific authority/consent evidence;
- support stop/pause and fail closed when permission is ambiguous;
- disclose processing providers, purpose, retention and deletion;
- never use customer content for training without a separate explicit opt-in.

Meeting deletion currently makes records unavailable to normal application reads but is not a complete privacy erasure workflow. Backups, audit retention, export, hard deletion and legal holds are not implemented.

## Open risks before production use

- Clerk session/JWT verification is not connected.
- The production non-bypass database role and grants are not provisioned by this repository; CI tests the required RLS behaviour with a temporary restricted role.
- Role-specific CRUD permissions, organisation-wide audit export, retention and customer-data erasure workflows are not yet specified.
- OpenAI output is available when explicitly configured, but provider
  privacy/retention/residency approval, network policy, quality evaluation,
  accurate cost/budget controls and production enablement are incomplete.
- The scheduler function necessarily reveals opaque eligible organisation UUIDs to the database worker role; deployment grants and role separation require production review.
- Transcript version counters do not preserve historical transcript bodies, so version traceability is not yet source snapshot retention.
- Hosting, secret management, monitoring, backup and incident-response providers are not selected.
- Recording wording, residency and deletion commitments require product/legal approval before conversation features.

Do not use this system with production customer data. Enabling OpenAI changes
the data-flow boundary and externally transmits selected transcript content.
Production identity verification, provider/privacy approval, operational
controls, consent evidence, retention/export/erasure and production audit policy
are not complete.
