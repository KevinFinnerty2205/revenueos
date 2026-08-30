# Native Pipeline retention, export and deletion

## Retention

Pipeline current state and transition history follow the canonical Opportunity
lifecycle. The existing transcript/source retention worker does not age out pipeline
history independently; deleting stage history while keeping the Opportunity would make
lifecycle reporting misleading.

Archiving an Opportunity keeps its history. Archiving a stage or pipeline is a
non-destructive configuration action and retains all references/snapshots. Definitions
cannot be casually hard-deleted while historical events refer to them.

## Organisation export

Authorised organisation export schema v25 adds:

- `salesPipelines` including default/archive metadata;
- `salesPipelineStages` including stable key/type/order/guidance/archive metadata;
- current Opportunity pipeline/stage, timing, actual close and current outcome fields;
- `opportunityStageEvents` including snapshot names/types, source, baseline marker,
  prior reliable entry time, seller-reported closure metadata and idempotency key.

The export does not include provider payloads, locks, leases or telemetry. Outcome
notes are included because the export is the organisation's authorised data
portability path and they are canonical tenant data.

## Deletion

The normal product delete is the existing recoverable Opportunity soft deletion and
retains stage history. A later authorised hard deletion/erasure cascades the
Opportunity's stage events. Organisation deletion cascades pipelines, stages,
Opportunities and events under the existing approved maintenance path. Parent hard
deletion is the only event-deletion path; the product exposes no standalone history
delete/update endpoint. Pipeline and stage foreign keys use `RESTRICT` so definitions
referenced by current/history rows are archived rather than removed out of order.

Migration downgrade is a deployment rollback, not a customer deletion workflow. It
removes WO-035 columns/tables only when an operator deliberately downgrades from
`0044_native_pipeline`.
