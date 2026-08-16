# WO-022 integration security review

**Decision:** Suitable for development/private-beta simulation with all WO-022
flags disabled by safe default. Not approved for live external actions.

## Controls verified

- Organisation context comes from verified authentication; repositories and RLS
  scope every new tenant row.
- Connection management is administrator-only; active members may use a connection.
- Capabilities and risk compatibility are owned by the server registry.
- Only the current approved Action version with current sources/targets can preview.
- Execute accepts no Action payload and requires a separate literal confirmation.
- Preview fingerprints bind content, version, connection state and mode.
- Unique keys and mock object checks prevent replay/duplicate side effects.
- Unknown outcomes never retry automatically.
- Revocation clears credential reference, invalidates previews and cancels queued work.
- Logs/audits are metadata-only; APIs/exports omit credential references and
  internal fingerprints/idempotency keys.
- Settings and database checks prevent a mock/live-mode ambiguity in production.

## Residual risks and release blockers

Mock state cannot model all provider consistency, throttling or outage behaviour.
There is no OAuth, real provider scope, credential rotation, webhook
authentication, live reconciliation, provider deletion or live incident runbook.
There is no operator resolution flow for unknown external state. These are
intentional blockers, not deferred details of a working connector.

No real external network action, production connector, browser automation,
autonomous agent or AI tool invocation was introduced by WO-022.
