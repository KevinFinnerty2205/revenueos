# Manual paid Credit grant operations

- **Status:** implemented internal support operation; engineering review passed
- **Migration:** `0061_manual_paid_credit_grant`
- **Customer mutation surface:** none
- **Production Credit prices/packs:** none

## Commercial rule

The normal customer purchase remains:

```text
card → verified provider payment → automatic purchased Credits
```

The only manual exception is:

```text
large negotiated purchase → externally managed invoice → cleared funds verified
→ authorised internal manual paid Credit grant
```

**No cleared payment means no paid Credits. Never grant against an unpaid invoice.**
Invoice issue, a purchase order, promise, pending bank transfer, screenshot, customer
email or accounts-payable confirmation is not cleared-funds authority.

## Internal authority and contracts

The supported surface is the deployment/support `revenueos-operations` CLI. It uses
the same protected environment and transaction-local tenant context as existing
provisioning/commercial support operations. There is deliberately no API route,
customer button or tenant-admin permission for manual grants, and no generic RLS
bypass or unrestricted tenant query.

The preview command requires the target organisation and the complete non-sensitive
transaction summary. It resolves the organisation server-side and returns its name,
UUID, current plan/state, Credit balances, expected balance version, high-value
warning where applicable, operator reference, reason and exact execute confirmation.
The confirmation review fingerprint binds every displayed payment/audit fact. The
execute command requires the same facts plus idempotency, the previewed version,
explicit cleared-funds confirmation and exact summary confirmation; changing any
bound value requires another preview.

Client/operator input never chooses ledger type, Credit type, lot ID, expiry, balance,
grant time, state, unit valuation, provider cost or actor stored in the customer-safe
ledger. The server always creates a purchased, non-expiring lot and purchase event.

## Data and atomicity

`manual_paid_credit_grants` contains only `completed` records:

| Field group | Stored authority |
| --- | --- |
| identity | UUID, organisation UUID, purchased lot UUID |
| value | positive bounded integer Credits; positive bounded AUD minor units |
| payment | bounded method, reference, normalised reference fingerprint, timezone-aware received time, cleared confirmation |
| operation | operator reference, bounded reason, hashed idempotency key, full request fingerprint, server grant time |
| margin | `production_execution_blocked_pending_policy` until an owner-approved production policy exists |

The operation locks the organisation/commercial state and its Credit balance, checks
the expected version and aggregate held-Credit technical bound, creates the completed
record, purchased lot and ledger entry, increments the purchased balance and commits
once. Any failure rolls back all of them. The table has composite tenant/lot foreign
keys, organisation-scoped unique
payment and idempotency identities, positive/bounded checks, forced PostgreSQL RLS
and update/delete rejection triggers.

The reference and key are checked before and after the lock. Identical retries return
the existing completed operation; different facts fail with a safe conflict. This
covers duplicate entry, simultaneous operators and response loss after commit.
Conflicting simultaneous facts produce one committed winner and one explicit
identity conflict, never two grants.

## Customer-safe history and privacy

The ordinary Credit projection shows the purchased balance and **Purchased Credits**
activity. The ledger contains a safe generic purchase reason. Payment reference,
operator identity and internal reason remain only on the support record and are not
added to the customer-facing projection or export. No bank statement, invoice file,
payment screenshot, bank account, PAN, CVV, card expiry or tax breakdown is accepted.
Reference/reason content is inert text, bounded and never logged by the operation.

Existing accounting-retention protection continues to block organisation deletion
when Credit history exists. WO-055 creates no statutory retention period.

## Refunds, corrections and commercial state

The manual lot is an ordinary purchased lot. Consumption attributes its remaining
received revenue proportionally. Existing append-only consumption refunds can create
a partial or full non-expiring purchased refund lot; support corrections remain a
separate operation and cannot produce a negative balance. Neither path edits the
completed payment record.

Inactive, deleted/missing and member-disabled organisations fail closed. Suspended
organisations may receive/preserve a paid lot because the existing purchased-Credit
architecture permits preservation, but a grant does not unsuspend access. Plans,
subscriptions, trials, seats, module entitlements, daily/provider/action caps and kill
switches are unchanged.

## Margin boundary

The paid amount and granted quantity are negotiated historical facts, not public
pricing. No FX conversion or derived catalogue rate is created. No production action
price can be activated without exact provider-cost inputs, positive margin and an
owner-approved margin floor/reference. No such floor exists, and production metered
execution is disabled; the manual grant does not override that boundary.

See the [owner runbook](manual-paid-credit-grant-runbook.md),
[Credits and variable-cost controls](credits-variable-cost-controls.md) and
[ADR 0076](../08-decisions/0076-internal-manual-paid-credit-grant.md).
