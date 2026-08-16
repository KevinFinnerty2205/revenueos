# ADR 0035: Evidence-centred end-to-end Sales OS architecture

**Status:** Accepted

## Context

WO-001–022 established tenant-isolated relationship records, Meetings/Interactions,
Evidence and AI artefacts, longitudinal Revenue Brain, review-only Actions and a
simulation-first execution boundary. Extending RevenueOS from interaction intelligence
into prospecting, engagement, content creation, CRM and revenue management could
otherwise fragment truth, navigation, security policy and commercial packaging.

RevenueOS must become more powerful without requiring users to understand its
architecture. The design also needs clear boundaries between current implementation,
future Core value, paid expansion and capabilities that should never become product
scope.

## Decision

Adopt an evidence-centred, modular end-to-end Sales OS with these constraints:

1. **RevenueOS Core** includes Sales Brain, Sales Methodology, RevenueOS Intelligence
   including future evidence-based forecasting, RevenueOS Workspace and RevenueOS
   Daily. Core is independently useful and does not depend on an add-on.
2. **Add-ons** are Prospect, Engage, Create and CRM. Complete may bundle them.
   Enterprise may package implemented governance, residency, permissions, integrations,
   support and audit capabilities; it is not a dumping ground for essential Core.
3. **Canonical Evidence and Revenue Brain remain the centre.** Methodology definitions
   project the same Evidence; Daily, analytics, forecast, coaching, content and handover
   consume versioned authorised projections/proposals rather than create rival truth.
4. **Permanent desktop navigation is Home, Find, Sell, Pipeline, Create and Insights.**
   Search and Settings are utilities. Account and Opportunity are contextual Sell
   workspaces. CRM enriches Sell/Pipeline and does not receive a top-level destination.
   Mobile is Today, Interactions, Actions and Search.
5. **One page primarily answers one salesperson question.** Use three-level progressive
   disclosure: what matters, why, and full detail. Every future work order applies the
   fifteen-question simplicity/discoverability gate.
6. **Lead and Prospect are workflow states, not duplicate identities.** A staged
   Prospect Account/Person is promoted through duplicate review to canonical Company/
   Contact; a Lead represents assigned pursuit. “Account” is user-facing Company context.
7. **Trust is explicit.** Methodology items use confirmed/partially supported/unknown/
   conflicting/stale. Research uses verified/provider supplied/inferred/unknown.
   Contact verification is separate from permission to contact. AI does not invent
   source Evidence, commercial facts, pricing or ROI numbers.
8. **Entitlements are server-authoritative.** Effective availability combines plan,
   organisation policy, runtime/provider capability and user permission. The client
   renders a typed safe projection; pricing rules are not scattered across pages.
9. **Architecture remains a modular monolith.** Extend the existing API/web/PostgreSQL,
   RLS, AI job, Action and Execution boundaries. Providers sit behind adapters. No
   microservice, broker, second datastore or unrestricted workflow engine is approved.
10. **External effects remain human-governed.** Research does not authorise outreach;
    exact approval, suppression, idempotency, stop/reconciliation and provider-specific
    security/privacy readiness apply before live action.
11. **Integration order follows validated customer systems.** Discover Microsoft and
    Google needs early, implement the first demanded mail/calendar ecosystem, then a
    first CRM connector only after source authority and safe update semantics exist.
12. **Explicit non-scope** includes generic project/document management, SharePoint or
    Salesforce clones, generic marketing automation/BI/no-code, employee surveillance,
    manipulative research, uncontrolled outreach, infinite customisation, a generic AI
    chatbot everywhere and near-term autonomous cold calling/AI SDR.

The roadmap adds explicit customer checkpoints after Core, top-of-funnel and broader
product/platform stages. Its WO-024–045 sequence is proposed, not authorised.

## Alternatives considered

- **One top-level area per entity or feature:** rejected because it recreates CRM-style
  navigation sprawl and makes purchases determine information architecture.
- **Separate CRM product/navigation and duplicated CRM entities:** rejected because it
  fragments the Company/Contact/Opportunity truth and Sales Brain workflow.
- **Methodology-specific AI systems or mutable methodology fields as truth:** rejected;
  switching methodology must preserve canonical Evidence and history.
- **Put methodology, forecasting, Workspace or Daily behind add-ons:** rejected because
  these are essential to the coherent Core promise.
- **One boolean feature flag in the browser:** rejected because access also depends on
  organisation policy, system capability and permission, and must be server-enforced.
- **Build WO-024–045 sequentially without checkpoints:** rejected because adoption,
  safety, provider and commercial evidence should change investment decisions.
- **Choose microservices or machine-learning forecasts now:** rejected as premature;
  the modular monolith and transparent deterministic/statistical baseline are safer.

## Consequences

Future work orders have stable package, navigation, truth, entitlement and safety
boundaries. Core remains useful when every add-on is unavailable, while add-ons can
reuse canonical identity, Evidence, Brain, Action and Workspace contracts.

The decision deliberately limits breadth. Some customers may expect deeper CRM,
marketing, file-management or customisation features; those expectations do not
override the Sales OS loop without new evidence and an ADR. The six-area navigation
will require a compatibility-aware migration from current routes when authorised.

Forecast, research, outreach, content generation, native CRM and live integrations
remain future work with substantial security, legal, evaluation and operational
gates. Accepting this ADR does not claim those capabilities are implemented.
