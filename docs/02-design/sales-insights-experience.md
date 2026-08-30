# Sales Insights experience and simplicity review

**Status:** WO-036 implemented design.

## Information architecture

Insights is a desktop Core destination beside Pipeline. It is not a fifth persistent
mobile navigation item: small-screen users reach it through the existing responsive
application route without displacing Today, Interactions, Actions or Search. One page
contains six capability-aware tabs—Overview, Targets, Forecast, Funnel, Activity and
Win/Loss. The four WO-036 views share a filter bar; Targets and Forecast own their
period-specific controls. Only the active read model loads.

## Interaction design

- Date presets cover this/last month, this/last quarter, last 90 days and this year;
  Custom exposes labelled native date inputs.
- Pipeline and owner are native labelled selects. All pipelines is valid except for
  Funnel, which explains why one pipeline is required.
- Metric cards prioritise answers, not dashboard density. CSS bars show relative
  shape, while each chart has an expandable semantic table of exact values.
- Missing denominators say **Not enough data**, never `0%`. Empty, loading and safe
  retry states preserve the page header and filters.
- Coverage, current-snapshot, mixed-currency, seller-reported and non-causal caveats
  sit beside the affected result instead of in hidden help.

## Funnel, activity and Win/Loss UX

Funnel bars use actual stage-entry counts and visible advance rates. A coverage banner
reports baseline-only and reliable history; skipped stages are explicitly not
inferred. Stage-duration cards always show completed interval sample size.

Activity separates counts from mature 30-day follow-on rates. Denominator exclusions
and immature counts remain visible. Wording never says activity “caused”, “drove” or
“received credit for” an outcome.

Win/Loss puts final outcome counts first, then seller-reported reason distributions,
loss-stage/cycle context and currency-separated values. Notes are not exposed.

## Accessibility and responsive review

The page uses one `h1`, labelled filters, a named tablist, keyboard-focus rings,
semantic regions, native details/summary controls and tables with captions and column
headers. Visuals do not depend on colour, data remains available as text, horizontal
tables scroll without clipping and motion is non-essential/reduced-motion safe.
The responsive grid collapses to one column; tabs and tables scroll within their own
bounds. No hover-only action or drag interaction exists.

## Simplicity gate

The implementation adds no charting dependency, saved report, query builder, custom
segment, drill-down entity browser, configurable widget, leaderboard or manager
surface. WO-038 adds a card-based Forecast review without a probability field or wide
table. Qualitative AI and coaching remain separate work orders.
