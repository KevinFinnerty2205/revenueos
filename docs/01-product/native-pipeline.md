# Native Pipeline implementation guide

**Status:** current WO-035 implementation.

Native Pipeline is the simple operating view for canonical Opportunities. It answers
where open deals are, what changed, how long the current tracked stage has lasted,
what requires explainable attention, what closed and what seller-reported outcome was
recorded. It does not infer customer truth or forecast an outcome.

## Current seller experience

- `/opportunities` provides Board, List and Closed views.
- The default view contains active open stages only; Won and Lost do not become large
  board columns.
- Cards show Account, Opportunity, amount/currency, expected close date, owner, current
  tracked stage duration, next open Action and at most two deterministic attention
  reasons.
- Filters cover Pipeline, owner, Account, stage, close-date window, search and attention.
- Selecting the Opportunity opens Sales Brain's existing Opportunity workspace.
- Open-stage movement uses an explicit accessible select. Won and Lost use dedicated
  closure flows. There is no drag-only interaction.
- Closed Opportunities can be reopened into an explicitly selected open stage without
  erasing the earlier closure event.

The summary is descriptive: current Opportunity count, current open amount grouped by
currency, count needing attention and salesperson-entered close dates this month. Null
amounts are not treated as zero. AUD and USD are never added together and no FX rate is
applied.

## Current administrator experience

`Settings → CRM → Pipelines` is visible to organisation administrators. In native CRM
mode an administrator can create up to five active pipelines, each containing one to
ten open stages plus exactly one Won and one Lost stage, with a maximum of twelve
stages. An administrator can rename and reorder stages, add an open stage, add optional
short guidance, choose the default pipeline and archive safely.

Stage semantic type is immutable. An open stage cannot be archived while it contains a
current Opportunity. Won and Lost cannot be archived. A pipeline cannot be archived
while it contains an open Opportunity, and the current default must be replaced first.
Changing the default affects new Opportunities only.

## Default and compatibility behaviour

Migration `0044_native_pipeline` creates one `RevenueOS Sales Pipeline` per existing
organisation using the existing canonical stage taxonomy: Discovery, Qualification,
Evaluation, Proposal, Negotiation, Procurement, Other, Closed Won and Closed Lost. New
Opportunities enter the first active open stage in the default pipeline and record a
`system_initial` event.

The existing `Opportunity.stage` classification remains as a compatibility surface for
current API clients, Methodology projections and HubSpot mappings. Stable pipeline and
stage identifiers are authoritative for native workflow. A custom open stage maps to
the compatibility value `other`; it does not create a second Deal model.

## Current attention rules

The read model applies only explainable rules and returns at most two reasons:

1. an overdue high/urgent open Action;
2. a salesperson-entered expected close date in the past;
3. no next open Action.

Time in stage is displayed neutrally. There is no arbitrary “stuck” threshold, numeric
health score or hidden ranking. Methodology gaps and Revenue Brain conflicts remain in
their existing evidence-aware surfaces rather than being recomputed by Pipeline.

## Current limitations

There are no probabilities, weighted amounts, forecasts, predicted close dates,
forecast categories, stage gates, stage-specific required fields, workflow automation,
bulk moves, saved views, target durations, deal scores, custom outcome taxonomies or
pipeline analytics. Historical time before WO-035 tracking may be unavailable. The
external-CRM board is read-only; a future mapped connector path may append
`external_crm` events through the same authoritative service, but WO-035 does not add
provider execution or polling.

See [Pipeline and Sales Brain boundary](pipeline-sales-brain-boundary.md),
[Opportunity stage and closure guide](opportunity-stage-closure-guide.md),
[Pipeline packaging](pipeline-packaging.md) and
[Native Pipeline architecture](../03-engineering/native-pipeline-architecture.md).
