# Simulation mode

WO-022 has one execution mode: `simulation`. This is an architectural and product
constraint, not merely a UI label.

- Database checks accept only `execution_mode = 'simulation'`.
- The connector registry contains mock providers only.
- Configuration rejects mock connectors in production;
- mock executors perform no HTTP, SMTP, calendar, CRM or task-provider request;
- outputs use `simulated_success`, never a live-success label; and
- the UI repeats “no external action will occur/occurred”.

Deterministic mock result IDs are derived from the execution idempotency key.
Tenant-scoped `mock_connector_objects` preserve simulated persistence for refresh
and stale-state tests. They are mock-only implementation data, are protected by
RLS, cascade with their owning organisation/connection/execution, and are not
exported as if they were real email, calendar, CRM or task records.

## Enabling locally

The Action Layer, Integrations, Action Execution and Mock Connectors flags must be
enabled together. The default repository development environment enables this
combination; safe Settings defaults remain off. Production fails validation if
Mock Connectors is enabled.

Simulation proves policy, lifecycle, idempotency, audit and UX boundaries. It
does not prove provider authentication, scopes, delivery, external availability,
webhooks or provider-specific conflict semantics.
