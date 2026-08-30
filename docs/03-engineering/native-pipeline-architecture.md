# Native Pipeline architecture

**Status:** implemented by WO-035 in the API modular monolith and existing Next.js app.

## Canonical model

WO-035 reuses `Opportunity`; there is no Deal copy. Three tenant-owned concepts are
added:

- `sales_pipelines`: stable definition identity, name, default and archive state;
- `sales_pipeline_stages`: stable immutable semantic type (`open`, `won`, `lost`),
  stable key/ID, display position, optional guidance and archive state;
- `opportunity_stage_events`: append-only transition facts with from/to pipeline and
  stage IDs, name/type snapshots, actor/time/source, prior reliable entry timestamp,
  closure metadata and a tenant-scoped idempotency key.

`Opportunity` gains current pipeline/stage IDs, reliable stage/tracking timestamps,
actual close date and current seller-reported outcome fields. Composite organisation
foreign keys prevent cross-tenant attachment. The legacy `stage`/`status` fields remain
compatible and are written in the same transaction.

## Definition change strategy

WO-035 deliberately uses stable IDs plus constrained edits instead of full definition
versions. Rename and guidance changes do not change stage identity; event name/type
snapshots preserve historical readability. Reordering is presentation only. Adding an
open stage is safe. Semantic type is never editable, and an in-use open stage cannot be
archived. Pipelines with open Opportunities cannot be archived.

This avoids a large version-activation and bulk stage-mapping workflow in private beta
without silently rewriting history. A future need for semantic replacement must use a
new stage/pipeline and explicit Opportunity transitions.

## Service and transaction boundary

`PipelineService` owns all stage movement, closure and reopen policy. Routes accept no
organisation ID. Repositories add explicit organisation predicates and row locks where
current state changes. Every mutation validates tenant, current observed stage,
authority, pipeline/stage membership, active state and Opportunity status.

An idempotency key is unique per organisation and Opportunity. A repeated completed
request returns current state and does not append another event. A different request
using a stale expected stage returns `stale_pipeline_state`; there is no silent
last-write-wins. Direct generic PATCH of native pipeline stage/final status is rejected
so callers cannot bypass the transition service.

Mutation order is one database transaction: append event, update canonical current
state/timestamp/outcome, append CRM field history and append metadata-only Opportunity
audit. No Evidence, Methodology or Revenue Brain repository is imported or mutated.

## Read model

`GET /api/v1/pipeline` uses a set-based join for bounded Opportunity cards and one
set-based Action query, avoiding a per-card query. It supports pipeline, owner, stage,
Account, search, close-date, attention and open/closed filters. Ordering is
deterministic. Definition/count reads are bounded by five pipelines and twelve stages.

Summaries aggregate current cards only. Monetary values are grouped by ISO currency;
null amounts are counted separately and no FX conversion or weighted value exists.

## Default, migration and baseline

Migration `0044_native_pipeline` follows `0043_native_crm` and is the single intended
head. It creates a default definition for every existing organisation and maps each
existing Opportunity using its preserved legacy stage/status. Unknown open values map
to the stable Other stage. Closed status maps to the corresponding final stage.

Each legacy row receives one `migration_baseline` event at activation time and a
`stage_tracking_started_at`. `stage_entered_at` remains null. This explicitly marks
incomplete history and prevents WO-036 from treating creation/update time as a real
stage-entry time. New Opportunities receive `system_initial` with a real entry time.

## Authority and external CRM

Board reads are Core. Native definition administration additionally requires admin,
CRM entitlement, native CRM mode and both server feature flags. If CRM mode is
external, board/current state is shown with `Managed in HubSpot`; all direct stage,
close and reopen mutations return `external_stage_authority`. Native definitions are
not presented as imported HubSpot pipelines.

The event source vocabulary reserves `external_crm` for a future mapped,
provider-authoritative update passed through this same service. WO-035 adds no provider
call, polling, inbound sync or hybrid authority path.

## Closure model

Each active pipeline has exactly one Won and one Lost stage. Close endpoints resolve
the correct final stage server-side, reject future actual dates, store optional final
amount in the existing amount/currency pair and append structured outcome metadata.
Lost reason is required; Won reason is optional. Both are seller reported. Reopen clears
current closure fields but its event does not mutate an earlier event.

## API surface

- `GET /api/v1/pipeline`
- `GET|POST /api/v1/pipelines`
- `PATCH /api/v1/pipelines/{pipeline_id}`
- `POST /api/v1/pipelines/{pipeline_id}/archive`
- `POST /api/v1/pipelines/{pipeline_id}/stages`
- `PATCH /api/v1/pipelines/{pipeline_id}/stages/{stage_id}`
- `POST /api/v1/pipelines/{pipeline_id}/stages/{stage_id}/archive`
- `GET /api/v1/opportunities/{opportunity_id}/pipeline`
- `POST /api/v1/opportunities/{opportunity_id}/stage`
- `POST /api/v1/opportunities/{opportunity_id}/close-won`
- `POST /api/v1/opportunities/{opportunity_id}/close-lost`
- `POST /api/v1/opportunities/{opportunity_id}/reopen`

FastAPI/Pydantic remains authoritative; the small shared TypeScript surface mirrors
responses.

## WO-036 and WO-038 contract

WO-036 can use canonical Opportunity creation, owner, amount/currency, expected close
date, current stage, exact transition time, prior reliable entry time, actual close,
outcome/reason and reopen events. Baselines are explicitly incomplete. Definitions for
conversion, stage re-entry, cohorts, currency and cycle time remain WO-036 work.

WO-036 now consumes those facts without changing their ownership. Funnel stage
entries use only actual non-baseline events in one selected pipeline; duration
requires an exact prior entry; closed cohorts use current final closure state;
and current owner attribution is explicit. Sales Analytics does not write back
to Pipeline or Opportunity lifecycle state.

WO-038 receives no probability, weighted amount, category, predicted close date,
commit/best-case value or deal score from this module. Forecasting must later use
versioned transparent assumptions and sufficient canonical outcomes.

## Observability and feature control

Safe category logs cover pipeline created/archived, stage changed, closed Won/Lost and
reopened using organisation/opportunity/stage identifiers only. Amounts, names,
outcome reasons and notes are excluded. `API_FEATURE_NATIVE_PIPELINE_ENABLED` is
server-authoritative and is exposed to clients only as the `nativePipeline` capability;
it does not override CRM mode or entitlement.
