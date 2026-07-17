# Security and privacy

This is the Sprint 1 engineering baseline, not legal advice or a certification claim.

## Authentication and authorisation

Clerk is the approved future identity/organisation provider. Sprint 1 provides adapter boundaries, configuration validation and server-side protected-route checks. Development mock auth is non-production only and visibly labelled.

Every request derives its user and organisation from the auth adapter. Client-supplied organisation identifiers do not select a tenant. Roles are `admin`, `manager` and `member`; policy denies by default.

## Tenant isolation

- Organisation-owned queries include explicit organisation predicates.
- PostgreSQL RLS policies use transaction-local trusted organisation context.
- Runtime application roles must not bypass RLS.
- Migration/admin credentials are separate from web/API runtime credentials.
- Missing membership or tenant context fails closed.

The initial schema contains only organisations, users and memberships. Cross-tenant tests expand with each tenant-owned feature.

## Secrets

Environment examples contain names and local-only placeholders. Real credentials belong in environment-specific managed secret stores. Production startup rejects mock auth or incomplete Clerk verification configuration.

Secrets, tokens, authorisation headers, database URLs, signed URLs and provider payloads must not enter responses, logs or traces.

## API and browser controls

- Explicit environment-based CORS allowlists; wildcard production origins are rejected.
- Server-side protection for private routes.
- Central safe JSON errors with request IDs.
- Structured logs containing method, path, status and latency, not request bodies or exception messages.
- Private data access through the API, never privileged browser database credentials.
- Locked dependencies and automated format, lint, type, test and build checks.

## Recording consent and privacy

Sprint 1 has no recording, microphone, upload, transcript or listening capability.

Future conversation capture must:

- start only after a deliberate user action;
- show a visible armed/active state;
- capture event-specific authority/consent evidence;
- support stop/pause and fail closed when permission is ambiguous;
- disclose processing providers, purpose, retention and deletion;
- never use customer content for training without a separate explicit opt-in.

Future sensitive data requires minimisation, source provenance, retention, export and deletion behaviour before implementation.

## Open risks before production use

- Clerk session/JWT verification is not connected.
- A separately provisioned non-bypass database role must be proven with PostgreSQL RLS tests.
- Hosting, secret management, monitoring, backup and incident-response providers are not selected.
- Recording wording, residency and deletion commitments require product/legal approval before conversation features.

Do not use the Sprint 1 foundation with production customer data.
