# ADR 0057 — Explicit canonical Sales Targets

**Status:** accepted, 30 August 2026.

## Context

WO-036 supplies versioned deterministic metrics. WO-037 must provide useful goals
without duplicating analytics, freezing mutable operational truth, turning Insights
into employee surveillance, or pre-implementing Forecasting/Manager Intelligence.
Targets also need historical integrity when a person or administrator changes a
goal.

## Decision

Implement Targets inside Core as explicit monthly, calendar-quarter and
calendar-year records. Bind each target to an allow-listed WO-036 metric ID and
definition version, its scope/origin, optional owner, Opportunity-only Pipeline, immutable timezone
snapshot and optional single currency. Persist only identity/configuration and
append-only goal revisions. Calculate every actual at read time through
`SalesMetricService`; never persist an authoritative actual, counter, pacing state or
forecast.

Allow owner-managed self-set personal goals, administrator-managed assigned personal
targets and administrator-managed organisation targets. Administrators may inspect
but cannot edit another user's self-set goal. Organisation totals are shared;
personal goals are hidden from ordinary peers. No manager/team hierarchy is inferred
from the admin role.

Use forced tenant RLS plus application user predicates. Prohibit formulas, rate
targets, FX, recurrence, bulk assignment, ranking, gamification, compensation use,
target-triggered Action/AI and Daily changes. Put exact progress in Insights through
a compact Overview section and dedicated Targets tab.

## Alternatives considered

- Persisted actual snapshots/counters were rejected because corrections, reopen,
  ownership changes, retention and metric-version changes would drift from Insights.
- Recurring target definitions plus scheduled jobs were rejected because explicit
  records are simpler, auditable and sufficient for v1.
- Generic KPI formulas and rate targets were rejected because denominator/direction
  semantics require later product policy.
- A team/manager roll-up was rejected because no authorised manager hierarchy exists.
- A leaderboard or attainment-sorted admin table was rejected as surveillance and
  contrary to the relationship-driven product.
- A Daily card was deferred to avoid converting Daily into another dashboard before
  user evidence supports a primary-target concept.

## Consequences

Insights and Targets reconcile by construction. Historical displayed actuals can
change after canonical correction, reopen, deletion or current-owner reassignment;
this is disclosed and appropriate for operational analytics, but not compensation.
Goal history remains immutable. Future targets are upcoming rather than fake zero.
Forecasting must add a separate uncertainty contract in WO-038, and team/manager
scope requires a separate WO-039 decision.
