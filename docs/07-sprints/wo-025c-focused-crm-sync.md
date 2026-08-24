# WO-025C — Focused CRM Sync

**Status:** Implemented on `feature/epic-11-wo-025c-focused-crm-sync`; draft PR,
not merged.

## Decision and outcome

HubSpot was selected over Salesforce as the first production CRM connector after
reviewing current official OAuth, object, test-account, rate-limit and administration
documentation. The implemented path makes the Core promise real:

> Finish the meeting. RevenueOS prepares the admin. Review it once, then update the CRM.

The only live connector is HubSpot. Existing WO-022 simulation connectors remain
clearly labelled and production-disabled.

## Delivered

- Migration `0034_crm_sync` with OAuth state, encrypted credential envelope, entity,
  field and stage mapping tables; connection/execution extensions; composite tenant
  FKs, checks, indexes and forced RLS.
- HubSpot 2026-03 direct-HTTP adapter with OAuth exchange/introspection/refresh/
  revoke, bounded search/discovery/read/update/activity operations and explicit
  timeouts with no hidden retry.
- AES-256-GCM tenant/connection-bound credential storage and production fail-closed
  master-key configuration.
- Admin connection/test/reconnect/disconnect and typed mapping UI.
- Contextual Opportunity search/link with no eager provider fetch or fuzzy match.
- Field authority, stage mapping, decimal/currency safety, next-step preparation,
  exact preview and stale-state protection.
- Review-only interaction activity proposals containing final summary and bounded
  next steps, never raw transcript or full Evidence.
- Live durable execution, duplicate-confirmation idempotency, provider verification,
  mapping sync timestamps, Retry-After-aware bounded retry and read-only unknown-
  outcome reconciliation.
- Safe export/deletion and metadata-only audit/logging.

## Security and privacy

OAuth state is high entropy, hashed, tenant/user/redirect-bound, expiring and
single-use. Admin configuration and active user/membership are server-enforced.
Tokens never leave the connector boundary. Mapping and execution are tenant-scoped
in services, repositories and RLS. No AI output directly invokes HubSpot and
approval never equals execution.

## Product decisions

- Each field is its own atomic Action; grouped updates are deferred to avoid
  partial success and preserve field provenance.
- Existing Contact mapping is required; contact create/merge is deferred.
- Methodology custom-field sync fits the typed architecture but is not exposed.
- Activity and opportunity field updates remain separate.
- No webhooks, bidirectional sync, bulk import, task creation or autonomous policy.

## Tests and evidence

Automated suites use mocked HTTP/provider state and perform no real provider call.
They cover OAuth and token security, typed/tenant mappings, exact preview, live
write/receipt, duplicate confirmation, stale provider state, currency/authority,
activity idempotency/privacy, timeouts, rate limit, malformed response and unknown
reconciliation, plus web setup/link/review controls. Migration upgrade/downgrade,
PostgreSQL RLS/drift and the complete repository gate are part of hand-off.

Deterministic Playwright evidence:

- [HubSpot admin connection and typed mappings](assets/wo-025c-hubspot-settings.png)
- [Opportunity exact-value CRM execution preview](assets/wo-025c-crm-preview.png)

## Known limitations

One production CRM only; no broad inbound/bulk sync, autonomous writes, contact
creation, arbitrary custom fields, methodology UI mapping, task capability, native
CRM expansion or Prospect work. Target-environment OAuth registration and gated
developer-account smoke proof remain deployment activities, not CI requirements.
