# Oryntela Prospect provider economics

- **As at:** 6 September 2026
- **Provider candidate:** Apollo
- **Production Credit action prices:** none
- **Production Credit packs:** none
- **Production margin floor:** not owner-approved
- **Provider agreement/cost:** custom product-use agreement required; exact cost unknown

## Action economics

| Oryntela action | Provider action | Published provider units | Provider cost/assumption | Customer Credit price | Candidate margin scenarios |
| --- | --- | ---: | --- | --- | --- |
| Prepare known company | Local domain validation | 0 | AUD $0 | None | Not applicable |
| Browse company search | Organisation search | 1 Apollo credit/page, up to 100 results | Monetary value of an Apollo credit under the required custom agreement is unknown | **NOT APPROVED** | Disabled until exact per-page cost and price exist |
| Company research/refresh | Organisation enrichment | 1 Apollo credit/organisation | Custom agreement unit price unknown | **NOT APPROVED** | At cost `C` AUD: 50% margin requires `2C`; 60% requires `2.5C`; 70% requires `10C/3` |
| People discovery | People API Search | 0 Apollo credits | No Apollo Credit under current documentation; API rate limits still apply | None proposed | Treat as provider-capacity limited, not permanently free economics |
| Person research/refresh | People enrichment/match, phone reveal off | 1 credit when demographics/email found; up to 9 with mobile, which Oryntela does not request | Base/custom agreement unit price unknown | **NOT APPROVED** | Same `C` formulas after exact configured maximum cost is known |
| Business email access | Base enrichment or future waterfall | Base people enrichment may consume 1; email waterfall typically 1–4 but can exceed 20 depending on configuration | Unknown; no standalone reveal implemented | **NOT APPROVED** | Must be separately quoted if not included in approved person action |
| Phone/mobile reveal | Phone enrichment/waterfall | Base mobile adds 8; waterfall typically 8–25 and can exceed 45 | Unknown and high-variance | **NOT APPROVED** | Not implemented; requires separate quote and customer choice |

`C` is the approved maximum variable cost in AUD for one unit, including provider,
foreign exchange buffer, tax/payment leakage and other variable cost. These formulas
are exact revenue floors, not recommended customer prices. A Credit quantity cannot be
chosen until the owner approves the Credit pack/value, provider contract, cost model
and margin floor.

## Settlement rules implemented

- A server-owned quote pins immutable action-price version, quantity and maximum cost.
- Explicit reservation is confirmation; no available Credits means no provider call.
- The Prospect run stores the same tenant's Credit operation and a stable request ID.
- Entitlement, organisation policy, daily/provider-cost caps and global, action and
  provider kill switches are rechecked immediately before execution.
- Successful units settle using the pinned price; unused reservation is released.
- A documented no-result with zero successful units settles/releases according to the
  pinned action price. If the signed Apollo agreement charges company enrichment per
  request even when no record is returned, the approved production price must use the
  existing `requested_unit` basis and say so in the customer-visible pricing notice
  before confirmation. A `successful_unit` price would release the reservation for a
  no-result and is unsuitable for that cost basis.
- Definite rejection/non-execution releases. Timeout, server ambiguity, malformed
  billable result or worker loss after execution becomes unknown and remains reserved.
- Unknown outcomes do not retry. Existing WO-049 reconciliation settles once when
  execution is proven or releases once when non-execution is proven.
- Demo provider runs have no operation, provider cost or purchased-Credit consumption.

## Commercial invariants

Normal customers: card payment → verified payment → Credits granted. Pending/failed
card payment, invoice issuance, unpaid invoice or a promise to pay grants no Credits
and authorises no provider work. Negative balance is database-prohibited. Auto-top-up
is off and not implemented.

For a future unusually large negotiated purchase, only cleared funds independently
confirmed by Kevin/Oryntela may precede an internal `MANUAL_PAID_GRANT`. That feature
is recorded as WO-055 and is not implemented here. Customer self-grant is prohibited.

## Activation inputs still required

1. Signed provider product-use/data agreement and exact recurring/usage quote.
2. Versioned maximum cost for each enabled action, including FX and variable costs.
3. Owner-approved production Credit pack/value and per-action price.
4. Owner-approved gross-margin floor and policy reference.
5. Production exposure caps, account quota/overage behaviour and kill-switch owners.

Do not infer sustainable economics from a promotional free tier. No provider account,
trial, paid unit, card or subscription was used in WO-050; new spend is AUD $0.
