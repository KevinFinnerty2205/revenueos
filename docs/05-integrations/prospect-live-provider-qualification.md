# Prospect live-provider qualification

- **Reviewed:** 6 September 2026
- **Engineering candidate:** Apollo
- **Production selection:** unresolved pending a written external-product/data licence and quote
- **Status:** production-capable adapter; **not activated**
- **Spend:** AUD $0

## Recommendation

Use Apollo as the first technical provider candidate only if Apollo supplies a written
agreement that expressly permits Oryntela to display and retain the selected data for
its customers. Apollo has the best fit among the evaluated options for bounded company
enrichment, zero-Credit people discovery, professional person enrichment, business
email metadata, Australian coverage claims, usage visibility and mature API limits.

This is conditional, not legal or commercial approval. Apollo's public pricing page
says standard plans are for internal business use and cannot power an external product,
share data with customers or resell Apollo data. Its API terms also require Apollo's
approval before integration with a product or service. Oryntela therefore needs a
separate custom agreement. No standard Apollo plan is suitable for production Oryntela
use based on the reviewed public terms.

If Apollo will not provide acceptable product-use, storage, export, deletion and
downstream-display rights at sustainable economics, qualify People Data Labs next.

## Capability and boundary

| Need | Apollo finding | WO-050 treatment |
| --- | --- | --- |
| API access | API key; most endpoints available to accounts; affected free endpoints require an account registered with a work email | No account created and no terms accepted by Codex |
| Company discovery | Organisation search; 1 Apollo credit per page, up to 100 results | Not called; known domains are prepared locally to avoid hidden spend |
| Company research | Organisation enrichment by domain/name/site; 1 Apollo credit per organisation | Implemented behind confirmed Oryntela Credit operation |
| People discovery | People API Search; 0 Apollo credits; no email/phone returned; organisation-domain search may include current or previous employment and currently returns an obfuscated surname | Implemented with documented query parameters, bounded to the existing limit, current-organisation filtering and ambiguous staging identity |
| Person research | People enrichment/match; 1–9 Apollo credits depending on returned data | Implemented with personal-email and phone reveal explicitly off; requested ID and current-company domain must match before identity is accepted |
| Business email | May be returned by person enrichment; provider status is not Oryntela verification | Stored only when it matches the company domain, labelled provider-supplied |
| Phone/mobile | Mobile adds 8 credits in base enrichment; waterfall may be materially higher | Not requested, mapped or activated |
| Recent professional posts | No approved API capability established | Unavailable; no LinkedIn scraping or credential use |
| Australia | Apollo advertises Australian business contacts and state/industry/company-size filtering | Plausible coverage, but quality and lawful-use validation require an authorised sample |
| Sources | Structured records do not establish independent public proof | Apollo attribution shown; no source URL is invented from provider IDs |
| Health | `auth/health` exists and account usage endpoints expose limits | No paid health request; readiness is configuration/gate based |

The adapter persists only an allow-list of business fields. Full payloads, personal
emails, phone arrays, credentials and raw provider errors are not stored or logged.
Provider IDs remain provenance/deduplication references, never canonical identities.
Shared generic inboxes are not treated as person contact points. Discovery identity is
staging data until a domain-bound person match supplies the full identity; neither
stage overwrites a canonical Contact without deliberate promotion/review.

## Licensing, privacy and retention

Before activation, the written agreement and professional privacy review must resolve:

- product integration and customer display rights;
- data storage, customer export and post-termination use rights;
- the removal-request feed and deletion versus independently documented legal basis;
- whether Oryntela may transform provider data into bounded, non-training inference;
- Australian Privacy Act, Spam Act, cross-border disclosure and direct-marketing duties;
- the current DPA, subprocessor list, processing locations and security evidence;
- retention periods for company, person, email and derived observations;
- use by Oryntela customers and any prohibition on onward sharing.

Apollo's DPA names Apollo as processor for Customer Personal Data, provides a current
subprocessor mechanism with notice, and requires return/deletion on termination subject
to legal retention. Its 2026 terms impose operational handling for removal requests in
downstream systems. Those documents do not establish Australian residency and do not
by themselves clear Oryntela's use of Apollo's own business-contact database.

## Alternative considered

People Data Labs (PDL) exposes person/company enrich/search APIs and synthetic sandbox
endpoints that mirror production without consuming credits. Its published self-serve
tiers are $0 for up to 100 monthly records, Person Pro from USD $98/month for 350+
records and Company Pro from USD $100/month for 1,000+ records. PDL documents charging
successful enrichments once and search per returned profile. Its published services
agreement expressly contemplates displaying PDL data to a customer's own end users,
which is more promising for a SaaS product than Apollo's standard terms.

PDL was not selected for this adapter because combined company/person/contact field
coverage, field-bundle cost, Australian quality, retention/export interpretation and
the precise Oryntela multi-tenant end-user licence still need provider confirmation.
Its free account also requires owner signup and acceptance of terms. It remains the
preferred fallback qualification, not an activated provider.

## Official sources reviewed

- [Apollo API overview](https://docs.apollo.io/reference/apollo-api)
- [Apollo API pricing and Credits](https://docs.apollo.io/docs/api-pricing)
- [Apollo organisation search](https://docs.apollo.io/reference/organization-search)
- [Apollo organisation enrichment](https://docs.apollo.io/reference/organization-enrichment)
- [Apollo People API Search](https://docs.apollo.io/reference/people-api-search)
- [Apollo People Search filters](https://docs.apollo.io/docs/find-people-using-filters)
- [Apollo people enrichment guide](https://docs.apollo.io/docs/enrich-people-data)
- [Apollo rate limits](https://docs.apollo.io/reference/rate-limits)
- [Apollo pricing/product-use restriction](https://www.apollo.io/pricing)
- [Apollo API terms](https://www.apollo.io/terms/api)
- [Apollo Terms of Service](https://www.apollo.io/terms)
- [Apollo DPA](https://www.apollo.io/dpa)
- [Apollo Trust Center](https://trust.apollo.io/)
- [Apollo Australian data page](https://www.apollo.io/email/email-database-lists-australia)
- [Apollo free trial](https://knowledge.apollo.io/hc/en-us/articles/5288168088205-Access-a-Free-Trial-of-Apollo)
- [People Data Labs account, plans and Credits](https://docs.peopledatalabs.com/docs/create-an-account)
- [People Data Labs sandbox APIs](https://docs.peopledatalabs.com/docs/sandbox-apis)
- [People Data Labs Services Subscription Agreement](https://privacy.peopledatalabs.com/policies?name=services-subscription-agreement)

Provider documentation, prices and terms can change. Re-check these sources and retain
the signed order/agreement reference before any production configuration is approved.
