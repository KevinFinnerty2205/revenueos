# Prospect research provider boundary

## WO-027 person/contact status

The provider protocol now has typed company-scoped people discovery and selected
person research operations. No production adapter is configured. The deterministic
mock supplies synthetic professional sources, role hypotheses, optional expiring
business contact points and an employment-change refresh fixture. Provider syntax and
raw responses never cross the API boundary.

See the [provider evaluation](person-contact-provider-evaluation.md) and
[licensing/storage decision](person-provider-licensing-storage-decision.md). Scraping
is not an allowed fallback.

**Status:** Adapter-ready; real provider deferred

`ProspectResearchProvider` is the only WO-026 research integration boundary. It
supports bounded company search, exact candidate lookup and one structured research
operation. Its input is a small target snapshot. Its output is a strict set of
source metadata and observations; it cannot return arbitrary provider payloads,
credentials, HTML, executable content or instructions.

Provider-specific identifiers are stored only as bounded references. Core domain
contracts expose RevenueOS candidates, sources, observations and trust states.
Every result is revalidated for URL safety, source uniqueness, citation ownership
and trust authority before it enters tenant persistence.

The implemented `mock` adapter contains synthetic `.example` companies and never
uses the network. It is the local/CI default and production rejects it. No paid
subscription, trial credits or external credentials were activated.

## Deferred production decision

No real provider was selected because WO-026 had no already-approved, no-cost
provider path with confirmed commercial use, licensing, attribution, retention,
rate-limit and regional/privacy terms. Production enablement must evaluate current
official documentation at that time and record:

- discovery/search coverage and identity quality;
- pricing/free-tier limits without purchasing during implementation;
- data licensing, commercial usage and source-link obligations;
- retention and deletion obligations;
- regional processing and privacy posture;
- quotas, rate limits, timeouts and outage behaviour; and
- whether supplied snippets remove the need for direct public-page fetching.

A selected adapter must use the existing secret/configuration boundary, remain off
by default, fail closed when incomplete and have contract tests with no real CI
traffic. A direct page fetcher, OpenAI synthesis, LinkedIn access or search-engine
HTML scraping is not part of this integration.
