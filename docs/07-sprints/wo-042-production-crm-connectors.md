# WO-042 — Production CRM Connectors

- **Branch:** `codex/wo-042-production-crm-connectors`
- **Baseline:** `d78c5b93`
- **Status:** engineering review complete; approved for merge
- **Migration:** `0058_production_crm_connectors`
- **Providers:** HubSpot and Salesforce, production-capable and not production-active
- **Data/spend:** deterministic synthetic fixtures and official public documentation
  only; no customer CRM and AUD $0

## Outcome

WO-042 turns the focused WO-025C HubSpot boundary into a provider-neutral Account,
Contact and Opportunity reconciliation layer and adds Salesforce through the current
External Client App model. Native Oryntela CRM remains first-class and required by
neither provider. One Oryntela organisation can have at most one active external CRM.

The durable worker performs paged, resumable initial and five-minute incremental
polling with tenant-local cursors, progress, bounded retries and immutable receipts.
Provider objects are projected through a common allow-list; no raw response or
arbitrary custom field is persisted. HubSpot uses `2026-03` CRM object APIs,
modified-time search and an archived pass. Salesforce pins REST `v67.0`, uses
`queryAll`/`SystemModstamp`, validates the OAuth instance origin and safely rejects
unsupported Person Accounts. HubSpot incremental Contact/Deal relationships use one
bounded association batch read per page; neither provider path performs record-wise
relationship discovery.

Default authority is conservative. Core CRM fields are provider-authoritative where
the connected CRM owns them; identity/currency/stage fields that can change meaning
require review. External owners and stages require explicit same-tenant mappings.
Strong matching is limited to one exact Account domain or non-generic Contact business
email; Opportunity names never merge records. Ambiguous identity, missing required
data, unmapped relationships, archives and concurrent changes create actionable
conflicts rather than last-write-wins.

Writeback is off by default and disabled again by any mapping change or connector kill
switch. An administrator must review the mapping version and enable it, and each
create/update still requires an expiring exact preview and explicit confirmation.
Success is verified and receipted. An ambiguous write becomes `unknown` and is not
blindly retried. External deletion is unsupported; disconnect does not delete either
Oryntela or customer CRM records.

## Security and privacy

- OAuth state is hashed, expiring, replay-safe and bound to Oryntela organisation,
  administrator, provider and exact redirect.
- Salesforce adds encrypted PKCE, signed token-response verification and identity URL/
  userinfo org-user cross-checking.
- Access/refresh tokens and Salesforce instance origin use the existing AES-256-GCM
  tenant/connection-bound envelope. Refresh rotation is row-locked.
- The Salesforce origin must be HTTPS under `*.salesforce.com` with no port,
  credentials, path, query or fragment. HubSpot uses a fixed official API origin.
- Browser inputs cannot supply SOQL, arbitrary canonical field names, provider hosts,
  cursor authority or bulk mutations.
- Seven new tenant tables use composite references and forced PostgreSQL RLS; the
  database enforces one active external CRM and one Oryntela owner for a provider
  tenant.
- Provider/customer strings remain inert and never acquire prompt, Action, Evidence,
  consent or cross-tenant authority.
- Export version 35 contains bounded canonical provenance and no token, secret, cursor
  or raw provider response. Offboarding revokes best-effort, removes local credential
  authority and stops future work while preserving external customer data.

## Product and commercial boundary

The Settings experience presents “Use Oryntela CRM” and “Connect your existing CRM”
without unsupported providers. Administrators can see lifecycle, health, truthful last
sync, record progress, field/stage/owner mapping, conflicts, mapping approval,
writeback and a stop-all-sync control. Ordinary sellers continue to use canonical
Oryntela records and existing Pipeline/Forecast/Targets/Analytics.

CRM activity mirroring, generic task sync, Notes/files, arbitrary custom fields or
objects, Salesforce record-type administration, external delete, webhooks/CDC and
Dynamics 365 are deferred. The existing reviewed HubSpot meeting-log Action is retained
but does not constitute broad activity sync. Ordinary CRM sync requires the CRM add-on
and consumes no Oryntela Credits. The customer supplies their CRM licence.

## Provider research and production boundary

Official research is dated and linked in [CRM provider research](../05-integrations/crm-provider-research-2026-09-06.md).
Dynamics 365 was the sole third-CRM assessment and is deferred because Dataverse/
Entra/licensing and support effort do not have enough incremental Australian launch
evidence.

HubSpot and Salesforce external smoke tests were not performed: provider app/account
creation, terms, identity/MFA and admin configuration are owner actions. Both adapters
are fail-closed in production without exact official endpoints, HTTPS redirects,
credentials, encryption key and separate owner activation approvals. Production app
registration, provider/customer consent, privacy/subprocessor review, monitoring,
synthetic smoke proof and explicit approval are parked for WO-054.

## Evidence and handoff

Deterministic tests cover existing HubSpot semantics plus Salesforce PKCE/signature/
identity, encrypted secrets, instance-host rejection, standard-object normalisation,
unknown fields, pagination, token rotation, ambiguous writes, Person Accounts,
read-only initial state and interval-bucketed incremental scheduling. Shared API,
commercial/export/deletion, migration and RLS suites exercise provider-neutral
behaviour. Final validation results and screenshots are recorded in the draft PR and
final handoff after the complete gate.

Synthetic visual evidence:

- [Native CRM choice — desktop](assets/wo-042/native-crm-choice-desktop.png)
  and [390px mobile](assets/wo-042/native-crm-choice-mobile.png)
- [HubSpot initial sync, mappings and conflict — desktop](assets/wo-042/hubspot-settings-desktop.png)
  and [390px mobile](assets/wo-042/hubspot-settings-mobile.png)
- [Salesforce mapping and conflict — desktop](assets/wo-042/salesforce-settings-desktop.png)
  and [390px mobile](assets/wo-042/salesforce-settings-mobile.png)
- [Salesforce reauthorisation — desktop](assets/wo-042/salesforce-reauthorisation-desktop.png)
  and [390px mobile](assets/wo-042/salesforce-reauthorisation-mobile.png)

See [production CRM connector architecture](../03-engineering/production-crm-connectors.md),
[authority matrix](../03-engineering/crm-authority-matrix.md) and
[ADR 0072](../08-decisions/0072-provider-neutral-production-crm-connectors.md).
WO-043 is not started. WO-055 remains recorded and not implemented.
