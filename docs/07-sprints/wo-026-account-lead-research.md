# WO-026 — Account & Lead Research

**Status:** Implemented on `feature/epic-12-wo-026-account-lead-research`; draft
PR required, not merged.

## Outcome

WO-026 adds a trustworthy, minimum lovable Prospect workflow:

> Find → choose company → Research → verify sources → understand why it may matter
> → Add to Sales

Prospect is a separately entitled module. The implementation uses deterministic
synthetic company research and the existing PostgreSQL worker. It introduces no
paid or real external provider traffic, no arbitrary page fetcher and no new queue
infrastructure. Production fails closed until a real adapter is separately approved.

## Delivered

- Migration `0035_prospect_research` with module entitlement, usage counters,
  Research Targets, immutable runs, source metadata, structured observations,
  citation links, Company domain lookup, composite tenancy and forced RLS.
- Provider-neutral strict contracts and a no-network Northstar/Harbourline mock
  covering ambiguity, all four trust states, partial results and refresh changes.
- Entitled name/domain search, explicit company selection, recent research and
  asynchronous persisted briefs.
- Exact Verified/provider/inference/unknown validation, bounded canonical source
  metadata and run-local citation enforcement.
- Idempotent enqueue, fresh-result reuse, row-locked single active run, worker lease,
  bounded retry and prior-result preservation after failed refresh.
- Concise desktop/mobile Find and Account Research Brief with source disclosure,
  history/change comparison and safe external links.
- Explicit Add to Sales confirmation with deterministic exact-domain linking and no
  automatic Opportunity or Contact creation.
- Separately labelled Public research link on the Company page, with no customer
  Evidence, Methodology, Revenue Brain or Ask RevenueOS mutation.
- Private-beta quotas, retention, export schema v16, target/organisation deletion,
  admin control and metadata-only logs.

## Provider and security decision

The smallest safe strategy is a deterministic structured adapter with no public
fetch. A production provider was deferred because cost, licensing, attribution,
retention and regional/privacy approval remain unresolved. No paid service was
activated. URL policy nevertheless rejects non-HTTPS, credentials, non-default
ports, Unicode hosts, IP literals, local/internal hosts, non-global DNS results,
redirect loops and excessive redirects. No LinkedIn or search-engine scraping was
added. Public content is never executed or sent to a model.

## Product boundaries

Research Target is the WO-026 early lead concept and remains separate from Company
until explicit promotion. Research is public context, never customer-direct
Evidence. There is no named-person dossier, contact enrichment, personal email or
phone discovery, ICP/territory/bulk list, predictive fit/intent score, monitoring,
outreach, sequence, campaign or autonomous prospecting. WO-027 owns deep
decision-maker research and WO-028 owns ICP/territory/bulk discovery.

## Automated evidence

Backend tests cover entitlement, membership, search and ambiguity, URL/DNS/redirect
security, quotas, RLS, worker lifecycle, strict trust/citations, partial results,
refresh comparison, promotion concurrency/duplicates, public/customer boundary,
retention, export and migration cycles. Web component and Playwright tests cover
empty/search/progress/completed/source/promotion, exact-domain attach, partial,
non-entitled and mobile journeys. Final command totals are recorded in the draft
PR after the complete gate.

## Visual evidence

- [Desktop search results](assets/wo-026-search-results-desktop.png)
- [Desktop research progress](assets/wo-026-research-progress-desktop.png)
- [Desktop completed brief](assets/wo-026-research-brief-desktop.png)
- [Desktop source disclosure](assets/wo-026-source-disclosure-desktop.png)
- [Desktop refresh changes](assets/wo-026-refresh-changes-desktop.png)
- [Desktop Add to Sales confirmation](assets/wo-026-promotion-confirmation-desktop.png)
- [Desktop partial research](assets/wo-026-partial-research-desktop.png)
- [Desktop failed research](assets/wo-026-failed-research-desktop.png)
- [Mobile Find](assets/wo-026-find-mobile.png)
- [Mobile research brief](assets/wo-026-research-brief-mobile.png)

## Validation

The complete repository gate passed on 25 August 2026. Web validation includes
45 Vitest files with 167 tests and 37 Playwright journeys. API validation includes
876 passing tests with four intentional skips; the focused Prospect module has 41
passing tests. Alembic upgraded a PostgreSQL schema from `0034_crm_sync` to
`0035_prospect_research` and reported no new upgrade operations. Both web and API
production builds completed successfully.

## Known limitations

Research is synthetic/mock-backed and incomplete by design; production provider
activation remains deployment work. Source availability can change and provider
data can differ from primary sources. There is no real page fetching, AI synthesis,
contact research, LinkedIn scraping, scoring, outreach or trigger monitoring.
