# Connector architecture

WO-022 adds a provider-neutral connector boundary to the existing FastAPI
modular monolith. It does not add a connector service, external queue or browser
provider SDK.

## Components

1. A server-owned registry declares stable connector keys, display names,
   capabilities, supported risk classes and configuration schema version.
2. `integration_connections` stores organisation-scoped connection state and a
   server-issued capability snapshot. Browser input cannot add capabilities.
3. `ActionExecutionService` reconstructs the approved Action version, verifies
   current provenance/targets, selects the required capability and creates a
   short-lived preview fingerprint.
   `GET /api/v1/actions/{id}/execution-options` exposes only matching active
   connection/capability choices, so the browser does not hardcode the
   Action-to-capability mapping.
4. Confirmation persists immutable execution intent in `action_executions`.
5. The existing worker process claims eligible rows and invokes an
   `ActionExecutor` implementation.
6. Append-only attempts/audits and mock-only external objects preserve safe
   lifecycle evidence.

Every repository query includes `organisation_id`. PostgreSQL forced RLS protects
connections, previews, executions, attempts, integration audits and mock state.
The worker discovers eligible organisation IDs through a bounded
`SECURITY DEFINER` function, then sets transaction-local trusted tenant context
before any tenant read or write.

## Registry rules

The initial keys are `mock_email`, `mock_calendar`, `mock_crm` and `mock_task`.
Only the server registry maps these to `send_email`, `create_calendar_event`,
`update_opportunity`, `update_contact` and `create_task`. Database constraints
close the same sets. Unknown keys, capability drift and risk mismatches fail
closed.

Mock adapters are enabled only when the Integrations, Action Execution, Action
Layer and Mock Connectors flags are all enabled outside production. The Settings
validator rejects mock connectors in production.

See [ActionExecutor contract](action-executor-contract.md),
[credential/OAuth design](credential-oauth-security-design.md) and
[ADR 0034](../08-decisions/0034-simulation-first-execution-boundary.md).
