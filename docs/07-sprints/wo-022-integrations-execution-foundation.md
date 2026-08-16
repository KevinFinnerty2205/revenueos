# WO-022 — Integrations and execution foundation

**Status:** Implemented on the WO-022 topic branch; simulation only.

## Delivered

- Server-owned connector/capability/risk registry for mock email, calendar, CRM
  and task providers.
- Organisation connections with administrator management, active-member use,
  revocation, metadata-only audit and a credential-reference abstraction.
- Current-approved-Action reconstruction, strict server preview, short-lived
  fingerprint and separate literal confirmation.
- Immutable execution intent, queued lifecycle in the existing worker, leases,
  bounded retry, terminal unknown state and deterministic idempotency.
- Tenant-scoped mock external persistence, including stale CRM conflict safety.
- Settings UI and approved-Action preview/confirmation/history UI with persistent
  simulation labelling.
- Migration `0032_integration_execution`, forced RLS, export version 13 and
  organisation cascade deletion.

## Security and tenant impact

All new tables carry organisation scope and forced PostgreSQL RLS. The application
role does not need bypass. Execute-time browser input cannot change approved
content. Credentials are neither implemented nor exposed. Mock connectors are
rejected in production configuration and make no external provider requests.

## Operations

Feature flags are off by safe default. Local development enables the complete
simulation flag set. Capability-specific daily limits, an organisation concurrent
limit, preview TTL, existing worker retry settings and metadata-only lifecycle
logs apply.

## Deliberate exclusions

No Gmail, Outlook, calendar, Salesforce, HubSpot, Dynamics, Slack, Teams, real
task system, OAuth, webhook, provider SDK, browser automation or autonomous
execution is included. Approval and final execution confirmation remain separate.
