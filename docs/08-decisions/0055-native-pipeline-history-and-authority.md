# ADR 0055 — Stable native pipeline stages, immutable history and explicit authority

- **Status:** Accepted
- **Date:** 2026-08-30
- **Decision owners:** Product and Engineering

## Context

WO-035 needs a configurable sales workflow without turning stages into customer truth,
corrupting existing Opportunity history or allowing RevenueOS and HubSpot to diverge.
Full immutable definition versions would require a draft/activation/stage-mapping and
bulk Opportunity migration experience disproportionate to the private-beta need.
Mutable names alone would make historical events unreadable if events only joined the
current label.

## Decision

1. Pipeline stage is workflow state only. Movement never creates Evidence, completes
   Methodology, changes Revenue Brain truth, supplies probability or enforces a gate.
2. Native definitions use stable pipeline/stage IDs. Stage semantic type is immutable.
   Rename/guidance/reorder/add are allowed; only an unused open stage may be archived.
3. Every real transition appends an immutable event with exact name/type snapshots.
   PostgreSQL rejects event UPDATE. Parent Opportunity/organisation deletion remains
   the approved erasure path.
4. Existing Opportunities receive one explicitly incomplete migration baseline. No
   earlier transitions or stage duration are inferred.
5. `Opportunity.stage` remains a denormalised compatibility classification while the
   stable IDs are authoritative for native workflow.
6. Native configuration is CRM-gated, while the descriptive Pipeline experience and
   canonical history remain Core foundations.
7. Native CRM mode permits manual authoritative movement. External CRM mode is
   explicitly read-only in WO-035 and rejects direct native movement; future mapped
   changes must use the same service and `external_crm` source.
8. Won/Lost use explicit closure endpoints with actual close date and controlled
   seller-reported outcome. Reopen appends history and clears current closure fields.
9. No stage probability, weighted pipeline, stage gate or arbitrary target duration is
   stored. Analytics and forecasting remain WO-036 and WO-038.

## Alternatives considered

- **Version every definition and activate with stage mapping:** strongest immutable
  definition model, rejected for WO-035 because it introduces a workflow migration
  product and bulk state mutation before representative demand exists.
- **Keep only the legacy stage enum/string:** rejected because custom labels,
  multi-pipeline assignment and reliable historical identity are impossible.
- **Let all edits mutate definitions freely:** rejected because semantic changes and
  deletion could silently corrupt history.
- **Copy HubSpot stages into native definitions:** rejected because it creates two
  competing registries and obscures field authority.
- **Assign conventional probabilities/gates:** rejected because it manufactures
  forecast precision and conflates workflow with evidence.

## Consequences

The private-beta model is small, queryable and analytically useful. Historical labels
survive rename and existing rows do not gain fabricated durations. Custom semantic
replacement requires a new stage or pipeline and an explicit Opportunity move. A later
need for large structural migrations may justify versioned definitions, but must add a
reviewed mapping lifecycle rather than reinterpret current IDs.
