# CRM execution and reconciliation

## Preview and confirmation

A live preview binds the approved Action version to the active HubSpot connection,
entity mapping, field mapping, authority, current external value, desired value,
provider update timestamp and connection metadata version. The fingerprint expires
and cannot be replaced by browser content. The final button says “Update CRM” for
field writes or “Log interaction in CRM” for activity creation.

At claim time the worker checks the confirming user and membership, active
connection, approved Action/source validity and exact mapping again. It re-fetches
HubSpot state and rebuilds the preview fingerprint. Any newer provider value returns
`stale_external_state`; the user must create a fresh preview.

## Idempotency

Confirmation uses a unique execution intent derived from organisation, Action
version, connection, capability and live/simulation mode. Concurrent or repeated
confirmation returns the same execution. A field update first checks whether the
desired value already exists and treats it as reconciled success.

HubSpot meeting creation has no general idempotency-key header. RevenueOS inserts
only a hashed execution marker into internal meeting notes, searches for that
marker before creation, and searches again after an uncertain response. One match
is success; multiple matches are ambiguous and never cause another create.

## Failures and retry

- Read-side timeouts, 429 and transient provider failures are retryable.
- Worker retries are exponential, bounded by configured attempt/delay limits and
  honour a numeric `Retry-After` up to the configured maximum.
- A timeout or 5xx after a write may have mutated HubSpot and therefore becomes an
  uncertainty check, not an automatic retry.
- Read-after-write verifies the exact mapped value.

If immediate reconciliation cannot determine the result, status is
`unknown_external_state`. `POST /executions/{id}/reconcile` performs a read-only
check. Desired state becomes `succeeded`; unchanged original state becomes a safe
retry; any third value becomes permanent attention. The endpoint never performs a
write. Operator logs and audits contain IDs, capability, state, attempt, latency
and safe codes only.
