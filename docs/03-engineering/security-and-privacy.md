# Security and privacy

This is the WO-004A1 engineering baseline, not legal advice or a certification claim.

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
- AI repositories, services, lifecycle policy, provider execution, structured-output validation and user access are not implemented; the new tables must not be exposed directly.
- Transcript version counters do not preserve historical transcript bodies, so version traceability is not yet source snapshot retention.
- Hosting, secret management, monitoring, backup and incident-response providers are not selected.
- Recording wording, residency and deletion commitments require product/legal approval before conversation features.

Do not use this system with production customer data. Production identity verification, operational controls, consent evidence, retention/export/erasure and production audit policy are not complete.
