# ADR 0069 — Versioned commercial authority without billing

- **Status:** Accepted
- **Date:** 4 September 2026
- **Work order:** WO-047

## Context

Organisation module switches existed, but RevenueOS had no authoritative plan,
trial, seat-limit or downgrade state. Putting package rules in the client or treating
provider flags as purchase state would create bypasses, erase historical commercial
meaning and couple access control to a future billing vendor.

## Decision

Use immutable global plan versions, one tenant commercial-state row, the existing
tenant module-entitlement boundary with `none`/`read`/`write`, and immutable tenant
commercial events. Exact V1 Core, Growth, Complete and Enterprise definitions live
server-side. Manual operator commands are the only mutation surface; administrators
receive a read-only projection. Trial is explicit, Complete-profile, 14 days, then 30
days read/export grace, with no card or automatic charge.

Count only active memberships whose user is active. Lock the organisation and state
at admission/change boundaries. Downgrades retain historical module data as read-only,
block new work and never delete users or content. Provider capability remains a
separate projection dimension. Native CRM stays Core; the CRM module represents
supported external CRM connectors.

Tenant rows use explicit predicates and forced RLS. Plan and event immutability is
also enforced in PostgreSQL. Export and approved deletion include the commercial
domain.

## Alternatives considered

- Browser-owned plan matrices were rejected because they are forgeable and drift.
- Reusing feature flags as purchase state was rejected because deployment/provider
  readiness and commercial inclusion are different facts.
- Mutable plan rows were rejected because later pricing would rewrite history.
- Implementing Stripe first was rejected because payment processing is outside the
  work order and the domain must not depend on a vendor.
- Destructive downgrade was rejected because entitlement loss is not data-erasure
  authority.

## Consequences

Support must inspect and mutate commercial state with explicit actor/reason,
confirmation and optimistic version. Over-limit downgrades require manual resolution.
Future prices require a new plan version. Future billing and Credits require separate
approved work and must reconcile into this authority without making provider or
browser state authoritative.
