# Person discovery and research provider architecture

`ProspectResearchProvider` now exposes `discover_people(target, limit)` and `research_person(target, person, run_sequence)`. Inputs are backend-controlled snapshots; clients cannot pass provider query syntax, arbitrary domains or a global people query.

The provider returns typed candidates, sources, observations, buying-role hypotheses and contact points. Validation requires a supported provider identity and professional source, exact company relationship, public-safe URLs, bounded categories, cautious hypotheses, contact trust and expiry metadata. Raw provider JSON is never accepted by the frontend or stored.

The active adapter is `DeterministicMockProspectProvider`. Its Northstar fixtures provide Jane Smith, John Brown and Sarah Jones, including a later Jane employment-change version. These are synthetic `.example` records. Production configuration continues to fail closed because no person/contact provider has approved licensing, cost and privacy terms.

Provider absence or contact-data absence does not invalidate professional research. A future live adapter must reserve quotas atomically, enforce timeouts/retries/circuit breaking, use allow-listed HTTPS APIs, honour per-field storage/export/expiry terms and remain disabled in CI. Scraping or browser automation is not an adapter fallback.
