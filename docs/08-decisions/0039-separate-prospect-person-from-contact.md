# ADR 0039: Separate Prospect Person research from canonical Contact

## Context

WO-027 needs professional public research before a seller has decided to add someone to the sales system. Reusing Contact would silently create canonical records, weaken duplicate handling and risk mixing public research with customer truth.

## Decision

Introduce tenant-owned `ProspectPerson` beneath a company `ProspectResearchTarget`. Reuse versioned Prospect runs/sources/observations with an optional person target. Crossing into Core requires explicit, duplicate-reviewed Contact promotion.

Prospect Person refresh and deletion never silently mutate or delete a promoted Contact. Promotion does not create Opportunities, stakeholders, Methodology facts, Evidence, Revenue Brain data or outreach.

## Alternatives

- **Create Contacts during discovery:** rejected because discovery is research, not seller intent.
- **Store people as observations only:** rejected because identity, versioning, roles, contact provenance and promotion require stable relationships.
- **Build a global people index:** rejected as unnecessary and high-risk.

## Consequences

The model adds a clear lifecycle and several tenant tables, but keeps trust and deletion semantics explainable. Future recruitment/customer-success reuse must make an explicit domain decision rather than treating Prospect Person as a universal person record.
