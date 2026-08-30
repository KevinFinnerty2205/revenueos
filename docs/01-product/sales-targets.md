# Sales Targets and KPI progress

**Status:** Implemented by WO-037 as a RevenueOS Core capability.

## Product promise

Targets let a salesperson or administrator choose a clear calendar-period goal and
compare it with the same deterministic metric already used by Sales Insights. A
target is a human-authored goal, not a forecast, quota/compensation ledger,
performance score or instruction to create work.

The Insights Overview shows at most five signed-in-person and organisation targets.
The dedicated **Targets** tab owns creation, exact progress, detail, history and
archive. RevenueOS Daily deliberately does not change in v1; it remains a concise
prioritisation surface rather than another dashboard.

## Supported metrics

Version 1 supports exactly five higher-is-better metrics:

| Category             | Metric                   | Unit and rule                          |
| -------------------- | ------------------------ | -------------------------------------- |
| Outcome              | Won value                | One required ISO currency; no FX       |
| Outcome              | Closed Won Opportunities | Whole-number count                     |
| Pipeline development | Opportunities created    | Whole-number count                     |
| Activity             | Meetings completed       | Whole-number count; supporting context |
| Activity             | Calls completed          | Whole-number count; supporting context |

Win rate, follow-on rates, Closed Lost, duration and live outreach are deliberately
not targetable. There are no custom formulas. A target binds both the stable metric
ID and its definition version so the meaning remains explainable.

## Target types and authority

- A member, including an administrator acting for themselves, may create a
  `self_set` personal goal. Only its owner may revise or archive it; administrators
  can inspect but cannot change it through normal target operations.
- An administrator may create an `admin_assigned` personal target for an active
  member. The owner can read it; administrators can revise or archive it.
- An administrator may create an organisation target. All active members can read
  its aggregate progress; individual contribution is never broken out.
- Self-set and administrator-assigned targets for the same metric and period may
  coexist because their origin is part of identity. Exact duplicates do not.
- Personal targets are visible to their owner and administrators, never ordinary
  peers. Member deactivation archives that person's current and upcoming targets
  while preserving history.

RevenueOS has only `admin` and `member` organisation roles today. WO-037 does not
invent a manager hierarchy, team object or manager role. Those remain WO-039 work.

## Period, value and progress behaviour

Targets are explicit monthly, calendar-quarter or calendar-year records. Creation
accepts the current period or a future period up to five years ahead. The
organisation's canonical IANA timezone is snapshotted on creation and period
boundaries never change afterwards. Fiscal calendars, rolling/weekly periods,
recurrence, cron creation and bulk assignment are not implemented.

Opportunity-based targets may optionally bind one active tenant Pipeline. Activity
targets are organisation-wide or creator-scoped and never accept a Pipeline filter.
An archived Pipeline remains attached to target history but cannot be selected for a
new current or future target.

The latest append-only revision supplies the goal. Current-period actuals cover the
full period start through today's local date, including eligible records created
before the target itself. Future targets are **Upcoming** and expose no invented
zero. Past targets are locked. Current and future targets can be archived with an
explicit confirmation; configuration and revisions remain available in history.

Progress is `actual / current goal × 100`, rounded to one decimal for display.
RevenueOS shows exact actual, goal, remaining or amount above goal, and supports
progress above 100%. The visual bar caps at its physical width but the text and API
retain the exact percentage. There is no pacing, “on track”, projection or forecast.

Canonical corrections, deletion, reopening and current Opportunity-owner
reassignment may change historical actuals because WO-037 does not freeze or persist
an actual. Interaction metrics inherit WO-036 creator attribution. These are
operational analytics semantics, not compensation-grade crediting.

## Trust boundaries and limitations

- Actuals come only from `SalesMetricService`; clients can never supply them.
- No target gap creates an Action, notification, AI output or Revenue Brain,
  Methodology or Evidence mutation.
- No leaderboard, ranking, badges, streaks, primary target or peer comparison exists.
- No FX, team hierarchy, allocation, roll-up or individual contribution table exists.
- No target import or production connector exists.
- Target records and revisions are included in organisation export; calculated
  actuals are not. Retention and hard deletion follow existing organisation data
  controls.

Forecasting must consume canonical facts independently and must not reinterpret
target attainment as probability. See the
[Targets/Forecast boundary](../03-engineering/sales-analytics-targets-forecast-architecture.md)
and [ADR 0057](../08-decisions/0057-explicit-canonical-sales-targets.md).
