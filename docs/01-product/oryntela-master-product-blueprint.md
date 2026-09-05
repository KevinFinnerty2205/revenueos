# Oryntela master product blueprint

- **Status:** Authoritative forward-looking product and commercial direction
- **Consolidated:** 4 September 2026 (Australia/Sydney)
- **Implementation name:** RevenueOS remains the current technical/internal name
- **Authority:** Strategy and documentation only; future scope still requires an approved work order

This document governs forward planning for Oryntela. Historical RevenueOS blueprints,
work orders and ADRs remain the record of what was built and why. Where a later
explicit owner or Checkpoint decision changes forward direction, this blueprint
governs the product plan without rewriting that history.

## Executive decision

Oryntela already has enough coherent product breadth to begin supervised customer
validation once the existing real-data launch gate is satisfied. It does not need
another major feature first.

The implemented strength is the connected path from deliberate Interaction capture
to reviewed Evidence, Sales Brain, Methodology, Actions, Pipeline, Targets, Forecast
and Manager Intelligence. Prospect, Engage, Create and Native CRM extend that loop.
The largest gap is not another domain model: it is proving the product in the selected
target environment with a suitable design partner, while keeping unavailable live
providers and commercial readiness accurately labelled.

The immediate owner milestone is **professional Oryntela trade mark clearance
preparation and review** before a broad customer-facing rebrand or public launch.
Safe design-partner discovery may proceed in parallel without receiving customer data.
Target-environment selection and proof remain the controlling technical launch gate.

## What Oryntela is

**Oryntela — The AI operating system for sales.**

Oryntela is an AI teammate for relationship-driven sales teams. Sales Brain turns
authorised customer interactions, sales records and approved organisation context
into source-aware understanding, reviewable actions and explainable commercial
judgement. It complements external CRMs and can also provide an optional, deliberately
simple Native CRM; it is not trying to reproduce Salesforce.

The internal product promise is:

> Oryntela helps sales teams know what matters, know what to do next and spend more
> time selling.

Other internal candidates for customer validation are:

- Turn customer conversations and sales data into the context, actions and forecast
  your team needs to sell.
- Remember what matters across every deal, then help your team follow through.

None is approved public copy. Claims must remain within the actual release boundary.

## Oryntela product invariants

1. Sales Brain stays at the centre.
2. Oryntela does the thinking and organising so the salesperson can do the selling.
3. Evidence and provenance come before assertion.
4. One customer and deal truth is shared across capabilities; no parallel intelligence silos.
5. Tell me what matters, then show me why, then show me everything.
6. Consequential external actions remain subject to explicit authority and review.
7. Unknown, conflicting, stale and inferred information is labelled honestly.
8. Core remains valuable without an add-on.
9. Add-ons expand capability; they do not repair an artificially weakened Core.
10. No employee surveillance, rep ranking or hidden productivity score.
11. No private-life buyer dossier, personality manipulation or creepy profiling.
12. No fabricated ROI, forecast, close date, customer fact or causal claim.
13. No generic workflow builder, BI builder, project manager or document platform.
14. Customer information is entered once where safe reuse is possible.
15. Material third-party variable cost is bounded and commercially sustainable.

See [Oryntela product principles](oryntela-product-principles.md) and
[simplicity principles](../02-design/oryntela-simplicity-principles.md).

## Target customer and users

The first validation target is an Australian, relationship-led B2B sales team with
roughly 3–15 sellers, an accessible founder or sales leader, recurring meaningful
sales conversations and visible pain in follow-through, CRM administration,
opportunity visibility or sales rhythm. The first active cohort should be 3–5 users.

The seller needs a clear day, better preparation, easier capture and trustworthy
follow-through. The manager needs evidence-backed deal and forecast conversations,
not surveillance. The administrator needs safe setup, import, permissions, retention
and support operations outside the selling flow.

The first partner must be able to test Native CRM and the reviewed meeting-to-action
loop without depending on Gmail, Apollo, recording, live transcription, SSO/SCIM,
autonomous action or a native mobile app.

## End-to-end workflow

```text
FIND -> UNDERSTAND -> ENGAGE -> INTERACT -> EVIDENCE -> ACT
  -> MANAGE THE DEAL -> TARGET / FORECAST -> CREATE -> WIN / LEARN
```

| Moment     | Oryntela responsibility                                           | Current truth                                                                     |
| ---------- | ----------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| Find       | Prospect target markets, account and professional person research | Workflow built; deterministic provider by default; no approved live data provider |
| Understand | Sales Brain, Revenue Brain, Evidence, Methodology and Ask         | Built in bounded forms                                                            |
| Engage     | Personalised one-to-one outreach, Campaigns and Events            | Draft/review/governance built; delivery is simulation-only                        |
| Interact   | Prepare, deliberately capture, debrief and review                 | Built across bounded manual/browser paths; background/native capture absent       |
| Act        | Review, approve and complete internal Actions                     | Built; approval does not silently execute externally                              |
| Manage     | Native CRM, Opportunity Workspace and Pipeline                    | Built; focused HubSpot path exists but target production proof is separate        |
| Measure    | Analytics, Targets, Forecast and Manager Intelligence             | Built as deterministic, non-surveillance Core capability                          |
| Create     | Approved-template PPTX and deterministic Business Cases           | Built and trust-hardened; no general proposal/CPQ engine                          |
| Learn      | Immutable history, corrections, Win/Loss and forecast outcomes    | Built in bounded form; customer value remains unvalidated                         |

## Product architecture

### Core experience

- Home / Daily
- Accounts and People
- Interactions and Evidence
- Opportunities and Pipeline
- Actions
- Search / Ask Oryntela
- Insights

### Core intelligence

- Sales Brain and Revenue Brain
- Methodology
- Meeting and Interaction Intelligence
- Next Best Action
- Sales Analytics and Win/Loss
- Targets
- Transparent Forecast
- Manager Intelligence

### Expansion modules

| Module   | Owns                                                                    | Does not own                                                    |
| -------- | ----------------------------------------------------------------------- | --------------------------------------------------------------- |
| Prospect | Net-new account/person research, Target Markets and safe promotion      | Saved Accounts, customer Evidence or buyer intent truth         |
| Engage   | Reviewed outreach, bounded Campaigns, sequences and Event follow-up     | Customer truth, uncontrolled sending or open/click surveillance |
| Create   | Approved-template presentations and deterministic Business Cases        | Pricing authority, customer acceptance or invented claims       |
| CRM      | Supported external CRM connectors over the Core-native sales graph       | Native CRM, Sales Brain, a second shell or Salesforce parity    |

`Core`, `Growth`, `Complete` and `Enterprise` are commercial **plans**. Prospect,
Engage, Create and CRM are product **modules**. Core is also the name of the product
foundation; context must make the distinction explicit. Complete is a plan, not a
separate module.

## Capability and readiness truth

| Capability                                         | Status                                                 | Provider needed for offered value?                  | Target proof?                  | Validation needed?                                   |
| -------------------------------------------------- | ------------------------------------------------------ | --------------------------------------------------- | ------------------------------ | ---------------------------------------------------- |
| Sales Brain, Evidence, Methodology, Actions, Ask   | **BUILT**                                              | Optional external AI for selected generation        | Yes for real data              | Yes                                                  |
| Home / Daily                                       | **BUILT**                                              | No                                                  | Yes                            | Yes; test whether target/forecast context is missing |
| Native CRM and Pipeline                            | **BUILT**                                              | No                                                  | Yes                            | Yes                                                  |
| Analytics, Targets, Forecast, Manager Intelligence | **BUILT**                                              | No                                                  | Yes                            | Yes                                                  |
| Interaction capture and intelligence               | **BUILT — LIVE PROVIDER/DEPLOYMENT NOT YET ACTIVATED** | Only for production external AI/transcription paths | Yes                            | Yes                                                  |
| Prospect                                           | **BUILT — LIVE PROVIDER NOT YET ACTIVATED**            | Yes for real research/data coverage                 | Yes                            | Yes                                                  |
| Engage                                             | **BUILT — LIVE PROVIDER NOT YET ACTIVATED**            | Yes for mailbox delivery/reply                      | Yes                            | Yes                                                  |
| Create                                             | **BUILT**                                              | No for current PPTX/Business Case path              | Yes, including storage/restore | Yes                                                  |
| Focused HubSpot connector                          | **BUILT — TARGET PROVIDER PROOF NOT YET COMPLETE**     | Yes                                                 | Yes                            | Yes if selected                                      |
| Company & Selling Profile                          | **BUILT — WO-046**                                      | No                                                  | Later                          | Yes                                                  |
| Commercial plan, trial, entitlement and test billing | **BUILT — WO-047/048; LIVE BILLING NOT ACTIVATED**     | Stripe only for later live payments                 | Yes before activation          | Yes                                                  |
| What Changed                                       | **VALIDATE WITH DESIGN PARTNER**                       | No new truth provider                               | Later                          | Yes                                                  |
| SMS                                                | **FUTURE / PROVIDER CANDIDATE**                        | Yes                                                 | Later                          | Yes, plus legal/economics                            |
| Native mobile/background recording                 | **FUTURE**                                             | Platform/provider dependent                         | Later                          | Yes                                                  |
| Files expansion                                    | **FUTURE / VALIDATE FIRST**                            | Not necessarily                                     | Later                          | Yes                                                  |
| AI voice/SDR                                       | **FUTURE**                                             | Yes                                                 | Later                          | Yes, plus legal/economics                            |

A capability may be built while not commercially live. Real customer use additionally
requires approved deployment, legal/privacy position, feature profile, support and a
named partner. A deterministic mock proves contracts, not provider quality or market
value.

## Brand readiness

| Item                                             | Status                                                |
| ------------------------------------------------ | ----------------------------------------------------- |
| ORYNTELA business name                           | **REGISTERED**                                        |
| `oryntela.com` and `oryntela.com.au`             | **OWNED**                                             |
| `kevin@`, `hello@` and `support@oryntela.com.au` | **ACTIVE; SYNTHETIC ROUTING VERIFIED**                |
| Professional trade mark clearance                | **PENDING; NO CLEARANCE CLAIM**                       |
| Trade mark application                           | **NOT FILED**                                         |
| Customer-facing technical rebrand                | **NOT STARTED; NOT AUTHORISED BY THIS CONSOLIDATION** |
| Public Oryntela website                          | **NOT ESTABLISHED BY THE REPOSITORY**                 |

Professional advice is needed to decide whether clearance is required before a
private branded design partnership or only before broader public/commercial launch.
That is an owner/legal decision, not a conclusion this document makes.

## Commercial authority and validation hypothesis

The following is an **owner-approved immutable V1 internal catalogue** implemented as
server commercial authority. It remains for validation and is not public pricing.
WO-048's test billing consumes these exact figures without making them a live offer:

| Plan       |          Monthly |      Annual prepay | Included-user hypothesis |
| ---------- | ---------------: | -----------------: | -----------------------: |
| Core       | AUD $200/company | AUD $2,000/company |                  Up to 5 |
| Growth     | AUD $350/company | AUD $3,500/company |                 Up to 10 |
| Complete   | AUD $500/company | AUD $5,000/company |                 Up to 15 |
| Enterprise |           Custom |             Custom |               Contracted |

The annual figures are equivalent to approximately two months free. Growth is Core +
Prospect + Engage; Complete adds Create and supported external CRM connectors. Native
CRM remains Core. Add-on prices, extra-user bands, GST presentation and live billing
activation remain undecided. Stripe is the implemented but unactivated first
test-adapter candidate. See [pricing](../04-commercial/oryntela-pricing-hypothesis.md)
and [packaging](../04-commercial/oryntela-packaging-hypothesis.md).

## Trial and Credits

The implemented authority supports one explicitly started 14-day Complete-profile
trial, no card and no automatic charge. The exact end begins a 30-day read/export
grace period; the exact grace end expires access without deleting data. Test checkout
is an explicit choice and verified payment can convert the same organisation without
data loss. Self-service public trial is not ready: signup, live billing activation,
abuse controls, provider-cost protection, legal approval and production operations
remain prerequisites.

The subscription pays for Oryntela software. Prepaid **Oryntela Credits** may fund
material third-party variable-cost operations such as paid enrichment, verification,
SMS, telephony or expensive external generation. Normal Core use and customer-mailbox
email sending without material Oryntela unit cost should not feel metered. Credits
must never go negative, auto-top-up by default or double-charge a retry, and must
produce positive gross margin. WO-048 reserves an idempotent payment-operation type.
WO-049 implements the provider-neutral ledger, balance, quote/reservation,
settlement/reconciliation and TEST-only purchase machinery needed to validate that
safety model. It activates no production Credit price or pack, live billing sale, or
metered external provider.

## Future opportunities

Highest-leverage validation candidates are Company & Selling Profile, What Changed,
meeting-to-meeting continuity, follow-through completeness and evidence-backed
customer commitments. These compose existing Evidence, history and Actions before
adding new product domains. Home target/forecast context is a small UX hypothesis,
not a new analytics engine.

SMS, native mobile, Files and AI voice remain later directions with explicit entry
criteria. See [future opportunities](oryntela-future-product-opportunities.md) and
[do-not-build register](oryntela-do-not-build-register.md).

## First design-partner validation

The first partner should validate whether:

- Home is the natural starting point and target progress is visible enough;
- Sales Brain saves material preparation and administration time;
- deliberate Interaction capture is easy enough without hidden recording;
- Evidence, Methodology, Actions and Ask are trusted and correctable;
- Native CRM and Pipeline are sufficient for the selected small team;
- Forecast and Manager Intelligence improve real review conversations;
- Create saves enough work and remains customer-safe;
- Oryntela understands enough about what the partner sells; and
- the team would be meaningfully disappointed if Oryntela disappeared.

The current launch state remains **WAITING FOR TARGET ENVIRONMENT PROOF**. Before any
real partner data, the existing owner/legal, target, named-partner, support, retention,
feature-profile and provider gates must pass. Discovery conversations may proceed;
data receipt or entry may not.

## Roadmap and dependency rule

```text
Professional brand clearance -> controlled customer-facing rebrand decision
Target selection -> target proof -> supervised real-data partner
Design-partner evidence -> pricing/packaging decision -> private paid beta
Live Prospect -> provider + licensing/privacy + Credits economics
Live Engage -> mailbox/OAuth + sender/reply/reconciliation + suppression operations
SMS -> business phone/contactability + provider + compliance + Credits
Public trial -> self-service + billing/trial state + abuse/cost controls + operations
```

No dates or automatic work-order sequence are implied. Customer evidence, trust and
milestone blockers outrank feature enthusiasm.

## Current next step

**The next thing recommended is professional Oryntela trade mark clearance
preparation and review.**

Why: Oryntela is selected, registered as a business name and supported by owned
domains and active email, but none of those establishes freedom to use or
registrability as a trade mark. Clearance reduces the risk of investing in a
customer-facing rebrand and partner material under a name that later needs changing.

What it unlocks: an informed owner decision on customer-facing Oryntela use, followed
by a controlled rebrand scope and safer design-partner/public material.

What should not start yet: technical rebrand, public price publication, live billing,
Credits, SMS, AI SDR, Files, native mobile, Apollo, mailbox activation or WO-040.
Safe design-partner discovery may run in parallel without customer data, while the
owner separately resolves target-environment and launch-gate decisions.

## What would make Oryntela difficult to live without?

Not more features. Oryntela becomes indispensable when it reliably remembers the
evidence and commitments that matter, makes the next action obvious, carries context
from one interaction to the next, and removes administration without taking authority
away from the seller. The defensible experience is connected, fast, explainable and
trusted every day.

## Canonical detail

- [Executive product map](oryntela-executive-product-map.md)
- [Product principles](oryntela-product-principles.md)
- [Company & Selling Profile concept](oryntela-company-selling-profile-concept.md)
- [Future opportunities](oryntela-future-product-opportunities.md)
- [Do-not-build register](oryntela-do-not-build-register.md)
- [Commercial handoff](../06-roadmap/oryntela-commercial-product-handoff.md)
- [Owner-note reconciliation](../06-roadmap/oryntela-owner-notes-reconciliation.md)
- [Post-partner roadmap](../06-roadmap/oryntela-post-design-partner-roadmap-framework.md)
- [First design-partner launch gate](../06-roadmap/first-design-partner/first-design-partner-launch-gate.md)
