# ActionExecutor contract

`ActionExecutor` is the provider-neutral port between approved RevenueOS Actions
and connector-specific behaviour. WO-022 supplies deterministic mock
implementations only.

## Required operations

- `validate_connection()` verifies adapter readiness without exposing secrets.
- `get_capabilities()` returns the immutable server registry capabilities.
- `validate_action(action)` enforces connector semantics.
- `preview_execution(action, current_external_state)` returns a strict,
  discriminated and read-only preview.
- `execute(action, idempotency_key, current_external_state)` returns a safe
  result identifier and mock state.
- `get_execution_status(external_result_id)` is the future reconciliation port.
- `cancel_if_supported(external_result_id)` declares cancellation support.
- `object_key(action, idempotency_key)` identifies the simulated external object.

The input is an `ApprovedActionInput` reconstructed by the backend from the
current approved version. Implementations never accept content, recipients,
attendees, targets or changed values from the execute request.

## Failure contract

- `RetryableExecutionFailure` permits bounded exponential-backoff retry.
- `PermanentExecutionFailure` stops safely.
- `UnknownExternalStateFailure` records an unresolved outcome and prohibits
  automatic retry until reconciliation is implemented.

Unexpected adapter exceptions are reduced to a safe retryable infrastructure
code. Logs and API errors contain identifiers, lifecycle metadata and safe codes,
not Action content, credentials or provider payloads.

Any live implementation must preserve this contract, add least-privilege
credentials and provider idempotency/reconciliation, and pass a separate launch
review. Merely implementing this interface is not a working integration.
