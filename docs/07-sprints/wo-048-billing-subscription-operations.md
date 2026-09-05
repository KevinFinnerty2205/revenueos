# WO-048 — Billing & Subscription Operations

- **Branch:** `codex/wo-048-billing-subscriptions`
- **Baseline:** `d884e770772c6b983d37635141f49809dff37ee4`
- **Status:** billing architecture / test mode implemented; engineering review completed
- **Migration:** `0053_billing_subscriptions`
- **Provider/data/spend boundary:** deterministic test provider and unactivated Stripe
  test adapter; synthetic data only; AUD $0

## Outcome

WO-048 adds provider-neutral, tenant-owned billing operations over the WO-047
commercial authority. The API prepares hosted checkout for the exact Core, Growth
and Complete monthly/annual catalogue, reconciles verified subscription and invoice
facts, supports cancellation at period end, pre-end reactivation, next-renewal
changes, provider-confirmed immediate higher-tier upgrades with provider-calculated
proration and a hosted provider portal, and projects truthful state in Billing &
Plan Settings. Enterprise remains manual.

The deterministic provider exercises the entire lifecycle without a network. A
Stripe adapter implements the same boundary for test keys and configured test price
identifiers, but was not activated because this work order authorised no account,
verification, terms, bank/payout, production webhook or live-mode action.

## Trust and lifecycle

Checkout amount, AUD currency, interval, plan contents, organisation and actor are
server-derived. Stable idempotency protects checkout and every consequential
operation. Hosted flows keep raw card data outside Oryntela. A browser success URL
never grants access. A hosted checkout remains unresolved until its verified
completion event, preventing another key from opening a parallel subscription.

Signed events resolve a unique server-owned customer mapping and retrieve current
provider objects before changing state. Immutable receipts make duplicate delivery
one-effect; current-object reconciliation and a terminal-cancellation guard make
out-of-order delivery safe. Trial-to-paid and grace-to-paid reuse the same
organisation, retain data and append commercial history.

Past-due status is a provider-bounded payment-recovery state with visible remediation
and no data deletion. A verified terminal unpaid/cancelled state ends paid commercial
authority without deleting retained data. Scheduled cancellation retains paid access
until period end. Higher-tier upgrades apply immediately only after verified provider
confirmation and use the provider's proration invoice; lower-tier and same-tier
interval changes apply at renewal. Exact live retry/dunning configuration still
requires owner approval before production use.

## Persistence, security and lifecycle

Migration 0053 adds billing account, subscription, invoice projection, idempotent
operation and immutable provider-event receipt tables. Tenant predicates, composite
foreign keys and forced PostgreSQL RLS apply throughout. Provider identities are
unique per provider/mode, client-supplied provider IDs are rejected, safe return and
hosted URLs are allowlisted, test/live configuration fails closed, and webhook bodies
and payment credentials are neither stored nor logged.

Export v32 contains safe billing projections but excludes external identifiers,
idempotency keys and hosted links. Billing history is restrictively retained;
organisation deletion stops instead of guessing a statutory accounting disposal
policy.

## Verification scope

Tests cover all six exact checkout variants; Enterprise denial; price/currency/
interval tampering; checkout idempotency, abandonment, timeout and unknown outcome;
direct and trial/grace conversion; duplicate and out-of-order webhooks; signature,
replay, customer-collision and cross-tenant denial; successful, past-due, unpaid and
terminal states and recovery; cancellation, reversal, immediate upgrade and
replaceable/cancellable next-renewal downgrade; provider proration invoices;
forged success URLs; ordinary-seller denial; test/live confusion; migration
downgrade/re-upgrade; PostgreSQL RLS; export/deletion boundaries; and Settings/success
UI loading, active, attention, cancellation, manual, invoice, error, desktop, 390 px,
keyboard and focus states.

## UI evidence

- [Desktop Billing & Plan Settings](assets/wo-048-billing-settings-desktop.png)
- [390 px Billing & Plan Settings](assets/wo-048-billing-settings-mobile.png)

## Explicit boundary

Live billing, real charges, customer data, public launch, general refunds, approved
GST/tax policy, dunning/collections and production Stripe operations are not
implemented or activated. The Credit billing operation is a reserved boundary only:
there is no Credit price, pack, balance, ledger, grant, expiry, refund or usage.
WO-049 and all later work orders remain unstarted. Spend is AUD $0.

See [Billing and subscription operations](../03-engineering/billing-subscription-operations.md)
and [Commercial authority](../03-engineering/commercial-authority.md).
