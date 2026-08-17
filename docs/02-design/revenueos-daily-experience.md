# RevenueOS Daily experience

- **Status:** Implemented in WO-025
- **Question:** What matters today?

Daily is the default signed-in Home at `/dashboard`. It turns authorised, current
persisted state into a short action-oriented plan. It is not a generic analytics
dashboard, notification inbox or second copy of the source workflows.

## Desktop hierarchy

```text
Home · RevenueOS Daily                         Search

Good morning, Kevin
Monday, 17 August · What matters today

TOP PRIORITY
Prepare for Qantas technical review
10:00 · Economic Buyer is still unknown.       Prepare →

TODAY'S INTERACTIONS              DAILY CONTEXT
chronological, maximum five       Open pipeline

ACTIONS                           Recommended focus
current, maximum five

DEALS NEEDING ATTENTION
explainable, maximum three
```

The dark priority card is the single visual focal point. Source sections remain
bounded, textual and actionable. Pipeline/Recommended focus use a narrower secondary
column. No chart competes with the next action.

## Mobile hierarchy

```text
Home · RevenueOS Daily              Search

Good morning, Kevin

NEXT
Qantas · 10:00
Economic Buyer is still unknown.
[ Prepare ]

Actions
Deals needing attention
Later today
Open pipeline
Recommended focus
```

The next Interaction replaces a duplicate large priority card when they refer to the
same item. Today's remaining Interactions are reduced to two simple links. Multi-
currency detail is hidden on mobile, while counts and links remain available.

## Section contracts

- **Top priority:** exactly zero or one deterministic focus with reason and CTA.
- **Today's Interactions:** current user's non-cancelled local-day Interactions in
  effective-time order; CTA is Prepare, Prepare for meeting, Open Companion, Capture
  what happened or Open interaction.
- **Actions:** proposed, edited and approved-but-open work only; current timing/state
  and source Opportunity remain visible.
- **Deals needing attention:** at most three owned open Opportunities; each shows why
  through at most two controlled current reasons. There is no deal-health score.
- **Open pipeline:** descriptive owned open value, separately by currency, plus
  closing-this-month value. It is explicitly not forecast.
- **Recommended focus:** up to three existing current Next Best Actions. Daily does
  not create another recommendation.

## First-time, empty and failure states

- No Opportunities: one welcome card explains the prepare/capture loop and offers
  **Add an opportunity**. Empty analytics are removed.
- Opportunities but no Interactions: show **No customer interactions scheduled
  today**, then useful Actions/deals/pipeline/recommendations.
- Nothing urgent: calmly show **You're caught up** and keep the useful context.
- Partial source failure: retain available sections and show only
  **Actions temporarily unavailable** (or the relevant source).
- Total failure: **RevenueOS couldn't load your day**, Retry and direct links to
  Interactions and Opportunities.

Loading uses a restrained skeleton. “Updated just now” is subtle, and browser focus
or the next local midnight triggers one refresh without polling.

## Explainability and control

Each card links to its existing source workflow for evidence, history and correction.
Daily exposes the deterministic product-safe reason but not raw Evidence or Brain
history. It contains no mutation, approval, execution or send control itself.
Dismiss/snooze is deferred until an approved preference and outcome contract exists.

Targets remain WO-037, forecasting remains WO-038 and team/manager Daily remains
WO-039. Without canonical target/forecast inputs Daily omits them instead of showing
placeholders that look authoritative.

See [prioritisation](../03-engineering/revenueos-daily-prioritisation.md),
[simplicity review](revenueos-daily-simplicity-review.md) and
[security review](../03-engineering/revenueos-daily-security-privacy-review.md).
