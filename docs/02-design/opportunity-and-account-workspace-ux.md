# Opportunity and Account Workspace UX

- **Status:** WO-025A implements the Opportunity summary → why → evidence hierarchy;
  the broader Account target remains future
- **Principle:** Keep the relationship and deal in one coherent working area

## Account Workspace

**Question:** What is happening with this customer?

The header shows Account identity, relationship owner, current opportunities, latest
meaningful interaction and one next action. Below it:

1. relationship overview and recent change;
2. key people and stakeholder coverage;
3. active opportunities;
4. Interaction and evidence timeline;
5. open commitments/actions;
6. files and customer material; and
7. account-level Revenue Brain insights.

Account is not a duplicate CRM record form. Editing core identity is a focused action;
history and evidence remain the default reading order.

## Opportunity Workspace

**Question:** How do I win this deal?

Use one page with a compact secondary navigation:

| Section  | Purpose                           | Level 1 content                                                    |
| -------- | --------------------------------- | ------------------------------------------------------------------ |
| Overview | Current deal truth and next focus | stage/value/date, headline, next action, material change           |
| People   | Buying committee and influence    | confirmed roles, gaps, conflict/staleness                          |
| Activity | Customer history                  | Interaction timeline and meaningful digital evidence               |
| Deal     | Qualification and commercial path | methodology projection, decision/procurement/security/timeline     |
| Actions  | What must happen next             | proposed, approved, due and execution states                       |
| Files    | Working evidence                  | presentations, proposals, documents, recordings and business cases |
| Insights | Why the deal is moving or stuck   | signals, objections, risks, forecast explanation and coaching      |

The page initially renders Overview; sections are anchors or responsive tabs, not
independent top-level routes. Deep links remain stable.

## Overview concept

```text
Qantas — Network Modernisation              Evaluation · $420K · 30 Sep
Forecast: $260K–$380K                       Updated 2 hours ago

NEXT BEST ACTION
Confirm who owns the security decision process.             Prepare question →

WHAT CHANGED
Technical fit strengthened; legal timing now conflicts with the close date.
Why? →

METHODOLOGY
5 confirmed · 2 partial · 1 unknown                         View gaps →

PEOPLE                    ACTIONS                  NEXT INTERACTION
6 known · EB unknown      3 open · 1 approval      Workshop · Tue 10:30

Recent activity / evidence (bounded)
```

## Progressive disclosure

- **Level 1 — Tell me what matters:** headline, next action, counts and exceptions.
- **Level 2 — Show me why:** methodology field, risk/forecast explanation, source
  labels, recency and conflict.
- **Level 3 — Show me everything:** evidence fragments, history, versions, audit and
  connected-record state subject to permissions.

The same levels apply to stakeholder, Action, forecast and file content.

## Deal Room and files

Deal Room is an Opportunity section, not a generic file product. It groups authorised
proposals, presentations, ROI/business cases, customer requirements, contracts,
security documents, pricing and recordings. Every item has owner, source, version,
audience, retention and approval state. External customer sharing is future and
requires a separate access model.

## Empty, partial and error states

- No evidence: show existing Opportunity fields and **Add customer information** or
  **Prepare an interaction**.
- Missing methodology item: show `Unknown`, why it matters and a natural suggested
  question; do not require bulk form completion.
- Conflicting evidence: show both positions and a review action.
- Deleted/restricted source: remove unsafe derived detail and explain the boundary.
- Stale CRM/provider: timestamp the last-known value and disable unsafe write action.
- Partial intelligence: preserve completed sections and identify only the unavailable
  capability.

## First-time, power-user, mobile and entitlements

- First-time: Overview with one next action; secondary sections explained in-place.
- Power user: keyboard command bar, saved section links and dense tables only within
  drill-down.
- Mobile: Overview, People, Actions and Activity first; Files/Insights collapse.
  Interactions use full-screen phase flows.
- Missing CRM add-on: core Opportunity Workspace works; native pipeline field/admin
  controls are absent or explain who owns the external CRM.
- Missing Create: files remain usable and **Create presentation** becomes one calm
  contextual discovery action.

## AI correction

Every AI-supported item offers **Why?** and, where appropriate, **Correct**. A
correction creates a versioned review event, preserves evidence origin and
invalidates dependent briefs, Actions or forecasts as required. Editing an external
CRM field follows its source-of-truth and approval rules.

## Current Sales Methodology area

WO-024 places a compact Methodology card directly under the Opportunity Deal header.
It leads with categorical counts and the three highest-priority gaps, then reveals
all fields, Evidence/provenance, review controls and history on demand. On mobile it
remains a single-column summary rather than a matrix. Methodology is absent from
top-level navigation and RevenueOS remains fully usable when the organisation selects
none. See [Sales Methodology UX](sales-methodology-ux.md).

WO-025 adds only source links into this existing workspace: Daily Action and deal
cards open the Opportunity, methodology gaps remain controlled summaries, and an
existing Next Best Action deep link opens its current workspace section. Daily does
not duplicate Evidence, Methodology, Action review or Revenue Brain history.
