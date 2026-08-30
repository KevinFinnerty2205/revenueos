# Sales analytics architecture

**Status:** WO-036 implementation contract.

RevenueOS Sales Analytics is a Core Intelligence read model inside the existing
FastAPI modular monolith. It reads canonical Opportunity, immutable stage-history,
Interaction and confirmed execution facts. It adds no warehouse, ETL job, queue,
provider, prompt, model call, generic query language or mutable analytics fact copy.

## Modules and API

- A code-owned metric registry publishes immutable IDs plus explicit definition
  versions.
- A tenant-scoped repository performs bounded, set-based fact reads with explicit
  organisation predicates.
- `SalesAnalyticsService` owns cohort, date, currency, reopen and follow-on policy.
- `SalesMetricService` returns typed scalar observations for registry metrics and is
  the sole WO-037 target handoff.
- Strict endpoints expose metadata/definitions, Overview, Funnel, Activity,
  Win/Loss and one canonical metric observation. They accept only date, timezone,
  pipeline, owner and required currency filters—never arbitrary grouping or SQL.

The web loads shared metadata once and the active Insights tab independently. The
four views are Overview, Funnel, Activity and Win/Loss. Exact values are rendered in
semantic tables alongside simple CSS bars; charts do not require a large dependency
and never rely on colour alone.

## Query and performance boundary

Requests are limited to five local years. Every source query is set-based; follow-on
matching and funnel calculation operate over the bounded returned fact sets without
per-record database reads. Database indexes cover tenant plus close date, stage-event
pipeline/time and Interaction completion/type. No result cache or persisted
observation is needed at private-beta scale. Operational telemetry records endpoint,
duration, safe identifiers and error class only—not requested business values,
counts, rates, amounts, reasons, names or notes.

## Trust and tenancy

Routes derive organisation/user from verified membership. Owner and pipeline filters
must resolve inside the tenant. Repository predicates and existing forced RLS provide
defence in depth; the browser supplies no organisation ID. Analytics does not read
transcripts, Evidence values, prompts, provider payloads or closure notes.

Campaign/enrolment `sent` state is not sufficient evidence of real outreach. A live
send requires `ActionExecution.execution_mode=live`, `execution_status=succeeded`
and `capability=send_email`; `simulated_success` is always excluded.

## Product boundaries

Sales Analytics describes what happened. WO-037 may compare registered observations
with targets. WO-038 may later consume clean lifecycle history but must introduce its
own transparent assumptions, range and calibration; WO-036 supplies no probability,
weight or forecast. WO-039 may later use authorised aggregate facts for coaching, but
WO-036 includes no team ranking, employee profile or performance score.

No analytics mutation path imports Revenue Brain, Methodology or Evidence
repositories. Seller-reported outcome reasons and observed activity sequences remain
provenance-labelled facts, not customer truth or causal intelligence.
