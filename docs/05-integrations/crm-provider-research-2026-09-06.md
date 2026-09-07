# CRM provider research — 6 September 2026

This is a technical/product activation review, not legal advice or provider approval.
Only current official provider material was used. No provider account, application,
licence, terms acceptance, customer connection or paid resource was created.

## Recommendation

Ship production-capable, fail-closed adapters for **HubSpot and Salesforce**. Retain
polling for V1 and defer webhooks/CDC. Assess Microsoft Dynamics 365 as the single
additional Australian-market CRM and **defer it**: Dataverse has a mature Web API, but
Entra application/tenant administration, Dynamics environment/licensing differences
and a third mapping/support surface do not have enough incremental launch evidence.

Production status remains `PROPOSED / NOT ACTIVATED` for both providers. CRM business
data and contact identity may be personal information; Oryntela must complete its own
privacy/subprocessor, customer authority and Australian cross-border review before
activation. Provider data location is account/service configuration dependent and is
not claimed here.

## HubSpot

### Current platform findings

- HubSpot supports OAuth for multi-customer/public apps and documents authorisation,
  required scopes, token exchange/refresh and account identity. See [HubSpot OAuth
  overview](https://developers.hubspot.com/docs/apps/developer-platform/build-apps/authentication/oauth/working-with-oauth)
  and [authentication overview](https://developers.hubspot.com/docs/apps/developer-platform/build-apps/authentication/overview).
- HubSpot introduced date-versioned APIs and currently documents `2026-03`; Oryntela
  pins that version rather than mixing route families. See [HubSpot API
  versioning](https://developers.hubspot.com/docs/developer-tooling/platform/versioning)
  and [CRM object APIs](https://developers.hubspot.com/docs/api-reference/latest/crm/using-object-apis).
- HubSpot documents a date-versioned association batch-read endpoint with up to 1,000
  input IDs. Oryntela stays below that ceiling with its 200-record hard page limit
  and uses one batch relationship read per incremental Contact/Deal page. See the
  [HubSpot associations guide](https://developers.hubspot.com/docs/api-reference/crm-associations-v4/guide).
- Published usage guidance describes app-specific burst/daily limits and `429`
  handling; limits vary by subscription/app category, so Oryntela must monitor the
  connected account rather than hard-code a commercial allowance. See [HubSpot usage
  guidelines](https://developers.hubspot.com/docs/developer-tooling/platform/usage-guidelines).
- Webhooks are available but require public subscription/signature/delivery recovery
  infrastructure. V1 polling avoids making delivery authoritative; a later webhook
  may only wake the durable reconciler. See [HubSpot webhooks](https://developers.hubspot.com/docs/apps/developer-platform/add-features/configure-webhooks).
- HubSpot has deprecated legacy OAuth token routes in favour of the current versioned
  token endpoints; the implementation uses the current path. See the [OAuth token
  migration guide](https://developers.hubspot.com/docs/api-reference/legacy/authentication/oauth-tokens/v1/migration-guide)
  and [deprecation notice](https://developers.hubspot.com/changelog/v1-oauth-api-deprecation?hs_amp=true).

### Exact requested scopes

| Scope | Why Oryntela requests it | V1 processing boundary |
| --- | --- | --- |
| `oauth` | OAuth connection/token metadata | Verify the connected portal and refresh authority |
| `crm.objects.companies.read` / `.write` | Account read and reviewed create/update | Allow-listed name/domain/industry/owner only |
| `crm.objects.contacts.read` / `.write` | Contact read and reviewed create/update | Allow-listed identity/title/phone/account/owner only |
| `crm.objects.deals.read` / `.write` | Opportunity read and reviewed create/update | Allow-listed commercial/stage/account/owner fields only |
| `crm.objects.meetings.read` / `.write` | Preserve WO-025C's explicitly reviewed meeting-log Action | No broad activity sync |
| `crm.objects.owners.read` | Resolve CRM owners | Bounded owner ID/name/email/active projection |
| `crm.schemas.companies.read`, `crm.schemas.contacts.read`, `crm.schemas.deals.read` | Validate standard mapping availability/type/read-only state | Only allow-listed property definitions are returned; raw schemas are not persisted |

Write scopes are necessary for the optional reviewed create/update path but do not
enable writeback by themselves. Oryntela leaves writeback off until mapping approval,
an explicit enable action and a fresh per-record confirmation.

### Terms/privacy activation notes

HubSpot's current [Developer Terms](https://legal.hubspot.com/hs-developer-terms)
and [Developer Policy](https://legal.hubspot.com/hubspot-developer-policy) require
authorised, disclosed handling of customer data. The current [HubSpot DPA](https://legal.hubspot.com/dpa)
includes processing, security, transfer and subprocessor terms. Owner/legal review of
the applicable product/app distribution model, privacy notice, customer authority,
deletion support and any marketplace requirements remains required before production.

## Salesforce

### Current platform findings

- Salesforce now recommends External Client Apps as its next-generation integration
  model; new Connected App creation is restricted from Spring '26. See [External
  Client Apps and Connected Apps](https://developer.salesforce.com/docs/platform/mobile-sdk/guide/connected-apps.html)
  and [Salesforce's External Client App security overview](https://developer.salesforce.com/blogs/2025/01/secure-your-org-with-external-client-apps).
- External Client Apps support authorisation code, client secret policy, refresh-token
  policy and PKCE. Oryntela selects server-side authorisation code plus PKCE S256 and a
  secret. See [Salesforce ECA setup](https://developer.salesforce.com/docs/platform/accsdk/guide/acc-sdk-setup-auth-external.html)
  and [PKCE token exchange guidance](https://developer.salesforce.com/docs/analytics/sdk/guide/sdk-access-token.md).
- OAuth returns an instance URL and identity URL. The implementation validates and
  binds both before use; it does not trust a browser-supplied org/host. See [Salesforce
  identity URLs](https://developer.salesforce.com/docs/platform/mobile-sdk/guide/oauth-using-identity-urls.html).
- The REST API supplies standard sObject, SOQL `query/queryAll`, conditional update
  and composite options. V1 uses bounded single-page `queryAll` reconciliation;
  composite/bulk is deferred pending measured quota need. See the [REST API quick
  start](https://developer.salesforce.com/docs/platform/connect-rest-api/guide/quickstart.html)
  and [composite resource](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_composite_composite_post.htm).
- API allocations vary by Salesforce edition/licence and can be monitored through
  response headers and Limits resources. Oryntela treats quota responses as degraded,
  avoids full scans and does not claim a fixed allowance. See [Salesforce API limits
  and monitoring](https://developer.salesforce.com/blogs/2024/11/api-limits-and-monitoring-your-api-usage).

### Exact requested scopes

| Scope | Why Oryntela requests it | V1 processing boundary |
| --- | --- | --- |
| `api` | Read and perform reviewed writes to standard CRM sObjects | Account, Contact, Opportunity, User owner and OpportunityStage only |
| `openid` | Bind the OAuth result to verified user/org identity | Stable Salesforce user/org identity and bounded display/email |
| `refresh_token` | Continue bounded background reconciliation without collecting credentials again | Encrypted server-side refresh authority; rotated under row lock |

The production permission set must narrow the authorised Salesforce user to the exact
standard objects/fields and record population intended by the customer. Oryntela does
not request broad custom-object, files, Notes, activity or metadata administration.
Person Accounts are detected and rejected as unsupported, not mapped to duplicate
business Account/Contact records. The adapter pins `v67.0`; upgrades require official
release review, deterministic provider contract tests and an authorised sandbox smoke
test.

Salesforce change data capture is deferred. Five-minute `SystemModstamp` polling plus
durable `nextRecordsUrl` checkpoints is operationally smaller, and CDC could later
wake the same reconciler without becoming the source of truth.

### Terms/privacy activation notes

Salesforce's [customer agreements](https://www.salesforce.com/company/legal/customer-agreements/),
[privacy resources](https://www.salesforce.com/privacy/resources/) and [Trust and
Compliance documentation](https://www.salesforce.com/company/legal/trust-and-compliance-documentation/)
identify current DPA, security/architecture, infrastructure/subprocessor and API-use
materials. The customer's own licence, edition, environment, API allowance, admin
permission-set/ECA install policy and processing location must be confirmed. No claim
is made that a Developer Edition is suitable for production; any signup, identity
verification, MFA or terms acceptance is an owner boundary.

## Third CRM assessment: Microsoft Dynamics 365 Sales

| Factor | Finding |
| --- | --- |
| Australian relevance | Available and credible for Microsoft-oriented organisations, but no WO-042 design-partner evidence shows launch demand beyond HubSpot/Salesforce |
| API maturity | Dataverse exposes a mature OData Web API and service protection limits |
| Authentication | Requires Microsoft Entra registration/tenant consent and Dataverse environment authority distinct from WO-040 Microsoft Graph mail/calendar |
| Commercial/operational burden | Dynamics licensing, environment/security roles, Dataverse tables/metadata and another support matrix materially widen launch work |
| Incremental launch value | Lower than finishing, operating and learning from the two selected CRM paths |

Official references: [Dataverse developer overview](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/),
[Dataverse authentication](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/authentication),
and [Dynamics 365 Sales Australian pricing](https://www.microsoft.com/en-au/dynamics-365/products/sales/pricing).

**Recommendation: DEFER. Implemented: NO.** WO-040 Microsoft 365 email/calendar is
not Dynamics CRM and must not be presented as such.

## Owner boundary and external proof

External HubSpot and Salesforce smoke tests were **not performed — owner boundary**.
Each requires Kevin or an authorised customer administrator to use a legitimate
provider account, accept current terms, configure an app/ECA, redirect and permission
policy, and provide secrets through approved storage. A free developer/sandbox option
does not authorise Codex to create an account or accept terms. No card or spend should
be required for deterministic engineering; exact production customer licensing is
customer-provided and account-specific.
