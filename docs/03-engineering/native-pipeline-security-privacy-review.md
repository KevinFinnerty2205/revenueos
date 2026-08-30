# Native Pipeline security and privacy review

**Status:** completed for WO-035.

## Trust boundaries and controls

| Risk | Control |
| --- | --- |
| forged organisation or Opportunity ID | organisation comes only from verified tenant context; repository predicates and RLS fail closed |
| cross-tenant pipeline/stage attachment | composite organisation foreign keys plus tenant-scoped lookup; foreign stage IDs resolve as not found |
| direct field-authority bypass | generic Opportunity PATCH rejects pipeline stage/final status; mutations use `PipelineService` |
| external CRM divergence | external mode rejects stage, close and reopen with `external_stage_authority` |
| stale concurrent move/double close | row lock, expected current stage and idempotency uniqueness; friendly 409 conflict |
| archived/invalid stage | active pipeline/stage and semantic target checks run server-side |
| event tampering | no update API and PostgreSQL trigger rejects UPDATE; stage/pipeline archive preserves references |
| closure-note disclosure | RLS, normal Opportunity permission, 500-character bound, export only in authorised organisation export; never logged |
| filter inference | every board query includes organisation predicate before owner/Account/search filters |
| admin abuse | definition configuration requires organisation admin plus CRM entitlement/native mode/features |

PostgreSQL enables and forces RLS on `sales_pipelines`, `sales_pipeline_stages` and
`opportunity_stage_events`. The runtime role does not bypass RLS. Tenant-owned unique
keys and indexes include organisation scope.

## Privacy and provenance

Outcome reason/note may contain sensitive internal commercial information. It is
stored as seller reported, never transformed into customer Evidence, never sent to a
provider and never placed in audit metadata or operational logs. The product shows
provenance beside closure reasons. Stage movement contains workflow metadata only and
does not trigger AI.

The board returns only tenant-visible canonical Opportunities under the current
organisation-wide beta visibility model. It adds no manager hierarchy, rep ranking,
screen telemetry, activity surveillance or employee score.

## Verification

Tests cover cross-organisation reads and stage IDs, forced RLS state, invalid/archived
targets, external authority, stale concurrency, idempotent duplicate requests,
controlled outcome input, no Methodology mutation, currency separation, migration
baseline accuracy and safe errors. Standard tests use deterministic local fixtures and
make no external provider call.

## Residual risks and future work

The current external mode is read-only rather than a complete provider reconciliation
loop. Future inbound/mapped execution must preserve the same tenant, authority,
idempotency and history boundary and use `external_crm` source. Team-level visibility
and manager permissions remain future work. Event DELETE is permitted only through
the parent Opportunity/organisation erasure lifecycle; there is no standalone event
delete route.
