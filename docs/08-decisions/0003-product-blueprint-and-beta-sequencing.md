# ADR 0003 — product blueprint and beta sequencing

- **Status:** Accepted
- **Date:** 2026-07-17
- **Scope:** Product direction through Sales Brain private beta

## Context

Sprints 1 and 2 established the modular-monolith foundation and tenant-owned company, contact, opportunity and task records. Before introducing meetings, ingestion, AI or integrations, the team needs one explicit product contract connecting customer outcomes, trust boundaries, conceptual domains and a realistically sequenced path to a design-partner pilot and private beta.

Without that contract, individual implementation sprints could:

- reproduce a CRM interface rather than solve relationship-workflow problems;
- choose provider or AI architecture before validating the narrow meeting loop;
- confuse generated proposals with executed actions;
- build broad capture before consent, review and deletion are trustworthy; or
- pre-build Recruitment/Customer Success abstractions that Sales Brain does not need.

## Decision

### Sales Brain comes first

Sales Brain is the only product through private beta. It validates the shared platform's hardest reusable capabilities—authorised conversation ingestion, source-backed intelligence, relationship memory, approvals, integrations and tenant isolation—inside one coherent workflow and one ICP.

Recruitment Brain and Customer Success Brain remain strategic future directions. They do not add beta personas, schemas or provider requirements until product-specific discovery and safety/privacy work are complete.

### RevenueOS does not become a CRM

Salesforce or HubSpot remains authoritative for mapped CRM fields. RevenueOS owns conversation-derived evidence, reviewable relationship memory, proposed work, approval and cross-system execution state.

The interface prioritises recent change, context, commitments, next actions and exceptions. Core business entities exist to anchor relationship intelligence; they are not a commitment to reproduce broad CRM administration, forecasting or engagement automation.

### The beta loop is narrow and end to end

The first-five-company design-partner pilot must complete:

`ingest → match → review → source-backed summary/next steps → follow-up and CRM proposals → human approval → relationship memory → next-meeting preparation`

Manual upload or transcript paste remains a supported fallback. The pilot selects one productivity ecosystem and one CRM from partner overlap rather than completing every adapter first.

### Human approval is mandatory

During beta:

- no email or other external communication is sent silently;
- no CRM field is written silently;
- accountable AI-suggested tasks require acceptance; and
- approval is bound to an exact action version, destination, actor and expiry.

Model confidence never substitutes for authorisation. Execution success requires a provider receipt or reconciliation, not a mock, log entry or accepted queue item.

### Meeting intelligence precedes broad integrations

The product first proves deliberate manual ingestion, transcript/matching review and source-backed intelligence. This establishes the core value and provider-neutral contracts before calendar, mail, meeting-platform and CRM adapters add operational risk.

Integration order is:

1. one selected calendar and mail ecosystem;
2. one selected CRM read path, then approved writes;
3. pilot validation;
4. the second productivity ecosystem and second CRM; and
5. priority meeting-platform import and later provider breadth.

### Meeting Domain Foundation is the next sprint

Sprint 3 should add only the non-AI meeting/participant aggregate, tenant protections, API and truthful UI. It must not add file ingestion, recording, transcript content, AI or provider connections.

This gives every later workflow a stable root without prematurely deciding transcription, object storage or integration behaviour.

### Mobile and ambient capture are deferred or constrained

Responsive web is the beta client. Native mobile is later and is not required to prove the Sales Brain loop.

In-person or phone capture is never ambient or covert. Any future design requires explicit arming/start, a persistent visible state, pause/stop/delete controls, consent evidence and region/customer policy review. Background recording must never be silently enabled.

## Alternatives considered

- **Build broad integrations before meeting intelligence:** rejected because it spends provider/security effort before the core reviewed output has demonstrated value.
- **Use CRM as the primary UI and data model:** rejected because it duplicates the system of record and weakens the memory/workflow differentiation.
- **Auto-apply high-confidence actions:** rejected for beta because confidence is not permission and provider/model errors can have customer-facing consequences.
- **Require native mobile for first pilot:** rejected because responsive web plus deliberate source upload can validate the narrow loop with less platform and consent complexity.
- **Build all Google, Microsoft, meeting and CRM adapters before pilot:** rejected because five well-selected partners can validate value with one ecosystem and CRM.
- **Generalise immediately for Recruitment and Customer Success:** rejected because premature shared abstractions risk encoding unvalidated terminology, policy and workflows.

## Consequences

### Positive

- Product, design, AI, domain, integration and roadmap documents share one beta boundary.
- Manual ingestion can validate value before provider breadth.
- Human trust and provider execution state are designed into workflows.
- The existing modular monolith/provider-port architecture remains suitable.
- The next sprint is small, demonstrable and independent of AI/provider selection.

### Trade-offs

- Time to broad integration availability is longer.
- The first five companies must be selected partly for stack compatibility.
- Approval adds interaction cost that must be made fast and measured.
- Manual ingestion remains necessary during early rollout.
- Relationship memory and assistant arrive after review/evidence foundations rather than as early demonstrations.
- Private beta timing depends on production identity, privacy/security gates and real provider sandbox access.

### Risks

- Pilot value may be too low if manual ingestion or approval feels burdensome.
- Provider API/edition restrictions may change the integration order.
- Source-backed output quality may not meet the trust threshold.
- A coarse role model could expose more transcript context than customers expect.
- Retention, recording law and regional requirements may constrain capture or launch geography.

These risks are addressed through explicit roadmap gates, first-five-company selection, evaluation and a production-readiness checklist.

## Follow-up triggers

Create or update decision records when:

- Sprint 3 fixes its exact meeting lifecycle/schema;
- a production role/permission matrix is approved;
- transcription/model/storage providers and regions are selected;
- an integration gains read/write capabilities or source-of-truth rules;
- approval policy is proposed to become automated;
- embeddings/search infrastructure is justified;
- billing packaging is decided; or
- Recruitment Brain, Customer Success Brain, native mobile or in-person capture enters discovery.

## Related documents

- [Master product blueprint](../01-product/master-product-blueprint.md)
- [MVP and beta scope](../06-roadmap/mvp-and-beta-scope.md)
- [Product roadmap to beta](../06-roadmap/product-roadmap-to-beta.md)
- [Privacy, security and trust model](../03-engineering/privacy-security-and-trust-model.md)
