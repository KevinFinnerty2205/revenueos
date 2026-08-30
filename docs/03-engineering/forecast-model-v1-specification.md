# Forecast Model v1 specification

**Status:** WO-038 implementation contract.

## Purpose and boundary

Forecast Model v1 answers two different questions without blending their answers:

1. **Seller forecast range:** what the Opportunity owner currently judges may close
   in one explicit calendar month or quarter.
2. **RevenueOS historical baseline:** what expected monetary contribution follows
   from the organisation's own reliably tracked outcomes for the current Pipeline and
   stable stage.

Actual remains a live `won_value` observation from `SalesMetricService`. Target remains
a human-defined `SalesTarget`. Neither is an input to Forecast. The model does not add
an Opportunity probability, fixed stage weight, predicted close date, methodology
score, Revenue Brain score, AI provider or learned model.

## Data-maturity decision

The WO-038 branch began at the merged WO-037 head and the local PostgreSQL schema was
at `0046_sales_targets`. Inspection on 30 August 2026 found no Opportunity or stage-
history rows in the migrated local database. The deterministic demo generator has
synthetic pipeline history, but synthetic fixtures are not customer calibration
evidence.

RevenueOS must therefore support an honest bootstrap state. Seller judgment is
available when the system cohort is sparse. The historical baseline is unavailable
for an Opportunity until the exact cohort below contains at least ten final outcomes.
There is no organisation-wide, stage-name, industry or external benchmark fallback.

## Forecast period and eligible set

- Cadence is exactly `month` or calendar `quarter`.
- Start and end are derived server-side from an anchor date and the organisation's
  IANA timezone. A persisted period snapshots those boundaries and timezone.
- A current or future open/on-hold Opportunity is eligible when its canonical
  `expected_close_date` falls within the period.
- Missing expected close dates are never guessed. Those Opportunities are reported as
  needing forecast setup and contribute no amount.
- Won/Lost or archived Opportunities are excluded from remaining Forecast. A current
  Won Opportunity contributes to Actual only through `SalesMetricService`.
- Current canonical Opportunity amount and currency drive the live seller and system
  aggregate. Null value is counted as unvalued and contributes no amount.
- Currency is mandatory for monetary aggregation. Currencies are never summed or
  converted together.
- Changing the canonical expected close date is the only way to move an Opportunity
  into another period. A forecast judgment never owns a second close date.

## Seller judgment and range

The current Opportunity owner may record one explicit category per forecast period:

| Category          | Meaning                                                                 |
| ----------------- | ----------------------------------------------------------------------- |
| `commit`          | The seller expects a Won close in the period and commits it to forecast |
| `likely`          | The seller believes it can reasonably close but is not committing it    |
| `possible`        | It could close, with significant uncertainty remaining                  |
| `not_this_period` | The seller does not expect it to close in the selected period           |

`unreviewed` is derived from the absence of a judgment; it is not a stored category.
No category is inferred from stage, Methodology, Revenue Brain or any other field.
The client cannot submit an amount, percentage, stage, close date, owner or model
input.

For one currency and authorised owner/Pipeline scope, the seller cases are:

```text
Commit case   = sum(current value for Commit Opportunities)
Likely case   = Commit case + sum(current value for Likely Opportunities)
Possible case = Likely case + sum(current value for Possible Opportunities)
```

`not_this_period` and unreviewed Opportunities are excluded and disclosed. An
unvalued categorized Opportunity contributes to the deal count but not the amount.
These inclusive cases are a human forecast range; categories are never assigned
fixed numerical weights.

## Historical cohort

For an eligible current Opportunity in stable Pipeline `P` and stable open stage `S`,
the v1 comparison cohort contains distinct Opportunities that:

- belong to the same organisation and Pipeline `P`;
- have an actual, non-baseline `OpportunityStageEvent` entering stable stage `S`;
- are currently in the final `won` or `lost` state, so a currently reopened
  Opportunity is excluded;
- have canonical `actual_close_date` within the trailing 730 calendar days through
  the calculation as-of date; and
- closed no later than the calculation as-of date.

One Opportunity counts once even after re-entry. `migration_baseline` and every event
with `is_baseline` are excluded. Stage labels are never merged across stable IDs or
Pipelines. Current owner is not part of the cohort, avoiding per-seller scoring and
unusable small samples.

The fixed v1 assumptions are visible in every available result:

- model version: `forecast_historical_stage_outcome_v1`;
- lookback: 730 days;
- minimum final sample: 10 Opportunities;
- outcome unit: one Opportunity, amount-independent;
- no fallback cohort.

Changing any of these semantics requires a new model version. Existing assessment
snapshots keep their original version and cohort counts.

## Observed outcome and expected contribution

For a cohort with `won_count + lost_count >= 10`:

```text
observed final Win Rate = won_count / (won_count + lost_count)

RevenueOS expected contribution =
    current Opportunity amount × observed final Win Rate
```

Decimal/rational arithmetic is used; binary floating point is not. The UI shows the
amount, Won count, final sample, displayed one-decimal rate, exact Pipeline/stage,
lookback, minimum sample, model version and multiplication lineage. Wording calls this
an observed historical baseline, not a known deal probability.

The aggregate RevenueOS baseline is the sum of expected contributions only for
covered valued Opportunities in the selected currency. It always discloses covered
and uncovered Opportunity counts and amounts. Uncovered Opportunities are not treated
as zero and the system baseline is not presented as a complete seller forecast.

## Why v1 has no system low/high interval

A confidence interval around a historical stage rate describes uncertainty in the
cohort estimate, not the binary outcome of an individual Opportunity. A fabricated
system low/high band would therefore overstate meaning in the current sparse private-
beta setting. WO-038 instead uses the explicit Commit/Likely/Possible seller cases as
the primary range and displays one separate empirical expected-value baseline.

RevenueOS never blends these perspectives into a hidden final number. A later system
range requires a separately versioned and calibrated policy.

## Context without numerical weighting

Current stage age, expected close date, latest Interaction, next Action, Methodology
state and Revenue Brain context may be shown as source-labelled facts. They do not
change eligibility, the observed rate or the expected contribution in v1. No guessed
coefficient such as “economic buyer confirmed +15%” exists.

## Immutable review snapshots and staleness

Each seller review appends a revision that snapshots category plus current owner,
amount, currency, expected close date, Pipeline, stage, Opportunity state and the
as-of system baseline status/counts/model window. The historical calculation includes
only outcomes available at the revision timestamp, preventing future-outcome leakage.

The live aggregate always uses current canonical Opportunity values. A latest seller
revision is marked for review when owner, amount, currency, expected close date,
Pipeline, stage or open/closed state differs from its snapshot. The category remains
visible and included while the Opportunity remains currently eligible; the review
warning exposes the change. Reconfirming even the same category appends another
revision. Previous revisions cannot be updated or deleted through ordinary runtime
paths.

Past periods and closed Opportunities cannot receive new revisions. Reopen preserves
all prior history; the reopened Opportunity becomes eligible only if its current
expected close date is in the selected period and its prior judgment is visibly stale.

## Calibration semantics

WO-038 reports organisation-level **final forecast realization**, not a single
accuracy score and not a seller ranking. For each completed forecast period and
Opportunity, it selects the last seller revision recorded before period end, then
reports by category how many of those Opportunities' current final state is Won with
`actual_close_date` inside that period.

The output is descriptive counts (`realized / assessed`) with visible period coverage.
It does not claim lead-time calibration, causal seller quality or model accuracy.
Per-user breakdowns and leaderboards are prohibited. Stored as-of system cohort
snapshots establish a leakage-safe foundation for later model calibration, but v1
does not manufacture an aggregate system backtest from incomplete reviewed coverage.

## Authority, privacy and operation

- Members receive their own aggregate; administrators may read the organisation
  aggregate and filter owners but are not managers and cannot overwrite a seller
  category.
- A deal-level judgment is visible with an otherwise-authorised Opportunity; only its
  current owner may append seller revisions.
- Tenant IDs come only from verified context. Every repository query has an explicit
  organisation predicate and every forecast table uses forced PostgreSQL RLS plus
  composite tenant foreign keys.
- Amounts, categories, names, target/actual values, historical rates and commercial
  context remain outside logs and metadata-only audits.
- The model runs synchronously with set-based aggregate queries. There is no worker,
  queue, scheduler, provider, network call, CRM mutation or background refresh.
- Forecast history follows the Opportunity/organisation export, retention and hard-
  deletion graph. Normal product use provides no delete action for revisions.

WO-039 may add an independently authorised manager/reviewer layer only after team
scope exists. It must preserve seller and system views rather than changing this
seller history in place.
