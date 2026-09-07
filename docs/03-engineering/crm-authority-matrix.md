# CRM authority and mapping matrix

**Canonical for WO-042.** This document prevents HubSpot/Salesforce reconciliation
from becoming implicit bidirectional last-write-wins. Code-level rules live centrally
in `crm_provider.py`; adapters translate provider names but do not decide authority.

## Authority meanings

| Authority | Inbound behaviour | Outbound behaviour | Conflict behaviour |
| --- | --- | --- | --- |
| CRM is source of truth (`crm_authoritative`) | Apply only when the mapping/relationship is coherent and the Oryntela row has not changed since reconciliation | Never include in writeback | Local concurrent change, invalid/null required value or unresolved reference requires review |
| Oryntela is source of truth (`revenueos_authoritative`) | Never silently replace a different local value | Eligible only after writeback enablement plus per-record preview/confirmation | Different provider value requires review |
| Review before update (`review_before_sync`) | Never silently replace a different local value | Eligible only after writeback enablement plus per-record preview/confirmation | Difference requires review |
| Oryntela-only | Provider input/output prohibited | Provider input/output prohibited | Provider field is ignored |
| Provider-only | May be retained only as bounded reconciliation metadata | Never written | Does not alter canonical reporting |

Mappings are versioned. Any field/stage change disables writeback and requires
administrator approval of the new version. Old receipts retain the mapping/authority
version that explained their effect.

## Account / Company

| Canonical field | HubSpot | Salesforce | Default | Direction | Transformation/null rule |
| --- | --- | --- | --- | --- | --- |
| Name | `name` | `Name` | CRM source of truth | Inbound; outbound only if admin deliberately changes authority | Trim, maximum 200; missing name prevents create |
| Domain/website | `domain` | `Website` | Review before update | Inbound conflict or reviewed outbound | Normalise through public URL/domain safety; blank clears only through reviewed mapping |
| Industry | `industry` | `Industry` | CRM source of truth | Inbound | Trim, maximum 120; nullable |
| Owner | `hubspot_owner_id` | `OwnerId` | CRM source of truth | Inbound; outbound only if authority is deliberately changed | Must map to an active same-tenant Oryntela user; unresolved owner is a conflict |
| Location/status/provider reference | No V1 field | No V1 field | Local/provider-only as applicable | Not synchronised | Existing Oryntela location/status remain local; provider ID/version remain mapping metadata |

## Contact

| Canonical field | HubSpot | Salesforce | Default | Direction | Transformation/null rule |
| --- | --- | --- | --- | --- | --- |
| First/last name | `firstname` / `lastname` | `FirstName` / `LastName` | CRM source of truth | Inbound | Trim to 100 each; both required for automatic create |
| Business email | `email` | `Email` | Review before update | Strong-match input, conflict-aware inbound, reviewed outbound | Exact case-folded business email; generic inbox is never an automatic person merge; nullable after link |
| Phone | `phone` | `Phone` | CRM source of truth | Inbound | Trim to 50; never a sole match key; nullable |
| Job title | `jobtitle` | `Title` | CRM source of truth | Inbound | Trim to 150; customer text remains inert |
| Account | Company association / `associatedcompanyid` | `AccountId` | CRM source of truth | Inbound; supplied on reviewed external create | Must resolve to one mapped Account; an unresolved relation is a conflict; changing the relation outbound is not supported |
| Owner | `hubspot_owner_id` | `OwnerId` | CRM source of truth | Inbound | Same-tenant explicit owner mapping required |

HubSpot may expose multiple Company associations. V1 projects only the bounded primary
association compatible with Oryntela's current one-Company Contact model and never
guesses among additional associations.

## Opportunity / Deal

| Canonical field | HubSpot | Salesforce | Default | Direction | Transformation/null rule |
| --- | --- | --- | --- | --- | --- |
| Name | `dealname` | `Name` | CRM source of truth | Inbound | Trim, maximum 200; missing name prevents create; never an identity key |
| Account | Company association / `associatedcompanyid` | `AccountId` | CRM source of truth | Inbound; supplied on reviewed external create | Must resolve to mapped Account when present; unresolved relation conflicts |
| Stage | `dealstage` plus pipeline | `StageName` | Review before update | Conflict-aware inbound; reviewed outbound | Requires exact admin mapping; no label similarity; unmapped value preserved in conflict |
| Amount | `amount` | `Amount` | CRM source of truth | Inbound | Exact Decimal, two fractional digits; no float/FX; negative/invalid values rejected |
| Currency | `hs_currency_code` | `CurrencyIsoCode` | Review before update | Conflict-aware inbound; reviewed outbound | Three-letter uppercase code; amount cannot silently exist without currency |
| Expected close date | `closedate` | `CloseDate` | CRM source of truth | Inbound | ISO date at presentation boundary; timezone-aware provider timestamps |
| Owner | `hubspot_owner_id` | `OwnerId` | CRM source of truth | Inbound | Explicit active same-tenant user mapping required |
| Description | `description` | `Description` | Review before update | Conflict-aware inbound; reviewed outbound | Plain inert text, maximum 2,000; no HTML execution or prompt authority |
| Next step | `hs_next_step` | `NextStep` | Review before update | Observed but not applied/written in V1 | Current canonical Opportunity has no matching field; difference remains review-only |
| Provider status/reference | archive/version/mapping | delete/version/mapping | Provider-only | Reconciliation only | Minimal tombstone/version; never deletes canonical data |

Closed won and closed lost come only from explicit stage mapping to the existing
canonical stage/status model. Provider labels alone do not determine outcome.

## Always Oryntela-only

Sales Brain recommendations and summaries, potential relevance, Prospect observations,
Evidence and interpretation, methodology conclusions, forecast/system/manager
judgements, Targets, analytics definitions, consent and suppression, recordings,
transcripts, AI artefacts, billing, entitlements and Credits are never read from or
written to a CRM by WO-042. Provider text cannot grant Action or prompt authority.

## Conflict and delete rules

A conflict retains only canonical field key, local/provider bounded values and
fingerprints, provider version, status and resolution metadata. Administrators may use
the CRM value, retain the Oryntela value for a subsequent reviewed write, or mark a
manual decision. Resolution is audited; history is not rewritten.

Provider archive/delete marks the mapping/tombstone and creates a conflict. It does
not archive/delete Oryntela Evidence, intelligence or canonical record. Oryntela
archive/delete never issues a provider delete. Disconnect turns provider-authoritative
values into local snapshots by stopping all future provider authority; records remain.
