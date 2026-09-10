# WO-054 production cost and Credit economics

- Research date: 10 September 2026 (Australia/Sydney)
- Currency: provider prices are quoted in their source currency; no tax treatment is assumed
- Approval status: proposal only; no purchase, subscription, price or Credit policy is active

## Minimum realistic baseline

The selected new-infrastructure baseline is USD 50/month before tax and variable usage: three USD 10 App Platform 1 GiB components, a USD 15 single-node managed PostgreSQL cluster, and USD 5 Spaces. The [DigitalOcean App Platform price list](https://docs.digitalocean.com/products/app-platform/details/pricing/), [PostgreSQL price list](https://docs.digitalocean.com/products/databases/postgresql/details/pricing/) and [Spaces price list](https://docs.digitalocean.com/products/spaces/details/pricing/) were verified on the research date.

The latest Reserve Bank of Australia daily observation available during research was 1 AUD = USD 0.7164 on 3 September 2026 ([RBA exchange rates](https://www.rba.gov.au/statistics/frequency/exchange-rates.html)). At that reference rate, USD 50 / 0.7164 = AUD 69.7934115019. Existing known annual domain/email costs add an equivalent AUD 5.1083333333/month, producing a known all-in fixed equivalent of AUD 74.9017448352/month before tax, FX movement and independent backup usage. Budget at least AUD 75/month plus those unknowns. This is a planning conversion, not a bank quote.

| Category | Provider | Required | Allowance / baseline | Fixed monthly | Usage component | Card / auto-renew | Owner action |
| --- | --- | --- | --- | ---: | --- | --- | --- |
| Web | DigitalOcean App Platform, Sydney | yes | 1 GiB fixed service | USD 10 | excess transfer USD 0.02/GiB | payment method; recurring | approve purchase |
| API | DigitalOcean App Platform, Sydney | yes | 1 GiB fixed service | USD 10 | excess transfer USD 0.02/GiB | payment method; recurring | approve purchase |
| Worker | DigitalOcean App Platform, Sydney | yes | 1 GiB fixed worker | USD 10 | scheduled jobs billed only while running | payment method; recurring | approve purchase |
| PostgreSQL | DigitalOcean managed PostgreSQL, Sydney | yes | 1 GiB single node; daily seven-day backup | USD 15 | transfer/resize if applicable | payment method; recurring | approve purchase; create admin/runtime roles |
| Object storage | DigitalOcean Spaces, Sydney | yes | 250 GiB and 1 TiB outbound | USD 5 | USD 0.02/GiB storage, USD 0.01/GiB outbound above allowance | payment method; recurring | approve purchase and separate backup destination |
| Independent backup candidate | AWS S3 Standard, Sydney (`ap-southeast-2`) | yes before customer data | no minimum charge | USD 0 fixed | USD 0.025/GB-month for the first 50 TiB plus requests/transfer | payment method; ongoing usage billing | approve account/bucket and a reviewed scheduled-upload implementation |
| Monitoring | App Platform/DB metrics, probes and email alerts | yes | baseline included | USD 0 incremental | none at launch | no separate card | set Kevin's controlled operational destination |
| Auth | Clerk Hobby | yes | 50,000 MRU/app; 100 retained organisations; one-day logs; no MFA | USD 0 | upgrade/overages beyond allowance | no card for Hobby | create production instance/domain or approve Pro |
| External AI | OpenAI API | can launch disabled | no free allowance relied upon | USD 0 | `gpt-5.6-terra`: USD 2/million input and USD 12/million output tokens | billing method and usage-based charges | approve data flow, project/key and hard limit separately |
| Stripe | Stripe standard + Billing PAYG | can launch disabled | no setup/monthly standard payment fee | AUD 0 | domestic cards 1.7% + AUD 0.30; international 3.5% + AUD 0.30; +2% FX; Billing 0.7% of Billing volume | bank/business verification for live; no fixed PAYG commitment | approve live implementation and activation |
| Prospect | none approved | can launch disabled | no provider call | 0 | unknown until commercial licence | likely contract/card | obtain redistribution/SaaS rights and quote |
| Microsoft | Entra/Graph | can launch disabled | standard APIs generally included within customer licence thresholds | USD 0 Oryntela baseline | customer Microsoft 365 licence; throttling applies | no Oryntela mailbox purchase authorised | owner/admin registers multitenant app |
| Google | Google OAuth/APIs | can launch disabled | API use has no stated licence fee | USD 0 Oryntela baseline | customer Workspace licence; external security assessor quote | assessor is paid/recurring annual review | owner starts verification only after legal URLs |
| HubSpot | developer app | can launch disabled | developer test account available | USD 0 Oryntela baseline | customer account/API entitlement | no new Oryntela paid licence required for sandbox | owner creates public OAuth app/test account |
| Salesforce | Developer Edition + External Client App | can launch disabled | synthetic dev org available | USD 0 Oryntela baseline | customer's edition/API access/integration user | no new Oryntela paid licence required for dev test | owner creates dev org/app |
| Domain/DNS | existing VentraIP | yes | owned `.com.au` and `.com` | AUD 0 incremental; current annual-cost equivalent AUD 2.9083333333/month | future registrar renewal | `.com` auto-renew off; `.com.au` not recorded here | approve exact records after target exists |
| System email | existing Zoho addresses + Clerk/Stripe hosted service emails | yes | one Mail Lite user and three approved identities | AUD 0 incremental; existing AUD 26.40/year = AUD 2.20/month equivalent | existing plan only | existing auto-renew remains enabled | no sender change; verify after DNS cutover |
| Error reporting | no dedicated provider | optional | platform logs/probes only | USD 0 | a privacy-reviewed provider is optional | none created | reassess after measured need |
| Google security assessment | Google-approved assessor | only if Google restricted scopes activate | annual CASA assessment likely required | quote unavailable | negotiated assessor fee | paid external engagement | obtain quotes; do not order |

Clerk pricing and feature boundaries come from [Clerk pricing](https://clerk.com/pricing). Hobby has no card requirement but lacks MFA and retains Clerk branding; Pro is USD 25 monthly or USD 20/month billed annually. The owner must explicitly accept Hobby's security/branding limitation or approve Pro. Stripe values come from [Stripe Australia pricing](https://stripe.com/au/pricing); the page says the domestic rate changes on 1 October 2026, so recheck immediately before activation. Domain and email equivalents use the actual current costs in the [Oryntela owner register](../00-company/oryntela-owner-register.md); they are existing commitments, not WO-054 spend.

AWS publishes no minimum S3 charge and currently identifies S3 Standard in Sydney at
USD 0.025/GB-month for the first 50 TiB ([AWS S3 pricing](https://aws.amazon.com/s3/pricing/),
[current AWS Sydney price example](https://aws.amazon.com/blogs/machine-learning/automated-reasoning-checks-rewriting-chatbot-reference-implementation/)).
Requests, transfer and the scheduled DigitalOcean job are additional variable costs.
The application backup command currently writes its encrypted bundle to a private
filesystem destination, so a reviewed scheduled upload/retention step is still
required; pricing a bucket does not create a working backup. Customer-data launch
remains blocked rather than hiding that implementation/target proof. A PostgreSQL HA
primary plus one standby changes database cost from USD 15 to USD 60 and total
baseline to USD 95/month (about AUD 132.61 at the reference rate).

## Current provider activation research

All links in this section were rechecked on 10 September 2026. No account, app,
project, key, API or trial was created.

- **OpenAI:** the implemented production candidate remains `gpt-5.6-terra`, currently
  USD 2/million input and USD 12/million output tokens
  ([official OpenAI model page](https://developers.openai.com/api/docs/models/gpt-5.6-terra)).
  Official OpenAI documentation recommends environment secrets, separate staging and
  production projects, restricted access and project spend/rate controls
  ([production practices](https://developers.openai.com/api/docs/guides/production-best-practices)).
  Standard Responses abuse-monitoring content may be retained up to 30 days; the
  Australian endpoint supports storage but not regional processing and requires
  approved retention controls ([data controls](https://developers.openai.com/api/docs/guides/your-data)).
  Keep it off for Core launch; if separately approved, retain the existing proposed
  AUD 50 monthly alert-and-stop amount. This is variable usage, not included in fixed
  infrastructure.
- **Microsoft:** register a web app as multitenant, verify the publisher domain, use a
  client credential and the existing exact redirect. Current delegated scopes are
  `openid`, `offline_access`, `User.Read`, `Mail.Send`, `Mail.Read` and
  `Calendars.ReadBasic`; `Mail.Read` is required for the implemented reply-content
  reconciliation. Microsoft documents the app-registration and multitenant process
  in its [identity-platform guide](https://learn.microsoft.com/en-us/graph/auth-register-app-v2)
  and [publisher-domain guide](https://learn.microsoft.com/en-us/entra/identity-platform/howto-configure-publisher-domain).
  No Oryntela Azure compute or mailbox is required; customers supply eligible
  Microsoft 365 licensing. Owner/admin MFA and tenant consent remain external gates.
- **Google:** use separate test/production Cloud projects, verified domains, Gmail and
  Calendar APIs and the exact redirect. The implementation requests `openid`,
  `email`, `profile`, `gmail.send`, `gmail.readonly` and
  `calendar.events.owned.readonly`; `gmail.readonly` is restricted. Google's current
  [restricted-scope verification guidance](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification)
  says a server that accesses restricted data must undergo annual Google-approved
  security assessment unless an enumerated exception applies. A public multitenant
  Oryntela SaaS does not fit the stated personal/testing/internal exemptions. Assessor
  price is not published and requires quotes; do not order it.
- **HubSpot:** create a public OAuth app and developer test account with Oryntela
  branding and exact HTTPS redirect. The current adapter requests OAuth plus company,
  contact, deal and meeting read/write, owner read, and company/contact/deal schema
  read scopes; do not broaden them. HubSpot's
  [OAuth quickstart](https://developers.hubspot.com/docs/apps/developer-platform/build-apps/authentication/oauth/oauth-quickstart-guide)
  requires the app/client configuration; public OAuth apps receive 110 requests per
  10 seconds per installed account excluding Search API calls under the current
  [usage limits](https://developers.hubspot.com/docs/developer-tooling/platform/usage-guidelines).
  Customer HubSpot entitlement is separate.
- **Salesforce:** new production configuration should use an External Client App;
  Salesforce says new Connected App creation is restricted from Spring '26 in the
  [current app guidance](https://developer.salesforce.com/docs/platform/mobile-sdk/guide/connected-apps.html).
  Request only `api`, `openid` and `refresh_token`. Use a free synthetic Developer
  Edition org for proof only. Customer edition, API access, integration user and
  limits remain customer-provided.
- **System email:** DigitalOcean App Platform blocks SMTP ports, so do not add direct
  Zoho SMTP to the containers. Existing Zoho remains the owner-operated support and
  general correspondence route; Clerk supplies identity messages when configured and
  Stripe supplies receipts only if live billing is later activated. Customer outreach
  continues through a customer's explicitly connected mailbox, never the system
  sender.

## Prospect recommendation

Apollo remains technically compatible with the existing adapter, but its [developer FAQ](https://docs.apollo.io/docs/developer-faqs) requires a custom contract to expose Apollo data to users who are not themselves Apollo users. Oryntela's shared provider model does exactly that. Apollo therefore remains off until Apollo grants the intended SaaS/data-sharing rights in writing and supplies a current quote. Public API credits alone do not establish commercial permission. Current [Apollo API pricing](https://docs.apollo.io/docs/api-pricing) and [rate-limit documentation](https://docs.apollo.io/reference/rate-limits) describe units and thresholds, not Oryntela's required licence price.

People Data Labs is the next diligence candidate, not a selected provider. It publishes 100 free records/month, Person plans from USD 98/month (350 credits at USD 0.28) and Company plans from USD 100/month (1,000 credits at USD 0.10), with one credit per successful enrichment or returned search profile ([PDL account/plans](https://docs.peopledatalabs.com/docs/create-an-account), [PDL pricing](https://support.peopledatalabs.com/hc/en-us/articles/25794271805211-Pricing-credits)). Its dataset reports 22,047,072 Australia-labelled records but warns the full dataset includes duplication ([PDL country aggregation](https://docs.peopledatalabs.com/docs/countries)). Oryntela would need a new adapter (outside feature freeze) and written SaaS redistribution, privacy/opt-out and Australian-use confirmation before selection. No PDL account was created.

## Exact-arithmetic Credit proposal

Production action prices cannot honestly be numerical until an approved provider contract supplies the landed cost of each action. The proposed policy is therefore an executable formula and pack catalogue for owner review, not active configuration:

- Target gross margin floor: 70.00% (`7000` basis points), not owner-approved.
- One Oryntela Credit face value: AUD 0.10 including whatever GST treatment the owner/accountant later approves; this value cannot publish before the GST decision.
- Proposed prepaid packs: 500 Credits for AUD 50; 1,250 for AUD 120; 3,000 for AUD 270. No expiry/refund terms are proposed as approved legal policy.
- For pack `p`, calculate exact ex-GST usable proceeds per Credit after Stripe fees. For provider action `a`, convert the worst-case contracted provider cost into AUD with the treasury rate fixed for the pricing review and add any non-refundable request fees. Set `actionCredits = ceiling(providerCostAud / (usableProceedsPerCredit × 0.30))`.
- Reserve the full `actionCredits` before execution; prohibit post-paid provider use. Re-price before the quote TTL expires when FX or provider pricing changes. Failed/no-match/refund behaviour must follow the provider contract and existing durable reservation rules.

Example only, not an Apollo price: if an action's exact landed provider cost were AUD 0.21 and usable proceeds were AUD 0.09 per Oryntela Credit, `ceiling(0.21 / (0.09 × 0.30)) = ceiling(7.777...) = 8 Credits`. The repository continues to reject production Credits, external Prospect execution and live Stripe. Owner approval requires a versioned provider contract/quote, GST decision, pack terms, action table and the 70% margin decision together.

## Fixed, variable and customer-provided separation

- Fixed recommended new-infrastructure baseline after approval: USD 50/month; known all-in fixed equivalent including current domain/email costs is about AUD 74.90/month before tax/FX. Database HA raises infrastructure to USD 95/month.
- Variable: independent backup storage/requests, platform overages, scheduled-job seconds, OpenAI, Stripe Payments/Billing fees, Prospect calls, foreign exchange and tax.
- Customer-provided: Microsoft 365, Google Workspace, HubSpot and Salesforce licences/API entitlements used by that customer.
- Optional: Clerk Pro/MFA, database HA, dedicated error reporting, Google/CASA assessment and any connector/provider not selected for V1.

No amount in this document authorises spend or activation.
