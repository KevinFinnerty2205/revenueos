# Manager Intelligence architecture

- **Status:** Current through WO-039
- **Migration head:** `0048_manager_intelligence`

## Boundary and composition

Manager Intelligence remains inside the API/web modular monolith. It adds no worker,
queue, provider, prompt, vector search, cache or datastore. `ManagerRepository`
performs tenant-scoped, bounded reads; `ManagerIntelligenceService` composes typed
deal conditions; FastAPI/Pydantic remains the contract source of truth.

The read path is derived from canonical current data:

| Output | Canonical input |
| --- | --- |
| Deal and owner context | Opportunity, Pipeline/stage and organisation membership |
| Action condition | current open/in-progress Actions |
| Methodology condition/question | latest Methodology projection and its typed evidence states |
| Customer blocker | existing controlled Revenue Brain change taxonomy |
| Seller forecast state | `SalesForecastService` rules and seller revision snapshot |
| Manager forecast state | independent reviewer revision using the same shared snapshot rules |
| Recent changes | stage events, typed CRM field changes, forecast revisions, completed Actions/Interactions and controlled Revenue Brain changes |
| Organisation summary | Forecast service, which delegates Actual to `SalesMetricService` and Target to the Target service |

Manager Intelligence never mutates Opportunity, Evidence, Methodology, Revenue Brain,
Action or seller forecast state. Its only write is an explicit manager forecast
revision through the Forecast domain.

## Attention composition

The v1 taxonomy and deterministic priority are:

1. `close_date_passed`
2. `overdue_high_priority_action`
3. `evidence_conflict`
4. `forecast_needs_review`
5. `forecast_not_reviewed`
6. `methodology_priority_gap`
7. `no_next_action`
8. `stale_evidence`
9. `customer_blocker`

Only open, non-archived Opportunities participate; a reopened Opportunity is
included once its canonical status is open, while won/lost records are excluded.
Each reason contains a stable code/ID, label, explanation and one or more typed source
references. Canonical issue keys de-duplicate equivalent labels. The list shows at
most two Methodology gaps and five total reasons. Sorting uses primary reason order,
then expected close date and Opportunity name—never amount, owner, score or
historical probability.

Questions are a pure projection of attention reasons and Methodology's existing
bounded `suggested_question`. The composer returns at most five questions with
`whyShown`, source reason IDs and source references. It stores no question history,
notes, coaching completion or employee profile.

## Reviewer forecast persistence

Migration `0048_manager_intelligence` adds
`sales_forecast_reviewer_judgments` and
`sales_forecast_reviewer_revisions`. Separate tables avoid changing the seller-only
identity, uniqueness and authorisation contract established by WO-038.

One reviewer identity exists for an organisation/period/Opportunity. Each explicit
review appends a numbered revision with category, actor and the same canonical owner,
amount/currency, close-date, Pipeline/stage, Opportunity status and model-as-of
snapshot used by seller revisions. Shared Forecast service helpers own snapshot,
staleness, baseline and aggregate semantics. Current aggregates use current canonical
amount and exclude closed Opportunities; past periods and closed records are locked.
Optimistic expected-revision checks prevent concurrent overwrite.

Both tables have composite tenant foreign keys, forced PostgreSQL RLS and an
UPDATE/DELETE rejection trigger. Only the explicit beta-maintenance transaction
setting may bypass immutability for lifecycle operations. Manager reviews produce a
metadata-only system audit event without category, amount or customer content.

## API and access

- `GET /api/v1/manager/deal-attention`
- `GET /api/v1/manager/opportunities/{opportunityId}`
- `GET /api/v1/manager/summary`
- `POST /api/v1/forecast/opportunities/{opportunityId}/manager-judgments`
- `GET /api/v1/forecast/opportunities/{opportunityId}/manager-history`

The first three and manager writes require the current organisation's admin role.
The Opportunity owner may read manager judgment/history through the existing forecast
scope but cannot write it; peers and cross-tenant IDs fail closed. Client-supplied
organisation IDs are never accepted. Owner and Pipeline filters are tenant-validated.
The feature fails with a safe 404 when `managerIntelligence` is disabled.

## Query and failure strategy

The attention list performs set-based bounded reads: up to 10,000 open Opportunities,
one current-Action query, one windowed latest-Interaction query, current Methodology
and Revenue Brain reads, current-period seller/manager forecast reads and one grouped
historical outcome query. There is no per-deal service call, persisted risk table or
background recomputation. Responses paginate to at most 50 deals and sources/change
feeds are bounded. Detail reads are scoped to one Opportunity and 90 days/20 items.

Malformed optional Methodology or Revenue Brain content is ignored safely. Missing
Methodology, Revenue Brain, Target or historical sample produces an honest sparse
state; it does not fabricate a fallback. No raw transcript, audit payload or Evidence
text enters manager responses or logs.

## Retention, export and deletion

Attention, summaries and questions are derived and have no retention footprint.
Reviewer identities/revisions follow the Forecast lifecycle. Organisation export v28
includes both reviewer collections and their canonical snapshots. Opportunity or
organisation hard erasure cascades through the reviewer identity; approved beta
maintenance enables the immutable-trigger bypass for erasure/reset. Membership,
Pipeline and stage references remain restrictive while retained revisions exist,
matching the seller forecast audit model.

See the [security/privacy review](manager-intelligence-security-privacy-review.md),
[ADR 0062](../08-decisions/0062-deal-centric-manager-intelligence.md) and
[Checkpoint 3 handoff](../06-roadmap/checkpoint-3-handoff.md).
