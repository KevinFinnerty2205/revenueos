# WO-025C CRM provider selection

**Decision date:** 24 August 2026

**Selected provider:** HubSpot

**Deferred provider:** Salesforce
**Evidence basis:** current official provider documentation only for technical claims

## Decision

WO-025C implements HubSpot as the only production CRM connector. HubSpot gives
RevenueOS the strongest first path for relationship-driven small and mid-market
teams: OAuth can be tested in free developer test accounts, CRM objects share a
consistent API shape, account properties and pipelines can be discovered, and
deals, contacts and meeting activities support the focused workflow without a
bulk import or enterprise deployment project.

Salesforce remains a high-value second connector, but its 2026 External Client App
administration, instance-specific policy, broad `api` permission model and deeper
enterprise setup make it a poorer fit for the first ten-minute setup experience.
This is a sequencing decision, not a claim that Salesforce is less capable.

## Evidence and comparison

| Criterion | HubSpot | Salesforce | Outcome |
| --- | --- | --- | --- |
| Target and route-to-market fit | Accessible to smaller teams as well as larger HubSpot customers | Strong enterprise footprint and admin-led buying motion | HubSpot first |
| OAuth | Confidential authorisation-code flow with client secret, exact redirect, state, short-lived access token and refresh token | Web-server flow plus External Client App policy; PKCE is configurable/required by policy | HubSpot is the smaller first surface |
| Test support | Up to ten free developer test accounts; no production records required | Developer/scratch/sandbox options are strong but ECA packaging and org policy add setup | HubSpot faster proof path |
| CRM API | Common 2026-03 object, property, search and association APIs | Mature versioned sObject, query and composite APIs | Both mature |
| Deals/opportunities, contacts, companies | Direct standard-object support | Direct Account, Contact and Opportunity support | Tie |
| Activities | Meetings are CRM activity objects and may be associated at creation | Tasks/Events and activity relationships are mature | Both viable |
| Custom fields and stages | Account property and pipeline discovery fits bounded selectors | Describe metadata is powerful but broader | HubSpot simpler for bounded mapping |
| Idempotency | No general single-record write key; read/compare/reconcile is required | External IDs and composite resources offer strong future options | Salesforce stronger primitives; not decisive |
| Rate limits | OAuth apps have documented per-account burst limits; search has separate limits | Org API limits vary by edition and allocation | Both require guards |
| Webhooks/future inbound | Supported but unnecessary for focused outbound sync | Change Data Capture/platform events are strong | Deferred for both |
| Enterprise administration | Super Admin installs the app and grants scopes | External Client App, profiles/permission sets and org security policy | HubSpot lower first-run cost |
| Future bidirectional sync | Object timestamps, search, webhooks and associations provide a credible route | Excellent enterprise sync platform | Both credible |

## Official sources

HubSpot:

- [OAuth quickstart](https://developers.hubspot.com/docs/apps/developer-platform/build-apps/authentication/oauth/oauth-quickstart-guide)
- [2026-03 OAuth token API](https://developers.hubspot.com/docs/api-reference/latest/authentication/manage-oauth-tokens)
- [OAuth scope configuration](https://developers.hubspot.com/docs/apps/developer-platform/build-apps/authentication/scopes)
- [CRM object APIs](https://developers.hubspot.com/docs/api-reference/latest/crm/using-object-apis)
- [API usage guidelines and limits](https://developers.hubspot.com/docs/developer-tooling/platform/usage-guidelines)
- [Developer test accounts](https://developers.hubspot.com/docs/getting-started/account-types)

Salesforce:

- [OAuth web-server flow](https://developer.salesforce.com/docs/platform/mobile-sdk/guide/oauth-web-server-flow.html)
- [Spring ’26 External Client App direction](https://developer.salesforce.com/blogs/2026/01/developers-guide-to-the-spring-26-release)
- [Composite REST resource](https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_composite_composite_post.htm)

## Implementation choice

RevenueOS uses direct bounded HTTP rather than a provider SDK. The adapter owns
explicit connect/read/write timeouts and performs no hidden retry. The durable
WO-022 worker remains the retry owner. This keeps provider types out of RevenueOS
contracts and makes every external response deterministic in tests.

The standard confidential HubSpot OAuth documentation specifies client-secret
authorisation-code exchange and does not specify PKCE for this app type. WO-025C
therefore uses high-entropy one-time state, an exact registered redirect and a
server-side secret. PKCE will be added if HubSpot documents it for this standard
public-app flow or makes it an app policy; the decision is not generalised to
Salesforce or HubSpot MCP authentication.

## Deferred second connector

A future Salesforce work order should implement a separate `SalesforceCRMExecutor`
behind the existing contract, use External Client Apps, define least-privilege
permission sets, support sandbox proof, and repeat the provider-specific security,
mapping, concurrency and deletion review. No Salesforce runtime code, scope,
credential or user-facing connection is included in WO-025C.
