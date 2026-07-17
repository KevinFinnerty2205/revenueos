# MVP and beta scope

This document turns “MVP” and “beta” into release gates. It does not claim that future capabilities exist.

## Scope ladder

| Stage | Users/data | Product outcome | Required system qualities | Explicit exclusions |
| --- | --- | --- | --- | --- |
| Technical prototype | Internal team; synthetic data only | Prove one risky component or contract in isolation | Disposable, clearly labelled, no production connection claims | Customer use, production data, external actions |
| Internal alpha | Authorised internal users; synthetic or approved redacted test data | Exercise the narrow loop end to end with mocks/manual sources | Deterministic tests, visible failure, measurement instrumentation | Customer production use, silent action, broad integrations |
| Design-partner pilot (MVP) | Exactly five selected companies; limited authorised production workflows after all gates | Save measurable time across the complete meeting-to-next-meeting loop | Verified identity/tenancy, consent, evidence, approval, deletion, recovery, direct support | Public signup, every integration, autonomous action, mobile capture |
| Private beta | Controlled additional companies in declared regions/stacks | Repeatable onboarding and support with both target productivity ecosystems/CRMs and one priority meeting import | SLO/cost controls, security/privacy review, entitlements if required, operational runbooks | Public availability, full provider breadth, ambient capture |
| Later product | Evidence-led expansion | Broader Sales Brain, Recruitment Brain and Customer Success Brain outcomes | Separate product, safety, privacy and architecture decisions | Assumed compatibility without discovery |

## Technical prototype

Technical prototypes answer one explicit unknown, such as transcription accuracy, citation alignment, provider API feasibility or retrieval quality. They:

- use synthetic data by default;
- cannot send communications or write to CRM;
- live behind an internal boundary and are not represented as shipped capability;
- record evaluation criteria before experimentation; and
- are removed, hardened through a planned sprint or retained only as test fixtures.

Prototype success is evidence for a product/engineering decision, not beta readiness.

## Internal alpha

Internal alpha should complete this loop with manual sources and deterministic/mock adapters:

`ingest → match → review transcript → source-backed summary → next steps → follow-up/CRM proposals → approval state → memory → next brief`

It must expose low-confidence, failure, correction, exclusion and deletion paths. External execution may remain mocked, but UI and documentation must say “proposal” or “mock” rather than “sent/synced”.

## Design-partner pilot: exactly the first five companies

### Selection criteria

Choose exactly five companies that:

- match the 20–500 employee, 5–100 seller, relationship-driven B2B SaaS ICP;
- have an accountable sales/revenue operations sponsor and security/IT contact;
- share enough provider overlap to support one productivity ecosystem and one CRM;
- can supply consented workflows and participants under their policies;
- agree to weekly feedback and time-saved measurement; and
- accept a controlled pilot with declared limits and direct support.

### Required end-to-end loop

For an eligible customer meeting, Sales Brain must:

1. **Ingest the meeting:** Accept an explicitly selected recording/pasted transcript; connected import is optional if safe. Record consent evidence and make progress/failure/delete visible.
2. **Identify participants and account:** Suggest same-tenant matches with reasons; let the user confirm, correct, create or leave unresolved. Link the opportunity where known.
3. **Produce a source-backed summary:** Present editable structured claims with transcript citations, confidence/uncertainty and conflict state.
4. **Extract next steps:** Propose owner/action/due date without inventing missing values; user accepts/edits/rejects before accountable task creation.
5. **Draft follow-up:** Generate a cited draft. User verifies recipients/content and approves the exact version. Delivery through the selected mail provider is required only after the safe adapter passes; copy/manual draft remains a fallback during controlled rollout.
6. **Propose CRM updates:** Show current authoritative values and field-level proposals for the selected CRM. No proposal is labelled synced.
7. **Allow human approval:** Bind every external communication/CRM write to actor, exact content/diff, destination and expiry. Changed/stale actions require new approval.
8. **Preserve relationship memory:** Store only reviewed, source-linked, correctable memory; make conflict, staleness, exclusion and deletion work.
9. **Prepare the next meeting:** Show a concise brief with recent events, commitments, risks, unknowns and citations; corrections must appear.

### Required cross-cutting behaviour

- Verified Clerk authentication, current membership and one trusted organisation context.
- Explicit repository tenant predicates, PostgreSQL RLS and tenant-scoped jobs/files/indexes.
- Manual source fallback even when a connector is enabled.
- Safe loading, empty, partial, low-confidence and failure states.
- Idempotent ingestion and external execution with bounded retries/reconciliation.
- Content-minimised audit, logging, metrics and direct incident/support procedures.
- Tested retention, deletion, export and provider disconnect.
- No production customer data before the [production readiness gates](../03-engineering/privacy-security-and-trust-model.md#production-readiness-gates) pass.

### Pilot integration requirement

The pilot supports:

- **one** of Google Calendar/Gmail or Outlook Calendar/Outlook Mail, chosen from partner overlap;
- **one** of Salesforce or HubSpot, chosen from partner overlap; and
- manual recording upload/transcript paste for all five companies.

A connected Zoom, Teams or Meet import may be enabled only if its dedicated safe adapter is ready; it is not a prerequisite. The cohort should not be expanded to compensate for incompatible stacks.

### Pilot success measures

Measure per meeting and per company:

- preparation and post-meeting administration time;
- percentage of meetings that complete the loop;
- artefact review time and one-business-day completion;
- summary/next-step/follow-up/CRM proposal acceptance, edits and rejections;
- citation usefulness and unsupported-claim incidents;
- corrections that persist into later briefs;
- approved external action success/recovery;
- deletion/consent/support incidents; and
- weekly active use and qualitative trust.

Provisional targets from the [master blueprint](../01-product/master-product-blueprint.md#expected-customer-outcomes) require validation; they are not contract promises.

## Private beta

Private beta begins only when:

- pilot evidence shows repeat value and no unresolved high-severity trust issue;
- both Google and Microsoft calendar/mail paths satisfy the integration contract;
- Salesforce and HubSpot read plus approved-write paths satisfy their documented contracts;
- manual ingestion and at least one priority Zoom/Teams/Meet import are supported;
- account assistant/search, notifications and administrator controls are production-ready;
- observability, audit, deletion/export, backup/restore, incident and support processes pass;
- billing/entitlement behaviour is implemented if the commercial model requires it; and
- provider/edition/region availability and capacity limits are explicit.

Private beta remains invitation-only and capacity-controlled. Remaining meeting-platform imports can roll out in focused beta increments; “beta priority” is not a claim that every provider is available on beta day one.

## Later product

- Deeper Zoom/Teams/Meet coverage and selected phone-provider capture.
- Broader CRM objects, provider-specific workflows and carefully evaluated low-risk automation.
- Native mobile experiences; in-person capture only with explicit visible controls and regional review.
- Slack notifications after in-product exception value is proven.
- Recruitment Brain with JobAdder and candidate/employment-specific safeguards.
- Customer Success Brain with product-specific health/workflow definitions.
- Enterprise SSO/SCIM, advanced data residency and compliance capabilities based on customer evidence.

## Non-negotiable boundaries

- RevenueOS does not become the CRM or silently compete as the field system of record.
- No external communication or CRM write occurs without user approval during beta.
- No ambient or covert recording.
- No unsupported AI claim becomes memory or action.
- No user-supplied organisation ID determines tenant scope.
- No real integration is represented by a mock, draft or log message.
- No production content is used in tests, evaluation or training without explicit lawful authority.

## Unresolved decisions

Resolve through design-partner discovery and implementation ADRs:

1. Which five companies and shared provider stack form the pilot cohort?
2. Is creating a provider email draft sufficient, or is approved send essential for pilot value?
3. Which CRM fields/objects may be proposed and written in each provider?
4. Which meeting-platform import has the highest beta value and viable API/edition access?
5. What transcript/raw-media retention bounds do the first region and customers require beyond the 30-day audio default?
6. Which role may access raw transcripts, approve another user's work or manage team exceptions?
7. Which launch region is first and what data residency/transfer commitments apply?
8. What evaluation thresholds are acceptable by artefact type?
9. Does private beta require automated Stripe billing or only entitlement readiness/manual contracting?
10. What capacity, support hours and incident commitments can the team sustain?

## Related documents

- [Master product blueprint](../01-product/master-product-blueprint.md)
- [User journeys](../01-product/user-journeys.md)
- [Product roadmap to beta](product-roadmap-to-beta.md)
- [Privacy, security and trust model](../03-engineering/privacy-security-and-trust-model.md)
- [Integration strategy](../05-integrations/integration-strategy.md)
