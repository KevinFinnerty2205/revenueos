# ADR 0072: provider-neutral CRM reconciliation with reviewed writeback

- **Status:** Accepted
- **Date:** 2026-09-06

## Context

Oryntela must remain useful as a first-class native CRM while also serving customers
whose system of record is HubSpot or Salesforce. Those providers differ in OAuth,
pagination, object names, relationship semantics, versions, rate limits and write
behaviour. Treating either provider response as an Oryntela record, or resolving
concurrent edits by last-write-wins, would couple canonical reporting to provider
quirks and could silently destroy customer intent.

WO-025C already supplied a narrow HubSpot link and reviewed Action update path. WO-042
needs inbound Account, Contact and Opportunity reconciliation, Salesforce support,
durable large-import progress, explicit ownership/stage/field authority and safe
outbound create/update without adding a second CRM database or a universal ETL tool.

## Decision

Keep Oryntela Company, Contact and Opportunity rows as the canonical working
representation. Permit at most one active HubSpot-or-Salesforce connection per
Oryntela organisation. Bind every provider record through a tenant-scoped,
version-bearing mapping; never infer Opportunity identity from its name.

Adapters return only the shared allow-listed `CRMProviderRecord` contract. The service
owns matching, authority, conflicts, receipts, mapping versions and writeback policy.
Initial and incremental sync run as checkpointed background pages. HubSpot uses its
date-versioned object APIs and modified-time search; Salesforce uses REST `queryAll`
with `SystemModstamp` high-watermarks at the single configured `v67.0` API version.
Five-minute polling is the launch default. Webhooks and Salesforce CDC are deferred;
they may later wake the same reconciler but may not become tenant authority.

Inbound provider-authoritative values may update mapped canonical fields. A local
change since the last reconciliation, a manual-review field, an unmapped owner/stage/
relationship, an archive or an invalid required value creates a durable conflict.
There is no silent last-write-wins fallback. Oryntela intelligence, Evidence,
methodology, forecast judgement, suppression/consent, billing and Credits never enter
the provider payload.

Writeback is off by default. An administrator must complete the initial read, map
owners/stages, approve the current mapping version and explicitly enable writeback.
Each create/update still requires a fresh ten-minute preview, fingerprint and explicit
confirmation. A timeout or ambiguous provider response records `unknown`; no blind
retry is issued. External delete is not supported. Provider archives create a
conflict/tombstone and do not delete Oryntela records.

Use Salesforce External Client App authorisation-code OAuth with PKCE, signed token
response verification, identity/userinfo cross-checking and an allow-listed HTTPS
`*.salesforce.com` instance origin. Reuse the encrypted tenant-bound credential store
and row-locked refresh rotation for both providers. Production configuration remains
fail-closed behind separate activation approvals.

## Alternatives rejected

- **Provider-specific canonical tables:** creates parallel sales worlds and divergent
  reporting.
- **Automatic bidirectional last-write-wins:** loses human intent and creates sync
  loops.
- **Webhook/CDC first:** adds public delivery verification, replay, subscription and
  recovery infrastructure before launch evidence justifies it.
- **Arbitrary custom-field mapping:** materially widens schema, privacy and support
  risk; unknown fields are ignored safely in V1.
- **Multiple active external CRMs:** creates split authority and ambiguous outbound
  routing.
- **Dynamics 365 in V1:** adds Dataverse, Entra, environment/licensing and another
  provider support surface without launch evidence.

## Consequences

Polling means the UI must show truthful last-sync and degraded state. Mapping changes
invalidate writeback and require a deliberate reconciliation, while historical
receipts keep the old mapping version. Large imports progress over multiple short
transactions and can resume after failure. Person Accounts, generic CRM activity/task
mirroring, Notes, files, arbitrary custom objects/fields and external deletes are
explicitly unsupported or deferred.

The adapters are production-capable but neither provider is production-active. Owner-
controlled app registration, customer/admin consent, provider/privacy review,
production secrets, monitoring, synthetic smoke tests and explicit approval remain
WO-054 activation gates.
