# ADR 0038: Separate unpromoted Prospect research from Company and customer Evidence

**Status:** Accepted

## Context

WO-026 needs to research companies before a seller decides they belong in the sales
workspace. Creating a canonical Company on every search would pollute Core and make
ambiguous or low-value candidates look qualified. Treating public findings as
customer Evidence would also overstate their authority. Direct page fetching would
introduce SSRF, hostile-content, copyright and provider-terms risk before a real
provider had been approved.

## Decision

Create a tenant-owned Prospect Research Target and immutable Research Runs separate
from Company, Contact, Opportunity and Evidence. Persist only bounded source
metadata, structured observations and validated citations. Use exactly four trust
states with deterministic authority rules.

Research does not create a Company. Add to Sales requires explicit confirmation,
locks the organisation/domain target and either links the deterministic existing
exact-domain Company or creates one Company. The link does not copy public research
into customer Evidence or mutate Methodology, Revenue Brain or Ask RevenueOS.

Implement a provider-neutral structured contract and deterministic no-network mock.
Do not implement a public-page fetcher or AI synthesis. Production using the mock
fails closed; provider selection is deferred until current official terms, cost,
licensing, attribution, retention and privacy posture are approved.

## Consequences

Sellers can research and discard early targets without filling Core with records.
Promotion is deliberate and duplicate-safe, while deleting research never silently
deletes a promoted Company. Public research remains inspectable but cannot be
mistaken for customer truth.

Real-world production coverage requires another provider decision and adapter. The
structured boundary is narrower than a generic browser but substantially reduces
security, legal and operating risk. A future fetcher or synthesis path requires a
new review and cannot be activated by flags alone.

## Alternatives

- **Create Company on search:** rejected because search interest is not qualification
  and ambiguous candidates would pollute Core.
- **Store research as customer Evidence:** rejected because public/provider context
  is not a customer statement or commitment.
- **Use a generic web crawler now:** rejected because the provider value did not
  justify SSRF, hostile-content, licensing and retention exposure.
- **Select or buy a provider during WO-026:** deferred because no approved no-cost
  commercial path was established and the work order prohibited purchasing.
- **Create a native Lead entity:** deferred; a Research Target is sufficient for the
  current early-interest lifecycle and avoids duplicating Company/Contact concepts.
