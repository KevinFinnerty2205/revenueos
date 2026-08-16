# ADR 0034: Simulation-first Action execution boundary

**Status:** Accepted

## Context

WO-021 established versioned, review-only Actions. A real provider integration
would combine high-risk concerns—credential handling, provider semantics,
idempotency, external-state conflict, reconciliation and user confirmation—before
the product had exercised a durable execution lifecycle.

## Decision

Introduce a provider-neutral `ActionExecutor` boundary and organisation connection
model, but permit only deterministic mock adapters and `simulation` execution in
WO-022. Approval produces no execution. The server reconstructs the approved
Action, creates a fingerprinted preview, and requires a separate exact
confirmation before durable queueing. The existing worker owns bounded execution,
attempts and unknown-outcome handling.

Capabilities and supported risk classes live in a server registry. Tenant scope,
forced RLS, immutable intent, idempotency and revocation are part of the foundation,
not provider-specific additions. Credentials are represented only by an opaque
future secret-store reference.

## Alternatives considered

- **Direct provider implementation:** rejected because it would obscure whether
  lifecycle and confirmation defects came from RevenueOS or provider behaviour.
- **Approval equals execution:** rejected because consequential intent requires a
  current preview and separate final decision.
- **Client-supplied execute payload:** rejected because it permits content/target
  substitution after approval.
- **External queue/service:** rejected; the existing PostgreSQL-backed worker is
  sufficient for this modular monolith and current scale.

## Consequences

The full UX and safety lifecycle can be tested without external effects. Mock
success is not evidence of a working integration. Each live adapter still needs
provider-specific OAuth, scopes, idempotency, reconciliation, deletion, webhook,
privacy and production launch approval in a later work order.
