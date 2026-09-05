# Oryntela variable-cost safety gate

- **Status:** Required approval gate for any future variable-cost capability
- **Last reviewed:** 5 September 2026
- **Current implementation:** WO-049 provides TEST-only Credits and variable-cost
  enforcement infrastructure; this gate still authorises no production price or provider

## Decision

No provider-backed feature that can create material per-use cost may enter a build work order until its unit economics, failure behaviour, exposure controls and customer value have passed this gate. A plan entitlement or a Credits balance alone is not a safety system.

## Gate checklist

### 1. Provider and billable unit

- Named provider candidate and a provider-neutral interface boundary.
- Exact billable event: token, minute, message, lookup, enriched record, generation, storage unit or other unit.
- Provider price, currency, tax treatment and effective date.
- Minimum commitments, tiering, expiry, rounding and prepaid obligations.
- Exchange-rate assumption and an explicit buffer for Australian-dollar pricing.

### 2. True cost per customer outcome

- Units required for one successful customer outcome.
- Retries, regeneration, polling, failed delivery and duplicate-call behaviour.
- Supporting compute, storage, observability and human-support cost.
- P50, P90 and credible worst-case cost per outcome.
- Whether failure is billable and whether the customer receives value.

### 3. Commercial mapping

- Included plan allowance, if any.
- Credits conversion and customer-visible unit.
- Top-up price, expiry and refund or reversal rules.
- Target gross-margin range and downside sensitivity.
- Trial allowance and maximum trial exposure.
- Plain-language customer explanation that does not obscure actual limits.

### 4. Runtime exposure controls

- Organisation-scoped quota and hard monetary ceiling.
- Per-user, per-action and time-window rate limits where warranted.
- Idempotency, replay protection and duplicate-delivery protection.
- Maximum retry count and safe failure state.
- Reservation or atomic debit design that prevents concurrent overspend.
- Insufficient-credit behaviour before work starts.
- Circuit breaker for provider price, error or usage anomalies.
- Administrative kill switch with an audit trail.

### 5. Reconciliation and support

- Provider usage reconciled to Oryntela usage without logging customer content.
- Explainable organisation-level usage ledger and dispute workflow.
- Treatment of failed, partial, cancelled and refunded work.
- Alerts before and at exposure thresholds.
- Safe error messages with request IDs and no provider internals.
- Retention and erasure treatment for provider artefacts.

### 6. Abuse, privacy and legal review

- Plausible abuse cases, including automation loops and account compromise.
- Data sent to the provider, location, retention and subprocessor impact.
- Consent, contactability and suppression obligations for communication channels.
- Contract and acceptable-use constraints.
- Security, privacy and legal owner approval where the capability warrants it.

### 7. Evidence of value

- The design partner has demonstrated the customer outcome matters.
- A lower-cost or manual validation path has been considered.
- The capability improves the Evidence → Sales Brain → Methodology → Action → Pipeline/Forecast loop.
- The outcome is valuable enough to justify the proposed customer price and operational risk.

## Required decision record

Every gated proposal must provide this concise decision table:

| Field            | Required answer                                                     |
| ---------------- | ------------------------------------------------------------------- |
| Customer outcome | Observable result, not provider activity                            |
| Billable unit    | Exact provider charging unit                                        |
| Cost range       | P50, P90 and credible maximum in provider and AUD terms             |
| Customer charge  | Included allowance or Credits price                                 |
| Margin           | Expected and downside gross-margin range                            |
| Exposure         | Per action, user, organisation and trial maximum                    |
| Failure          | Customer, accounting and retry behaviour                            |
| Reconciliation   | How provider usage and customer usage agree                         |
| Approvals        | Product, engineering, security/privacy, legal and commercial owners |
| Decision         | GO, LIMITED PILOT, REWORK or NO-GO                                  |

Unknown values produce **REWORK**, not an optimistic GO. A limited pilot must have a named cohort, finite exposure and an exit decision.

## Current application

Normal deterministic Sales Brain infrastructure work does not establish a generally available paid AI service. Future research, message generation, presentation generation, SMS and voice capabilities may create variable cost and must pass this gate before provider selection or public pricing. The commercial Credits model remains a hypothesis until these measurements exist.

## Related sources

- [Oryntela Credits commercial model](../04-commercial/oryntela-credits-commercial-model.md)
- [Oryntela pricing hypothesis](../04-commercial/oryntela-pricing-hypothesis.md)
- [End-to-end security and privacy](end-to-end-sales-platform-security-privacy.md)
