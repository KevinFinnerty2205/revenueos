# Oryntela pricing hypothesis

- **Status:** **OWNER-APPROVED V1 INTERNAL CATALOGUE; TEST BILLING IMPLEMENTED, LIVE DISABLED**
- **Consolidated:** 4 September 2026
- **Publication:** Internal only; implemented as commercial authority and test checkout mapping, not public pricing or live billing

## Current hypothesis

| Plan       |    Monthly price |      Annual prepay | Included-user hypothesis | Purpose                                                      |
| ---------- | ---------------: | -----------------: | -----------------------: | ------------------------------------------------------------ |
| Core       | AUD $200/company | AUD $2,000/company |                  Up to 5 | Core operating loop, including Native CRM and Pipeline       |
| Growth     | AUD $350/company | AUD $3,500/company |                 Up to 10 | Core plus Prospect and Engage                                |
| Complete   | AUD $500/company | AUD $5,000/company |                 Up to 15 | Growth plus Create and supported external CRM connectors     |
| Enterprise |           Custom |             Custom |               Contracted | Larger teams and approved enterprise requirements            |

Annual pricing is paid annually under the current hypothesis and equates to
approximately two months free relative to monthly pricing. Do not reinterpret it as
monthly instalments under an annual commitment.

Pricing is primarily per company/organisation with included user bands. It is not
AUD $200 per salesperson and should not be led as AUD $40 per user. Extra-user bands
and prices are not decided.

## Rationale

- Oryntela creates shared team value across Evidence, Sales Brain, Pipeline, Targets,
  Forecast and Manager Intelligence.
- Company pricing is simpler and reduces seat-by-seat friction for a small team.
- Core must be independently worth keeping; pricing cannot depend on crippling it.
- Growth and Complete should reflect coherent workflow value, not arbitrary feature count.
- Material third-party variable costs should not be hidden inside an unlimited flat fee.

## Commercial status

| Item                                   | Status                                       |
| -------------------------------------- | -------------------------------------------- |
| Plan names, price anchors and user bands | Implemented as immutable V1 internal authority |
| Growth bundle                          | Core + Prospect + Engage                     |
| Complete module matrix                 | Growth + Create + external CRM connectors    |
| Add-on prices                          | **UNDECIDED**                                |
| Extra-user bands/prices                | **UNDECIDED**                                |
| GST-inclusive or ex-GST public display | **OWNER/LEGAL/COMMERCIAL DECISION REQUIRED** |
| Billing provider and implementation    | **PROVIDER-NEUTRAL TEST MODE BUILT; STRIPE TEST ADAPTER UNACTIVATED; LIVE NOT APPROVED** |
| Terms, cancellation and public launch  | **NOT READY**                                |

## Economic risks to test

- company-level pricing may underprice large or high-support teams;
- Complete may create services-heavy onboarding before modules are productised;
- normal AI usage may create variable cost that needs fair-use/cost controls without
  making every Sales Brain interaction feel metered;
- annual discounts reduce cash-price flexibility and can increase early buyer friction;
- add-ons and Credits can make the commercial model feel complex if displayed too early; and
- Oryntela must not compare an AUD company price with a competitor's per-seat price
  without normalising seats, billing term, currency, required tier and add-ons.

## Public presentation concept

If later approved, show one company price, included users, monthly/annual toggle,
annual saving, 14-day trial, concise outcome and clearly separate optional modules
from Credits. Do not publish a detailed feature grid until publication is separately
approved and the advertised provider-backed capabilities are genuinely live.

See the [packaging hypothesis](oryntela-packaging-hypothesis.md),
[Credits model](oryntela-credits-commercial-model.md),
[trial hypothesis](oryntela-free-trial-hypothesis.md) and
[pricing validation plan](oryntela-pricing-validation-plan.md).
