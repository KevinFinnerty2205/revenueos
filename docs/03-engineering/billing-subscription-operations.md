# Billing and subscription operations

- **Status:** test and live Stripe engineering implemented; live activation remains blocked
- **Migrations:** `0053_billing_subscriptions`, `0062_live_stripe_billing`
- **Providers:** deterministic test provider and mode-separated Stripe adapter
- **Live billing:** production-capable but not configured, authorised or activated
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
provider-confirmed immediate upgrade, next-renewal change, hosted billing portal and
signed-event verification. Proration is an invoice fact returned by the provider;
it is not calculated by Oryntela or WO-047 commercial authority. Provider DTOs are
translated into Oryntela states rather than leaking provider enums into commercial
policy.

The deterministic provider is the default for local tests and CI. It can model
success, abandonment, duplicate/out-of-order events, failure, cancellation, renewal
and unknown checkout or subscription-mutation results without network or
credentials. The Stripe adapter uses Stripe's HTTPS API directly in explicit `test`
or `live` mode. Production permits billing only with `stripe` plus `live`; local/CI
deterministic billing remains `test` only. Secret-key prefixes, webhook event/object
`livemode`, event API version and the official Stripe API origin must agree with the
selected mode. Account, subscription, invoice, operation and receipt queries include
provider mode, so a test object cannot satisfy live authority or block a live-mode
checkout.

Provider price identifiers live only in environment configuration. Production
preflight retrieves all six configured Prices and verifies exact identifier, active
state, AUD currency, amount, recurrence interval/count and the immutable plan-version
metadata before billing can be enabled. Checkout independently repeats verification
for its server-selected Price. The browser never supplies a Price ID.

| Plan version | Interval | Exact authority | Required Price metadata |
| --- | --- | ---: | --- |
| Core v1 `ee299a7d-3f12-5845-847e-3425f78ed6f2` | monthly | AUD 200 | `oryntela_plan_version_id=ee299a7d-3f12-5845-847e-3425f78ed6f2` |
| Core v1 `ee299a7d-3f12-5845-847e-3425f78ed6f2` | annual | AUD 2,000 | same Core v1 UUID |
| Growth v1 `2d8aa6a4-30aa-52e8-8273-3859210a8406` | monthly | AUD 350 | `oryntela_plan_version_id=2d8aa6a4-30aa-52e8-8273-3859210a8406` |
| Growth v1 `2d8aa6a4-30aa-52e8-8273-3859210a8406` | annual | AUD 3,500 | same Growth v1 UUID |
| Complete v1 `43cb5fa7-1b0b-5ca7-b5a3-740bd3e063a0` | monthly | AUD 500 | `oryntela_plan_version_id=43cb5fa7-1b0b-5ca7-b5a3-740bd3e063a0` |
| Complete v1 `43cb5fa7-1b0b-5ca7-b5a3-740bd3e063a0` | annual | AUD 5,000 | same Complete v1 UUID |

No Stripe account, Product, Price, webhook, portal configuration, customer or charge
was created by WO-054B, and no Stripe network smoke was performed.

## Tenant-owned model

- `billing_accounts` owns the unique organisation-to-provider customer mapping.
- `billing_subscriptions` stores the bounded status, plan-version reference,
  interval, provider service period, independently confirmed paid period/paid-through
  boundary, payment state, scheduled cancellation or next-renewal change, provider
  timestamps and reconciliation state. A partial unique index permits only one
  non-cancelled subscription per mode-owned billing account.
- `billing_invoice_projections` stores invoice date, AUD amounts, optional
  provider-reported tax total, bounded status and validated provider-hosted links
  only. It does not label that total as GST or decide inclusive/exclusive treatment.
- `billing_operations` gives checkout, portal, cancellation, reactivation, plan
  change and future Credit-purchase preparation mode-scoped stable idempotency and
  safe audit.
- `billing_provider_event_receipts` stores immutable event identity/type, provider
  time and result without retaining the webhook body or related payment objects.

Every tenant-owned table has explicit organisation predicates, composite tenant
relationships and forced PostgreSQL RLS. Provider customer, subscription, invoice
and event identities are unique within provider and mode. One provider customer
cannot map to two organisations. Billing history uses restrictive organisation
foreign keys: offboarding refuses blind deletion until an approved statutory
retention/disposal policy is supplied.

Export schema v38 includes safe account, subscription, invoice, operation and event
projections. It deliberately omits provider customer/subscription/invoice/event
identifiers, idempotency keys, hosted links, webhook bodies and payment credentials.

## Checkout and idempotency

Only active organisation administrators may mutate billing. A checkout operation
uses a client-stable idempotency key bound to organisation, member, plan and interval.
Reusing it for the same request returns the same hosted result; reusing it for a
different request fails. Stripe receives the same key as its idempotency key. If a
provider call times out, the operation remains `unknown_reconciliation`; retrying
uses the same operation/provider key and never assumes that a second subscription is
safe. A successfully created hosted session remains unresolved until its verified
completion event and the database permits only one pending/unknown checkout per
organisation. Another key therefore cannot open a parallel subscription checkout;
an expired provider session must be resolved before a fresh key is accepted.

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
Stripe uses the mode-specific `API_STRIPE_WEBHOOK_SECRET` and timestamped
`Stripe-Signature` HMAC with a bounded replay window. Invalid, stale, oversized,
wrong-mode, wrong-version or wrong-provider requests fail before domain mutation.

Reconciliation follows these rules:

1. verify the signature and bounded event contract;
2. resolve the server-owned customer mapping;
3. for checkout completion, verify the stored checkout operation and retrieve the
   current checkout object;
4. retrieve the current provider subscription and its current latest invoice instead
   of trusting event metadata as entitlement authority;
5. translate the provider price back to exactly one canonical plan/interval;
6. apply billing and commercial changes with the immutable event receipt in one
   transaction.

Duplicate event identifiers return the stored result and have no second commercial
effect. Provider retrieval makes delayed updates converge on current state. A stale
provider timestamp cannot overwrite newer state, and an old paid invoice cannot move
the paid-through boundary when it is no longer the subscription's latest invoice.
Unsupported signed event types are acknowledged without tenant lookup or mutation.
Ambiguous supported events return a retryable failure without writing an immutable
receipt, so provider delivery can converge after a checkout/database overlap; they
cannot grant an entitlement. Logs never contain webhook payloads or payment data.

## Subscription policy

The provider-neutral states are `pending`, `active`, `past_due`,
`cancel_at_period_end`, `cancelled`, `unpaid`, `incomplete` and
`unknown_reconciliation`.

- Active/cancel-at-period-end status activates the matching WO-047 plan only when the
  current latest invoice is verified paid and its Stripe-supplied item service period
  establishes a future `paid_through`. The current subscription must have exactly one
  item with quantity one; multi-item or quantity changes fail reconciliation. Checkout
  completion or its success redirect alone never grants access.
- `past_due` is the bounded payment-recovery state. It marks payment as needing
  attention, preserves existing access and data, and offers the hosted resolution
  path while the provider runs its configured retry policy. Oryntela does not
  hard-code or extend the retry duration.
- A verified terminal `unpaid` or `cancelled` fact ends billing-provider-managed
  commercial authority and paid functionality without deleting customer data. A
  later verified active fact can restore paid authority through the normal
  commercial transition.
- Cancellation is scheduled for period end. Paid access continues until the recorded
  end, after which a verified terminal provider state moves billing-provider-managed
  commercial state to inactive without deleting retained data.
- A scheduled cancellation may be reversed before period end when the provider
  permits it. An ended subscription uses a new checkout for the same organisation.
- A genuinely higher-tier change is immediate only after the current provider state
  confirms the target plan. The provider calculates and invoices proration;
  ambiguous or payment-incomplete results leave the previous commercial plan
  authoritative until reconciliation succeeds.
- Lower-tier changes take effect at current paid period end. Same-tier interval
  changes also use the renewal boundary. The provider schedule can be replaced or
  released safely; WO-047 applies the effective downgrade once and preserves paid
  capabilities until then without deleting data.

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

WO-048 introduced `credit_purchase` as a reserved billing-operation kind. WO-049 now
attaches separate TEST-only Credit infrastructure: an exactly matched, verified
test-mode payment event can atomically create one purchased lot and ledger grant.
There is still no public purchase endpoint, live provider product mapping, production
price/pack, live payment or real sale. All Credit semantics belong to
[Credits and variable-cost controls](credits-variable-cost-controls.md).

## Production configuration and blocked activation

The checked-in production template remains deliberately inactive. A live target must
set `API_FEATURE_BILLING_ENABLED=true`, `API_BILLING_PROVIDER_NAME=stripe` and
`API_BILLING_MODE=live`, safe success/cancel/portal-return URLs, an `sk_live_` value in
`API_STRIPE_SECRET_KEY`, the endpoint's `whsec_` value in
`API_STRIPE_WEBHOOK_SECRET`, the exact verified `acct_` value in
`API_STRIPE_ACCOUNT_ID`, an active live `bpc_` value in
`API_STRIPE_PORTAL_CONFIGURATION_ID`, and the six `API_STRIPE_PRICE_*` mappings.
`API_STRIPE_API_VERSION` remains exactly `2026-02-25.clover` and the API origin remains
`https://api.stripe.com`.

GST remains unresolved. `API_BILLING_TAX_TREATMENT` must stay `unresolved` and the
billing flag must stay false until the owner/accounting decision supplies either
`inclusive` or `exclusive` plus a durable `API_BILLING_TAX_POLICY_REFERENCE`. This
engineering work does not choose tax wording or activate Stripe Tax.

The exact live webhook URL is
`https://api.oryntela.com.au/api/v1/billing/webhooks/stripe`. Subscribe only to
`checkout.session.completed`, `customer.subscription.updated`,
`customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`,
`invoice.finalized`, `invoice.voided` and `invoice.marked_uncollectible`, pinned to the
same API version. Portal configuration is a separate live object; start with invoice
history, billing details and payment-method updates, keep plan switching and promotion
codes off, and use the configured return URL. Both remain external owner actions.

The adapter is direct REST over `httpx`; there is no Stripe SDK dependency to upgrade.
The pinned REST contract was reverified against Stripe's current Clover changelog.
Subscription periods come from `subscription.items.data[]`, invoice subscription
identity comes from `invoice.parent.subscription_details.subscription`, and live/test
authority comes from Stripe's `livemode` field.

Live billing must remain disabled until GST, legal terms, retention, the Stripe
account and live catalogue, portal policy, webhook, secret management, monitoring,
external preflight and a separately authorised synthetic/minimum live smoke have all
passed. No customer data, raw card data, provider action, charge or spend was used in
WO-054B.

## Provider references

- [Stripe Checkout Sessions](https://docs.stripe.com/api/checkout/sessions)
- [Stripe webhook signatures and replay protection](https://docs.stripe.com/webhooks)
- [Stripe API versioning](https://docs.stripe.com/api/versioning)
- [Subscription item billing-period change](https://docs.stripe.com/changelog/basil/2025-03-31/deprecate-subscription-current-period-start-and-end)
- [Stripe subscription schedules](https://docs.stripe.com/api/subscription_schedules/object)
- [Stripe subscription updates and proration behaviour](https://docs.stripe.com/api/subscriptions/update)
- [Stripe idempotent requests](https://docs.stripe.com/api/idempotent_requests)
