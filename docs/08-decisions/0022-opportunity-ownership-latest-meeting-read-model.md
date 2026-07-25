# ADR 0022: Own meeting association on Meeting and derive the Opportunity Workspace from the latest meeting

- **Status:** Accepted
- **Date:** 2026-07-24

## Context

RevenueOS already has tenant-owned opportunities, meetings, transcripts and ten
independently persisted Meeting Intelligence capabilities. WO-007 needs an
opportunity-centred experience without duplicating intelligence, analysing a
transcript again or implying longitudinal reasoning. A meeting belongs to at
most one current opportunity, while an opportunity can have many meetings.

The product also needs one stable definition of “latest” and must exclude stale
or cross-meeting artefacts while preserving completed content through partial
failure.

## Decision

- Extend the existing Opportunity minimally with normalised stage/status,
  optional decimal value/currency, optional company/date and description. Do not
  add probability, forecast or CRM subdomains.
- Store one nullable `opportunity_id` on Meeting, protected by a composite
  `(organisation_id, opportunity_id)` foreign key and index. Association writes
  lock the meeting, compare `updated_at`, validate company compatibility and
  write metadata-only Meeting and Opportunity audits atomically.
- Select the latest meeting from active, non-cancelled associated meetings by
  `meeting_date DESC, meeting UUID DESC`. Bound recent meetings to 20 in the
  same order.
- Derive, rather than persist, the Opportunity Workspace. Read only the latest
  meeting's stored current-transcript jobs and artefacts. Accept only completed
  current registered prompt/schema traces whose content validates; prefer the
  newest completed valid equivalent result over a later failed attempt.
- Preserve valid empty output, exclude stale/failed/cancelled/malformed/cross-
  meeting/cross-tenant output and retain Follow-up Email source consistency.
- Use window and batch queries for list previews and bounded aggregate queries
  for the workspace. Never select transcript text in the opportunity path.
- Keep generation, retry and provider use in the existing Meeting Intelligence
  experience. The opportunity route offers navigation, not a second
  orchestration system.
- Label all intelligence as latest-meeting evidence. Do not claim opportunity
  health, history or trend.

## Alternatives

- **Association table:** rejected because the current cardinality is one
  opportunity per meeting and no association history/domain attributes require
  a separate entity.
- **Copy intelligence onto Opportunity:** rejected because it duplicates
  customer content, weakens provenance and creates stale invalidation paths.
- **Call the Meeting aggregate repeatedly from the browser:** rejected because
  one backend read model enforces selection and tenancy consistently with fewer
  requests.
- **Re-read transcripts for an opportunity summary:** rejected because WO-007
  adds no intelligence capability and transcript exposure is unnecessary.
- **Merge intelligence across meetings:** rejected because there is no approved
  longitudinal evidence, identity-resolution or conflict model.
- **Use creation time as latest:** rejected because meeting occurrence/schedule
  time is the product-relevant order; UUID provides only a deterministic tie.

## Consequences

Users get a coherent opportunity workspace from existing validated data with a
small schema change and no new external transmission. Tenant consistency is
enforced both in services and the database. Query cost remains bounded, and
transcript or infrastructure fields cannot leak through the typed response.

The workspace represents only one latest meeting. Reassigning a meeting changes
which opportunity can display it, and cancelled/deleted meetings disappear from
selection. Future relationship history or Revenue Brain work needs a separate
source/provenance decision and cannot treat this read model as longitudinal
truth. Downgrading the migration loses associations and opportunity audit data
and may delete company-less opportunities.
