# Oryntela Credits commercial model

- **Status:** **OWNER-APPROVED CONCEPT; VALUES AND IMPLEMENTATION UNDECIDED**
- **Consolidated:** 4 September 2026
- **Boundary:** No balance, ledger, purchase, billing or provider activation exists

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

## Required future safety

- prepaid authoritative organisation balance; never negative;
- immutable tenant-scoped ledger and idempotent reservation/settlement/refund;
- no double charge under user, worker, network or provider retry;
- atomic purchase and balance update with safe unknown-payment handling;
- explicit roles, purchase limits and separately approved auto-top-up if ever offered;
- reservation expiry/cancellation and partial-batch reconciliation;
- provider receipt and unknown-outcome policy;
- versioned Credit price and provider-cost basis;
- promotional Credits distinguishable from purchased Credits;
- organisation/provider/trial exposure caps and abuse controls; and
- export, chargeback, support-dispute and accounting operations.

Credits do not override provider rate limits, availability, permission, suppression,
legal constraints or customer contactability. Queued paid work must revalidate all of
them when execution begins.

## Open decisions

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

No implementation may begin until billing/entitlement authority is defined and the
[variable-cost safety gate](../03-engineering/oryntela-variable-cost-safety-gate.md)
passes for the first operation.
