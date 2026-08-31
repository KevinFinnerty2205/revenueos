# Journey reliability contract

The primary seller journey is dependable only when the following behaviours hold.

## Navigation and state

- Every primary destination supports direct load, refresh, browser history and
  contextual navigation.
- A hand-off carries a canonical identifier or an explicit return target; display
  names are never used as identity.
- A successful mutation updates the local owner and deliberately revalidates every
  visible consumer that could now be stale.
- No normal workflow asks the seller to hard refresh or repair the database.
- Terminal states offer the next useful canonical destination.

## Loading, errors and writes

- A load announces progress and settles to content, an honest empty state or a
  recoverable error.
- Safe idempotent reads may retry only a small bounded number of transient network
  failures. Writes are never replayed by the browser automatically.
- A recoverable error explains the next action and shows a safe request ID when one
  exists. Provider payloads, stack traces and customer content remain hidden.
- Mutation controls disable while in flight. Idempotency and server-side version
  checks remain authoritative.
- A stale write is described as: “This changed since you opened it. Refresh and
  review the latest version.” The client does not silently overwrite the winner.

## Trust and accessibility

- Research state describes a real durable run. “Ready to research” means no run has
  started; “Researching” means one exists and is active.
- Provider-supplied, public-source, salesperson-reported and customer-direct
  provenance remain distinct after every hand-off.
- Primary pages have one `h1`, semantic landmarks, labelled controls, visible focus,
  meaningful status/alert regions, reduced-motion support and 44 px touch targets.
- At 390 px, all required destinations and tabs remain reachable without page-level
  horizontal clipping or bottom-navigation obstruction.
- Disabled or unentitled modules fail closed with customer language and an allowed
  recovery destination. Role-hidden actions are not rendered to members.

## Verification

The contract is enforced by component tests, API tests, the direct-route matrix and
the deterministic flagship Playwright journey documented in
[the browser test architecture](../03-engineering/journey-reliability-architecture.md#browser-test-architecture).
