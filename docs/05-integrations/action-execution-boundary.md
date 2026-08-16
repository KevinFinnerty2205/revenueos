# Action execution boundary

WO-021 stopped at proposal, revision, review and intent capture. WO-022 now
implements a provider-neutral `ActionExecutor`, organisation connection metadata,
server previews, separate confirmation and durable simulation execution for mock
email, calendar, CRM and task adapters. `approved` is still not an execution state.

A future **live** connector must be separately authorised and designed around least-privilege
credentials, tenant-scoped installation, explicit target preview, final confirmation,
idempotency keys, provider receipts, retries, revocation and safe rollback. It must
also distinguish proposed, approved, dispatched, acknowledged and failed states.

Typed payloads and successful mock simulations are contract properties, not evidence
that any provider integration works. WO-022 performs no real external action.

WO-023 proposes future Engage, CRM and handover consumers of this boundary. They must
add recipient/source-authority, suppression, jurisdiction, provider-security and
operational gates without weakening exact approval, idempotency or unknown-outcome
handling. See the
[outreach architecture](../03-engineering/outreach-campaign-architecture.md) and
[end-to-end roadmap](../06-roadmap/end-to-end-sales-platform-roadmap.md). WO-023
does not authorise a live adapter.
