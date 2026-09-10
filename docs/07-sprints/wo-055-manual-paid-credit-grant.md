# WO-055 — Manual Paid Credit Grant

- **Status:** complete; engineering review passed
- **Date:** 2026-09-10
- **Baseline:** `29d6b5aabe5b5776a77e9177a1d74c2f79ded315`
- **Branch:** `codex/wo-055-manual-paid-credit-grant`
- **Migration:** `0061_manual_paid_credit_grant`
- **Provider/data/spend boundary:** no provider activation; synthetic data only; AUD $0

## Outcome

WO-055 adds one supported owner operation for an exceptional negotiated bulk Credit
purchase. The normal customer path remains card payment, verified provider payment
reconciliation and an automatic purchased-Credit grant. The exceptional path is:

```text
external negotiation and invoice
→ cleared funds independently verified by an authorised internal operator
→ preview exact organisation, amount, Credits and current balance version
→ explicitly confirm cleared funds and the exact grant summary
→ append one immutable manual-paid record, purchased lot and purchase ledger event
→ update the locked balance in the same transaction
```

An issued invoice, purchase order, promised payment, pending transfer, screenshot,
customer email or accounts-payable confirmation is not authority. There is no unpaid
or pending Credit state. **Never grant paid Credits against an unpaid invoice.**

## Authority and operation

The operation reuses the existing `revenueos-operations` deployment/support CLI. It
is available only to an operator with the protected application runtime environment
and database connectivity; it has no HTTP route and no Billing Settings control.
Customer administrators, ordinary members/sellers and disabled members cannot invoke
it through the product.

`credits-manual-paid-preview` resolves the exact server-side organisation and shows
its name, stable UUID, plan, commercial state, current purchased/promotional/reserved
balance, balance lock version, amount, Credit quantity, payment facts, operator,
reason and the exact final confirmation phrase. A review fingerprint in that phrase
binds every displayed payment/audit fact, so any change requires another preview.
`credits-manual-paid-grant` additionally requires:

- a positive bounded integer Credit quantity;
- an exact positive AUD amount parsed to integer minor units, never a float;
- `BANK_TRANSFER`, `CARD_OUTSIDE_AUTOMATIC_FLOW` or `OTHER_APPROVED`;
- a bounded printable payment/reference identifier and timezone-aware received time;
- an explicit `--cleared-funds-confirmed` flag that is absent by default;
- an operator reference, concise reason and stable idempotency key;
- the inspected balance version and exact review-summary confirmation; and
- `--large-grant-reviewed` at 1,000,000 Credits or more as a warning/recheck, not a
  commercial maximum or separate approval policy.

The service rejects missing/inactive organisations and organisations without any
active member. A suspended organisation may preserve and receive paid Credits,
matching the existing purchased-Credit boundary, but the grant does not change its
commercial state, plan, trial, subscription, seats, modules or execution authority.

## Persistence, idempotency and accounting

`ManualPaidCreditGrant` is a completed-only immutable audit row. It records the
organisation, purchased lot, Credits, exact received minor units, AUD, payment
method/reference/time, cleared-funds confirmation, operator, reason, hashed
idempotency key, request/reference fingerprints, margin boundary and server grant
time. It is not an invoice, payment processor, general ledger or accounts-receivable
record.

The payment reference and idempotency key are each unique within an organisation.
Reference normalisation is case-insensitive and whitespace-stable. An identical retry
returns the completed grant, including after response loss; a reused identity with
changed organisation, Credits, amount, currency or any other audited fact fails.
Organisation balance locking serialises simultaneous attempts so one payment creates
exactly one logical grant. Conflicting simultaneous values produce one committed
winner and one explicit conflict. The locked aggregate held-Credit check prevents a
grant from exceeding the service arithmetic boundary.

The operation creates one non-expiring purchased `CreditLot`, one ordinary purchase
`CreditLedgerEntry` and the balance projection change atomically. The lot records
received value in exact revenue micros. Customer activity uses the safe label
**Purchased Credits** and the ledger reason contains neither payment reference nor
operator notes. The support-only payment record is not added to customer export;
existing safe lot and ledger history remains exported under the current policy.

## Refund, margin and execution boundary

Manual paid lots use the existing consumption order, immutable ledger, non-negative
balance constraints, reconciliation, compensating refund and support correction
paths. A purchased refund remains non-expiring and can be partial only under the
existing consumption-refund rule. Completed manual grant history is never edited or
deleted.

The grant records negotiated historical facts; it does not create a catalogue pack
or rate. The production margin floor remains not owner-approved, production Credit
prices/packs remain absent and production metered execution remains fail-closed. The
record therefore carries
`production_execution_blocked_pending_policy`. A Credit balance alone does not
authorise a provider: module entitlement, immutable action price, approved margin
policy, organisation exposure caps and global/action/provider kill switches still
gate later execution.

## Explicit boundary

No public pricing or pack, auto-top-up, post-paid/negative/overdraft Credit, invoice
generation, tax policy, document upload, accounting/bank/Stripe integration, card or
bank-account data, provider activation, deployment, customer data, Privacy/Terms
content, WO-054 or WO-045 work was added. Live Stripe and all production providers
remain inactive. Spend is AUD $0.

## Verification scope

Automated coverage includes exact amount handling; confirmation, reference, currency,
quantity and timestamp validation; duplicate/idempotent/conflicting replay;
response-loss retry; stale preview; high-value review; missing, inactive, disabled and
suspended organisations; tenant-scoped references; no customer route; purchased lot,
ledger and balance reconciliation; refund/correction compatibility; automatic
verified card-purchase regression; production execution fail-closed behaviour;
database constraints/immutability; migration downgrade/re-upgrade/drift; and genuine
PostgreSQL contention and forced-RLS isolation.

## Engineering review

The merge review closed four defects before acceptance: preview now displays the
operator reason and its confirmation fingerprint binds every payment/audit fact;
plain decimal/integer parsing and duplicate CLI facts fail closed; aggregate held
Credits cannot exceed the service arithmetic boundary; and support audit text is
restricted to bounded plain text. Regression coverage now injects an atomic commit
failure, exercises exact technical bounds and proves that conflicting simultaneous
PostgreSQL grants produce one reported winner and one explicit conflict.

See [Manual paid Credit grant operations](../03-engineering/manual-paid-credit-grants.md),
the [owner runbook](../03-engineering/manual-paid-credit-grant-runbook.md) and
[ADR 0076](../08-decisions/0076-internal-manual-paid-credit-grant.md).
