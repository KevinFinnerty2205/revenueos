# Core simplicity readiness review

- **Review date:** 17 August 2026
- **Surfaces inspected:** current app shell, onboarding, Daily desktop/mobile,
  Opportunity/Methodology desktop/mobile, Interaction, Meeting, Actions, Settings and
  Assistant placeholder
- **Outcome:** Daily passes; the complete Core experience does not yet pass the
  pre-Prospect simplicity gate

## Five-second findings

RevenueOS Daily clearly answers “What matters today?” The greeting, date, dark top-
priority/next-Interaction card and one CTA establish a useful hierarchy. Bounded
Actions, deal attention, pipeline and recommended focus follow in a sensible order.

The surrounding product is less clear:

- desktop exposes eleven permanent navigation links, including entity and technical
  workflow names;
- mobile renders the same links in a horizontally clipped navigation strip;
- Daily's visible Search button opens an Assistant page that explicitly does
  nothing;
- Opportunity stacks methodology, meeting association, evidence capture, Action
  generation, Revenue Brain, source-specific intelligence, ten latest-meeting panels
  and recent Meetings in one long page; and
- onboarding teaches Companies → Opportunities → Meetings → transcript → generation
  → Workspace → Brain rather than helping a seller complete one useful outcome.

Adding Find/Prospect to this shell would make the product materially harder to learn.

## Major Core workflow classification

| Workflow                               | Current classification                    | Finding                                                                                      | Required treatment                                                       |
| -------------------------------------- | ----------------------------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Start the day                          | **Obvious**                               | One priority and CTA lead; reasons and bounded sections support it                           | Preserve Daily; do not add widgets for parity                            |
| Find the next Interaction              | **Obvious**                               | Desktop Today and mobile Next/Day overview are clear                                         | Preserve mobile-first order                                              |
| Add first Opportunity                  | **Understandable with small improvement** | Clear form/CTA, but existing CRM users must re-key context                                   | Import/match through WO-025C; keep manual fallback                       |
| Prepare for an Interaction             | **Understandable with small improvement** | Daily/Interaction routes link to preparation, but route taxonomy is broad                    | Surface from Today and Opportunity; keep brief concise                   |
| Capture face-to-face without recording | **Understandable with small improvement** | Companion explains deliberate passive/capture paths                                          | Validate wording and recovery with real users                            |
| Import online/phone evidence           | **Confusing**                             | Honest controls exist, but users must understand source type, authority and later generation | One guided “Add authorised source” flow with progressive policy detail   |
| Review post-Interaction intelligence   | **Understandable with small improvement** | Source labels and review are strong                                                          | Lead with “what changed/needs review”, then source detail                |
| Understand an Opportunity              | **Too technical**                         | Correct content appears as a long architecture-shaped stack                                  | Create Overview → Why → Evidence hierarchy and contextual sections       |
| Review methodology                     | **Understandable with small improvement** | Counts and important gaps work; full fields are disclosed                                    | Keep inside Opportunity Deal, reduce repeated copy/controls              |
| Review/approve an Action               | **Understandable with small improvement** | Lifecycle is explicit and safe; “approved is not executed” is clear                          | Present the next lifecycle step and destination without internal terms   |
| Configure simulated integrations       | **Too technical**                         | Correct for development, not a seller workflow                                               | Keep in admin Settings and label simulation; future live setup is guided |
| Search/ask                             | **Confusing**                             | Search CTA leads to an unavailable Assistant                                                 | WO-025B must replace placeholder before Prospect                         |
| Manage the team                        | **Confusing**                             | No manager experience; admin can be mistaken for manager capability                          | Keep unavailable until WO-039; do not fake with admin data               |
| First-run onboarding                   | **Too technical**                         | Nine entity/architecture steps and synthetic-only wording delay the value story              | Rebuild around first outcome in WO-025A                                  |
| Mobile Core navigation                 | **Too technical**                         | Desktop navigation is horizontally overflowed/clipped                                        | Move to Today, Interactions, Actions and Search                          |

## Navigation decision

### Core-only desktop

Before Prospect, the task-led shell should expose:

- **Home** — personal Daily;
- **Sell** — account, people, Interactions and relationship work;
- **Pipeline** — Opportunities and deal attention;
- **Insights** — only when a useful current Core projection exists;
- **Search** — utility/command entry, not a destination competing with work; and
- **Settings** — utility for organisation/user configuration.

Do not show disabled Find or Create areas just to preview add-ons. When Prospect or
Create is enabled later, they enter the six-area target IA without moving Core work.
Getting started becomes contextual onboarding/progress, not permanent primary
navigation. Feedback and sign-out remain utilities.

Existing Companies, Contacts, Opportunities, Interactions, Meetings, Tasks,
Assistant and Settings URLs should remain compatible while page composition and
navigation labels change through an authorised work order.

### Mobile

Use exactly the task set already approved by ADR 0035:

- **Today**;
- **Interactions**;
- **Actions**; and
- **Search**.

Account, Opportunity, methodology, evidence and Settings are contextual destinations,
not permanent mobile tabs. No horizontal feature strip.

## Home review

### What works

- a seller can identify the first action within 30 seconds;
- one CTA is visually dominant;
- priority reasons are controlled and understandable;
- “approved — not complete” prevents false completion;
- pipeline is explicitly descriptive rather than a fake forecast;
- partial-source failure does not collapse the day; and
- caught-up/new-user states are calm and instructional.

### What should not be added before its engine exists

- forecast number, target attainment, team leaderboard or methodology percentage;
- notification centre, activity feed or chart wall;
- module ads in empty cards; or
- another AI-generated ranking beside the deterministic top priority.

Targets, forecast and team exceptions should enter the existing Home hierarchy only
after WO-037–039 establish trusted source contracts.

## Opportunity review

The current page contains valuable information but violates “one page answers one
primary question” by giving every capability similar card weight. It should answer:

> What is happening in this deal, why, and what should I do next?

### Level 1 — what matters

- concise deal state and important recent change;
- one next action;
- top risk/conflict/gap;
- next Interaction/commitment; and
- current source freshness.

### Level 2 — why

- methodology summary;
- people/stakeholder coverage;
- risks, objections, commitments and actions;
- relevant Interaction/Revenue Brain timeline; and
- source-specific reported/visual/document/email context grouped by sales question.

### Level 3 — Evidence and administration

- cited source locations and history;
- full methodology definition/history;
- meeting association/source correction;
- generation/reprocessing and technical recovery; and
- connection/mapping details for authorised admins.

Do not solve the page by creating ten new routes. Use a stable Opportunity section
model and progressive disclosure. Search/Ask should deep-link to the relevant level.

## Interaction and capture review

The BEFORE/DURING/AFTER model is easier to understand than the underlying Capture
Session and Evidence objects. Keep product language centred on:

- **Prepare** — what matters and what to ask;
- **Capture** — record, add a source or continue without recording;
- **Review** — what RevenueOS understood and what needs correction; and
- **Follow through** — approve the resulting work.

Source authority, consent, upload state and provider limitations remain visible at
the decision point, but detailed provenance/storage terminology should move behind
“Why this source?” or an admin/security explanation.

## Action and integration review

The lifecycle is safe but the product copy must separate user outcomes:

- “Prepared for review”;
- “Approved — not sent/updated”;
- “Ready to confirm in Salesforce/HubSpot”; and
- “Updated”, “Failed” or “Needs reconciliation”.

Connection IDs, fingerprints, idempotency and adapter names belong in operator
diagnostics, not the normal seller screen. Simulation stays unmistakable in the
current build.

## Ask RevenueOS placement

Search should be globally reachable and context-aware. It should open normal search
first, then accept supported natural-language questions. Account/Opportunity pages
may pre-scope it, but should not embed separate chat histories.

An answer contains:

1. the concise answer or explicit “RevenueOS does not have enough evidence”;
2. important conflict/freshness/coverage qualifiers;
3. source citations/deep links; and
4. one safe navigation/refinement action.

It does not send, update, approve or create an Action from free-form text.

## Onboarding and time-to-value redesign

### Admin setup

1. confirm organisation, data-use and retention policy;
2. connect the selected CRM with the minimum scopes;
3. review a small suggested mapping and one sample match;
4. choose/confirm the offered capture path and no-recording fallback; and
5. invite the first seller.

### Seller first outcome

1. open Home and see a single welcome action;
2. select an imported/matched Opportunity or add one manually;
3. prepare for the next Interaction;
4. capture or debrief deliberately;
5. review what changed and one proposed follow-through; and
6. approve one useful CRM update and see its receipt.

Internal names such as Meeting Intelligence, Revenue Brain snapshot, artefact,
projection and execution foundation should not be prerequisites. Synthetic demo data
remains available for a safe walkthrough, not the main product journey.

## Simplicity and discoverability gate

| Question                                      | Checkpoint answer                                                                                                      |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Does the recommendation simplify seller work? | Yes for Core consolidation, Ask and CRM sync; later intelligence stays in existing Home/Opportunity/Insights contexts. |
| Does it reduce admin?                         | CRM sync and outcome-led capture directly do; Ask reduces retrieval work.                                              |
| Does it create another screen unnecessarily?  | No new top-level destination; Search is a utility and Opportunity uses disclosure.                                     |
| Can it live in Home/Opportunity/Search?       | Yes; this is the governing placement rule.                                                                             |
| Does it require training?                     | Current onboarding does; the target first-outcome path should not. Admin mapping may need guided support.              |
| Can AI remove fields?                         | Ask, evidence projection and CRM proposals should replace repeated manual forms, not add an AI form.                   |
| Is the next action obvious?                   | Yes on Daily; Opportunity and Action need the same hierarchy.                                                          |
| Does mobile remain simple?                    | Yes only after replacing the clipped desktop navigation with four tasks.                                               |
| Can the user verify/correct AI?               | Existing review/provenance supports this; Ask and CRM sync must preserve it.                                           |
| Does it preserve progressive disclosure?      | The proposed summary → why → Evidence pattern strengthens it.                                                          |

## Decision

WO-025 Daily passes. RevenueOS Core as a whole does not yet pass the simplicity gate
for Prospect expansion. WO-025A must consolidate navigation/onboarding and the
Opportunity hierarchy; WO-025B must replace the Search/Assistant dead end. Deal Room,
forecast, coaching and manager features stay in their later owning work orders so
they do not overload the pre-Prospect experience.
