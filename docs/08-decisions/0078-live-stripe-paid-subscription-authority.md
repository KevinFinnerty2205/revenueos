# ADR 0078 — Mode-isolated live Stripe paid-subscription authority

- **Status:** Accepted for engineering; external activation blocked
- **Date:** 11 September 2026
- **Work order:** WO-054B remediation

## Context

WO-048 established provider-neutral billing and a deterministic/Stripe test path, but
it did not admit live mode or persist an independently confirmed paid-through period.
A Checkout success redirect and an active subscription status are not proof that the
current invoice settled. The owner selected live Stripe for paid subscriptions and
explicitly rejected extending WO-055's exceptional manual paid-Credit workflow into a
general subscription ledger. GST treatment, provider setup, production spend and live
activation remain outside the engineering authority.

Stripe can deliver duplicate and out-of-order events. Its current Clover contract
places the service period on subscription items, exposes environment through
`livemode`, and links invoices to subscriptions through parent subscription details.
The system therefore needs durable mode and payment authority without storing raw
payment payloads or card data.

## Decision

Keep the existing provider-neutral modular-monolith boundary and direct REST adapter.
Admit explicit `test` and `live` provider modes, while restricting production-enabled
billing to Stripe live mode and deterministic CI to test mode. Scope billing accounts,
operations, subscriptions, invoices and immutable event receipts by selected provider
and mode. A key prefix, object/event `livemode`, webhook signing secret and pinned API
version must all agree; mismatches fail closed.

The immutable Oryntela plan/version catalogue remains price authority. Six configured
Stripe Price IDs map server-side to Core/Growth/Complete v1 monthly/annual terms. A
read-only production preflight and checkout-time verification require exact ID,
activity, AUD amount, recurrence and `oryntela_plan_version_id` metadata. The browser
does not supply provider Price IDs.

Paid entitlement requires a verified current Stripe subscription, its current latest
paid invoice, and a valid Stripe-supplied subscription-item service period. Persist
provider service period separately from confirmed `paid_period_start`, `paid_through`
and bounded payment state. A success URL, checkout-complete event without a paid
invoice, old paid invoice or stale provider state grants no new entitlement. Current
provider retrieval, provider timestamps and immutable mode-scoped receipts make retry,
replay and out-of-order processing converge.

Keep the approved WO-048 policies: provider-bounded past-due recovery preserves
existing access; terminal unpaid/cancelled ends provider-managed paid authority;
higher-tier changes require a paid provider-calculated invoice; lower-tier and
interval changes apply at renewal; cancellation is end-of-period with pre-end
reactivation and fresh checkout after ending. The live customer portal is a separately
configured Stripe-hosted surface.

Production configuration includes an unresolved/inclusive/exclusive tax switch plus a
durable owner/accounting policy reference. Live mode refuses unresolved GST. This
decision does not choose inclusive/exclusive presentation or Stripe Tax.

## Alternatives considered

- Extend WO-055 into a manual subscription ledger: rejected by the owner; it would
  duplicate payment, renewal, invoice and expiry authority and blur the exceptional
  paid-Credit control.
- Treat active subscription or Checkout redirect as payment: rejected because neither
  proves current settled funds.
- Trust event snapshots in arrival order: rejected because Stripe retries and does not
  guarantee event order.
- Adopt or upgrade a Stripe SDK: unnecessary; the bounded direct REST adapter already
  pins the required contract and no Stripe SDK dependency exists.

## Consequences

Migration `0062_live_stripe_billing` widens existing account/receipt mode checks, adds
mode to operations, scopes invoice identity to its mode-owned subscription and adds
payment/paid-period fields to the existing forced-RLS subscription table. It is the
smallest schema change that makes payment authority and test/live identity durable.
Downgrade refuses while live authority exists. Export
v38 adds the safe payment fields but continues to omit provider identifiers, hosted
links, webhook bodies, credentials and card data.

The feature flag is the billing mutation kill switch; a configured Stripe endpoint
continues verified reconciliation while mutations are disabled. Operational rollback
retains the forward schema and settles unknown outcomes before credential revocation.

Engineering readiness does not mean live readiness. GST/legal approval, Stripe account
verification, live Products/Prices, secrets, webhook, portal, read-only external
preflight and a separately authorised minimum synthetic live smoke all remain blocking.
WO-054B creates none of them, uses no customer data or real charge and spends AUD 0.
