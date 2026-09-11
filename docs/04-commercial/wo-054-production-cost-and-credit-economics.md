# WO-054 production cost and Credit economics

- Research date: 11 September 2026 (Australia/Sydney)
- Currency: provider prices are quoted in their source currency; no tax treatment is assumed
- Approval status: proposal only; no purchase, subscription, price or Credit policy is active

## Minimum realistic paid/customer-data baseline

The recommended new-production baseline is **USD 120/month** before tax and variable usage: three USD 10 App Platform 1 GiB components, a USD 60 two-node highly available managed PostgreSQL cluster, USD 5 Spaces and USD 25 month-to-month Clerk Pro. The [DigitalOcean App Platform price list](https://docs.digitalocean.com/products/app-platform/details/pricing/), [PostgreSQL price list](https://docs.digitalocean.com/products/databases/postgresql/details/pricing/), [Spaces price list](https://docs.digitalocean.com/products/spaces/details/pricing/) and [Clerk price list](https://clerk.com/pricing) were verified on the research date. DigitalOcean expressly recommends its single-node database for preliminary development/testing; USD 15 is therefore not used as a paid-customer production baseline.

The latest Reserve Bank of Australia daily observation available during research was 1 AUD = USD 0.7172 on 11 September 2026 ([RBA exchange rates](https://www.rba.gov.au/statistics/frequency/exchange-rates.html)). At that reference rate, USD 120 / 0.7172 = approximately AUD 167.32. Existing known annual domain/email costs add AUD 5.1083333333/month equivalent, producing approximately **AUD 172.43/month** before tax, FX movement and variable backup usage. Clerk Pro billed annually would reduce the USD equivalent by USD 5/month but creates an annual commitment; the month-to-month figure is the conservative approval baseline. This is a planning conversion, not a bank quote.

| Category | Provider | Required | Allowance / baseline | Fixed monthly | Usage component | Card / auto-renew | Owner action |
| --- | --- | --- | --- | ---: | --- | --- | --- |
| Web | DigitalOcean App Platform, Sydney | yes | 1 GiB fixed service | USD 10 | excess transfer USD 0.02/GiB | payment method; recurring | approve purchase |
| API | DigitalOcean App Platform, Sydney | yes | 1 GiB fixed service | USD 10 | excess transfer USD 0.02/GiB | payment method; recurring | approve purchase |
| Worker | DigitalOcean App Platform, Sydney | yes | 1 GiB fixed worker | USD 10 | transfer/resize if applicable | payment method; recurring | approve purchase |
| Scheduled backup job | DigitalOcean App Platform, Sydney | yes before customer data | 1 GiB fixed job, daily | USD 0 continuously allocated | billed only while running, one-minute minimum; roughly USD 0.007–0.069/month at 1–10 minutes/day using the USD 10 continuous-plan equivalent | covered by DigitalOcean payment method | approve variable cap and prove observed duration |
| PostgreSQL | DigitalOcean managed PostgreSQL, Sydney | yes | 2 GiB primary plus matching standby; managed backups/PITR | USD 60 | transfer/resize if applicable | payment method; recurring | approve HA purchase; create admin/runtime roles |
| Object storage | DigitalOcean Spaces, Sydney | yes | 250 GiB and 1 TiB outbound | USD 5 | USD 0.02/GiB storage, USD 0.01/GiB outbound above allowance | payment method; recurring | approve purchase and separate backup destination |
| Independent backup | AWS S3 Standard, Sydney (`ap-southeast-2`) | yes before customer data | no minimum charge; daily encrypted logical bundle; 14-day lifecycle | USD 0 fixed | USD 0.025/GB-month for the first 50 TB; USD 0.0055/1,000 PUT/COPY/POST/LIST; USD 0.0044/10,000 GET/other; transfer and scheduled-job seconds extra. At a 1–10 GB average retained footprint and about 30 uploads/month, storage plus upload requests is about USD 0.03–0.26/month before transfer/tax | payment method; ongoing usage billing | approve account/bucket/lifecycle and run named restore proof |
| Monitoring | App Platform/DB metrics, probes and email alerts | yes | baseline included | USD 0 incremental | none at launch | no separate card | set Kevin's controlled operational destination |
| Auth | Clerk Pro | yes | production organisation identity, MFA/passkeys and seven-day logs | USD 25 month-to-month; USD 20/month billed annually | upgrade/overages beyond allowance | payment method for Pro; recurring | approve Pro and create production instance/domain |
| External AI | OpenAI API | required for the advertised paid Sales Brain profile; synthetic/no-AI launch can disable | no free allowance relied upon | USD 0 | `gpt-5.6-terra`: USD 2/million input and USD 12/million output tokens | billing method and usage-based charges | approve data flow, project/key and stop amount separately |
| Stripe | Stripe standard + Billing PAYG | required for paid launch unless a separately authorised manual-subscription ledger is built | no setup/monthly standard payment fee | AUD 0 | domestic cards 1.7% + AUD 0.30; international 3.5% + AUD 0.30; +2% FX; Billing 0.7% of Billing volume | bank/business verification for live; no fixed PAYG commitment | authorise live implementation and activation or manual-ledger engineering |
| Prospect | none approved | can launch disabled | no provider call | 0 | unknown until commercial licence | likely contract/card | obtain redistribution/SaaS rights and quote |
| Microsoft | Entra/Graph | can launch disabled | standard APIs generally included within customer licence thresholds | USD 0 Oryntela baseline | customer Microsoft 365 licence; throttling applies | no Oryntela mailbox purchase authorised | owner/admin registers multitenant app |
| Google | Google OAuth/APIs | can launch disabled | API use has no stated licence fee | USD 0 Oryntela baseline | customer Workspace licence; external security assessor quote | assessor is paid/recurring annual review | owner starts verification only after legal URLs |
| HubSpot | developer app | can launch disabled | developer test account available | USD 0 Oryntela baseline | customer account/API entitlement | no new Oryntela paid licence required for sandbox | owner creates public OAuth app/test account |
| Salesforce | Developer Edition + External Client App | can launch disabled | synthetic dev org available | USD 0 Oryntela baseline | customer's edition/API access/integration user | no new Oryntela paid licence required for dev test | owner creates dev org/app |
| Domain/DNS | existing VentraIP | yes | owned `.com.au` and `.com` | AUD 0 incremental; current annual-cost equivalent AUD 2.9083333333/month | future registrar renewal | `.com` auto-renew off; `.com.au` not recorded here | approve exact records after target exists |
| System email | existing Zoho addresses + Clerk/Stripe hosted service emails | yes | one Mail Lite user and three approved identities | AUD 0 incremental; existing AUD 26.40/year = AUD 2.20/month equivalent | existing plan only | existing auto-renew remains enabled | no sender change; verify after DNS cutover |
| Error reporting | no dedicated provider | optional | platform logs/probes only | USD 0 | a privacy-reviewed provider is optional | none created | reassess after measured need |
| Google security assessment | Google-approved assessor | only if Google restricted scopes activate | annual CASA assessment likely required | quote unavailable | negotiated assessor fee | paid external engagement | obtain quotes; do not order |

Clerk pricing and feature boundaries come from [Clerk pricing](https://clerk.com/pricing). Hobby has no card requirement but lacks MFA/passkeys and retains only one day of logs; it is not approved for paid/customer-data production. Stripe values come from [Stripe Australia pricing](https://stripe.com/au/pricing); the page says the domestic rate changes on 1 October 2026, so recheck immediately before activation. Domain and email equivalents use the actual current costs in the [Oryntela owner register](../00-company/oryntela-owner-register.md); they are existing commitments, not WO-054 spend.

AWS publishes no minimum S3 charge and currently identifies S3 Standard in Sydney at
USD 0.025/GB-month for the first 50 TB ([AWS S3 pricing](https://aws.amazon.com/s3/pricing/),
[current AWS Sydney price file](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/ap-southeast-2/index.json)).
Requests, transfer and the scheduled DigitalOcean job are additional variable costs.
The repository now includes a daily scheduled job that streams an encrypted database
and source-object bundle to independent S3, verifies uploaded size/SHA metadata and
publishes its manifest last. Pricing and code still do not create an account, bucket,
versioning/lifecycle policy, failure alert or successful named-cloud restore. Those
external proofs remain customer-data blockers.

## Current provider activation research

All links in this section were rechecked on 11 September 2026. No account, app,
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
  A synthetic/no-AI profile can keep it off, but the advertised paid Sales Brain
  proposition is not commercially credible without it. If separately approved, retain the existing proposed
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

Example only, not an Apollo price: if an action's exact landed provider cost were AUD 0.21 and usable proceeds were AUD 0.09 per Oryntela Credit, `ceiling(0.21 / (0.09 × 0.30)) = ceiling(7.777...) = 8 Credits`. The repository continues to reject production Credits and external Prospect execution. Live Stripe engineering is production-capable but remains fail-closed until its separate account, secret, Price, preflight and activation gates pass. Owner approval requires a versioned provider contract/quote, GST decision, pack terms, action table and the 70% margin decision together.

## Fixed, variable and customer-provided separation

- Fixed recommended paid/customer-data baseline after approval: USD 120/month month-to-month; known all-in fixed equivalent including current domain/email costs is about AUD 172.43/month before tax/FX.
- Variable: independent backup storage/requests, platform overages, scheduled-job seconds, OpenAI, Stripe Payments/Billing fees, Prospect calls, foreign exchange and tax.
- Customer-provided: Microsoft 365, Google Workspace, HubSpot and Salesforce licences/API entitlements used by that customer.
- Optional/deferred: dedicated error reporting, Google/CASA assessment and any connector/provider not selected for V1. Clerk Pro and database HA are not optional for paid/customer-data production.

At the reference rate and before tax/FX/variable usage, one AUD 200 Core subscription leaves about AUD 27.57 after the known fixed platform/domain/email amount. If a future domestic Stripe payment and Billing PAYG both apply at the researched rates, their illustrative combined fee is AUD 5.10 and the remainder is about AUD 22.47. One AUD 350 Growth subscription leaves about AUD 168.87 on the same assumptions. These are contribution examples, not profit forecasts: owner labour, advice, tax, backup, AI and other variable costs remain excluded. The production-capable Stripe adapter still cannot collect either subscription until the live account, exact Prices, webhook, portal, mode-matched secrets and production preflight are configured and approved; the operator commercial-state commands are not a substitute for cleared-funds evidence.

No amount in this document authorises spend or activation.
