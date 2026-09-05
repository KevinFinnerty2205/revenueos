# WO-049 — Credits & Variable-Cost Controls

- **Branch:** `codex/wo-049-credits-variable-cost`
- **Baseline:** `d9f03d1a2098d3383269875c61af1a504a7f6b30`
- **Status:** implemented; engineering review pending
- **Migration:** `0054_credits_variable_cost`
- **Provider/data/spend boundary:** deterministic test provider and TEST catalogue
  only; synthetic data only; AUD $0

## Outcome

WO-049 adds the provider-neutral Credits safety layer needed before any future
material variable-cost provider can be considered. It defines one integer Oryntela
Credit, immutable versioned pack/action catalogues, purchased and promotional lots,
an append-only ledger, a locked organisation balance projection, server-owned quotes,
reservation allocations and explicit operation outcomes.

The lifecycle supports promotional/trial grants, verified TEST purchase grants,
expiry, quote, reserve-before-execute, full/partial/zero settlement, release, unknown
outcome reconciliation, refund and support correction. Tenant-scoped idempotency and
request fingerprints make retry effects stable. Balance-row locking, non-negative
database constraints and exact PostgreSQL contention tests prevent overspend.

## Commercial and billing boundary

The only pack is `TEST_100`: 100 test Credits for AUD $20. The only action price is
synthetic Prospect company research at 5 Credits per successful unit. Both are
labelled `TEST ONLY / NOT CUSTOMER PRICING`; the Settings purchase control is disabled.
These values prove mechanics and are not public or owner-approved production prices.

WO-048 deterministic/test billing may grant a purchased lot only after a verified
successful `credit_purchase` event matches the exact server-owned pack, AUD amount
and billing operation. The grant and billing receipt commit atomically. Browser
redirects, arbitrary calls, duplicate events and mismatches do not create Credits.
Live Stripe remains inactive and no real charge is possible.

Trial Credits are promotional, require active WO-047 trial authority, obey the
organisation trial exposure cap and cannot outlive the trial. Credits neither grant a
module nor override permission, suppression, quota, licensing or provider health.

## Economics and safety

Action-price versions preserve provider-native minor units/currency, fixed-precision
FX evidence, expected and maximum AUD variable cost, other variable cost, customer
revenue and exact basis-point gross margin. Production activation fails closed
without positive margin, a configured owner-approved margin policy reference and its
floor. There is no approved production margin floor, Credit price or pack.

Organisation policy caps Credits per operation/day, provider-cost exposure per day,
trial Credits per day and operations per minute. Global, action and
provider-capability circuit breakers stop new execution while allowing settlement,
release and reconciliation of prior work. Auto-top-up is off and absent.

## Persistence, security and customer data

Migration 0054 follows 0053 and keeps one Alembic head. All seven tenant tables use
explicit organisation predicates, composite tenant relationships and forced
PostgreSQL RLS. Catalogue, control-event and ledger history is database-immutable.
Customer APIs accept bounded typed inputs and reject extra/forged price or provider
cost fields. Support and infrastructure mutations have no public route.

Export v33 adds safe balance, lot, operation and transaction history without provider
cost/request or idempotency internals. Offboarding fails closed when Credit ledger
history exists because the accounting-retention treatment remains a pre-live owner
decision; this work order invents no legal period and deletes no history.

## Admin UI

Settings now provides an admin-only Oryntela Credits area with Available, Purchased
and Promotional balances, reserved context, recent activity and explicit ordinary
software guidance. TEST pack details remain visibly non-customer pricing and cannot
be purchased. The component includes loading, empty, error/retry, semantic,
keyboard/focus, reduced-motion-compatible and responsive 390 px states. Screenshots
are retained with this record after visual validation.

## Verification scope

Automated coverage exercises ledger and balance invariants; purchased/promotional
ordering; trial expiry; verified and mismatched purchases; refunds/corrections;
full, partial, zero, failure and unknown outcomes; reconciliation; versioned
successful-unit/requested-unit charge bases; V1/V2 quote pinning; stale/tampered
input; exact money and margin cases; every exposure control;
global/action/provider circuit breakers; cross-tenant denial; migration
downgrade/re-upgrade and drift; and real PostgreSQL contention for reservation,
purchase, settlement, release and correction.

## UI evidence

- [Desktop Credits Settings](assets/wo-049-credits-settings-desktop.png)
- [390 px Credits Settings](assets/wo-049-credits-settings-mobile.png)

## Explicit boundary

No live provider, Apollo contact/activation, live Stripe, production Credit price or
pack, real sale, customer data, deployment, SMS, voice, native mobile, website,
rebrand or WO-050 work was started. Spend is AUD $0.

See [Credits and variable-cost controls](../03-engineering/credits-variable-cost-controls.md),
[Credits commercial model](../04-commercial/oryntela-credits-commercial-model.md) and
[Variable-cost safety gate](../03-engineering/oryntela-variable-cost-safety-gate.md).
