# WO-007 — Opportunity Workspace Foundation

## Status

Complete in the feature branch. Draft pull-request publication is a delivery
step and does not change implementation status.

## Delivered scope

- minimally extended tenant-owned Opportunity metadata with normalised stage
  and status, decimal-safe optional value/currency, optional company and close
  date, description, optimistic update protection and metadata-only audit;
- nullable organisation-safe Meeting association with audited, stale-write-safe
  association and disassociation;
- enriched paginated Opportunities list without N+1 reads;
- product-safe aggregate workspace for the deterministic latest active,
  non-cancelled associated meeting and 20 newest recent meetings;
- composition of the ten existing validated, current-transcript Meeting
  Intelligence capabilities without transcript access, AI work or provider use;
- accessible list, create/edit and workspace routes with direct Meeting links,
  prominent Latest Next Best Action, Copy-only Follow-up Email, responsive and
  no-meeting/partial/error states;
- migration `0017_opportunity_workspace` with focused constraints, indexes,
  composite tenant keys, opportunity audit RLS and destructive downgrade
  documentation; and
- backend, frontend, migration, query-bound and deterministic browser coverage.

## Security and privacy result

Every read and write derives the organisation from trusted authentication,
applies explicit repository predicates and retains forced PostgreSQL RLS.
Opportunity/company/meeting relationships use composite tenant keys. Workspace
reads select transcript identity/version metadata only and return neither the
transcript nor AI infrastructure fields. Logs and audits contain metadata only.
WO-007 creates no new external data flow.

## Out of scope retained

No new AI prompt, schema, capability, job, worker path or provider call was
added. There is no cross-meeting reasoning, opportunity health, probability,
forecast, Revenue Brain, CRM sync, automatic matching, line item, quote,
contract, generated-content editing, email send, task/calendar integration or
action execution.

## Rollback

Deploy the WO-006D application and workers first. If deletion is approved,
downgrade `0017_opportunity_workspace`; this removes opportunity audit history
and meeting associations, deletes opportunities that cannot fit the earlier
required-company shape after clearing dependent links, and maps the expanded
opportunity fields back to the Sprint 2 contract. Back up and obtain an explicit
data-loss decision before downgrade.

## Detailed reference

See [Opportunity Workspace](../03-engineering/opportunity-workspace.md) and
[ADR 0022](../08-decisions/0022-opportunity-ownership-latest-meeting-read-model.md).
