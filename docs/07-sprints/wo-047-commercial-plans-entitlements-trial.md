# WO-047 — Commercial Plans, Entitlements & Trial

- **Branch:** `codex/wo-047-commercial-plans-trial`
- **Baseline:** `6bf31fed439491ee0f286c81cec68a7305acbcbb`
- **Status:** implemented; engineering review pending
- **Migration:** `0052_commercial_plans_trial`
- **Provider/data/spend boundary:** no provider activation, synthetic tests only, AUD $0

## Outcome

WO-047 establishes one server-authoritative commercial answer per organisation. The
immutable internal V1 catalogue is Core (AUD 200 monthly/AUD 2,000 annual, 5 users),
Growth (AUD 350/AUD 3,500, 10), Complete (AUD 500/AUD 5,000, 15) and custom
Enterprise. Core includes the existing operating loop and Native CRM/Pipeline;
Growth adds Prospect and Engage; Complete adds Create and supported external CRM
connectors. Operator-selected module add-ons are supported without public prices.

The tenant state records plan version, status, interval, trial dates, add-ons,
included/custom limit, current active count resolution, effective time, actor/reason
and optimistic version. Immutable events preserve each historical commercial
snapshot. The existing entitlement domain now represents write, retained read-only
and unavailable access instead of creating a second flag system.

## Trial, limits and downgrade

An explicit support command starts one Complete-profile 14-day trial. No payment
method is required and no automatic charge exists. At the exact end instant the
organisation enters 30 days of read/export grace; new work is blocked. At the exact
grace end it expires and fails closed. No trial transition deletes data.

Active user count means active membership plus active user. Pending identity/invite,
disabled and removed memberships do not count. Admission uses database row locks;
fixed and custom limits fail closed at the boundary. A plan downgrade below current
count removes no user and marks the state for resolution.

A removed module retains existing records as read-only/exportable, while new module
actions and worker execution are denied. Engage work is safely halted. Native CRM
remains Core; external HubSpot connection/sync work requires CRM connector access.

## Surfaces and security

`GET /api/v1/commercial` is an active-admin-only, tenant-derived read model. Settings
shows plan/status, trial/grace dates, user count/limit, module access and separate
provider-operational state. It contains no purchase or payment control. Legacy admin
entitlement mutation endpoints fail with `commercial_plan_managed`; there is no
client plan/trial mutation endpoint.

Support changes use `commercial-inspect`, `commercial-start-trial`,
`commercial-assign-plan` and `commercial-change-state` with exact confirmation,
expected lock version, actor reference and reason. Tenant state/history use forced
RLS and explicit predicates. Plan versions/history have database immutability;
cross-tenant access and forged mutation fail closed. Export v31 and approved
organisation deletion cover all commercial rows. Migration 0052 also reapplies the
checked-in WO-046 PostgreSQL history guard, forward-repairing an earlier applied
function body whose native JSON comparison could fail during a permitted lifecycle
transition.

## Verification scope

Tests cover the exact catalogue and immutability; plan/add-on matrix; deterministic
trial boundary, grace, one-trial, no-charge and no-delete rules; Core/Growth/Complete
and Enterprise custom seat limits; disabled/removed/pending definitions; concurrent
PostgreSQL seat admission and downgrade/write serialisation; over-limit downgrade;
retained export; client/admin and cross-tenant denial; RLS/migration
downgrade-reupgrade; provider distinction; read-only settings states; desktop/390 px
rendering; and keyboard/focus/screen-reader semantics.

## UI evidence

- [Desktop commercial settings](assets/wo-047-commercial-settings-desktop.png)
- [390 px commercial settings](assets/wo-047-commercial-settings-mobile.png)

## Explicit boundary

Billing, Stripe, checkout, cards, invoices, tax, proration, refunds, extra-user
pricing and payment-failure automation are not implemented. Credits, providers,
WO-048, Microsoft, Google, Salesforce, Deal Room, handover, rebrand, website and
production deployment are not started or activated by this work order.
