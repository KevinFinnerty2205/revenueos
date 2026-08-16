# RevenueOS Core product

- **Status:** Future product definition; current capability is explicitly identified below
- **Purpose:** Make Sales Brain indispensable without requiring another module

## Core promise

RevenueOS Core understands authorised customer evidence, remembers the relationship,
helps a seller prepare and follow through, and explains what matters today.

Core has five inseparable parts:

1. Sales Brain;
2. Sales Methodology;
3. RevenueOS Intelligence;
4. RevenueOS Workspace; and
5. RevenueOS Daily.

## Sales Brain

### Before

AI Companion and Pre-Interaction Brief assemble account, opportunity, stakeholder,
commitment, risk, objection, objective, question, methodology-gap and recent-history
context. WO-012 already implements a bounded deterministic brief. Future maturity
adds methodology and broader evidence without turning preparation into a checklist.

### During

The browser Companion, online-meeting and phone workflows, optional recording,
transcription, Visual Evidence, Quick Markers and provisional Live Intelligence are
implemented in bounded forms through WO-020. They remain passive, deliberate and
honest about browser/provider limitations. Future native or provider paths require
separate evidence and approval.

### After

AI Debrief, Voice Journal, Executive Summary, Buying Signals, Objections,
Competitive Signals, Stakeholders, Decisions, Action Items, Risks, Open Questions,
Follow-up Email, Next Best Action and reviewable Actions exist today in scoped forms.
They need broader source-neutral reconciliation, user correction and production
provider evaluation before the full Core promise is mature.

### Brain

Revenue Brain currently composes immutable validated references and deterministic
adjacent-snapshot changes. Future Revenue Brain becomes the longitudinal
account/opportunity memory used by methodology, Daily, content creation, coaching
and forecasts while preserving source and historical interpretation.

## Sales Methodology

Methodology is included in Core. Evidence remains canonical; MEDDIC, MEDDPICC,
BANT, SPICED, SPIN, Challenger, Sandler, GAP Selling, Solution Selling and a safe
custom definition are projections over the same evidence.

Each item is `confirmed`, `partially_supported`, `unknown`, `conflicting` or `stale`.
The user sees what RevenueOS believes, why, the evidence, last support date,
conflicts and missing information. A methodology can change without erasing history.

Gaps influence preparation, questions, debrief, Next Best Action, deal coaching and
forecast explanation. They do not become a simplistic completion or rep score.

## RevenueOS Intelligence

Core eventually includes:

- descriptive analytics: what happened;
- diagnostic analytics: what changed and where the funnel is weak;
- targets and KPI progress;
- an explainable evidence-based forecast with ranges and calibration;
- manager deal-attention views; and
- coaching grounded in actual evidence and historical outcomes.

The default is a short narrative and action list. Charts and tables are drill-down.
Forecasting in Core avoids forcing customers to buy an add-on to understand the
revenue already represented in Sales Brain.

## RevenueOS Workspace

Workspace is the organised evidence and working memory of a revenue relationship.
It includes Account Workspace, Opportunity Workspace, the Interaction timeline,
files, documents, emails, recordings, Visual Evidence, proposals, presentations,
business cases and deal-room material when implemented.

It is not generic file storage. Every item should have account/opportunity context,
provenance, access, retention and a clear sales purpose. Broad enterprise document
management is outside Core.

## RevenueOS Daily

Daily is the default habit surface and answers **What matters today?** It combines
upcoming interactions, actions, commitments, deal attention, deadlines, target
progress, forecast and pipeline gap into a bounded priority view. It is not an
analytics dashboard or notification dump.

## Core maturity definition

Core is mature when a seller can:

1. open Home and see the next useful work;
2. prepare for and capture an Interaction with or without recording;
3. review source-aware understanding and Actions;
4. see methodology gaps without maintaining dozens of fields;
5. use an Account or Opportunity as the relationship workspace;
6. understand target, forecast and risk explanations; and
7. correct or delete AI-supported information and see that change propagate.

## Simplicity test

- **Where/first action:** Home is the default; open the top priority or next Interaction.
- **Navigation:** Core owns Home, Sell, Pipeline and Insights; Account, Opportunity
  and Interaction stay contextual rather than becoming more top-level items.
- **Hidden until needed:** Full Evidence, methodology detail, analytics definitions,
  history and administration sit behind summary and explanation.
- **Mobile:** Today, Interactions, Actions and Search cover the field workflow.
- **When not purchased:** Not applicable—Core is the base product and must not become
  unusable because an add-on is absent.
- **First-time/power user:** A first-time seller sees one priority and guided empty
  states; a power user adds saved filters, Search and the optional command bar.
- **AI/manual work:** AI proposes sourced understanding, gaps and Actions to reduce
  fields/forms; the user can inspect, edit, reject, undo or delete where appropriate.

## Explicit exclusions

Core does not include account discovery, broad contact data, campaign sending,
template-generated customer materials or full native CRM administration. Those are
the Prospect, Engage, Create and CRM add-ons. Core also excludes surveillance,
generic BI, autonomous external action and unrestricted custom workflow code.

See [Sales Methodology architecture](../03-engineering/sales-methodology-engine-architecture.md),
[Intelligence architecture](../03-engineering/sales-analytics-targets-forecast-architecture.md)
and [Daily experience](../02-design/revenueos-daily-experience.md).

WO-024 now implements the methodology slice of Core: one organisation default or
none, four immutable standards, bounded custom definitions, explainable Opportunity
views and preparation/action context. It does not implement Daily, analytics,
forecasting, manager dashboards or methodology-based rep measurement.
