# WO-039A security and privacy review

## Decision

The reliability changes do not alter tenant derivation, RLS, authentication,
entitlements, storage, retention, provider boundaries or audit content. No migration
is required.

## Preserved guarantees

- The active organisation still comes only from verified authentication context;
  repository queries and PostgreSQL RLS remain tenant scoped.
- Reads retry only transient browser network failures. Writes, external execution and
  any non-idempotent request are never replayed automatically.
- A request ID is safe diagnostic metadata. Error UI still excludes customer content,
  tokens, stack traces and provider payloads.
- Prospect promotion remains explicit and Company-first. Reviewed email values retain
  field provenance; no private-profile or sensitive-person category was added.
- Candidate Evidence remains review-only. Deduplication does not change source class,
  support classification or the human acceptance gate.
- Feature and role UI remains a convenience layer only; API authorisation remains the
  fail-closed authority.
- No behavioural-surveillance event, analytics beacon or new logging payload was
  introduced.

## Provider and data impact

Only deterministic mock/synthetic data was used. No live mailbox, CRM, research,
meeting, AI or other provider was activated or mutated, and no paid service was used.
WO-039B still owns Create output trust/security. WO-039C still owns production
identity/RLS/backup/retention/operations proof and real-data onboarding.

## Residual risk

Bounded GET retries can delay a terminal network error by roughly 150 ms; this is
accepted in exchange for resilience to the reproduced local browser transport race.
The request ID is intentionally reused across attempts for correlation. Provider
calls must not be placed behind GET endpoints with side effects.
