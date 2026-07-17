# RevenueOS master product blueprint

- **Status:** Target product direction through private beta
- **Current shipped baseline:** Sprints 1–3 foundation, core business entities and Meeting Domain
- **Scope notation:** **Current** exists in the repository; **Pilot** is required for the first five design-partner companies; **Beta** is required before private beta; **Later** is deliberately deferred; **Future** is directional only.

This is the primary product blueprint. It defines outcomes and boundaries, not an authorisation to implement future scope. The sequenced delivery plan is in [Product roadmap to beta](../06-roadmap/product-roadmap-to-beta.md).

**Mission:** Eliminate administrative work from relationship-driven professions by building AI teammates that remember, reason and act.

**Core principle:** Automate work, not relationships.

## Executive summary

RevenueOS is the AI teammate for relationship-driven professionals. It sits above systems of record and communication tools—including Salesforce, HubSpot, email, calendars, phone and meeting platforms—as an intelligence and workflow layer. It is not a CRM.

The first product, Sales Brain, should turn a consented customer conversation into a reviewable chain of evidence, decisions and approved work:

1. ingest a meeting or transcript;
2. identify the people, company and opportunity;
3. produce a source-backed summary and next steps;
4. draft a follow-up and propose CRM changes;
5. let a human approve every consequential external action;
6. preserve correctable relationship memory; and
7. use that memory to prepare the next interaction.

RevenueOS exists to eliminate administrative work from relationship-driven professions by building AI teammates that remember, reason and act. Its governing principle is **automate work, not relationships**.

## Product thesis

Revenue professionals lose time and context because customer knowledge is distributed across conversations, inboxes, calendars, personal notes and CRM records. Systems of record preserve fields but do not reliably reconstruct why a relationship changed, what was promised or what should happen next.

RevenueOS can create durable value by:

- treating conversations as consented, attributable evidence rather than disposable recordings;
- maintaining source-backed relationship memory instead of another undifferentiated data store;
- preparing work proactively at the moment it is useful;
- converting intelligence into drafts and proposals without silently acting;
- learning from explicit correction while retaining provenance; and
- fitting over the customer's existing systems rather than forcing replacement.

This thesis depends on users trusting the evidence, correcting mistakes quickly and measuring enough administrative time saved to justify another layer in their stack.

## Problem definition

### User problems

- Sellers reconstruct account context before meetings from several tools.
- Notes, commitments and objections are incomplete or inconsistently entered.
- Follow-ups and CRM updates compete with customer-facing time.
- Managers see stale fields without the conversational evidence behind them.
- Revenue operations teams cannot distinguish missing data, low-confidence inference and confirmed fact.
- Organisations face privacy, consent and access risks when conversation data is captured or processed opaquely.

### Organisational problem

The organisation needs better relationship continuity without creating a shadow CRM, eroding seller trust or granting autonomous systems authority to communicate or alter records silently.

## Initial ideal customer profile

The initial ICP is a relationship-driven B2B SaaS company with:

- 20–500 employees;
- 5–100 sales representatives;
- Microsoft 365 or Google Workspace;
- Salesforce or HubSpot; and
- repeated discovery, evaluation and expansion conversations where context affects revenue outcomes.

Design-partner selection should favour a narrow, repeatable sales motion and an accountable operational sponsor. The first five companies do not need every supported integration; the chosen calendar, mail and CRM adapters should follow their actual stack.

## Target users

| User | Primary need | Beta value |
| --- | --- | --- |
| Sales representative | Spend less time reconstructing context and completing post-meeting administration | Accurate preparation, reviewable meeting intelligence, approved follow-up and CRM proposals |
| Sales manager | Understand deal movement and coach from evidence | Exception-led pipeline review with links to source material |
| Revenue operations leader | Improve data quality and workflow consistency without adding seller burden | Governed proposals, measurable completion and integration health |
| System administrator | Connect systems and enforce secure access, retention and consent controls | Least-privilege setup, health visibility, audit evidence and reliable deletion |

Detailed needs are in [Personas and jobs](personas-and-jobs.md).

## Jobs to be done

1. **Before a customer interaction:** “Help me understand what matters now without making me search every system.”
2. **After a customer interaction:** “Turn the conversation into an accurate, editable record and the work I need to do.”
3. **When updating systems:** “Show me the proposed change, its source and impact before I approve it.”
4. **Across a relationship:** “Remember decisions, preferences, risks and commitments, while letting me correct or remove them.”
5. **When managing a team:** “Show me where attention is needed and why, rather than another static pipeline table.”
6. **When governing the platform:** “Let me control access, connections, retention, consent and audit evidence without exposing customer content unnecessarily.”

## Product positioning

### Category

RevenueOS is an AI teammate and relationship intelligence layer. Sales Brain is the first application on that platform.

### Positioning statement

For relationship-driven B2B revenue teams whose customer context is fragmented across meetings, communications and CRM, Sales Brain turns consented conversations into source-backed memory and approved next actions. Unlike a CRM or general meeting-notes tool, it works across existing systems, prepares future interactions and keeps people in control of consequential actions.

### Platform direction

- **Current through beta:** Sales Brain.
- **Later:** Recruitment Brain, using the same tenant, conversation, memory, approval and integration foundations for recruiters.
- **Future:** Customer Success Brain, using those foundations for onboarding, adoption, renewal and expansion relationships.

The later products are not beta requirements and must not distort Sales Brain workflows prematurely.

## Product boundaries

RevenueOS owns:

- the reviewable intelligence derived from authorised source material;
- provenance, confidence, corrections and exclusions;
- relationship memory optimised for future context;
- proposed next actions, approvals and execution receipts;
- cross-system workflow status and exceptions; and
- the user experience for preparing, reviewing and approving work.

Connected systems remain authoritative for:

- CRM-native records and final field values;
- email and calendar delivery state;
- meeting-platform recordings and attendance where supplied;
- identity and organisation membership through Clerk; and
- billing transactions through Stripe when introduced.

RevenueOS may cache the minimum connected data needed for its workflows, with source identity, sync state and retention recorded. Conflicts must be visible; a local inference must never silently overwrite an authoritative external value.

## Competitive differentiation

| Alternative | Useful capability | RevenueOS distinction |
| --- | --- | --- |
| CRM | Structured system of record | Preserves conversational context and prepares work while leaving the CRM authoritative |
| Meeting notetaker | Transcription and per-meeting summaries | Builds correctable, cross-meeting relationship memory and carries it into the next interaction |
| Sales engagement platform | Sequenced outreach and activity execution | Prioritises relationship context and human-approved, situation-specific actions |
| General AI assistant | Flexible generation and questions | Uses tenant-authorised evidence, explicit confidence, provenance, domain workflows and audit trails |
| Manual notes and personal memory | High individual control | Provides continuity, team visibility and measurable administration reduction without removing control |

Differentiation is only credible when outputs are attributable, corrections persist, external actions require approval and time saved is observable.

## Expected customer outcomes

The product should be evaluated against outcomes, not document volume or model activity:

- less seller time spent on meeting preparation and post-meeting administration;
- faster, more consistent follow-up;
- higher completion of agreed next steps;
- more current CRM data with fewer unsupported updates;
- fewer lost commitments when ownership changes;
- faster manager identification of stalled or risky opportunities;
- demonstrable user trust through review, approval and correction behaviour; and
- secure deletion and access controls that work as described.

Initial targets are hypotheses to validate with design partners:

- median combined preparation and post-meeting administration reduced by at least 20 minutes per customer meeting;
- at least 80% of generated meeting artefacts reviewed or dismissed within one business day;
- at least 70% of approved suggestions require no material factual correction;
- no external communication or CRM write without recorded human approval; and
- zero confirmed cross-tenant data exposures.

## North-star product experience

Shortly before a meeting, the seller receives a concise brief containing recent changes, open commitments, risks and suggested questions, each linked to its source. After an explicitly authorised conversation is available, RevenueOS identifies the relationship context and presents a review queue—not a falsely final answer. The seller corrects the transcript or matching, accepts or edits the summary, approves selected tasks, follow-up content and CRM changes, then returns to customer work. The next brief reflects confirmed memory and any corrections.

The interface prioritises:

- recent relationship movement;
- context and evidence;
- next actions and deadlines;
- low-confidence or failed work requiring attention; and
- approvals, conflicts and exceptions.

It does not centre on reproducing CRM tables.

## Product principles and operating rules

1. **Memory over storage:** retain information because it improves a future interaction, not merely because it can be stored.
2. **Proactive over reactive:** prepare bounded, timely suggestions without taking unauthorised action.
3. **Admit uncertainty:** distinguish quoted fact, confirmed memory, external record and inference.
4. **Measure time saved:** instrument workflow duration and avoided manual steps without surveilling individuals.
5. **Customer trust first:** make capture, processing, retention, deletion and sharing understandable.
6. **Simple, accessible UX:** progressive disclosure, clear language and complete loading, empty and failure states.
7. **Human control:** require approval for CRM writes, communications and other consequential actions during beta.
8. **No silent action:** surface intended destination, changed fields and execution result.
9. **Tenant isolation by design:** scope every tenant-owned query, job, file, event and cache key.
10. **Source-backed AI:** preserve citations and provenance; unsupported output is not promoted to memory or action.

## Assumptions requiring validation

| Assumption | How to test | Decision signal |
| --- | --- | --- |
| The first ICP feels acute enough administrative pain | Baseline time study and weekly interviews across five design partners | Repeated, measurable time loss in the narrow loop |
| Users will review output when the queue is short and evidence is clear | Instrument review time, edits, approvals and dismissals | Most artefacts resolved within one business day |
| Manual upload or transcript paste is sufficient before broad capture | Pilot the loop without ambient capture | Continued weekly use despite manual ingestion |
| Source-backed corrections build trust | Compare trust interviews and correction rates over time | Users rely on later briefs and correct errors rather than abandon |
| One mail/calendar ecosystem and one CRM can support the first pilot cohort | Select partners by stack and integration value | Five companies can complete the loop without broad adapter coverage |
| CRM proposals are valuable before broad write coverage | Present explicit diffs and track acceptance | Proposals are approved or edited, not routinely ignored |
| Relationship memory can remain concise and useful | Review memory use in meeting preparation | Memory is cited in briefs and stale items are corrected or retired |
| Managers value exceptions more than surveillance-style scoring | Test evidence-led review with manager and seller feedback | Coaching improves without reduced seller trust |

Unresolved product decisions are recorded in [MVP and beta scope](../06-roadmap/mvp-and-beta-scope.md#unresolved-decisions).

## MVP definition

“MVP” means the minimum Sales Brain product suitable for a controlled design-partner pilot, not the current repository and not a public release. It must:

- use production-verified identity, membership and tenant isolation;
- accept an explicitly selected meeting file or pasted transcript with consent confirmation;
- match or let the user match participants, company and opportunity;
- show an editable transcript and source-backed meeting summary;
- extract reviewable next steps;
- draft, but never silently send, a follow-up;
- propose, but never silently apply, supported CRM changes;
- record approval and execution outcome for any external action;
- create source-backed, correctable and deletable relationship memory;
- prepare a concise brief for the next meeting;
- expose failures, low confidence and retry state;
- provide retention, deletion and audit controls; and
- measure workflow completion and time saved without using production content in logs.

The pilot may support one calendar/mail ecosystem and one CRM selected from the first partners. Manual ingestion remains a valid fallback.

## Beta definition

Private beta adds repeatable onboarding and operational support beyond the first five companies:

- supported Google Workspace and Microsoft 365 calendar/mail connection paths;
- a deliberately phased subset of Zoom, Microsoft Teams and Google Meet ingestion;
- supported Salesforce and HubSpot read/match/proposal/write paths, each independently gated;
- assistant and search answers grounded in authorised sources;
- notifications and exception management;
- production administration, permissions, audit export and connection health;
- operational observability, cost and latency controls, support runbooks and recovery;
- defined entitlements and billing readiness where commercially required; and
- documented privacy, deletion, backup, incident response and regional launch gates.

An integration appears in beta only after its real adapter, authorisation, idempotency, deletion and failure behaviour are tested. A mock or proposal UI is not an integration.

## Explicit non-goals through beta

- replacing Salesforce, HubSpot or another system of record;
- silently sending email, changing CRM data or performing consequential actions;
- broad sales engagement automation or generic workflow building;
- lead generation, contact enrichment, prospect databases or automated outreach;
- autonomous forecasting, performance ranking or employment decisions;
- ambient, covert or always-on recording;
- unsupported legal conclusions about recording consent;
- complete phone-provider coverage;
- JobAdder, Slack or customer-success-platform support before their later phase;
- native mobile parity; responsive web and tightly constrained future capture companions come first;
- Recruitment Brain or Customer Success Brain product workflows;
- training provider models on customer content without a separate, explicit choice; and
- claiming model output as fact when no authorised source supports it.

## Related documents

- [Personas and jobs](personas-and-jobs.md)
- [User journeys](user-journeys.md)
- [Information architecture](../02-design/information-architecture.md)
- [Core workflows](../02-design/core-workflows.md)
- [AI system blueprint](../04-ai/ai-system-blueprint.md)
- [Target domain model](../03-engineering/target-domain-model.md)
- [Integration strategy](../05-integrations/integration-strategy.md)
- [Privacy, security and trust model](../03-engineering/privacy-security-and-trust-model.md)
- [MVP and beta scope](../06-roadmap/mvp-and-beta-scope.md)
- [Product roadmap to beta](../06-roadmap/product-roadmap-to-beta.md)
