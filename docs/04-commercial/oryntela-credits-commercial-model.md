# Oryntela Credits commercial model

- **Status:** **WO-049 INFRASTRUCTURE IMPLEMENTED; PRODUCTION VALUES UNDECIDED**
- **Consolidated:** 5 September 2026
- **Boundary:** provider-neutral mechanics exist in TEST mode; no production price,
  pack, provider, live Stripe payment or real Credit sale exists

## Purpose

The subscription pays for Oryntela software. Prepaid Oryntela Credits may fund
services for which Oryntela incurs material third-party variable cost. Customers buy
an Oryntela unit of value, not a named provider's API unit, so providers can change
without changing the customer mental model.

Credits must not turn ordinary use into a coin-operated experience.

## What should and should not consume Credits

| Generally subscription-funded                                                      | Potentially Credit-funded                       |
| ---------------------------------------------------------------------------------- | ----------------------------------------------- |
| Sales Brain and normal intelligence consumption                                    | Paid Prospect company/person research           |
| Daily, Methodology and Actions                                                     | Contact-data enrichment and paid verification   |
| Pipeline, Analytics, Targets and Forecast                                          | SMS and future telephony                        |
| Manager Intelligence and Native CRM workflow                                       | Future AI voice/SDR calls                       |
| Navigation, Search and normal Ask use within fair-use controls                     | Expensive third-party document/media generation |
| Reviewed email through a customer's mailbox where no material per-send cost exists | Other metered APIs with material unit cost      |

A module entitlement and a Credit balance answer different questions. A customer may
own a module but lack Credits for a paid provider operation; owning Credits does not
grant access to a module or override permission, licensing, quota or provider health.

## Customer experience

Before a paid operation, show the exact Credit cost or a conservative maximum. Show
the current balance, intended operation, quantity and who may approve it. Default to
no automatic top-up. If balance is insufficient, stop the paid operation without
breaking the rest of Oryntela.

On failure, explain whether Credits were reserved, used, released or refunded. Do not
expose raw supplier cost or require customers to understand provider-specific units.
Receipts and an exportable history should reconcile purchases, grants, reservations,
usage, release, refund and manual adjustment.

## Commercial invariant

Every material third-party variable-cost service sold through Oryntela must have a
credible positive-gross-margin path. A universal markup is not approved. The initial
strategic hypothesis is a healthy SaaS-like usage gross margin, potentially 60–70%
where customer value and market pricing allow, but this is not a committed target for
every operation.

```text
fully loaded variable cost
= provider cost + FX/tax + expected retry/failure + incremental infrastructure/support

gross margin
= (customer price - fully loaded variable cost) / customer price
```

Illustrative only: if an operation costs AUD $0.20 at the provider and AUD $0.05 in
expected retry/infrastructure/support, its fully loaded cost is AUD $0.25. A customer
price of AUD $1.00 would produce 75% gross margin. That is a margin calculation, not a
recommendation for a Credit value or operation price. A 300% markup on AUD $0.25 is
not the same statement as 75% margin.

## Implemented infrastructure

WO-049 implements the commercial safety mechanics without deciding the commercial
values:

- integer, organisation-owned purchased and promotional balances backed by lots;
- an append-only transaction ledger and independently reconcilable balance projection;
- server-owned versioned action prices and Credit-pack catalogue records;
- quote, reservation-before-execution, full/partial/zero settlement, release and
  explicit unknown-outcome reconciliation;
- verified TEST billing purchase grants, bounded trial promotional grants, expiry,
  referenced refunds and actor/reason/reference corrections;
- exact provider-cost, FX, customer-revenue and basis-point margin calculation;
- per-operation, daily, provider-cost, trial and rate exposure limits;
- global, action and provider-capability emergency controls;
- forced tenant RLS, cross-tenant relationship constraints and retry-safe
  idempotency; and
- admin balance/activity UI plus safe organisation export history.

The deterministic catalogue contains a 100-Credit AUD $20 test pack and a synthetic
5-Credit research action solely to validate the system. Every surfaced value is
labelled `TEST ONLY / NOT CUSTOMER PRICING`, and purchase is disabled. These figures
must not be quoted or inferred as Oryntela pricing.

## Safety rules retained for production activation

- prepaid authoritative organisation balance; never negative (implemented);
- immutable tenant-scoped ledger and idempotent reservation/settlement/refund
  (implemented);
- no double charge under user, worker, network or provider retry;
- atomic purchase and balance update with safe unknown-payment handling;
- explicit roles, purchase limits and separately approved auto-top-up if ever offered;
- reservation expiry/cancellation and partial-batch reconciliation;
- provider receipt and unknown-outcome policy;
- versioned Credit price and provider-cost basis (implemented structurally; production
  values absent);
- promotional Credits distinguishable from purchased Credits (implemented);
- organisation/provider/trial exposure caps and abuse controls (implemented); and
- export and support-dispute history (implemented), with chargeback policy and legal/
  accounting retention still requiring owner decisions.

Credits do not override provider rate limits, availability, permission, suppression,
legal constraints or customer contactability. Queued paid work must revalidate all of
them when execution begins.

## Undecided production prices and policies

- value of one Credit;
- action catalogue and per-action price/max price;
- packages, currency, tax and minimum purchase;
- purchased/promotional expiry and rollover;
- trial allowance and whether trial purchase is permitted;
- refund rules for partial, failed and unknown outcomes;
- customer vs organisation purchase permissions;
- enterprise committed pools/invoiced usage;
- billing provider, stored-value/legal/accounting treatment; and
- provider-specific cost, margin and loss caps.

No production Credit catalogue or provider-backed operation may activate until the
[variable-cost safety gate](../03-engineering/oryntela-variable-cost-safety-gate.md)
passes for that operation and the owner approves its exact economics. WO-049 is an
infrastructure implementation, not that approval.
