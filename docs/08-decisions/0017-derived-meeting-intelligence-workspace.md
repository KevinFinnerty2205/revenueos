# ADR 0017: derive a unified Meeting Intelligence workspace

- Status: accepted
- Date: 2026-07-20

## Context

RevenueOS already persists six independently traceable Meeting Intelligence
capabilities. Six frontend panels each read and polled their own endpoint, so the
page could not explain overall readiness or reliably start Follow-up Email after
its four validated source artefacts became available. Collapsing outputs into a
new artefact or adding a workflow engine would duplicate existing lifecycle,
idempotency and traceability.

## Decision

Add a tenant-scoped aggregate read endpoint that derives product-safe capability,
progress and overall state from existing current-version jobs and artefacts. Add
a small generation endpoint that invokes the existing five extraction request
services and queues/reuses Follow-up Email only when its backend-derived source
preconditions are complete.

Use one frontend polling chain. When the aggregate response reports the composer
preconditions satisfied, that chain calls the same idempotent orchestration
endpoint. Keep all individual endpoints and persistence unchanged. Validate the
composer source set by organisation, meeting, transcript, artefact type, prompt
version and schema version; continue excluding Risks & Blockers and transcript
content.

Do not persist overall state and do not add a migration.

## Alternatives considered

- **One new combined AI job/artefact:** rejected because it loses independent
  retries, audit trace and capability reuse.
- **Client fan-out to six POST and six GET endpoints:** rejected because it keeps
  redundant polling and makes dependency readiness a browser coordination rule.
- **Worker-side general dependency graph or workflow engine:** rejected as
  disproportionate to one fixed dependency.
- **WebSockets or streaming:** rejected because durable three-second polling is
  already established and sufficient.
- **Persisted workspace status:** rejected because it can drift from the six
  authoritative capability states.

## Consequences

The product presents one coherent workspace while jobs and artefacts remain
independent. Aggregate reads are bounded rather than N+1, direct refresh works,
and concurrent orchestration reuses equivalent work. Follow-up Email creation may
wait until an Intelligence page poll or another explicit generate request occurs;
there is no background workflow engine. Existing individual API clients remain
compatible. Rollback requires only an application deploy rollback and no data
migration.
