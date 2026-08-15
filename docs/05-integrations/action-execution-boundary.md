# Action execution boundary

WO-021 stops at proposal, revision, review and intent capture. There is no Action
executor and no adapter for email, CRM, calendar, task or collaboration systems.
`approved` is not an execution state; all API responses remain `not_executed`.

A future connector must be separately authorised and designed around least-privilege
credentials, tenant-scoped installation, explicit target preview, final confirmation,
idempotency keys, provider receipts, retries, revocation and safe rollback. It must
also distinguish proposed, approved, dispatched, acknowledged and failed states.

Typed payloads are intentionally connector-ready, but that is a contract property,
not evidence that any integration works.
