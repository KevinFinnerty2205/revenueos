# Prospect and Engage simplicity review

- **Status:** Checkpoint 2 design review of current WO-026–031 implementation
- **Viewport evidence:** desktop at 1440 × 900; mobile at 390 × 844; committed
  responsive Event/Target Market evidence inspected as a fallback where local hard
  navigation failed
- **Decision:** **READY WITH REFINEMENTS**; no design-system rework before WO-032

## Summary

Prospect and Engage generally behave like one guided sales workflow rather than a
collection of AI features. Pages ask one question at a time, advanced policy is
mostly disclosed only when needed and trust language is adjacent to the action it
constrains.

The experience is strongest on research detail, contactability, exact outreach review
and Event identity boundaries. The main work before a real design partner is first-use
reliability and recovery—not a new navigation model.

## Navigation and terminology

| Surface                  | Finding                                                                                                                                 | Decision                                                                                   |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Package name             | **Prospect** and **Engage** are clear commercial outcomes.                                                                              | Keep.                                                                                      |
| Primary entry            | Desktop uses **Find**, which describes the seller’s immediate task better than a module name.                                           | Keep.                                                                                      |
| Canonical work           | Accounts, People, Interactions, Campaigns and Events remain under **Sell**.                                                             | Keep; do not introduce a seventh top-level area.                                           |
| Mobile                   | Today, Interactions, Actions and Search preserve the four-item mobile model.                                                            | Keep; expose Prospect/Engage work contextually rather than duplicating desktop navigation. |
| Prospect/person language | Research Target, Account, Person, Contact and Evidence are distinguished in action copy.                                                | Strong; retain explicit promotion language.                                                |
| Campaign language        | Campaign, step, audience and recipient are understandable without sales-automation jargon.                                              | Strong; do not expose jobs/enrolment internals.                                            |
| Settings                 | Admin-only controls use seller language for offering, value, limits, opt-out and business-address policy; provider absence is explicit. | Sufficient for now; keep OAuth/provider diagnostics out of ordinary seller settings.       |

The package names belong in availability/settings and commercial explanation. The
day-to-day navigation should continue using seller verbs and familiar relationship
nouns.

## Desktop review

### Find and Target Markets

The Find landing page offers two legitimate starts: research a known company or
discover accounts from a Target Market. Recent research and Target Markets are visible
without turning the page into a dashboard.

The Target Market result experience is particularly clear:

- **Who and where** summarises the versioned market;
- filters operate on a small set of categorical states;
- each company explains matched criteria, missing context and relationship state;
- **High priority** is explicitly described as fit, not intent; and
- source/date information appears with developments rather than behind an AI badge.

Refinement: discovery creates Research Targets before a run, but Recent research
labels them **Research queued**. The corresponding detail says research has not
started. Use **Ready to research** and reserve queued/running for actual jobs.

### Account and Person Research

Account Research uses a productive reading order: overview, why this may matter,
verified/provider/inferred context, what is not established, sources and history.
The four trust states are visible in plain language.

Person Research is appropriately shorter and more conservative. It explains why the
professional may matter, shows current role and eligible activity, marks buying roles
as hypotheses and puts contact-source/permission warnings beside the business email.
No profile photos or private-person signals compete for attention.

Refinement: **Add to Sales** on a Person can complete its confirmation flow before
the UI reports that the Company must be added first. The domain invariant is correct,
but the user hits a dead end. If the Company is absent, show a primary **Save Company
first** action that returns to the same Person after successful promotion.

### Contact and one-to-one outreach

The Contact page puts **Contactability** ahead of the composer and clearly states that
address trust does not establish permission. The composer is deliberately small: one
purpose selector and one draft action.

Draft review is strong:

- the subject/body are concise and editable;
- **Why this message?** names approved seller context and specific research sources;
- approval copy states that nothing has been sent;
- exact preview shows From, To, subject and body; and
- **Simulation only / No external email** is impossible to miss.

The synthetic draft was relevant but used a recognisable template phrase. For live
provider evaluation, measure edit/rejection rate and whether source selection produces
a genuinely useful reason to contact—not merely grammatically personalised copy.

### Campaigns and Sequences

The four-stage Campaign builder—goal/audience, steps, review, launch—is simpler than a
workflow canvas. Canonical Contacts, four purposes, explicit delays, review-each-send
and disabled-by-policy auto-send make the default safe without forcing the seller to
learn the underlying execution architecture.

Campaign detail shows the sequence, immutable audience snapshot, eligible/blocked
recipients, progress, seller-reported outcomes and sending controls. The statement
**No open or click tracking** is direct and appropriately calm.

Refinements:

- the live local builder intermittently showed **Failed to fetch** and empty Contact/
  policy state even while the API returned success;
- the seeded Campaign showed a next-send time of 5:33 am beside an 08:30–17:00
  Australia/Sydney window; synthetic fixtures must demonstrate the actual rule; and
- retain review-each-send as the first live design-partner default even where an
  administrator later enables bounded auto-send.

### Events

The first-use Event screen is short: why Events exist, the authority/permission
warning and one **Create Event** action. Event detail uses four task-oriented tabs:
Overview, People, Activity and Follow Up. The dark summary card and four counters
make current state scannable without implying a numeric buying score.

CSV import is correctly desktop-first and progressively disclosed. Limits, allowed
fields, raw-file handling and authority attestation appear before commitment. Event-
day actions—plan, met, follow up, Companion, draft and research—remain attached to a
person card, while seller-note copy explains that it is not customer Evidence.

## Mobile review

The Contact and Campaign detail pages remained readable at 390 pixels. Contactability
appeared before outreach, and the Campaign’s sequence, audience, recipients and
controls stacked in a sensible order.

Committed WO-028/031 responsive evidence shows the intended Target Market and Event-
day layouts. The Event person card provides high-value field actions without hiding
trust, permission or the seller-note boundary.

Three mobile refinements are required:

1. a hard reload of Target Market and Event detail reproduced **Failed to fetch** in
   the local review, while Contact and Campaign detail loaded; diagnose the shared
   capability/data-fetch lifecycle before a partner session;
2. the Event **Follow Up** tab clips at 390 pixels; use a horizontally scrollable tab
   list with an obvious affordance or a compact select/menu, preserving keyboard and
   screen-reader semantics; and
3. ensure the fixed bottom navigation never obscures Event feedback or final card
   actions, including safe-area insets and increased text sizes.

These are material for field use but do not justify a new mobile app or alternate
information architecture.

## Progressive disclosure

| Decision            | Visible first                         | Revealed later                                          | Assessment                                |
| ------------------- | ------------------------------------- | ------------------------------------------------------- | ----------------------------------------- |
| Find an account     | known-company search or Target Market | criteria/edit/history                                   | **STRONG**                                |
| Understand research | overview and why it matters           | sources and run history                                 | **STRONG**                                |
| Save a relationship | explicit Company/Contact promotion    | duplicate/provenance detail                             | **READY**, with prerequisite recovery fix |
| Write outreach      | purpose                               | sources, editing, approval and exact preview            | **STRONG**                                |
| Create Campaign     | audience and four steps               | per-recipient message review and operational exceptions | **READY**                                 |
| Use an Event        | create/list                           | CSV mapping, person actions and follow-up               | **READY**                                 |
| Configure auto-send | review each by default                | administrator policy plus launch confirmation           | **STRONG**                                |

## First-use and empty/error states

Empty states explain a seller job and offer one next action. Trust restrictions are
written as reasons, not legalistic tooltips. Error copy is usually safe, but the
intermittent broad **Failed to fetch** state lacks a useful retry or diagnostic path.

Before supervised sessions:

- show a local retry action for recoverable reads;
- preserve last safe content when refresh fails where confidentiality and freshness
  allow;
- distinguish entitlement unavailable, configuration missing, network failure and
  resource not found; and
- keep mock/provider unavailability conspicuous.

## Complexity budget

Keep the present constraints:

- one guided Target Market model, not a spreadsheet formula builder;
- one four-state research trust vocabulary;
- Company before Contact promotion;
- one Contact composer and one shared personalisation service;
- maximum 50 Campaign recipients and four steps;
- review-each-send as default and no arbitrary branching;
- four Event task tabs and no event-management suite; and
- no open/click tracking dashboard.

Do not add dashboards, scores, agents or configuration merely to match competitors.
Create should adopt the same design pattern: a guided sequence with source inspection
and a reviewable artefact, not a blank prompt or generic design canvas.

## Design readiness decision

The desktop and mobile concepts are coherent enough for WO-032. Fix navigation/data-
fetch reliability and the named recovery/layout inconsistencies before real partner
use. Validate time to first useful result with a live provider before claiming speed.
