# Execution idempotency and reconciliation

Confirmation computes a SHA-256 idempotency key from organisation, Action ID,
approved version, connection, capability and execution mode. Unique constraints
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

## HubSpot live reconciliation

WO-025C uses the same durable execution identity for HubSpot. Field writes first
read/compare current state, then verify the desired value after mutation. Activity
creation uses a hashed execution marker in internal notes and searches before create
and after any uncertain result. A response timeout or provider 5xx after a mutation
is never blindly retried.

An `unknown_external_state` execution exposes one explicit read-only reconciliation
operation. Desired state resolves to success; unchanged original state permits a
bounded safe retry; a third value becomes permanent attention. Reconciliation never
writes. HubSpot does not provide a general idempotency header for these single-record
operations, so these comparison and durable-marker rules are the connector's
documented mechanism. See [CRM execution and reconciliation](crm-execution-reconciliation.md).
