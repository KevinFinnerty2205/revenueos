# ROI & Business Case Builder

## Current implementation (WO-033)

ROI & Business Case Builder belongs to RevenueOS Create and requires the existing `create` entitlement. It lets a salesperson select a canonical Account, optionally select an Opportunity, choose the latest approved organisation Value Model, enter every required numeric input, calculate on the server, review formulas and provenance, compare explicit scenarios, approve an immutable version and reuse that exact version in a presentation.

The product rule is absolute: AI may explain a supplied number, but no AI or provider creates a calculation input or output. WO-033 uses no AI provider. Missing values block calculation.

## Seller flow

1. Open Create or an Opportunity and choose **Create Business Case**.
2. Select an approved Value Model and one confirmed ISO currency.
3. Review every required value, unit, bound, origin and visible default.
4. Calculate the base case and optional conservative/upside overrides.
5. Inspect negative outcomes, unavailable payback, formulas, dependencies and assumptions.
6. Optionally run a bounded one-variable sensitivity table.
7. Approve the exact version.
8. Select that version in Create and choose **base** or **all scenarios**.

Approval is invalidated by a new calculation. Deleted/stale sources make the current case require review. No Business Case changes Revenue Brain, Methodology, forecast, CRM or customer Evidence.

## Current limits

- deterministic annual ROI/payback-style models only;
- 30 inputs, 30 outputs, three controlled scenarios and up to five sensitivity points;
- no Excel import, spreadsheet engine, arbitrary code, AI estimates or benchmark scraping;
- no FX, tax/GST, NPV, IRR, Monte Carlo, CPQ, discounts or CRM writes;
- current Evidence does not store a reviewed typed numeric fact, so text/ranges are never converted automatically; a seller may enter an exact value and optionally link available Evidence, retaining a salesperson-reported label.
