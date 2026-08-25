# Person provider licensing and storage decision

## Status

No production person, professional-research or contact-data provider is approved or configured in WO-027. The runtime supports only clearly labelled deterministic synthetic fixtures.

## Storage contract for a future adapter

An adapter must map provider output into RevenueOS-owned typed fields and discard the raw response. Each contact field must declare source, trust/verification semantics, observation time, contractual expiry and export permission. Provider identifiers stay server-side and are omitted from authorised person exports unless a future contract explicitly permits them.

The adapter must document permitted source acquisition, caching, refresh frequency, deletion obligations, redistribution/export, data-subject handling, geographic restrictions, sub-processors, DPA, breach duties, service limits and unit cost. RevenueOS retention must choose the shorter of organisation policy and provider permission.

## Activation gate

Production configuration remains fail-closed until Product, Security/Privacy and Engineering approve the provider assessment, budget and operational runbook. Secrets must live in the environment secret manager, provider calls must be disabled in CI, quotas must reserve before chargeable work, and logs must remain metadata-only.

No paid service was activated and no real provider request is part of standard automated tests.
