# ADR 0056 — Deterministic canonical Sales Analytics

**Status:** accepted, 30 August 2026.

## Context

WO-035 supplies stable pipeline stages and immutable transition history. WO-036 must
make that history useful without creating a generic BI platform, copying mutable
facts, inventing legacy timing, overstating activity causality or establishing an
employee-surveillance surface. WO-037 Targets needs stable reusable metrics and
WO-038 Forecasting needs analytics to remain descriptive.

## Decision

Implement Sales Insights as a tenant-scoped read model inside the FastAPI modular
monolith. Use a code-owned registry of stable metric IDs and explicit definition
versions. Calculate results from canonical Opportunity, stage-event, Interaction,
Meeting participant and confirmed live Action-execution facts. Add only bounded
query indexes; do not persist observations or add a warehouse/job pipeline.

The funnel cohort is first reliable non-baseline entry into one pipeline during an
inclusive local-date period. Stages count only actual entry; reliable completed
intervals supply duration. Current final state plus `actual_close_date` defines
Win/Loss. Follow-on metrics use a fixed mature 30-day window and non-causal language.
Currencies remain separate. Controlled seller-reported reasons may aggregate;
free-text closure notes may not.

Expose strict typed endpoints and exact semantic tables beside minimal CSS charts.
Prohibit arbitrary SQL, formula, grouping and report definitions. Do not create
open/click tracking, employee rankings, probabilities, weights, forecasts or AI
qualitative interpretation. Analytics is Core and has one server-authoritative
rollout flag, not a separate entitlement.

## Alternatives considered

- A warehouse/materialised fact copy was rejected because private-beta volume does
  not justify freshness, correction, deletion and tenancy complexity.
- A generic report/query builder was rejected because it expands security and product
  scope and weakens metric consistency.
- Inferring pre-WO-035 entries/durations was rejected because synthetic history would
  look authoritative.
- Counting campaign `sent` or simulated success was rejected because it is not proof
  of external delivery.
- Event-time owner attribution was deferred because canonical history does not record
  it reliably; current-owner semantics are explicit.

## Consequences

Metrics reconcile and can be reused by Targets through `SalesMetricService`.
Historical results change after owner reassignment, corrections or reopen, which is
honest current-state behaviour. Large-scale analytics, forecast assumptions,
qualitative win/loss synthesis and manager permissions require later decisions.
Query indexes in `0045_sales_analytics` must be rolled back with that migration.
