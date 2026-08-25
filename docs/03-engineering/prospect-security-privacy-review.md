# Prospect Account Research security and privacy review

## WO-027 extension

Person discovery remains subordinate to one researched company, uses the same
entitlement and trusted tenant context, and adds atomic people-discovery quotas.
Every new person/provenance table has forced RLS. Provider candidates, professional
claims, hypotheses and contact points pass source, trust, URL, freshness and
sensitive-content validation before persistence.

The live-provider status remains unavailable. No LinkedIn/private-social scraping,
personal contact harvesting, sensitive/personality inference, photos, bulk export or
outreach was added. See the
[Person Intelligence review](prospect-person-security-privacy-review.md).

**Status:** Passed for the implemented WO-026 boundary

## Threat findings and controls

| Risk                                                       | Current control                                                                                                                                   |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| SSRF, DNS rebinding and redirect attacks                   | No runtime fetcher; strict HTTPS/domain/DNS/redirect policy gates all stored URLs and any future adapter.                                         |
| Malicious HTML, script, MIME, downloads or oversized pages | No page-body retrieval, parser, script execution or download surface exists.                                                                      |
| Prompt injection                                           | No public content or research observation is sent to a model. Strict provider schemas and citation validation treat strings as data.              |
| Source spoofing or fabricated citation                     | Canonical URL/fingerprint dedupe; run-local source keys; trust-authority validation; composite tenant/run foreign keys.                           |
| Domain ambiguity or target poisoning                       | Bounded provider candidates require explicit user selection; candidate IDs must be returned by the provider; normalised-domain target uniqueness. |
| Cross-tenant access/promotion                              | Verified tenant context, repository predicates, composite foreign keys, forced RLS and tenant-local exact-domain lookup.                          |
| Entitlement bypass                                         | Global feature flag plus organisation entitlement at every service operation and worker execution; admin-only mutation.                           |
| Disabled/removed user                                      | Existing authentication/membership dependency fails closed; worker revalidates requester and entitlement.                                         |
| Denial of service and cost abuse                           | Bounded search/results, strict payload sizes, per-user/per-organisation daily quotas, concurrent-run cap, leases and bounded attempts.            |
| Sensitive-person profiling                                 | Company-focused schema; no emails, phones, personal dossiers, protected traits, contact discovery or LinkedIn scraping.                           |
| Copyright and provider terms                               | Metadata and concise derived observations only; no page mirror; no real provider selected or paid service activated.                              |
| Customer-truth contamination                               | Separate Prospect domain and explicit promotion link; no Evidence, Methodology, Revenue Brain, Ask, Contact or Opportunity mutation.              |

Logging is metadata only: organisation, actor, target/run identifiers, status,
counts and safe error codes. It excludes queries, company names/domains, objectives,
source URLs/excerpts, brief text, page content, credentials and raw payloads. No new
content telemetry was added.

Retention, export and deletion are covered by the private-beta maintenance path.
Source metadata remains subject to the organisation policy. Research availability
and accuracy may change and the UI communicates partial and unknown results.

## Residual and deferred risk

Production value requires an approved external provider. Provider licensing,
regional/privacy terms, source attribution, commercial use, retention and rate
limits must be reviewed against current official documentation at selection time.
A public fetcher or AI synthesis is a separate security change and cannot be enabled
by configuration alone. Deep person research, enrichment, scoring, monitoring and
outreach remain outside WO-026.
