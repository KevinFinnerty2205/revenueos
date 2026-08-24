# Core go-to-Prospect readiness

- **Status:** Current product boundary after WO-025C
- **Decision:** Core is ready to support the start of WO-026
- **Design-partner status:** Ready with restrictions; real customer data requires a
  separately approved target environment
- **Decision authority:** [Checkpoint 1B](../06-roadmap/checkpoint-1b-core-readiness.md)

## Product conclusion

RevenueOS Core now delivers a coherent relationship-selling loop for known accounts
and active opportunities:

1. **Prioritise** — Daily shows one primary focus, upcoming Interactions, Actions and
   deal attention.
2. **Prepare** — an Interaction brief turns current account, opportunity, stakeholder,
   methodology and prior-interaction context into objectives and questions.
3. **Capture deliberately** — the seller chooses recording, passive Companion,
   authorised uploads/photos or typed debrief; RevenueOS never listens implicitly.
4. **Review** — structured intelligence, Evidence, trust state, conflict and unknowns
   remain visible and correctable before becoming accepted context.
5. **Understand** — Opportunity, Revenue Brain and methodology views explain risks,
   stakeholders, gaps and next action without a synthetic deal score.
6. **Act safely** — the seller reviews an Action; approval is not execution. A linked
   HubSpot change receives a fresh read, exact preview and second confirmation.
7. **Return** — the reviewed outcome and action feed the next Daily priority and future
   preparation.

Ask RevenueOS is a bounded access path across that same authorised evidence. It is not
a second truth store, a general chatbot or a public-web research product.

This loop is useful before Prospect exists. Prospect adds the upstream ability to
find and qualify new accounts and people; it does not complete a broken Core loop.

## What Core is good enough to promise

Core can credibly promise:

- a seller can walk into a prepared RevenueOS Interaction with clear objectives and
  questions;
- authorised customer evidence can become structured, reviewed and source-aware deal
  context;
- Daily, methodology and reviewed Actions help the seller decide what to do next;
- a supported question can be answered from authorised RevenueOS evidence or return a
  clear unknown; and
- a configured, linked HubSpot record can receive a bounded change only after review
  and explicit confirmation.

Core cannot credibly promise:

- every meeting is captured automatically;
- every CRM field or CRM provider is synchronised;
- email or calendar actions are sent in production;
- any action is autonomous;
- close probability, forecast accuracy, targets, team analytics or manager coaching;
- comprehensive answers to arbitrary natural-language questions; or
- native mobile/background capture.

## The current value statement

The strongest concise product statement is:

> RevenueOS helps relationship-led sellers prepare for every important conversation,
> turn authorised evidence into a clear next action, and apply the HubSpot update they
> review and confirm.

The phrase “Finish the meeting. RevenueOS handles the admin.” is usable only with the
following qualifier:

> RevenueOS prepares the follow-through and applies the supported HubSpot update you
> review and confirm.

Do not imply automatic email sending, general CRM autofill or silent execution.

## Core and Prospect boundary

| Concern                    | Core owns                                                   | Prospect may add                                            | Prospect must not do                               |
| -------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------- | -------------------------------------------------- |
| Identity and tenancy       | Verified user/organisation context, membership, RLS         | Reuse exactly                                               | Accept a client-supplied organisation as authority |
| Canonical people/companies | Reviewed Company and Contact records                        | Propose duplicate-safe promotion                            | Write provider findings directly as accepted facts |
| Evidence                   | Provenance, source, time, trust state, conflict, correction | Research sources and findings using the same trust language | Present inference as verified or hide its source   |
| Revenue Brain              | Accepted longitudinal customer context                      | Add reviewed promoted context later                         | Treat a prospect observation as customer truth     |
| Ask                        | Bounded Q&A over current authorised RevenueOS knowledge     | Deep-link to Prospect results when explicitly scoped        | Become an unrestricted browsing or SQL agent       |
| Actions                    | Review, approval and separate execution                     | Draft future outreach after the Stage B gate                | Send, enrol or update without explicit authority   |
| Integrations               | HubSpot-first reviewed write path                           | Provider-neutral research adapters                          | Couple Prospect domain rules to HubSpot payloads   |

Research results are observations, not Contacts. Contact details can be unknown,
reported, inferred or verified; only an approved verification source may claim the
last state. A seller must see why a result is relevant, where it came from, when it was
observed and what will happen before Save to Sell.

## Design-partner offer

### Readiness classification

**READY WITH RESTRICTIONS.** A supervised cohort can be shown the complete Core loop
with synthetic or otherwise approved non-customer data now. Real customer-data use is
not approved until the target-environment launch checklist is complete.

### Offered journey

The first design-partner journey should be deliberately narrow:

1. select or create one real, permitted Opportunity;
2. prepare one supported Interaction;
3. use one approved capture method or the manual/no-recording fallback;
4. review and correct the resulting intelligence;
5. approve one next action;
6. where enabled, preview and confirm one bounded HubSpot update; and
7. return the next day to Daily and ask one account/opportunity question.

Avoid a broad feature tour. Prospect discovery can run beside this journey, but the
partner should experience Core value before being asked to evaluate new pipeline.

### Restrictions

- named, supervised users and organisations only;
- an approved target environment with production identity, tenant/RLS and operational
  checks before customer data;
- documented data authority, notice, retention, export and deletion handling;
- selected capture/browser/provider combinations only, always with a manual fallback;
- HubSpot only after target OAuth and sandbox evidence; no Salesforce claim;
- no automatic recording, mailbox ingestion, customer-facing send, forecast,
  coaching, manager surveillance or autonomous action; and
- high-touch support, visible correction, incident escalation and rollback.

### Time-to-value hypotheses

| Hypothesis                                                         | Evidence to collect                                                   |
| ------------------------------------------------------------------ | --------------------------------------------------------------------- |
| A new seller understands the first useful journey without training | unaided start/completion; prompts required                            |
| Preparation is useful before the first supported Interaction       | time to brief; usefulness rating; questions used                      |
| Review produces trusted customer context                           | time to review; corrections; unsupported findings                     |
| The next action is clearer than the seller's prior process         | action acceptance/edit and interview evidence                         |
| HubSpot review removes admin without reducing control              | minutes saved; preview comprehension; confirm/retry/conflict outcomes |
| Daily and Ask create a reason to return                            | next-day return; useful supported answers; correct unknowns           |

Partner success is not the number of features opened. The indispensable moment is a
seller saying that RevenueOS helped them enter a conversation better prepared or
leave it with a trusted next step and less reviewed admin.

## Simplicity contract

Core remains the default product. Prospect is an add-on destination and may not make
the seller's daily loop feel like a suite switcher.

- Desktop keeps Home, Sell and Workspace task groups.
- Mobile keeps Today, Interactions, Actions and Search as the fixed primary set.
- Find/Prospect appears only when entitled and uses account, person and lead language
  consistent with the [navigation terminology contract](../02-design/core-navigation-and-terminology.md).
- Progressive disclosure keeps Evidence, methodology detail, sync receipts and
  advanced capture controls close to the decision but out of the first scan.
- Search remains deterministic retrieval; Ask remains explicitly scoped and cited;
  Prospect research is a separate, source-rich workflow.
- Empty, loading, partial, unavailable, forbidden and error states must explain the
  next safe step rather than exposing internal capability labels.

The current UI still needs minor refinement: navigation says Accounts/People while
some page headings say Companies/Contacts; Settings exposes technical capability
language; and a few completed-Interaction calls to action are ambiguous. These are
normal Core maintenance issues, not a new pre-Prospect product layer.

## Marketing claim register

| Claim                                                      | Product status                                                               |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Walk into every customer conversation prepared.            | Ready now for supported RevenueOS Interactions.                              |
| Know what to do next.                                      | Ready now; do not add “exactly” or imply guaranteed outcomes.                |
| Turn customer evidence into a clear, reviewed next action. | Ready now.                                                                   |
| Finish the meeting. RevenueOS handles the admin.           | Ready only with the HubSpot/review qualifier.                                |
| Keep HubSpot updated without hours of manual entry.        | Ready with linked-record, supported-field and confirmation qualifiers.       |
| Ask RevenueOS anything about your deals.                   | Ready only as “ask supported questions about authorised RevenueOS evidence”. |
| Never write meeting notes again.                           | Ready only for an approved capture path; not an absolute.                    |
| Know which deals will close.                               | Future.                                                                      |
| Coach every rep automatically.                             | Future.                                                                      |
| One autonomous system runs your revenue team.              | Not the RevenueOS product promise.                                           |

## Product decision

Start WO-026. Preserve the Core loop as an independently useful product, keep research
facts outside canonical records until reviewed, and validate controlled partner value
in parallel. Do not move forecast, coaching, manager, analytics, targets, win/loss or
a second CRM ahead of the first Prospect learning loop.
