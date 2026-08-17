# WO-025 — RevenueOS Daily

- **Status:** Implemented
- **Branch:** `feature/epic-11-wo-025-revenueos-daily`
- **Migration:** None; `0033_sales_methodology` remains the single head

## Delivered

- Replaced the protected Dashboard content with RevenueOS Daily while retaining the
  compatible `/dashboard` Home route and changing the shell label to **Home**.
- Added one strict tenant/user-scoped `GET /api/v1/daily` read model with partial
  source availability and bounded, set-based queries.
- Added deterministic top priority, local-day Interactions, current Action states,
  explainable deal attention, stage-aware staleness, current methodology/Revenue
  Brain context, existing Next Best Action focus and currency-safe pipeline.
- Added responsive loading, instructional empty, caught-up, partial-failure and total
  failure experiences. Mobile puts the next Interaction first and reduces analytic
  detail.
- Extended synthetic demo data with near-term Interactions, two current Actions, an
  overdue commitment and valued AUD open pipeline. All data remains labelled
  synthetic and provider-free.
- Added API, policy, security, component and Playwright regression coverage plus
  inspected desktop/mobile screenshots.

## Scope decisions

Daily is deterministic composition, not a new AI engine. No target value exists, so
WO-037 remains authoritative. No approved forecast exists, so Daily labels only open
pipeline and closing-this-month values. No numeric deal score, team/manager view,
module entitlement promotion, new integration, prompt/provider, persistence or
surveillance was introduced.

## Acceptance notes

Home answers “What matters today?” with one obvious CTA. Interactions can lead to
Preparation, Companion, the Interaction or deliberate capture. Approved Actions are
explicitly still open. Deal reasons use controlled text/codes and link to the
Opportunity for verification. Mixed currencies remain separate. There is no separate
Daily nav item and source workflows remain intact.

Implementation details are in the [implementation guide](../03-engineering/revenueos-daily-implementation.md),
[priority rules](../03-engineering/revenueos-daily-prioritisation.md),
[API guide](../03-engineering/revenueos-daily-api.md),
[simplicity review](../02-design/revenueos-daily-simplicity-review.md) and
[security review](../03-engineering/revenueos-daily-security-privacy-review.md).
