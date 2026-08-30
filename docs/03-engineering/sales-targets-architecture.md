# Sales Targets architecture

**Status:** Current WO-037 implementation.

## Boundary and dependency direction

Sales Targets remains inside the FastAPI modular monolith. The code-owned
`sales_target_policy` selects five definitions from the WO-036
`SALES_METRIC_REGISTRY`. `SalesTargetService` validates policy and authority,
`SalesTargetRepository` applies explicit organisation/user predicates, and progress
calls `SalesMetricService.observe`. No analytics formula is copied into the target
domain and no actual/progress counter is stored.

The feature requires both `API_FEATURE_SALES_TARGETS_ENABLED` and the Sales Analytics
flag. It is a Core server capability (`salesTargets`), not a module entitlement.

## Persistence

Migration `0046_sales_targets` adds the organisation timezone and two tenant-owned
tables:

- `sales_targets` is the immutable identity/configuration: metric ID/version, scope,
  origin, optional owner/pipeline, explicit period, timezone snapshot, optional
  currency, creator, archive and timestamps.
- `sales_target_revisions` is an append-only sequence of positive decimal goal
  values with actor/time metadata. The latest revision is current.

Composite foreign keys prevent cross-tenant owner, pipeline, creator and revision
attachment. PostgreSQL RLS is enabled and forced for both tables. Runtime queries
also bind organisation, and ordinary-member reads additionally allow only
organisation targets or their own personal targets. An expression unique index
prevents duplicate active identity while allowing one self-set and one assigned
target for the same person/metric/period. PostgreSQL triggers prevent target identity
rewrites and revision update/delete; the established maintenance setting is the only
hard-deletion bypass.

## API

| Method | Route                            | Behaviour                                                   |
| ------ | -------------------------------- | ----------------------------------------------------------- |
| `GET`  | `/api/v1/targets/metadata`       | timezone, policies, active owners/pipelines and permissions |
| `GET`  | `/api/v1/targets?view=...`       | authorised current, past, archived or all targets with live progress |
| `POST` | `/api/v1/targets`                | create current/future explicit-period target and revision 1 |
| `GET`  | `/api/v1/targets/{id}`           | calculation explanation and complete revision history       |
| `POST` | `/api/v1/targets/{id}/revisions` | optimistic append-only goal change                          |
| `POST` | `/api/v1/targets/{id}/archive`   | confirmed archive of current/future target                  |

Pydantic forbids extra request fields, so client attempts to submit actual/progress
fail. Goal text forbids exponent notation, limits two decimal places and is bounded
by database precision. Count metrics require whole numbers. Currency targets require
one uppercase ISO-shaped code; non-currency metrics reject currency.

## Period and calculation

Month/quarter/year boundaries are derived server-side from one anchor and the
organisation timezone snapshot. Past creation is rejected; future creation is
bounded to five years. Current observation range is `[period_start, local_today]`;
past is the full period; future returns `upcoming` with null actual/progress.

For personal targets, owner filtering uses WO-036 current Opportunity-owner semantics
or Interaction creator semantics. Organisation targets omit owner. Pipeline filters
are accepted and passed through only for the three Opportunity metrics; activity
targets reject them. Won value additionally passes one currency. Progress calculations
use the latest revision:

```text
remaining = max(goal - actual, 0)
above = max(actual - goal, 0)
percentage = round_half_up(actual * 100 / goal, 1)
```

The API does not cap percentage. A canonical correction, reopen, deletion or
reassignment is therefore reflected on the next read without a refresh job.

## Limits and operation

A user may have at most ten active/upcoming personal targets and an organisation at
most twenty active/upcoming organisation targets. List responses are capped at 200.
Disabling a member archives their current/upcoming personal targets. There is no
worker, recurrence, scheduler, notification, provider, AI call or connector.

Metadata-only system events record create/revise/archive and deactivation archive
counts. They include IDs, metric/version, scope, origin, period type and revision
number where relevant; goal and actual values never enter audit metadata or logs.
Errors use existing safe codes/messages/request IDs.

## Handoffs

WO-038 Forecasting may reuse canonical metrics but must add versioned assumptions,
uncertainty/ranges and calibration; target gap is neither a forecast input nor a
probability. WO-039 must introduce an approved manager/team scope before any manager
roll-up. It must preserve owner/admin visibility, avoid leaderboards and cannot
retrofit a manager role into this implementation silently.
