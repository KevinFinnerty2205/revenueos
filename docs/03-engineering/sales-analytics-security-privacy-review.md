# Sales analytics security and privacy review

**Status:** WO-036 implementation review. No unresolved high-severity finding.

## Data and threat boundary

Sales Insights processes tenant-owned Opportunity lifecycle, immutable stage events,
completed Interaction metadata, canonical Meeting participant links and confirmed
live Action executions. Outcome reasons may reveal internal commercial judgement.
Free-text closure notes, transcripts, prompts, Evidence content and provider payloads
are outside the read model.

Primary risks are cross-tenant filter attachment, guessed history, causal overclaim,
synthetic simulation counted as external activity, surveillance-style employee
profiling, sensitive values in telemetry and unbounded analytical queries.

## Controls

- Verified authentication supplies organisation and user. The API accepts no
  organisation identifier. Every repository query has an explicit organisation
  predicate and existing PostgreSQL forced RLS remains defence in depth.
- Pipeline and owner filters must resolve inside the active tenant or fail closed.
- The maximum inclusive range is five years; filters are typed and there is no SQL,
  arbitrary field/grouping or custom formula input.
- Migration baselines cannot create a funnel cohort or completed duration. Skips are
  not imputed. Reopened Opportunities are excluded from final outcome metrics.
- Only `execution_mode=live`, `execution_status=succeeded`, `capability=send_email`
  executions count as Outreach. Simulations never qualify.
- Responses aggregate controlled reasons only and never select `outcome_note`.
- No login, screen-time, click/open, presence, call-duration ranking, leaderboard,
  rep score or productivity metric exists.
- Analytics services have read dependencies only and cannot write Evidence,
  Methodology, Revenue Brain, Opportunity or Interaction state.
- Safe errors carry request IDs. Application telemetry must contain route, status,
  duration and safe error class only—not dates, counts, rates, amounts, reasons,
  entity names or notes.

## Privacy interpretation

Current-owner filtering is a business-record scope, not event-time performance
credit, and is documented as mutable after reassignment. Interaction creator is used
only to answer a selected activity scope. Follow-on metrics are temporal association,
not individual attribution or causal performance scoring. WO-039 must perform a new
permission and employee-impact review before any manager or coaching view.

## Retention, export and deletion

WO-036 adds no analytics fact table. Results are recomputed from canonical records,
so their existing tenant export, retention, soft-delete and parent-lifecycle deletion
rules apply. Migration `0045_sales_analytics` adds indexes only. The fixed demo set is
synthetic, tenant-scoped, deterministic, idempotent and removed by demo reset.

## Residual limitations

PostgreSQL RLS remains meaningful only when the runtime role cannot bypass it.
Seller-reported reasons are not customer-confirmed. Historical owner-at-event is not
available, and pre-WO-035 stage timing is incomplete. These limitations are disclosed
rather than inferred away.
