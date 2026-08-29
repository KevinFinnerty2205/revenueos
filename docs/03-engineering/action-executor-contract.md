# ActionExecutor contract

`ActionExecutor` is the provider-neutral port between approved RevenueOS Actions
and connector-specific behaviour. WO-022 supplies deterministic mock
implementations; WO-025C adds one HubSpot implementation behind the same port.

## Required operations

- `validate_connection()` verifies adapter readiness without exposing secrets.
- `get_capabilities()` returns the immutable server registry capabilities.
- `validate_action(action)` enforces connector semantics.
- `preview_execution(action, current_external_state)` returns a strict,
  discriminated and read-only preview.
- `execute(action, idempotency_key, current_external_state)` returns a safe
  result identifier and mock state.
- `get_execution_status(external_result_id)` is available for provider-specific
  status/reconciliation behaviour; HubSpot reconciliation additionally reads exact
  mapped state because a provider receipt alone is insufficient.
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

The HubSpot implementation preserves this contract, adds least-privilege encrypted
credentials and comparison/marker reconciliation, and passes the WO-025C code and
security review. Target-environment/customer launch approval remains separate;
merely enabling the feature flag is not release approval.

## Native CRM boundary after WO-034

WO-034 does not register RevenueOS itself as a connector and does not route approved
Actions through an external-connection-shaped executor. Native `update_contact` or
`update_opportunity` execution remains deferred until the server can select the
organisation system of record, construct an exact local preview, revalidate current
state/authority/concurrency, apply idempotently and append `reviewed_action` history.
Until then manual CRUD is the only native mutation path and AI cannot mutate CRM.
