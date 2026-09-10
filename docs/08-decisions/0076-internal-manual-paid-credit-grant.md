# ADR 0076 — Internal immutable manual paid Credit grant

- **Status:** accepted and implemented by WO-055; engineering review passed
- **Date:** 2026-09-10

## Context

Normal Credit sales must collect and automatically verify card payment before value is
granted. A genuinely large negotiated purchase may instead be invoiced externally,
but Oryntela must not fund variable provider usage while payment is unpaid or pending.
The existing platform has an owner-operated support CLI, purchased Credit lots, an
immutable ledger, locked balances and compensating refund/correction semantics. It
has no global support user role or safe cross-tenant support UI.

## Decision

Use the existing protected support CLI as the sole WO-055 authority. Require a
read-only preview, explicit human confirmation that funds cleared, exact transaction
summary confirmation, expected balance version, stable idempotency key and an extra
warning acknowledgement for technically large grants.

Persist one completed-only, immutable, forced-RLS `ManualPaidCreditGrant` linked by a
composite tenant foreign key to one server-created purchased lot. Store exact AUD
minor units, integer Credits, bounded payment facts, operator/reason and hashed
idempotency/reference fingerprints. Append the ordinary purchase ledger event and
locked balance change in the same transaction. Expose no customer mutation route and
no pending/unpaid lifecycle.

Record that production execution remains blocked pending an owner-approved margin
policy. The grant is payment history and Credit funding, not action-price, provider or
plan authority.

## Alternatives

- **Customer/tenant-admin grant UI:** rejected because it permits self-grant and makes
  browser-supplied organisation/payment truth authoritative.
- **Global super-admin web system:** rejected because the repository has no suitable
  global support identity and WO-055 does not justify building one.
- **Reuse billing invoice/subscription rows:** rejected because no provider invoice or
  subscription exists and doing so would fabricate Stripe/accounting facts.
- **Direct balance update or correction:** rejected because it loses paid-purchase
  provenance and bypasses the purchased lot/ledger invariant.
- **Pending Credit/invoice state:** rejected because unpaid Credits and accounts
  receivable are outside policy.

## Consequences

Kevin or an authorised deployment/support operator can perform the exception without
database editing. The operation is deliberate and auditable but remains a human
cleared-funds assertion, not automated bank verification. Customer history remains
safe, normal card payment remains primary, retries cannot double-grant, and existing
refund/correction/exposure controls continue unchanged. A future support UI,
accounting verification adapter, non-AUD currency or production margin policy requires
separate approval and must preserve this authority boundary.
