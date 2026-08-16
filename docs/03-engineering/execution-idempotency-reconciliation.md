# Execution idempotency and reconciliation

Confirmation computes a SHA-256 idempotency key from organisation, Action ID,
approved version, connection, capability and simulation mode. Unique constraints
cover preview confirmation, idempotency key and the Action/version/connection/
capability tuple. Concurrent confirmations therefore converge on one execution.

Mock adapter result IDs are deterministic from that key. Before invoking an
adapter the worker checks tenant-scoped mock external state for the same key; a
matching object completes the execution without a second side effect.

## Retries

The worker records an immutable attempt for every invocation. Retryable failures
use bounded exponential backoff and stop at `max_attempts`. Permanent failures
do not retry. A lease that expires while an execution was in progress becomes
`unknown_external_state`, because blindly invoking an external provider again
could duplicate a consequential action.

## Future live reconciliation

A live connector must provide a provider idempotency mechanism or durable
request/result mapping, and implement status lookup. Unknown outcomes require
operator-visible reconciliation evidence before retry or resolution. Webhook
delivery alone is not sufficient because it can be delayed, duplicated or absent.
No manual force-retry endpoint exists in WO-022.
