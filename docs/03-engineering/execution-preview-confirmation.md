# Execution preview and confirmation

Execution is a two-request protocol after Action approval.

## Preview

`POST /api/v1/actions/{action_id}/execution-preview` accepts only a connection
identifier. The server verifies tenant membership, feature flags, approved/current
Action version, provenance, target records, active connection, capability and risk
class. It reconstructs connector content and returns a short-lived preview with a
SHA-256 fingerprint over:

- Action/version and immutable content fingerprint;
- connection ID, status, metadata version and capability state;
- capability and strict preview content; and
- the server-selected `simulation` or `live` execution mode.

The stored preview contains only fingerprint and lifecycle metadata; Action
content remains in the approved Action version.

## Confirmation

`POST /api/v1/actions/{action_id}/execute` accepts only `previewId`,
`connectionId` and literal `confirmed: true`. Extra fields are rejected. The
server locks the preview, revalidates every source and connection condition,
rebuilds the preview and compares fingerprints before persisting queued intent.

The confirmation button uses the consequential capability label—such as “Send
email” for simulation or “Update CRM” for HubSpot—inside a prominent execution
panel. A live CRM preview additionally shows exact current/proposed value, field
authority, mapped destination and provider update timestamp. Approval itself never
queues work.

Expired, revoked, changed, cross-tenant, already superseded or tampered previews
fail closed. A repeated confirmation returns the original execution. Daily
capability and organisation-concurrency limits apply before new work is queued.
For live HubSpot, the worker rebinds the mapping, rereads the external value and
recomputes the fingerprint immediately before mutation. This is the server-side
stale-write guard; browser confirmation can never substitute new field content.
