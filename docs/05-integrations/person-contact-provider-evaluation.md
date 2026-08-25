# Person and contact provider evaluation

## WO-027 decision

RevenueOS remains provider-abstraction/mock-only. No free or paid production account, credit bundle or trial was activated.

| Candidate | Useful capability | Review finding | Decision |
| --- | --- | --- | --- |
| Apollo | People enrichment/search and business contact data | [Official pricing documentation](https://docs.apollo.io/docs/api-pricing) describes credit consumption per person and variable credit use. Cost, redistribution and retention were not sufficiently bounded for this work order. | Not configured |
| Hunter | Domain/contact discovery and email verification | [Official API documentation](https://hunter.io/api-documentation/) distinguishes discovery, reveal and verification operations. Inference/verification semantics and contact storage terms need a dedicated review. | Not configured |
| People Data Labs | Person enrichment/search | [Official person pricing](https://www.peopledatalabs.com/pricing/person) limits free testing and obfuscates data; the [subscription terms](https://privacy.peopledatalabs.com/policies?name=services-subscription-agreement) require commercial/licensing review. | Not configured |
| Crunchbase | Company/person business data | [Official API guidance](https://data.crunchbase.com/docs/using-the-api) places API access behind commercial products. It is not a no-cost person/contact foundation. | Not configured |

The deterministic mock adapter proves bounded company-scoped discovery, professional research, contact trust, missing-contact success, refresh/departure and duplicate-safe promotion. Any production choice must separately approve identity provenance, source access, verification meanings, regional coverage, request/record cost, storage/refresh/deletion, export/redistribution, auditability and DPA/security terms.

Scraping LinkedIn or private social networks is not an acceptable cost workaround.
