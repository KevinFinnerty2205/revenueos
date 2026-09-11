# How to manually grant a paid bulk Credit purchase

> **NEVER GRANT PAID CREDITS AGAINST AN UNPAID INVOICE.** Proceed only after the
> exact funds are cleared/received and independently verified by the authorised
> internal operator.

This is the exceptional large negotiated purchase workflow. Normal customers pay by
card and receive Credits only after automatic verified-payment reconciliation.

## Before the operation

1. Agree the bulk amount and Credit quantity externally. This does not create public
   pricing or a reusable Credit pack.
2. Prepare/manage the invoice externally. Oryntela does not generate it here.
3. Wait for cleared funds. An invoice, purchase order, promise, pending transfer,
   screenshot, email or accounts-payable confirmation is insufficient.
4. Record only a safe invoice/payment/accounting reference. Do not copy bank details,
   card data, documents or screenshots into this operation.
5. Use the protected deployment/support environment at current migration head
   `0063_terms_acceptance` (which includes the WO-055 `0061` grant schema). Do not
   give its credentials to a customer admin.

## Preview and review

Use synthetic placeholders below; replace them with the independently verified facts:

```bash
uv --directory apps/api run revenueos-operations credits-manual-paid-preview \
  --organisation-id ORGANISATION_UUID \
  --credits 50000 \
  --amount-received 12345.67 \
  --currency AUD \
  --payment-method BANK_TRANSFER \
  --payment-reference INV-EXAMPLE-055 \
  --payment-received-at 2026-09-10T10:30:00+10:00 \
  --operator-reference OWNER_OR_APPROVED_SUPPORT_REFERENCE \
  --reason "Negotiated bulk purchase; exact cleared funds independently verified."
```

Stop unless the returned `status` is `ready_for_confirmation`. Check:

- organisation name and UUID;
- current plan and commercial state;
- existing purchased, promotional and reserved balances;
- exact Credits, amount, currency, method, reference, received time, operator
  reference and reason;
- `expectedBalanceVersion` and `confirmationRequired`; and
- any large-grant warning.

Suspended does not mean reactivated: the grant will preserve suspension. Inactive,
missing or member-disabled organisations must be resolved through their own approved
lifecycle before any paid grant.

## Execute once

Copy the previewed balance version and exact confirmation phrase. Use a stable support
case/payment-derived idempotency key; never use a secret:

```bash
uv --directory apps/api run revenueos-operations credits-manual-paid-grant \
  --organisation-id ORGANISATION_UUID \
  --credits 50000 \
  --amount-received 12345.67 \
  --currency AUD \
  --payment-method BANK_TRANSFER \
  --payment-reference INV-EXAMPLE-055 \
  --payment-received-at 2026-09-10T10:30:00+10:00 \
  --expected-balance-version PREVIEWED_VERSION \
  --idempotency-key STABLE_SUPPORT_OPERATION_KEY \
  --operator-reference OWNER_OR_APPROVED_SUPPORT_REFERENCE \
  --reason "Negotiated bulk purchase; exact cleared funds independently verified." \
  --cleared-funds-confirmed \
  --confirm "EXACT CONFIRMATION PHRASE FROM PREVIEW"
```

For 1,000,000 Credits or more, recheck every displayed value and add
`--large-grant-reviewed`. This is a safety warning, not a commercial ceiling.
The copied confirmation includes a review fingerprint over the payment method,
received time, operator reference and reason as well as the visible organisation,
Credits, amount, currency and payment reference. Any change requires a new preview.
Supply each flag once; duplicate financial or confirmation flags are rejected.

## Verify and reconcile

Require a successful result with:

- `status=complete`, `clearedFundsConfirmed=true` and `creditType=purchased`;
- `expiresAt=null`;
- the expected organisation, Credit quantity, exact minor-unit amount and reference;
- one `grantId` and one `creditLotId`;
- `ledgerReconciled=true`; and
- the expected purchased/available balance.

If the terminal or network fails after submission, run the exact same command with
the same idempotency key and facts. `alreadyApplied=true` is the safe response-loss
replay. Do not change values or create a second reference. A stale balance error means
run preview again and review the new state. Any identity conflict requires inspection;
do not work around it with direct SQL.

Finally, reconcile the payment in the external accounting process. Do not represent
Oryntela as having generated the invoice, and do not activate a provider or grant
execution authority as part of this runbook.

If a later service-value refund is required, use the existing referenced consumption
refund/correction procedure. Never update or delete the completed grant or ledger.
