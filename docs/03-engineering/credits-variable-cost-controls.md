# Credits and variable-cost controls

- **Status:** implemented infrastructure in TEST mode only
- **Migration:** `0054_credits_variable_cost`
- **Production Credit prices/packs/providers:** none
- **Spend and data boundary:** AUD $0; synthetic data only

## Purpose and unit

An Oryntela Credit is an integer customer-facing unit for a deliberately metered
operation that may create material third-party variable cost. It is not money,
provider currency, a provider API unit, a module entitlement, or permission to
contact a person. Ordinary Oryntela software and existing AI use remain
subscription-funded and outside this domain.

The database stores Credits as bounded integers, provider and customer revenue as
integer millionths of explicitly recorded currency units, pack amounts as integer
minor units with their currency, and FX as fixed-precision decimal. A Credit has no
fixed AUD value; the current accounting basis, TEST values and billing checks are
AUD-only. No binary floating-point money arithmetic is used.

## Authority and data model

`CreditPackVersion` and `CreditActionPriceVersion` are append-only global catalogues.
The only active catalogue is deterministic TEST data labelled
`TEST ONLY / NOT CUSTOMER PRICING`: 100 test Credits for AUD $20, and the synthetic
`PROSPECT_COMPANY_RESEARCH` action at 5 Credits per successful unit. Purchasing is
not exposed in the UI. Production configuration rejects Credit activation, and a
production action price cannot become active without complete cost inputs, positive
margin, an owner-approved margin-floor reference, and the configured floor. No such
approval or production version exists.

Tenant state consists of:

- a locked `OrganisationCreditBalance` projection with separate purchased and
  promotional available/reserved counters;
- `CreditLot` provenance, expiry, remaining quantity, and exact purchased-revenue
  attribution;
- server-owned `CreditQuote` rows pinned to one immutable action-price version;
- `CreditOperation` lifecycle rows plus lot-level reservation allocations;
- append-only `CreditLedgerEntry` events; and
- a fail-closed `CreditOrganisationPolicy` for local enablement and exposure caps.

Every tenant repository predicate includes `organisation_id`. Composite foreign keys
prevent cross-tenant attachment, and all seven tenant tables use enabled and forced
PostgreSQL RLS with the trusted transaction-local tenant setting. The browser never
supplies an organisation identifier.

## Ledger and balance invariant

The ledger records purchase, promotional grant, reservation, consumption, release,
refund, correction and expiry. Database triggers reject ledger update or deletion.
Every event has a tenant-scoped idempotency key, request fingerprint, actor, reason,
lot, exact deltas and optional operation/reference metadata.

The balance is a lockable projection, not independent commercial authority:

```text
available = purchased_available + promotional_available
reserved  = purchased_reserved + promotional_reserved
all projected and lot counters >= 0
ledger totals = balance projection = lot totals
```

Reservation serialises on the organisation balance row. Consumption draws
promotional lots first, earliest expiry first, then non-expiring promotional lots,
then purchased lots oldest first. The projection and lots change in the same
transaction as ledger entries. Reconciliation compares ledger, projection and lot
totals and reports mismatch; it never silently rewrites history.

## Grant, purchase, expiry, refund and correction

Purchased Credits can arise only from a successful WO-048 `credit_purchase`
`BillingOperation` whose verified provider event and retrieved checkout both confirm
paid status and match the server-owned TEST pack, AUD currency and exact amount. A
success redirect, pending payment, unsigned event, mismatched amount, duplicate fact
or arbitrary service call cannot grant value. The billing receipt, purchase lot,
ledger event and balance change commit atomically.

Promotional grants are an internal support operation requiring an actor, reason,
source, amount and stable idempotency key. A trial grant additionally requires an
active WO-047 trial, is limited to one per organisation, cannot exceed the configured
trial safety cap and cannot expire after the trial. Expired available promotional
Credits append an expiry event; reserved Credits do not disappear underneath
in-flight work, and a promotional refund retains the source lot's expiry.

A refund references an existing consumption entry and cannot exceed its net
refundable quantity. A correction is a separate, explicitly authorised event with
actor, reason and reference; it never edits old ledger rows and cannot drive a
balance negative. These mutation paths are deliberately absent from the public API.

## Quote, reserve, execute and settle

1. The server validates module write entitlement, feature/control state, quantity and
   the active immutable price version, then persists a short-lived quote containing
   the exact/max Credit cost and a fingerprint.
2. Confirmation submits only the quote ID and an idempotency key. Reservation locks
   the balance, revalidates the quote, entitlement, controls and caps, then moves lot
   amounts from available to reserved before provider work may begin.
3. Provider execution requires a reserved operation and rechecks the module
   entitlement, organisation policy, and global, action and provider-capability
   circuit breakers. Providers receive an operation identifier,
   requested units and idempotency key; they cannot mutate Credits.
4. Settlement follows the immutable action version's explicit customer charge basis:
   successful units or requested units. It attributes purchased revenue exactly,
   records provider cost internally and releases any unused reservation. The TEST
   action charges successful units, so zero success releases the whole amount and
   partial success consumes only the successful fraction; that policy is not assumed
   for every future provider.
5. A definite pre-value failure releases the reservation. An ambiguous provider
   result becomes `unknown` and remains reserved until explicit success/failure
   reconciliation. Disabling execution never blocks settlement, release or
   reconciliation of work that already ran.

A quote remains bound to its original price version. A later price version does not
silently increase an already valid quote; expired quotes must be refreshed. Bulk
quantity is multiplied server-side using bounded integer arithmetic, so the customer
sees the maximum aggregate Credit cost before confirmation.

## Cost, margin and exposure

Each action-price version preserves customer revenue per unit, provider native minor
units/currency and the minor-units-per-major scale, cost basis, FX rate/source/time,
other variable cost, expected and maximum AUD cost, derived gross margin, and any
approved floor/reference. The conservative check is:

```text
gross_margin_basis_points =
  ((customer_revenue_micros - maximum_variable_cost_micros) * 10_000)
  // customer_revenue_micros
```

Production eligibility requires positive gross profit and margin at or above the
owner-approved floor. The production floor and production prices remain undecided.

Before reservation, the service enforces maximum Credits per operation, Credits per
organisation per UTC day, maximum provider-cost exposure per organisation per UTC
day, an optional stricter trial daily cap, and operations per rolling minute. Daily
Credit and provider-cost checks include already reserved, executing and unknown work,
so multiple in-flight operations cannot collectively bypass a cap. Global,
action and provider-capability controls are internal only and append an immutable
control event with actor and reason. Organisation policy is disabled until explicitly
configured. Auto-top-up is off and not implemented.

## Public surface and customer UX

Authenticated members may request a server-owned quote and reserve it; module and
commercial policy remain authoritative. Only organisation admins may read the
Settings projection. Support grants, purchases, settlement, release, reconciliation,
refunds, corrections, price versions, policies and circuit breakers are internal
service boundaries with no customer mutation endpoint.

Settings shows Available, Purchased, Promotional, reserved context, recent readable
activity, a clear ordinary-software explanation, and TEST pack information with a
disabled purchase control. It never exposes provider cost, internal identifiers,
idempotency material or production-looking pricing. Loading, empty, error/retry,
keyboard, focus, reduced-motion and 390 px layouts are covered.

Organisation export v33 includes safe balance, lot, operation and transaction
history, excluding provider request/cost, fingerprints and idempotency keys. Because
Credits can be commercial/accounting history, organisation deletion fails closed
when ledger history exists until an owner-approved retention treatment is recorded;
no legal period has been invented.

## Provider contract and current boundary

`MeteredProvider.execute` is provider-neutral and returns the operation ID, safe
provider request reference, outcome, requested/successful units and exact provider
cost. The deterministic adapter is network-free and idempotent. It exists only to
prove success, partial, failure and unknown outcomes. No Apollo or other Prospect
provider, live Stripe, real Credit sale, customer data, SMS, voice or auto-top-up is
active. WO-050 reuses this lifecycle for a dormant Prospect provider adapter; see
[Live Prospect provider boundary](live-prospect-provider.md).
