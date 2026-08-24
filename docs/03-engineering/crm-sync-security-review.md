# WO-025C CRM sync security and privacy review

**Decision:** Suitable for a feature-gated HubSpot private-beta rollout after
target-environment OAuth registration, secret injection and manual sandbox proof.

## Controls reviewed

- **Consent and takeover:** admin-only one-time tenant/user-bound OAuth state,
  exact redirect, fixed official hosts, account identity verification and fixed
  scopes prevent a connection being rebound through browser input.
- **Secrets:** authenticated AES-256-GCM envelopes, deployment master key and opaque
  references; no plaintext token column, frontend field, audit or export.
- **Tenant isolation:** all connection, credential and mapping access has explicit
  organisation predicates and forced RLS. Composite tenant FKs prevent relationship
  attachment across organisations.
- **Configuration:** admin-only typed fields/stages and explicit authority. Members
  cannot change policy. Provider read-only/type changes fail closed.
- **Object safety:** exact selected IDs only; no name/email/phone fuzzy merge,
  contact create or broad import. Provider payloads are not persisted.
- **Write boundary:** final validated source → immutable Action → edit/review →
  approval → fresh preview → literal confirmation → worker. No AI/tool/provider
  path can skip these server transitions.
- **Overwrite and concurrency:** current value and update time appear in preview;
  worker re-read/fingerprint check blocks newer provider state. CRM-authoritative
  fields cannot be written. Currency mismatch blocks amount without conversion.
- **Activity privacy:** final Executive Summary and bounded final Action Items only.
  Transcript, full Evidence, customer email and unreviewed content are excluded.
- **Idempotency:** unique execution intent, result verification, activity marker,
  search-before-create and read-only unknown-state reconciliation.
- **Identity lifecycle:** active user and membership checked at integration entry,
  claim and execution. Disconnect blocks new work immediately.
- **Observability:** metadata-only connection/mapping/preview/execution/reconciliation
  audit. No customer names, emails, notes, field values, token or provider payload.
- **Lifecycle:** export includes safe connection/mapping/policy/execution metadata;
  disconnect/deletion attempts token revocation then deletes local secrets. RevenueOS
  deletion never deletes or rolls back external CRM records.

## Threat regressions

Tests cover state tenant binding/replay/expiry/redirect/provider error, admin role,
disabled user, ciphertext tamper/cross-connection binding, refresh, scope/account
validation, rate limit, malformed provider responses, explicit/duplicate mapping,
cross-tenant denial, type/read-only checks, exact preview, currency and authority,
duplicate confirmation, stale state, uncertain writes and duplicate-free activity.
Automated tests use deterministic HTTP fixtures and make no real provider mutation.

## Residual risks and launch conditions

- HubSpot scopes apply at account level rather than mirroring the installing user’s
  record visibility. Admin consent copy and least-privilege scopes remain important.
- A deployment key loss makes tokens unrecoverable; reconnect is the recovery path.
- Provider API/schema changes can invalidate mappings; connector health and safe
  field errors must be monitored.
- No webhook means inbound changes are observed only on explicit link/preview/write/
  reconciliation reads. This is deliberate and avoids unnecessary CRM ingestion.
- Private beta must keep the connector flag off until HTTPS redirect, app scopes,
  credentials and revocation have been proven in a developer test account.
