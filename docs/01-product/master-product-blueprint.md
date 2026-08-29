# RevenueOS master product blueprint

- **Status:** Target product direction through the Interaction Platform private beta
- **Current shipped baseline:** Sprints 1–3 plus Meeting Intelligence, Opportunity
  Workspace, deterministic Revenue Brain, private-beta controls, Interaction
  foundation, Pre-Interaction Brief and reviewed AI Debrief/Voice Journal through
  WO-013, browser-first visual evidence and Presentation Mode through WO-014, and
  optional browser recording/batch transcription through WO-015, the
  mobile-first foreground browser Companion through WO-016, phone/online/document
  capture through WO-017–019 and provisional Live Intelligence through WO-020
- **Scope notation:** **Current** exists in the repository; **Pilot** is required for the first five design-partner companies; **Beta** is required before private beta; **Later** is deliberately deferred; **Future** is directional only.

This is the primary product blueprint. It defines outcomes and boundaries, not an
authorisation to implement future scope. The recommended next sequence is in the
[Interaction Intelligence roadmap](../06-roadmap/interaction-intelligence-roadmap.md);
the older [product roadmap to beta](../06-roadmap/product-roadmap-to-beta.md)
retains integration-led planning and completed-baseline context.

**Mission:** Eliminate administrative work from relationship-driven professions by building AI teammates that remember, reason and act.

**Core principle:** Automate work, not relationships.

**Interaction north star:** RevenueOS captures the best possible evidence from every
customer interaction, transforms that evidence into trusted intelligence, and helps
sales teams build stronger customer relationships over time.

WO-010 expands the future direction beyond uploaded meeting transcripts and
recordings. WO-011 through WO-020 implement the initial Interaction identity,
preparation, reviewed salesperson-reported post-interaction slice and reviewed
browser visual plus consented audio evidence foundations and the thin
BEFORE/DURING/AFTER field Companion orchestration, deliberate phone/online/document
sources and a separate opt-in provisional live aggregate. The
[Interaction Intelligence vision](interaction-intelligence-vision.md)
and [product blueprint](interaction-intelligence-product-blueprint.md) define the
Capture → Intelligence → Action lifecycle and face-to-face priority. They do not
describe implemented behaviour or authorise a later work order.

## Executive summary

RevenueOS is the AI teammate for relationship-driven professionals. It sits above systems of record and communication tools—including Salesforce, HubSpot, email, calendars, phone and meeting platforms—as an intelligence and workflow layer. It is not a CRM.

The first product, Sales Brain, should turn authorised evidence from a customer
interaction into a reviewable chain of evidence, decisions and approved work:

1. prepare for and associate the interaction;
2. capture the best available evidence through recording, debrief, voice, visual,
   document or authorised metadata sources;
3. identify the people, company and opportunity;
4. produce source-aware intelligence and next steps;
5. draft a follow-up and propose CRM changes;
6. let a human approve every consequential external action;
7. preserve correctable relationship memory; and
8. use that memory to prepare the next interaction.

RevenueOS exists to eliminate administrative work from relationship-driven professions by building AI teammates that remember, reason and act. Its governing principle is **automate work, not relationships**.

## Product thesis

Revenue professionals lose time and context because customer knowledge is distributed across conversations, inboxes, calendars, personal notes and CRM records. Systems of record preserve fields but do not reliably reconstruct why a relationship changed, what was promised or what should happen next.

RevenueOS can create durable value by:

- treating authorised interaction sources as attributable evidence rather than
  disposable recordings;
- maintaining source-backed relationship memory instead of another undifferentiated data store;
- preparing work proactively at the moment it is useful;
- converting intelligence into drafts and proposals without silently acting;
- learning from explicit correction while retaining provenance; and
- fitting over the customer's existing systems rather than forcing replacement.

This thesis depends on users trusting the evidence, correcting mistakes quickly and measuring enough administrative time saved to justify another layer in their stack.

## Problem definition

### User problems

- Sellers reconstruct account context before meetings from several tools.
- Face-to-face conversations are lost when recording is refused, inappropriate or
  unreliable and the seller cannot type notes.
- Important details decay before a seller can reconstruct them hours later.
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

| User                      | Primary need                                                                      | Beta value                                                                                  |
| ------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Sales representative      | Spend less time reconstructing context and completing post-meeting administration | Accurate preparation, reviewable meeting intelligence, approved follow-up and CRM proposals |
| Sales manager             | Understand deal movement and coach from evidence                                  | Exception-led pipeline review with links to source material                                 |
| Revenue operations leader | Improve data quality and workflow consistency without adding seller burden        | Governed proposals, measurable completion and integration health                            |
| System administrator      | Connect systems and enforce secure access, retention and consent controls         | Least-privilege setup, health visibility, audit evidence and reliable deletion              |

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

For relationship-driven B2B revenue teams whose customer context is fragmented
across interactions, communications and CRM, Sales Brain captures the best available
authorised evidence and turns it into source-backed memory and approved next
actions. Unlike a CRM, recorder or meeting-notes tool, it works before, during and
after online and face-to-face interactions while keeping people in control of
consequential actions.

### Platform direction

- **Current through beta:** Sales Brain.
- **Later:** Recruitment Brain, using the same tenant, conversation, memory, approval and integration foundations for recruiters.
- **Future:** Customer Success Brain, using those foundations for onboarding, adoption, renewal and expansion relationships.

The later products are not beta requirements and must not distort Sales Brain workflows prematurely.

WO-023 defines the future end-to-end Sales OS direction within Sales Brain. It keeps
Sales Brain, Methodology, Intelligence, Workspace and Daily in Core; adds Prospect,
Engage, Create and CRM as optional modules; and organises the experience around Home,
Find, Sell, Pipeline, Create and Insights. The authoritative expansion contract is the
[End-to-End Sales Platform vision](end-to-end-sales-platform-vision.md), with the
[conditional roadmap](../06-roadmap/end-to-end-sales-platform-roadmap.md). It does not
change the implemented WO-022 baseline or authorise a later work order.

WO-029 implements separately entitled, one-to-one personalised outreach for a
canonical Contact, using bounded sourced professional research, approved seller
context, immutable review, durable suppression and exact execution preview. WO-030
adds an explicit immutable audience and one-to-four-step Campaign orchestration over
those same one-to-one primitives, with review-per-send by default and bounded
campaign-level auto-send only after separate organisation policy and launch
confirmation. Execution remains deterministic simulation outside production;
Gmail/Microsoft production sending and automatic reply detection remain deferred.
See [Personalised one-to-one outreach](personalised-outreach.md) and
[Campaigns & Sequences](campaigns-and-sequences.md).

WO-031 implements manual business Events under Engage: authorised bounded CSV
attendee import, conservative relationship matching, explainable categorical
priority, per-user planning, seller-reported encounters, explicit Contact promotion,
existing Companion capture and truthful WO-029/WO-030 handoff. EventAttendee remains
separate from Contact; attendance is neither contact permission nor customer Evidence,
buying intent, Methodology state or Revenue Brain truth. See
[Events](event-intelligence.md).

WO-032 implements the first Create slice: an organisation-entitled Sales Content
Studio for administrator-attested and approved PPTX templates, Account-bound
deterministic plans, typed customer-safe context, exact claim provenance, seller
review and private editable PPTX download. It makes no AI-provider call and adds no
proposal/DOCX/PDF, pricing, ROI, generated imagery, external sending or Office
execution. See [RevenueOS Create](revenueos-create.md). WO-033 and broader Create
outputs remain future and require separate approval.

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

| Alternative                      | Useful capability                         | RevenueOS distinction                                                                                 |
| -------------------------------- | ----------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| CRM                              | Structured system of record               | Preserves conversational context and prepares work while leaving the CRM authoritative                |
| Meeting notetaker                | Transcription and per-meeting summaries   | Builds correctable, cross-meeting relationship memory and carries it into the next interaction        |
| Sales engagement platform        | Sequenced outreach and activity execution | Prioritises relationship context and human-approved, situation-specific actions                       |
| General AI assistant             | Flexible generation and questions         | Uses tenant-authorised evidence, explicit confidence, provenance, domain workflows and audit trails   |
| Manual notes and personal memory | High individual control                   | Provides continuity, team visibility and measurable administration reduction without removing control |

Differentiation is only credible when outputs are attributable, corrections persist, external actions require approval and time saved is observable.

## Expected customer outcomes

The product should be evaluated against outcomes, not document volume or model activity:

- less seller time spent on interaction preparation and post-interaction administration;
- faster, more consistent follow-up;
- higher completion of agreed next steps;
- more current CRM data with fewer unsupported updates;
- fewer lost commitments when ownership changes;
- faster manager identification of stalled or risky opportunities;
- demonstrable user trust through review, approval and correction behaviour; and
- secure deletion and access controls that work as described.

Initial targets are hypotheses to validate with design partners:

- median combined preparation and post-interaction administration reduced by at
  least 20 minutes per important customer interaction;
- at least 80% of generated interaction artefacts reviewed or dismissed within one
  business day;
- at least 70% of approved suggestions require no material factual correction;
- no external communication or CRM write without recorded human approval; and
- zero confirmed cross-tenant data exposures.

## North-star product experience

Shortly before an interaction, the seller receives a concise brief containing recent
changes, open commitments, risks and suggested questions, each linked to its source.
During it, RevenueOS is passive by default and capture is optional. Afterwards it
offers “Let’s capture this while it is fresh,” using a recording, Voice Journal,
targeted AI Debrief, visual evidence or another authorised source. RevenueOS presents
a provenance-aware review queue—not a falsely final answer. The seller corrects
attribution or interpretation, approves selected tasks, follow-up content and CRM
changes, then returns to customer work. The next brief reflects confirmed memory and
corrections.

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

| Assumption                                                                 | How to test                                                           | Decision signal                                                             |
| -------------------------------------------------------------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| The first ICP feels acute enough administrative pain                       | Baseline time study and weekly interviews across five design partners | Repeated, measurable time loss in the narrow loop                           |
| Users will review output when the queue is short and evidence is clear     | Instrument review time, edits, approvals and dismissals               | Most artefacts resolved within one business day                             |
| Immediate non-recording debrief is useful before broad recording           | Pilot preparation plus Voice Journal/AI Debrief                       | Repeated face-to-face use and usable intelligence without transcript upload |
| Source-backed corrections build trust                                      | Compare trust interviews and correction rates over time               | Users rely on later briefs and correct errors rather than abandon           |
| One mail/calendar ecosystem and one CRM can support the first pilot cohort | Select partners by stack and integration value                        | Five companies can complete the loop without broad adapter coverage         |
| CRM proposals are valuable before broad write coverage                     | Present explicit diffs and track acceptance                           | Proposals are approved or edited, not routinely ignored                     |
| Relationship memory can remain concise and useful                          | Review memory use in meeting preparation                              | Memory is cited in briefs and stale items are corrected or retired          |
| Managers value exceptions more than surveillance-style scoring             | Test evidence-led review with manager and seller feedback             | Coaching improves without reduced seller trust                              |

Unresolved product decisions are recorded in [MVP and beta scope](../06-roadmap/mvp-and-beta-scope.md#unresolved-decisions).

## MVP definition

“MVP” means the minimum Sales Brain experience suitable for controlled use in real
face-to-face customer interactions, not the current repository and not a public
release. It must:

- use production-verified identity, membership and tenant isolation;
- associate a planned or completed Interaction with account and opportunity context;
- prepare a concise source-aware brief;
- work when recording is unavailable, inappropriate or refused;
- offer an immediate, safe Voice Journal and opportunity-aware AI Debrief;
- distinguish salesperson-reported, direct customer, system, imported and inferred
  evidence;
- ask only high-value questions about missing, changed or conflicting information;
- present reviewable claims, uncertainty and conflicts before promotion;
- produce source-aware Interaction Intelligence and reviewable next steps;
- update Opportunity Workspace and Revenue Brain from eligible validated structured
  intelligence without rewriting historical Meeting snapshots;
- draft, but never silently send, follow-up;
- propose, but never silently apply, supported record changes;
- expose partial, failed, skipped and deletion states;
- provide retention, deletion, consent/policy and audit controls; and
- measure workflow completion and time saved without using production content in
  logs or employee-surveillance metrics.

The first face-to-face MVP is reached by WO-013 in the
[Interaction Intelligence roadmap](../06-roadmap/interaction-intelligence-roadmap.md),
subject to target-environment customer-data, privacy/legal and operational gates.
Manual transcript input remains a valid current fallback; broad recording, native
mobile capture and meeting bots are not MVP prerequisites.

## Beta definition

Private beta adds repeatable onboarding and operational support beyond the first five companies:

- a supported preparation, debrief and source-aware Interaction Timeline loop;
- included capture modes with honest non-recording and partial-failure fallbacks;
- validated evidence provenance, conflict, verification and deletion across every
  included source;
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

- recreating Salesforce/HubSpot breadth; RevenueOS may be the intentionally lightweight native sales system of record selected by an entitled organisation;
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

- [Interaction Intelligence vision](interaction-intelligence-vision.md)
- [Interaction Intelligence product blueprint](interaction-intelligence-product-blueprint.md)
- [Interaction Intelligence roadmap](../06-roadmap/interaction-intelligence-roadmap.md)
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

## WO-033 implemented extension

The current Create boundary includes the transparent ROI & Business Case Builder.
Organisation administrators approve bounded, versioned formulas and visible default
assumptions. Sellers create an Account-linked, optionally Opportunity-linked case,
enter or review every input with provenance, inspect deterministic formulas/results,
compare explicit scenarios and one-variable sensitivity, and approve an exact version.
Only an approved version may feed Create, with cautious language, material assumptions,
the approved disclaimer and exact claim-source lineage.

This is not forecasting, CPQ or an autonomous recommendation system. It cannot invent
inputs or outputs, confirm customer truth, mutate Methodology/Revenue Brain, import or
execute spreadsheets, convert currencies, calculate tax/GST or provide NPV, IRR or
Monte Carlo analysis. See [ROI & Business Case Builder](roi-business-case-builder.md).

## WO-034 implemented extension

RevenueOS can now be deliberately configured as the lightweight native sales CRM or
continue alongside connected HubSpot. Existing Company, Contact and Opportunity are
the only CRM records. Core keeps their basic CRUD and readable canonical
activity/history; the CRM add-on provides explicit system-of-record administration,
bounded typed custom fields and admin archive/restore. Existing activity domains are
composed rather than copied.

Exact domain/email dedupe, one-person ownership, archive/restore, optimistic
concurrency and field-authority controls provide the v1 governance boundary. There
is no Lead, CRM Task/Note/Activity, custom object/workflow, destructive merge,
autonomous AI mutation or Pipeline redesign. Operational CRM CSV is deferred while
organisation export includes the new CRM data. See [Native CRM](native-crm.md).
