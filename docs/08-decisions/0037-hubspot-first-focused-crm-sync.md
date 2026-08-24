# ADR 0037: HubSpot-first focused CRM sync and field authority

**Status:** Accepted

## Context

WO-022 proved the provider-neutral execution lifecycle using simulations. Core
still lacked one production CRM route that could turn reviewed intelligence into
a safe external update. Implementing several CRMs would multiply OAuth, mapping,
concurrency and recovery risk before one complete path had been proven.

## Decision

Implement HubSpot as the sole WO-025C production connector through the existing
`ActionExecutor` and worker. Use direct HTTP to the HubSpot 2026-03 APIs. Integrated
CRM mode keeps HubSpot as the external system of record; native RevenueOS CRM is
unchanged future scope.

Every syncable field has one authority value:

- `review_before_sync` is the default and requires approval, a fresh external
  preview and a separate explicit confirmation;
- `crm_authoritative` permits reads but blocks RevenueOS writes; and
- `revenueos_authoritative` exists in the persistence/adapter model for future
  policy but is deliberately absent from the v1 admin UI.

Entity IDs live in tenant-scoped mapping records, not domain primary keys. Field
and stage mappings are explicit and typed. Existing contacts must be linked; the
connector does not fuzzy-match, merge or silently create contacts. Each field
update is a separate atomic Action. Activity creation is a separate Action with a
deterministic reconciliation marker.

## Consequences

The Core promise can be demonstrated end to end with a small setup surface. The
worker re-reads provider state before writing; stale previews fail. Writes with an
uncertain response are reconciled before any retry, and ambiguous activity outcomes
never create another activity. HubSpot tokens require AES-256-GCM envelope storage
with an environment-managed 256-bit key.

Field-level Actions avoid partial multi-field success and preserve provenance,
at the cost of more than one confirmation when several fields change. Grouped
atomic provider updates can be reconsidered only when the Action editor supports
removing individual fields and per-field receipts are modelled.

## Alternatives

- **Salesforce first:** deferred because Spring ’26 External Client App and
  enterprise permission administration add more first-run complexity.
- **Two production connectors:** rejected because it weakens test depth and does
  not prove the first customer workflow faster.
- **Approval triggers write:** rejected; approval records reviewed intent but is
  never execution authority.
- **Broad bidirectional or bulk sync:** rejected; current provider reads occur only
  for discovery, linking, preview, execution and reconciliation.
- **RevenueOS-authoritative by default:** rejected because it would silently invert
  the integrated CRM source-of-truth boundary.
