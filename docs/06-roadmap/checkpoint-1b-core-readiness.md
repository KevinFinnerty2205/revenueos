# Checkpoint 1B — Core product, competitive and architecture readiness

- **Date:** 24 August 2026
- **Decision:** **GO** — begin WO-026 Account & Lead Research
- **Core design-partner readiness:** **READY WITH RESTRICTIONS**
- **Customer-data launch status:** not approved until the target-environment launch
  checklist is complete
- **Authority:** this record closes the pre-Prospect product/architecture checkpoint;
  it does not authorise production deployment or any work order after WO-026

## Executive verdict

RevenueOS Core is coherent, useful and trustworthy enough to begin Prospect. The
implemented loop now helps a seller prepare for an Interaction, capture authorised
evidence, review structured intelligence, understand an Opportunity, choose and
approve the next action, update a bounded HubSpot record with an exact preview, and
return to a prioritised Daily view. Ask RevenueOS adds a safe evidence-backed query
surface. This is a complete active-opportunity loop rather than a collection of
isolated AI features.

The decision is **GO**, not because Core is feature-complete, but because none of its
remaining gaps requires Prospect to change the identity, tenant, Evidence,
Interaction, Revenue Brain, Action or connector foundations. Prospect can add sourced
candidate discovery and reviewed promotion at the edge of those boundaries.

The decision does not waive the private-beta release gate. A supervised partner can
see the product with synthetic data now. Real customer data may enter only an approved
target environment after identity, tenant/RLS, privacy, provider, retention,
export/deletion, backup/restore and operational evidence is signed off. That launch
work proceeds in parallel and can stop partner use without stopping bounded WO-026
engineering.

## Decision basis

The review covered:

- the merged WO-011–025C product, engineering, design, security, decision and sprint
  records;
- the implemented domain, API, web, worker, connector and migration boundaries;
- desktop and 390-pixel mobile inspection of Home/Daily, Accounts, People,
  Interactions, Opportunity, Search/Ask, onboarding, Settings and the Companion;
- deterministic synthetic flows for preparation, evidence review, methodology, Ask,
  Action approval and HubSpot change preview;
- the current private-beta launch checklist and security review; and
- current official Airspeed material for its [platform](https://www.goairspeed.com/),
  [CRM automation](https://www.goairspeed.com/academy/platform/crm-automation),
  [forecasting](https://www.goairspeed.com/ai-sales-forecasting),
  [seller experience](https://www.goairspeed.com/sales-reps) and
  [integrations](https://www.goairspeed.com/integrations).

This was a repository and controlled synthetic-product review, not observed partner
validation or a production HubSpot certification. Local mock-mode observations do not
replace the target-environment evidence required by the
[private-beta launch checklist](../03-engineering/private-beta-launch-checklist.md).

## Core capability matrix

The labels answer whether each capability is strong enough for the next decision,
not whether it is finished forever.

| Capability                   | Classification         | Evidence and decision                                                                                                                                   |
| ---------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Customer interaction capture | **STRONG**             | Multiple Interaction types, deliberate capture choices, passive/no-recording fallback and explicit lifecycle are implemented.                           |
| Transcription                | **SUFFICIENT FOR NOW** | Consent-gated recording/import and provider-neutral transcription exist; target provider enablement and browser limitations remain launch restrictions. |
| Conversation structuring     | **STRONG**             | Reviewed summaries, decisions, actions, risks, questions, signals and provenance form a reusable structured layer.                                      |
| Summaries                    | **STRONG**             | Current-version, source-aware meeting and longitudinal summaries are available with safe unknown/error states.                                          |
| CRM admin                    | **READY**              | One bounded HubSpot link/read/preview/confirm/write/reconcile path exists; it is not general CRM administration.                                        |
| CRM autofill/sync            | **SUFFICIENT FOR NOW** | Selected fields, stages and activities can be reviewed and updated; no silent bulk or bidirectional sync exists.                                        |
| Sales methodology            | **STRONG**             | MEDDIC, MEDDPICC, BANT, SPICED and bounded custom methods use categorical, cited and correctable states.                                                |
| Deal intelligence            | **STRONG**             | Workspace, Revenue Brain, methodology, Evidence and Daily compose a useful account/opportunity picture without false forecast precision.                |
| Risks/blockers               | **STRONG**             | Risks and blockers are extracted, cited, reviewed and carried into deal attention and next-action reasoning.                                            |
| Stakeholder intelligence     | **READY**              | Evidence-backed stakeholder observations and gaps exist; broad external person research belongs to Prospect.                                            |
| Next steps                   | **STRONG**             | Action items, next-best action, methodology gaps and Daily priority converge on clear reviewed next steps.                                              |
| Follow-up preparation        | **READY**              | Follow-up content and reviewed Action proposals exist; sending remains provider-gated.                                                                  |
| Action execution             | **SUFFICIENT FOR NOW** | Approval, preview, confirmation, idempotency and reconciliation are strong; only the selected HubSpot path is production-capable.                       |
| Ask/Q&A                      | **SUFFICIENT FOR NOW** | Ask is permission-scoped, deterministic and citation-safe, but its supported question taxonomy is deliberately narrow.                                  |
| Manager visibility           | **FUTURE CORE WORK**   | No team/manager operating surface exists; this does not block a seller-led design-partner cohort.                                                       |
| Forecasting                  | **FUTURE CORE WORK**   | RevenueOS intentionally exposes no close probability or forecast before stable stage/outcome history.                                                   |
| Coaching                     | **FUTURE CORE WORK**   | Methodology gaps and preparation questions help sellers now; systematic rep coaching needs manager policy and longitudinal outcomes.                    |
| Win/Loss                     | **FUTURE CORE WORK**   | Outcome learning needs a reliable closed-deal lifecycle and sufficient history.                                                                         |
| Onboarding                   | **READY**              | The first-run journey is short, outcome-led, skippable and explains the prepare/capture/review/follow-through loop.                                     |
| Security/trust               | **SUFFICIENT FOR NOW** | Product controls are strong; real-data use remains conditional on target-environment and operational approval.                                          |
| UX simplicity                | **READY**              | Task-first navigation, Daily hierarchy and progressive disclosure make the primary loop understandable; small terminology and admin-polish gaps remain. |
| Mobile usability             | **READY**              | Today, Interactions, Actions and Search form a focused mobile shell; Companion and post-capture flows are usable in a supported foreground browser.     |

There are no **BLOCKER** classifications for starting WO-026.

## Competitive readiness against Airspeed

As of this review, Airspeed publicly positions an end-to-end system that captures
calls, automatically updates Salesforce and HubSpot, coaches representatives,
forecasts, analyses losses, generates pipeline and executes follow-up. RevenueOS does
not have that breadth and must not imply it does.

The wider category sets the same expectation: Gong connects
[conversation intelligence](https://www.gong.io/conversation-intelligence) to deal
risk, coaching, engagement and forecasting, while Clari positions
[captured revenue signals](https://www.clari.com/lp/get-real/) as inputs to CRM
automation, deal inspection, coaching and forecast. These are category breadth
signals, not instructions to copy scoring, surveillance or automatic execution before
RevenueOS has the evidence and permission model to support them.

| Area                               | RevenueOS position           | Consequence                                                                                                                                 |
| ---------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Evidence and trust                 | **Parity-plus**              | RevenueOS makes source, time, conflict, trust state, correction and human review unusually explicit.                                        |
| Face-to-face and no-recording work | **Differentiated**           | Deliberate passive capture, photos, markers and typed debrief support relationship-led field selling without mandatory recording.           |
| Active-opportunity intelligence    | **Competitive**              | Preparation, structured interaction intelligence, methodology, risks, stakeholders, next action, Daily and Ask form a coherent loop.        |
| CRM write-back                     | **Narrower but credible**    | RevenueOS has one review-first HubSpot path; Airspeed claims broad automatic Salesforce/HubSpot population after every call.                |
| Ask                                | **Trustworthy but narrower** | RevenueOS answers bounded current evidence or says it does not know; Airspeed claims natural-language access across calls, email and Slack. |
| Coaching, manager and forecasting  | **Behind by design**         | These remain later Core work because RevenueOS lacks the lifecycle/history needed to make them trustworthy.                                 |
| Win/loss and pipeline generation   | **Behind**                   | These are planned after outcomes and Prospect foundations respectively.                                                                     |
| Automation breadth                 | **Behind but safer**         | RevenueOS requires review and explicit confirmation; mail/calendar and broad autonomous execution are absent.                               |

The product therefore meets the Checkpoint 1 requirement of credible parity on the
active-opportunity loop, with defensible differentiation, while accepting that it is
not yet a broad revenue-execution suite.

## “Finish the meeting. RevenueOS handles the admin.”

**Classification: READY WITH QUALIFICATION.**

The unqualified sentence is too broad. RevenueOS can prepare follow-through, create
reviewable actions and apply a confirmed, allow-listed HubSpot update. It cannot yet
send the follow-up email, update every CRM, infer every field, reconcile arbitrary
objects or operate autonomously.

The honest current claim is:

> Finish the meeting. RevenueOS prepares the follow-through and applies the HubSpot
> update you review and confirm.

To make the shorter claim defensible, Core still needs target-environment HubSpot
OAuth and sandbox proof, measured end-to-end reliability, and at least one approved
mail-delivery path. Those are integration and launch gaps, not a reason to delay
Prospect research foundations.

## Time-to-value and day-to-day usefulness

The value chain is now concrete:

| Moment                   | Expected value                                                           | Checkpoint measure                            |
| ------------------------ | ------------------------------------------------------------------------ | --------------------------------------------- |
| First 5 minutes          | Understand Home and create/open a deal-led first Interaction             | unaided start rate; support prompts           |
| Before first Interaction | Open a useful brief and identify objectives/questions                    | time to useful brief; brief usefulness        |
| Immediately after        | Capture outcomes, review findings and correct unsupported claims         | time to reviewed record; correction rate      |
| Same work session        | Approve a next action and preview/confirm a HubSpot change where enabled | action acceptance/edit; sync success/recovery |
| Next working day         | See one clear priority and ask a supported account/deal question         | Daily return; useful-answer/citation rate     |

Core is useful without Prospect: it helps a seller progress known relationships and
active Opportunities. Prospect should improve the missing upstream job—finding and
qualifying who to engage—without becoming a prerequisite for Daily, Interactions,
Opportunity or Ask.

## Major product and architecture decisions

### 1. Begin Prospect now

**Decision: GO to WO-026.** Keep the modular-monolith, tenant and Evidence boundaries.
WO-026 must create sourced research candidates and a reviewed promotion path; it must
not write unverified findings directly into Company, Contact or Revenue Brain truth.

### 2. Forecasting stays later

Keep forecast in WO-038. Current methodology and deal-risk signals support action,
but do not yet provide stable stage transitions, outcomes, target definitions or a
calibrated history. Moving forecasting earlier would create confidence theatre.

### 3. Coaching stays after analytics/forecast foundations

Keep systematic coaching in WO-039. Current briefs, methodology gaps, suggested
questions and next actions provide seller guidance now. Team comparison, performance
scoring and coaching plans require permissions, manager policy and outcome evidence.

### 4. Manager visibility is not a seller-led beta blocker

Keep the manager surface in WO-039. Validate the buyer and manager jobs during the
design-partner cohort, but do not add a premature dashboard before WO-026. Escalate
only if every viable design partner requires a manager-controlled rollout.

### 5. Win/loss remains tied to outcome history

Keep Win/Loss Learning in WO-036B. Build it after native opportunity lifecycle and
analytics definitions can distinguish reviewed outcomes from anecdotes.

### 6. Analytics and targets stay later

Keep Sales Analytics in WO-036 and Targets in WO-037. Daily and descriptive Pipeline
are sufficient to start seller use. Prospect must first produce trustworthy funnel
events before those layers can be meaningful.

### 7. Salesforce does not block Prospect

HubSpot remains the first supported CRM. Keep Salesforce as the first candidate in
WO-042 expansion, pulled forward only by paid/design-partner evidence. Prospect uses
provider-neutral internal contracts and must not couple research to HubSpot.

### 8. No additional Core work order moves ahead of WO-026

The remaining Core gaps are refinements or data-dependent later layers. Fix small
terminology, settings and reliability issues alongside normal maintenance. Do not
insert another broad Core work order before Prospect.

## Prospect foundation architecture

Prospect does not require a foundational rearchitecture. It reuses:

- verified identity and organisation context, explicit tenant predicates and RLS;
- Company and Contact canonical records and duplicate-safe creation rules;
- Evidence provenance, trust state, freshness, correction and deletion concepts;
- provider interfaces, feature flags, deterministic mocks, quotas and safe audit;
- accepted-fact projection into Revenue Brain and current seller work; and
- Action review/approval/execution separation for any later outreach.

WO-026 must add separate tenant-owned research run, source, finding and promotion
concepts. External observations remain untrusted candidates until reviewed. Source
terms, purpose limitation, prohibited traits, retention, deletion, cost and abuse
controls are provider-selection gates. Prospect must not reuse Ask as an unrestricted
web-research agent or place provider payloads in logs.

## Gap ledger

| Class                     | Gap                                                                                                  | Owner and timing                   | Blocks WO-026?                                 |
| ------------------------- | ---------------------------------------------------------------------------------------------------- | ---------------------------------- | ---------------------------------------------- |
| A — Core before Prospect  | None                                                                                                 | No new Core work order             | No                                             |
| B — Core later            | Forecast, manager visibility, coaching, analytics, targets, win/loss                                 | WO-036/036B/037/038/039            | No                                             |
| C — Prospect              | Sourced company/person research, duplicate-safe promotion, prospect trust UX                         | WO-026–028                         | Defines Stage B                                |
| D — Integrations          | Target HubSpot proof, approved mail delivery, later Salesforce                                       | launch track; WO-029 gate; WO-042  | No for WO-026                                  |
| E — Architecture/security | Target-environment identity/privacy/operations evidence; research provider legal/security assessment | launch track and WO-026 acceptance | Yes for real data, not for bounded engineering |
| F — Validation/learning   | Observed unaided use, Ask usefulness, admin minutes saved, partner willingness to pay                | supervised cohort                  | No; run in parallel                            |

## Design-partner readiness

**Classification: READY WITH RESTRICTIONS.**

Today, a small supervised cohort may use synthetic or approved non-customer data.
Real customer-data use requires every applicable launch gate to be signed off first.
The initial cohort restrictions are:

- named organisations and users in one approved target environment;
- verified Clerk organisation membership and tested tenant/RLS denial;
- approved data authority, notices, retention, export, deletion, backup and restore;
- one explicitly selected capture path plus a no-recording/manual fallback;
- OpenAI, recording and live-provider flags enabled only under the approved policy;
- HubSpot enabled only after OAuth registration, secret injection, sandbox
  connect/revoke, preview/confirm, retry and reconciliation evidence;
- no Salesforce, automatic mailbox ingestion, automatic recording, background mobile
  capture, forecast, manager-coaching or autonomous-action claims;
- visible source/correction/unknown controls and high-touch support with rollback; and
- no production customer data while any mandatory launch item remains unchecked.

Product readiness and launch approval are deliberately separate: failure of a target
environment or partner condition stops that use; it does not authorise weakening the
control or silently broadening the product.

## Claim readiness

| Claim                                                 | Status                   | Required wording or reason                                                                      |
| ----------------------------------------------------- | ------------------------ | ----------------------------------------------------------------------------------------------- |
| “Walk into every customer conversation prepared.”     | **Ready now**            | Supported for prepared RevenueOS Interactions with available context.                           |
| “Know what to do next.”                               | **Ready now**            | Daily, methodology and reviewed next actions support this without claiming certainty.           |
| “Finish the meeting. RevenueOS handles the admin.”    | **Ready with qualifier** | Say it prepares follow-through and applies a reviewed HubSpot update.                           |
| “Keep HubSpot updated without hours of manual entry.” | **Ready with qualifier** | Limited to linked records and supported reviewed fields/activities after setup.                 |
| “Ask RevenueOS anything about your deals.”            | **Ready with qualifier** | Say ask supported questions about authorised RevenueOS evidence; unknown is an expected answer. |
| “Never write meeting notes again.”                    | **Ready with qualifier** | Only for an authorised supported capture path; manual/no-recording fallback remains.            |
| “Know which deals will close.”                        | **Future**               | No forecast or probability exists.                                                              |
| “Coach every rep automatically.”                      | **Future**               | No manager coaching or rep scoring exists.                                                      |

## Next sequence and gates

The recommended sequence is:

1. continue target-environment launch evidence and a supervised Core cohort in
   parallel;
2. authorise and implement WO-026 Account & Lead Research;
3. proceed conditionally through WO-027 Prospect Intelligence and WO-028 Buying
   Committee & Stakeholder Mapping;
4. before WO-029 can send anything, select and approve one mail ecosystem and either
   include its smallest reviewed delivery slice or keep WO-029 draft-only;
5. continue conditionally through WO-029 Personalised Outreach, WO-030 Campaigns and
   WO-031 Event & Trade Show Workflow; and
6. stop at Checkpoint 2 to decide whether Prospect creates trusted, qualified pipeline
   before funding Stage C.

WO-027–031 remain unauthorised until their individual work orders are approved. The
mail gate prevents a planning label from being mistaken for a working integration.

## Measures for the next checkpoint

Measure outcomes rather than feature exposure:

- median time to first useful brief, reviewed Interaction and accepted next action;
- percentage of design-partner journeys completed unaided;
- Evidence/methodology correction rate and unsupported-claim rate;
- Ask supported-answer, valid-citation, correct-refusal and repeated-use rates;
- HubSpot match, confirmation, success, retry, conflict and recovery rates;
- estimated post-interaction admin minutes saved;
- Prospect result usefulness, source trust, duplicate burden and accepted-promotion
  rate;
- partner weekly return, qualitative indispensable moment and willingness to pay; and
- security, privacy, deletion, tenant and support incidents.

## Decision summary

Core is ready to support a focused, supervised seller loop and stable enough to be the
downstream destination for Prospect. Begin WO-026. Keep forecasting, coaching,
manager, analytics, targets and win/loss in their evidence-dependent positions. Keep
HubSpot first. Treat partner launch approval and mail delivery as explicit gates, not
as reasons to re-open the Core architecture.

## WO-026 follow-through — 25 August 2026

The authorised company-only slice is now implemented. It reuses the existing Core
tenant, Company, API and worker foundations while keeping unpromoted Research Targets
and public observations separate from customer Evidence. Explicit Add to Sales uses
exact normalised-domain duplicate handling. No Contact or Opportunity is created.

The provider/legal gate remains open for real data: WO-026 selected no paid or live
provider and added no arbitrary page fetcher. The deterministic mock proves the
complete product and trust lifecycle, but production mock configuration fails closed.
WO-027 decision-maker research and WO-028 ICP/territory/bulk discovery remain
unauthorised until separately approved.
