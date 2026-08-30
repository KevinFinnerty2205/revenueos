# RevenueOS Sales Analytics and Win/Loss Intelligence

**Status:** implemented by WO-036 as a RevenueOS Core capability.

> **WO-038 handoff:** Transparent Forecasting reuses `won_value` definition version 1
> through `SalesMetricService` for Actual. Closing, reopening or correcting canonical
> Opportunities therefore reconciles Insights, Targets and Forecast without copied
> Won formulas. Historical expected contribution remains a separate model.

Sales Insights answers five bounded questions from canonical RevenueOS history: what
entered the pipeline, what progressed, how long completed stages took, what later
followed recorded calls and meetings, and what was finally won or lost. It complements
Pipeline workflow; it is not a general reporting or business-intelligence product.

## Experience and packaging

Authenticated Core users open **Insights** from desktop navigation. Overview,
Targets, Funnel, Activity and Win/Loss form the current information architecture.
The four analytical views share one inclusive local-date range, IANA timezone, current
Opportunity-owner and pipeline scope. Funnel requires one pipeline because stage
identities and positions cannot be combined honestly. Historical inactive pipelines
remain available and visibly labelled. No separate Analytics entitlement or paid
add-on exists; one server-side rollout flag can fail the whole capability closed.

Overview shows current open count, Opportunities created in-period, currently final
Won/Lost results, closed win rate, median sales cycle and Won value separated by
currency. Open count is a current snapshot, while created/closed metrics use the
selected period. Reopened-currently-open Opportunities are not final outcomes.

## Funnel analytics guide

The v1 funnel cohort is Opportunities whose first reliable, non-migration-baseline
entry into one pipeline occurred in the selected period. Progression is measured
through request time. A stage counts only when it was actually entered; skipped stages
are not manufactured. Advancing means a later actual entry to a higher open stage in
the same pipeline or that pipeline's Won stage. Regression does not erase a prior
advance. Baseline-only history, sample counts and earliest reliable tracking are
disclosed.

Completed stage duration is the median time between a real non-baseline stage entry
and its recorded exit, where the exit occurred in-period. Current, null, negative and
baseline-derived intervals are excluded.

## Activity and outcome analytics

Activity counts completed canonical `phone_call` Interactions and completed meeting or
customer-session Interaction types. Owner scope uses Interaction creator; Opportunity
metrics use the Opportunity's current owner; confirmed live Outreach uses sender.
This current-owner rule means reassignment may change historical filtered results.

The follow-on window is 30 days. A call is eligible only after the full window has
elapsed and it has a canonical Account or Contact association. It counts when a later
completed meeting matches that Account or a canonical Meeting participant Contact.
A meeting is eligible only after maturity, Opportunity association and reliable stage
context; later higher-stage or Won movement counts, while regression and Lost do not.
The language is always **followed by**: these sequences do not prove causality or
assign credit.

Outreach is shown only where Engage is available. Only provider-succeeded `live`
send-email Action executions count. Draft, approval, campaign step state, failed,
uncertain and simulation results never count. Reply analytics remain unavailable
until a production reply-ingestion path is approved.

## Win/Loss Intelligence

Win/Loss uses current final Won and Lost Opportunities whose `actual_close_date` is
inside the range. Win rate is Won divided by Won plus Lost. Reason distributions use
only controlled `outcome_reason` values and are labelled **seller reported**; they are
not customer-confirmed. Free-text `outcome_note` is deliberately neither selected nor
aggregated. The final Lost transition's `from_stage` snapshot supplies loss-stage
context. Sales-cycle and outcome-value tables include samples, and currencies remain
separate without FX.

## Metric definitions and boundaries

The inspectable versioned catalogue is
[Sales analytics metric catalogue](../03-engineering/sales-analytics-metric-catalog.md).
It is also the implemented WO-037 Targets contract. Target progress calls the same
metric service and persists no actual. WO-038 Forecasting may later use clean
lifecycle history, but WO-036/037 have no probability, weighting, predicted close or
forecast. They also have no arbitrary report builder, text-to-SQL, custom formula,
benchmark, open/click tracking, employee leaderboard, rep score, productivity
telemetry, qualitative AI synthesis or manager coaching.

Analytics reads but cannot mutate customer Evidence, Methodology or Revenue Brain.
Accuracy is limited by recorded canonical history: pre-WO-035 timing is incomplete,
unrecorded external CRM changes cannot be analysed, and activity associations remain
non-causal.
