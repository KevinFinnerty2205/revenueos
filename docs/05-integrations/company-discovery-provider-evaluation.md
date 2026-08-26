# Company discovery provider evaluation

- **Decision:** deterministic mock only for WO-028
- **Reviewed:** 26 August 2026 from official provider documentation

## Required contract

A future provider must support licensed organisation discovery by bounded industry,
geography and size criteria; stable company identity/domain; explicit unknown values;
field provenance/freshness; deletion/export obligations; rate and cost controls; and
production terms permitting the intended storage and display. It must not require
LinkedIn scraping or permit sensitive-trait targeting.

## Options reviewed

- [Apollo Organisation Search](https://docs.apollo.io/reference/organization-search)
  documents organisation filters including location, headcount and revenue. Production
  approval would still require plan, licensing, field-level provenance, retention and
  unit-economics confirmation.
- [People Data Labs Company Search](https://docs.peopledatalabs.com/docs/company-search-api)
  documents full-dataset company filtering, paged result limits, rate limits and
  per-record credit use. A paid-plan and redistribution/storage review is required.
- [Crunchbase API documentation](https://data.crunchbase.com/docs/using-the-api)
  describes organisation search/filter APIs whose available fields and limits depend
  on product access. Exact coverage, cost and storage rights require commercial review.

No provider was activated, no trial credit or paid service was consumed and no real
provider request runs in tests or demo data. A live adapter needs a separate decision
record, legal/privacy/security approval, cost guardrails, contract tests and a real
sandbox verification before it may be described as implemented.

## Current adapter

`DeterministicMockDiscoveryProvider` exposes an honest capability set and returns six
synthetic organisations. RevenueOS—not the provider—applies exclusions, missing-data
policy, priority labels and relationship/whitespace reconciliation. The adapter is
clearly labelled synthetic and fails closed in production.
