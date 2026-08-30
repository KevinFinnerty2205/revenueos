# Manager Intelligence experience and simplicity review

- **Status:** Current through WO-039
- **Question:** Which deals need attention, why, and what should we discuss?

## Information architecture

There is no standalone Manager application or top-level navigation item. The existing
workflow remains the map:

```text
Home / RevenueOS Daily
  → compact Deals needing attention (maximum five)
  → Pipeline?view=attention
  → existing Opportunity
  → Manager review + existing Sales Brain
  → source / Action / Forecast as needed
```

Insights Overview includes the organisation reference summary without adding a
seventh tab. Forecast owns seller/manager review and factual differing-view filtering.
Members keep the seller experience; manager-only organisation surfaces hide safely.

## Home and Pipeline

Admin Home adds one compact section after Daily. It lists deal, owner, up to two
plain-language reasons and **Review deals**. Empty copy is “Nothing currently matches
the selected deal-attention conditions,” never an unsupported claim that the team is
healthy.

Pipeline's Manager view reuses the existing filters and cards. Each card shows owner
as deal responsibility, current stage/close/amount, seller and manager forecast views,
and a bounded reason list. It does not sort or colour by person, amount, health,
probability or score. The default deterministic order is reason priority, close date
and deal name.

## Opportunity Manager review

The existing Opportunity remains Sales Brain-centred. An admin-only Manager review
section provides:

1. **What matters** — deal facts, seller view, manager view and reason labels;
2. **Why this appears** — explanation and click-through source;
3. **Questions to discuss** — at most five questions, each with why/source;
4. **Actions and latest interaction** — safe metadata, not content surveillance;
5. **What changed** — at most twenty safe changes from the last 90 days; and
6. **Historical baseline** — the same exact-stage sample used by Forecast.

Manager forecast is an explicit control with the same four non-probabilistic
categories. Seller judgment is visible beside it and cannot be edited through this
control. If no manager review exists, it says so; it never copies the seller view.

No raw transcript, Evidence dump, hidden reasoning, manager comment thread, coaching
checkbox or employee record appears. Derived questions are practical deal questions,
not seller competency questions.

## Insights and Forecast

Insights Overview stacks five independently labelled references for the current
quarter/currency: Actual, organisation Target, Seller Likely, Manager Likely and
RevenueOS baseline. Missing Target/review/sample stays missing. Personal Targets are
not included and no gap creates pressure on a customer or Action.

Forecast continues to own the detailed range. Admins see separate seller and manager
aggregate cards plus the system baseline. Per-deal review shows all perspectives and
supports **Different seller and manager views**, which is a factual filter—not a
judgment that either person is wrong. Members see a manager judgment on an
Opportunity they own read-only, with no organisation manager aggregate.

## Mobile and accessibility

At 390 px, summary references and deal cards stack; reason/source buttons and forecast
controls remain keyboard reachable; questions wrap without horizontal overflow. The
existing mobile navigation is unchanged. Semantic headings/links/buttons, visible
focus and existing reduced-motion behaviour are preserved. Dense cohort analysis
stays in existing desktop-first Insights views.

## Simplicity gate

- Deals—not people—are the primary objects.
- Every reason and question explains why and exposes its source.
- Seller, manager and RevenueOS views are distinct; there is no final blend.
- Home is a compact extension, Pipeline remains familiar and Opportunity remains the
  source workspace.
- There is no rep/deal score, grade, rank, leaderboard, activity-performance table,
  personal-Target comparison, behavioural surveillance or coaching dossier.
- Empty/sparse states are honest and tell the user what is unavailable.
- The next click is always review deals, open Opportunity or inspect a source.

Known access and product limits are in the
[implementation guide](../01-product/manager-intelligence.md).
