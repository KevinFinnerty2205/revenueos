# Billing and subscription operations

- **Status:** Billing architecture / test mode implemented by WO-048
- **Migration:** `0053_billing_subscriptions`
- **Providers:** deterministic test provider and Stripe test-mode adapter
- **Live billing:** not authorised or activated
- **Legal billing entity:** Management Services Australia Pty. Ltd., ABN 15 113 119 556

## Authority boundary

Billing supplies verified payment and subscription facts to the existing WO-047
commercial authority. It does not calculate plan contents, user limits or module
entitlements. The immutable commercial catalogue remains canonical for the six
self-service offers:

| Plan     | Monthly term | Annual prepayment |
| -------- | -----------: | ----------------: |
| Core     | AUD 200      | AUD 2,000         |
| Growth   | AUD 350      | AUD 3,500         |
| Complete | AUD 500      | AUD 5,000         |

Enterprise has no self-service price or checkout. Its route remains a manual
commercial process. The server accepts only a plan code and monthly/annual interval,
then resolves the exact amount, AUD currency and configured provider price. It never
accepts a browser-supplied amount, currency, provider price identifier, entitlement,
subscription status or trial date.

The existing 14-day trial remains an Oryntela no-card clock. It does not become a
provider trial and never converts automatically. A verified paid subscription ends
trial/grace through a normal, history-preserving commercial transition for the same
organisation.

## Provider boundary

`BillingProvider` expresses the bounded operations Oryntela needs: hosted checkout,
subscription and invoice retrieval, cancellation at period end, reactivation,
next-renewal plan change, hosted billing portal and signed-event verification.
Provider DTOs are translated into Oryntela states rather than leaking provider enums
into commercial policy.

The deterministic provider is the default for local tests and CI. It can model
success, abandonment, duplicate/out-of-order events, failure, cancellation, renewal
and an unknown checkout result without network or credentials. The Stripe adapter
uses Stripe's HTTPS API directly and is restricted to `sk_test_` credentials and
configured test price identifiers. Production configuration rejects billing
activation, Stripe selection, live keys and non-official Stripe API endpoints.

Provider price identifiers live only in environment configuration. On first use the
Stripe adapter retrieves each price and verifies active state, AUD currency, amount,
recurrence interval and term against the WO-047 catalogue before opening checkout.
No Stripe account was created or changed and no network smoke test was performed,
because no owner-approved test account credentials were available.

## Tenant-owned model

- `billing_accounts` owns the unique organisation-to-provider customer mapping.
- `billing_subscriptions` stores the bounded status, plan-version reference,
  interval, current paid period, scheduled cancellation or next-renewal plan change,
  provider timestamps and reconciliation state.
- `billing_invoice_projections` stores invoice date, AUD amounts, optional
  provider-reported tax total, bounded status and validated provider-hosted links
  only. It does not label that total as GST or decide inclusive/exclusive treatment.
- `billing_operations` gives checkout, portal, cancellation, reactivation, plan
  change and future Credit-purchase preparation stable idempotency and safe audit.
- `billing_provider_event_receipts` stores immutable event identity/type, provider
  time and result without retaining the webhook body or related payment objects.

Every tenant-owned table has explicit organisation predicates, composite tenant
relationships and forced PostgreSQL RLS. Provider customer, subscription, invoice
and event identities are unique within provider and mode. One provider customer
cannot map to two organisations. Billing history uses restrictive organisation
foreign keys: offboarding refuses blind deletion until an approved statutory
retention/disposal policy is supplied.

Export schema v32 includes safe account, subscription, invoice, operation and event
projections. It deliberately omits provider customer/subscription/invoice/event
identifiers, idempotency keys, hosted links, webhook bodies and payment credentials.

## Checkout and idempotency

Only active organisation administrators may mutate billing. A checkout operation
uses a client-stable idempotency key bound to organisation, member, plan and interval.
Reusing it for the same request returns the same hosted result; reusing it for a
different request fails. Stripe receives the same key as its idempotency key. If a
provider call times out, the operation remains `unknown_reconciliation`; retrying
uses the same operation/provider key and never assumes that a second subscription is
safe.

Checkout and portal URLs are provider-hosted HTTPS links on an explicit allowlist.
Application success/cancel/portal return URLs are fixed server configuration, with
HTTPS required outside exact localhost development. Oryntela contains no card form
and never receives or stores card number, CVV or complete payment credentials.

The `/billing/success` page reads server state only. Visiting or forging that URL
cannot grant access; it reports payment confirmation pending until a verified
provider fact has been reconciled.

## Webhook verification and reconciliation

The webhook route is intentionally outside user authentication and instead requires
the selected provider's signature. The deterministic provider uses an HMAC signature;
Stripe uses the timestamped `Stripe-Signature` HMAC with a bounded replay window.
Invalid, oversized or wrong-provider requests fail before domain mutation.

Reconciliation follows these rules:

1. verify the signature and bounded event contract;
2. resolve the server-owned customer mapping;
3. for checkout completion, verify the stored checkout operation and retrieve the
   current checkout object;
4. retrieve the current provider subscription/invoice instead of trusting event
   metadata as entitlement authority;
5. translate the provider price back to exactly one canonical plan/interval;
6. apply billing and commercial changes with the immutable event receipt in one
   transaction.

Duplicate event identifiers return the stored result and have no second commercial
effect. Provider retrieval makes delayed updates converge on current state. A
terminal cancellation is not overwritten by a stale active update. Ambiguous or
unmapped events are recorded for reconciliation and cannot grant an entitlement.
Logs contain safe event/result identifiers only, not webhook payloads or payment
data.

## Subscription policy

The provider-neutral states are `pending`, `active`, `past_due`,
`cancel_at_period_end`, `cancelled`, `unpaid`, `incomplete` and
`unknown_reconciliation`.

- Active verified subscription facts activate the matching WO-047 plan once.
- Past-due or unpaid facts mark payment as needing attention and offer the hosted
  resolution path. V1 does not invent dunning, delete data or automatically remove
  access.
- Cancellation is scheduled for period end. Paid access continues until the recorded
  end, after which a verified terminal provider state moves billing-provider-managed
  commercial state to inactive without deleting retained data.
- A scheduled cancellation may be reversed before period end when the provider
  permits it. An ended subscription uses a new checkout for the same organisation.
- Upgrades and downgrades are scheduled for the next renewal with no immediate
  proration. This is the safest implemented test policy, not approved live commercial
  policy; owner/accounting approval is required before live activation.

Provider invoices remain the source of invoice/receipt documents. Oryntela displays
only dates, amounts, currency, state and validated hosted links. Existing provider
refund facts can be projected during reconciliation, but no refund operation or
general refund policy is implemented.

## Customer and support surfaces

Billing & Plan Settings distinguishes trial, manually managed/unconfigured billing,
active, past-due, scheduled cancellation, cancelled and reconciliation-pending
states. It shows the actual renewal/access date and invoice projection, prepares the
six exact offers for review, and links to hosted checkout or the billing portal. It
does not claim that reminders are sent or display synthetic payment details.

The hosted portal is an external management surface only. Portal changes still need
verified webhook/provider reconciliation before Oryntela state changes. Browser/API
authorisation is tenant-derived and organisation-admin-only; arbitrary provider IDs
are never accepted from the client.

## Credit purchase boundary

`credit_purchase` is a reserved billing-operation kind and provider-neutral boundary
only. There is no public endpoint, provider product mapping, price, purchase flow,
balance, allowance, pack, ledger, grant, expiry, refund or consumption. WO-049 owns
all Credit semantics and has not started.

## Pre-live decisions and proof

Live billing must remain disabled until a separately authorised work order completes
all applicable items:

- owner/accounting approval of GST-inclusive versus +GST presentation, tax-invoice
  wording and any Stripe Tax configuration;
- owner approval of renewal plan-change/proration timing, dunning/access policy,
  refunds, discounts, public prices and customer terms;
- approved billing-history statutory retention, export and disposal procedure;
- Stripe account ownership, commercial terms, business verification, bank/payout
  details, test/live product and price configuration, portal policy and production
  webhook setup;
- production secret management, key rotation, alerting, reconciliation/support
  runbook and target-environment proof; and
- authorised live-mode integration tests covering tax, invoice, payment failure,
  cancellation, refunds and recovery without customer data.

The Stripe REST contract is pinned to `2026-02-25.clover`; test webhook endpoints
must emit that version. This avoids silently inheriting an account default and reads
the current paid period from subscription items. WO-048 used deterministic fixtures
only, no customer data, no live provider action, no real charge and AUD $0 spend.

## Provider references

- [Stripe Checkout Sessions](https://docs.stripe.com/api/checkout/sessions)
- [Stripe webhook signatures and replay protection](https://docs.stripe.com/webhooks)
- [Stripe API versioning](https://docs.stripe.com/api/versioning)
- [Subscription item billing-period change](https://docs.stripe.com/changelog/basil/2025-03-31/deprecate-subscription-current-period-start-and-end)
- [Stripe subscription schedules](https://docs.stripe.com/api/subscription_schedules/object)
