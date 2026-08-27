# Prospect and Engage product readiness

- **Status:** Checkpoint 2 product and commercial decision
- **Decision:** Keep Prospect and Engage; proceed to WO-032 Create
- **Read with:** [Checkpoint 2 decision](../06-roadmap/checkpoint-2-prospect-engage-validation.md)

## Product judgement

Prospect and Engage now form one understandable top-of-funnel workflow:

1. define a Target Market or research a known company;
2. understand why the Account and relevant people may matter;
3. inspect sources, trust and unknowns;
4. explicitly save the Company and Contact;
5. create one reviewed, source-backed message or a bounded Campaign;
6. use an authorised Event list to prepare and follow up deliberately; and
7. capture an actual Interaction before anything becomes customer Evidence.

The implementation is useful enough to keep and the boundary is safe enough for
Create to consume. It is not ready for unsupervised commercial use because its
research and mailbox edges are deterministic mocks.

## Product promises

### Prospect

Prospect helps a relationship seller answer three questions:

- Which companies fit the market we deliberately chose?
- Which relevant professionals may participate, and why?
- Which facts are supported, provider-supplied, inferred or still unknown?

Its product value is responsible research connected to action, not an enormous
contact database. A selected result remains staged until the seller promotes it. That
promotion preserves source provenance and does not create an Opportunity, buying
signal, Stakeholder, Methodology state or customer Evidence.

### Engage

Engage helps the seller turn an approved Contact into a legitimate conversation:

- use eligible source-backed account/person context and approved seller context;
- show why the message was created;
- review the exact recipient, sender and copy;
- apply contactability, permission, suppression, frequency and scheduling policy;
- stop when the relationship state changes; and
- connect a later deliberate Interaction to Core.

Engage is not a marketing-automation suite. Its useful first shape is individual
outreach, small four-step Campaigns and authorised Event preparation/follow-up.

## Quality and seller-trust assessment

| Quality dimension               | Assessment                                                                                                                                                                   |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Company identity and duplicates | Domain/name normalisation plus explicit duplicate-safe promotion are sufficient for the current staged-to-canonical path; live-provider false-merge rates remain unmeasured. |
| Research freshness              | Runs and observations are versioned and dated, contact points expire and stale sources are revalidated before outreach; provider refresh coverage remains a live gate.       |
| Source quality                  | Verified requires primary/official/regulatory support; provider data stays provider-supplied and unknown remains visible.                                                    |
| Current employment              | People remain company-scoped and the current role is a sourced observation; provider-backed job-change/conflict quality must be tested before availability claims.           |
| Professional-only rapport       | Eligible activity is work-relevant, public/permitted and source-backed. Private life, personality and fake familiarity are excluded.                                         |
| Contact trust                   | Source, verification state, observation/expiry and permission are separate. Inferred/unknown addresses cannot send.                                                          |
| Buying Committee honesty        | Roles are labelled hypotheses needing validation; they do not become canonical Stakeholders or customer Evidence.                                                            |

The principal trust weak spots are operational: unproven live-provider freshness and
coverage, the Company-before-Contact recovery dead end and Campaign/mock fixture
inconsistency. The underlying truth model is strong.

## Jobs replaced

| Today’s seller job                                       | Prospect/Engage replacement                                                                    | Current proof                            |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------- |
| Maintain ICP and territory spreadsheets                  | Versioned Target Markets with bounded criteria, exclusions and reproducible runs               | Implemented with synthetic data          |
| Search many company/profile pages and copy notes         | Sourced Account/Person briefs with trust and missing-state labels                              | Implemented with synthetic data          |
| Guess whether a contact point is reliable                | Field-level business-contact source, trust, expiry and separate permission                     | Implemented with synthetic data          |
| Copy research into ChatGPT, then copy a draft into email | Server-selected sources, approved seller context and exact outreach review                     | Implemented; external email unavailable  |
| Track a short sequence and suppressions in a sheet       | Immutable bounded Campaign, schedule, collision, suppression and stop controls                 | Implemented with Mock Email              |
| Reconcile a trade-show CSV manually                      | Authorised preview/mapping, conservative matching, categorical priority and explicit promotion | Implemented; no event-platform connector |

## Why the connected experience matters

Apollo, ZoomInfo, Clay, LinkedIn Sales Navigator, Outreach, Salesloft, HubSpot and Gong
each cover substantial parts of research, engagement or interaction intelligence.
RevenueOS should not claim broader data or automation. Its distinctive product bet is
the full trust path:

`public/professional source → staged research → canonical relationship → reviewed
outreach → deliberate interaction → customer Evidence → Revenue Brain`

That path is more valuable than standalone ChatGPT plus spreadsheets when the seller
cares about traceability, correction, permission and preserving what the customer
actually said. It is also meaningfully narrower than a mature sales-engagement or
data platform, which should be stated honestly.

## Package boundary

| Package  | Owns                                                                                                                                                              | Does not own                                                    |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Core     | Sales Brain, Daily, Methodology, Intelligence, Workspace, Ask, focused CRM integration and the canonical Company/Contact/Opportunity/Interaction/Evidence domains | Provider-backed discovery or campaign execution                 |
| Prospect | Target Markets, staged account/person research, sources/trust and promotion workflow                                                                              | Canonical relationship truth, outreach or customer Evidence     |
| Engage   | Contact-based outreach, Campaigns, Event prep/follow-up and execution policy                                                                                      | Public research domain, canonical Contacts or customer Evidence |
| Create   | Templates, approved content and customer-specific generated assets                                                                                                | Prospect/Engage data ownership or deterministic ROI calculation |
| CRM      | Future native lightweight system-of-record administration inside Sell and Pipeline                                                                                | A separate product shell or ownership of Revenue Brain          |

Events remain in Engage because attendee import, planning and follow-up are engagement
jobs. When an Event produces a deliberate Interaction, its accepted Evidence and
Revenue Brain value belong to Core. That boundary should feel like one workflow, not
an entitlement seam.

Current module gating is tasteful: unavailable capabilities are contextual, Core
remains usable and there is no hardcoded price or aggressive modal. Preserve one calm
**Learn more** action at a relevant workflow boundary; do not fill navigation or
results with locked controls.

## Time-to-value target

With an approved provider and representative coverage, the first design-partner
targets should be:

- known-account research: useful sourced brief within five minutes;
- new Target Market: guided setup and first explainable candidates within ten minutes;
- relevant-person brief and first reviewed outreach draft: within a further five
  minutes; and
- bounded Event CSV: preview, mapping, authority confirmation and first priorities
  within ten minutes for a clean file.

These are validation targets, not current marketing claims. Current synthetic runs
show the interaction pattern, while live latency, match rate and provider coverage are
unmeasured.

## Readiness by use mode

| Use mode                                 | Readiness                   | Product boundary                                                                        |
| ---------------------------------------- | --------------------------- | --------------------------------------------------------------------------------------- |
| Synthetic product demonstration          | **READY**                   | Full workflow with conspicuous mock labels and no provider calls                        |
| Supervised real customer-data evaluation | **READY WITH RESTRICTIONS** | Only after target-environment approval; live research/email remain separately gated     |
| Unsupervised paid product                | **NOT READY**               | Provider, operational, legal/compliance, reliability and support evidence is incomplete |

## Claims register

### READY NOW

- RevenueOS keeps public prospect research separate from customer Evidence.
- Sellers can inspect the source and trust state behind a synthetic research brief.
- Every outreach simulation is reviewable by recipient, sender, content and source.
- Event attendance does not automatically become consent, intent or a canonical
  Contact.

### READY WITH QUALIFIER

- RevenueOS can find and research target Accounts and relevant professionals **when an
  approved provider is enabled; current demonstrations use synthetic provider data**.
- RevenueOS can create source-backed individual outreach and bounded Campaigns
  **while current execution is Mock Email and external sending requires a supported
  mailbox**.
- RevenueOS can help sellers prepare for and follow up after Events **from an
  authorised manual/CSV source, not a live event-platform integration**.

### FUTURE

- automatic prospecting or autonomous outreach;
- production Gmail/Microsoft, data-provider or event-platform claims;
- automatic reply/delivery analytics;
- verified buyer intent or guaranteed contact/reply accuracy; and
- any claim that RevenueOS replaces established data or sales-engagement platforms on
  breadth.

## Product gaps to carry forward

- Activate and validate one responsible Prospect provider before real research use.
- Implement one partner-led mailbox slice before external Engage use.
- Add a direct **Save Company first** recovery path from person promotion.
- Rename pre-run **Research queued** states to **Ready to research**.
- Resolve hard-navigation fetch instability before supervised product sessions.
- Keep review-each-send as the first live Campaign policy even though bounded
  auto-send exists.
- Measure replies, meetings, Opportunities, opt-outs and halts; do not add open/click
  tracking as a substitute for outcome evidence.

These gaps do not require a new domain foundation before WO-032.
