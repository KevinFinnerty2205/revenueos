# Security and privacy

This is the WO-004B1 engineering baseline, not legal advice or a certification claim.

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

## Secrets

Environment examples contain names and local-only placeholders. Real credentials belong in environment-specific managed secret stores. Production startup rejects mock auth or incomplete Clerk verification configuration.

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
- AI jobs contain bounded safe failure metadata, usage counts and integer minor-unit cost estimates; they contain no raw transcript, prompt, secret or full provider response.
- AI artefact content is validated-data storage for future use, protected from overwrite by a database trigger and separated from the supplied transcript.
- AI job, lifecycle and artefact writes commit atomically with metadata-only audit events.
- AI audits may identify job/artefact/type/status/version and optional provider/model labels, but exclude transcript/artefact bodies, prompts, provider secrets, participant-sensitive values and raw exceptions.
- Infrastructure-test JSON is strict, versioned and rejected before persistence when malformed or extended unexpectedly.
- Worker claims use PostgreSQL row locks, bounded leases and exact worker ownership; no in-memory queue can override persisted state.
- Retry/cancellation/recovery and artefact completion use short atomic transactions and store only bounded safe errors.
- Worker logs allow safe IDs, attempts, status, duration and error codes only; they exclude content, participant data, secrets, database URLs and raw exception messages.
- The deterministic executor does not load transcript text or make network calls.
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
- Only deterministic infrastructure-test worker execution exists; provider execution, prompt governance and user/API lifecycle access are not implemented.
- The scheduler function necessarily reveals opaque eligible organisation UUIDs to the database worker role; deployment grants and role separation require production review.
- Transcript version counters do not preserve historical transcript bodies, so version traceability is not yet source snapshot retention.
- Hosting, secret management, monitoring, backup and incident-response providers are not selected.
- Recording wording, residency and deletion commitments require product/legal approval before conversation features.

Do not use this system with production customer data. Production identity verification, operational controls, consent evidence, retention/export/erasure and production audit policy are not complete.
