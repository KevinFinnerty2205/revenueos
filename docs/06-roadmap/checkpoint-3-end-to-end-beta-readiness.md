# Checkpoint 3 — End-to-end product and beta readiness

- **Decision date:** 30 August 2026
- **Branch:** `docs/checkpoint-3-end-to-end-beta-readiness`
- **Reviewed baseline:** `3e548b8fe279f6b33fbbbb09b963d6b75f8b429e`
- **Baseline parity:** local `HEAD`, `main` and `origin/main` matched before review
- **Database head:** `0048_manager_intelligence`
- **Decision:** **OPTION 3 — insert targeted pre-WO-040 work orders**
- **WO-040 status:** **Do not begin**
- **Review data:** synthetic only; local mock identity and deterministic providers

## Executive verdict

RevenueOS now feels like one product often enough to validate the product thesis. The
strongest path is Interaction → reviewed Evidence → Revenue Brain → Methodology →
Action → Opportunity → Pipeline → Actual/Target/Forecast → manager discussion. Sales
Brain remains the centre; CRM has not displaced it. The product is already more
coherent than its feature count suggests, and the transparent separation of facts,
reports, assumptions, calculations and judgments is a genuine strength.

It is not ready for real design-partner data or external sending. Three gate failures
are too serious to defer into a broad connector sprint:

1. hard navigation and refresh intermittently leave major pages at `Failed to fetch`
   even while every underlying API request returns `200`; post-interaction capture,
   Opportunity Workspace, Create and Event are among the affected flows;
2. the tested Create review state did not match the downloaded PPTX: Business Case
   claims appeared in the review manifest but not in the editable file, and the source
   title slide retained the wrong executive name; and
3. the operational launch boundary remains unproved: target-environment identity and
   RLS, restore, retention/deletion, support/incident handling, provider approval and
   current production dependency remediation are not signed off.

There are also two trust defects in the flagship journey: researched email was dropped
during Contact promotion and a subsequent manual edit displayed as Provider Supplied;
and Opportunity close/date mutations produced dropped or stale UI state. These are not
cosmetic. They undermine the provenance and system-of-record contract.

The safe next move is to stop adding breadth, complete WO-039A–039C below, then test the
product with humans. After those gates, move the narrow Gmail delivery slice ahead of
the broader Microsoft work. The product is ready to move from feature building to
supervised product testing with synthetic data; it is not ready to move real customer
data or commercial messages through production.

## Readiness language

These terms are deliberately separate:

| Term                 | Meaning in this review                                                                       |
| -------------------- | -------------------------------------------------------------------------------------------- |
| **Operational**      | The current deterministic/local capability can be exercised end to end.                      |
| **Foundational**     | Domain, tenancy, contracts and safety boundaries are credible.                               |
| **Coherent**         | The capability fits the Sales Brain workflow and user language.                              |
| **Full**             | The promised beta proposition is present, including required real-world boundary capability. |
| **Productised**      | A normal customer can configure, recover and use it without repository/API intervention.     |
| **Integrated**       | A selected external provider has passed live connect, use, reconcile and revoke evidence.    |
| **Production-ready** | Target-environment security, privacy, operations and dependencies are approved.              |

| Proposition                        | Operational     | Foundational | Coherent      | Full                  | Productised       | Integrated                         | Production-ready |
| ---------------------------------- | --------------- | ------------ | ------------- | --------------------- | ----------------- | ---------------------------------- | ---------------- |
| Core / Sales Brain                 | Yes, synthetic  | Yes          | Mostly        | No                    | No                | HubSpot foundation only            | No               |
| Prospect                           | Mock only       | Yes          | Yes           | No live source        | No                | No                                 | No               |
| Engage                             | Simulation only | Yes          | Yes           | No mailbox            | No                | No                                 | No               |
| Create Business Case               | Yes             | Yes          | Yes           | Mostly                | Needs admin setup | Not required                       | No               |
| Create Presentation                | Partly          | Mostly       | Review UI yes | No                    | No                | Not required                       | No               |
| Native CRM/Pipeline                | Yes             | Yes          | Mostly        | No import/merge admin | No                | Native mode; HubSpot unproved live | No               |
| Analytics/Targets/Forecast/Manager | Yes             | Yes          | Yes           | Appropriate v1        | Nearly            | Not required                       | No               |

## Design-partner status

| Cohort                                               | Status                      | Exact boundary                                                                                                                                                        |
| ---------------------------------------------------- | --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A. Synthetic demo**                                | **READY WITH RESTRICTIONS** | Supervised local/demo use; avoid representing Create export as faithful until manifest/output equivalence is fixed; retry/navigation failures may interrupt the demo. |
| **B. Supervised design partner, synthetic data**     | **READY WITH RESTRICTIONS** | Suitable for observed usability and value testing with no production promises, external sends or customer content.                                                    |
| **C. Supervised design partner, real customer data** | **NOT READY**               | Blocked by production identity/RLS evidence, operations, dependency advisories, retention/deletion approval, provenance defects and selected-provider approval.       |
| **D. Unsupervised beta**                             | **NOT READY**               | Also blocked by UI recovery/reliability, customer onboarding/import, support and provider reconciliation.                                                             |
| **E. Commercial beta**                               | **NOT READY**               | Also needs terms/privacy/DPA, launch-region review, billing/commercial operations and advertised-module release evidence.                                             |

## Review method and limitations

This was an actual local product review, not a document-only assessment. It included:

- all specified checkpoint, WO-023–039, product, IA, packaging, provider, security,
  beta and WO-040–045 roadmap material;
- desktop browser use and a 390 × 844 mobile pass;
- one synthetic Northstar flagship Account and decision maker;
- mock Prospect research, governed outreach simulation, Interaction preparation and
  debrief, Evidence acceptance, Revenue Brain update, Opportunity/Pipeline, approved
  Business Case, generated PPTX, Analytics, Target, Forecast, manager perspective,
  Campaign and Event/person-to-person Interaction;
- a temporary local scale fixture of 1,000 Accounts, 5,000 Contacts, 1,000
  Opportunities and 10,000 Interactions, removed immediately after measurement; and
- repository validation, dependency/security review and PostgreSQL/RLS/migration gates.

No paid service was activated, no external provider was called or mutated, and no
production/customer data was used. Production deployment, real OAuth, deliverability,
backup restoration and multi-user observed behaviour cannot be proven from this local
checkpoint and remain explicit gates.

## Flagship journey result

Synthetic target: **Northstar Facilities Group**, decision maker **Jane Smith, CIO**,
Opportunity **Northstar multi-site access pilot**.

| Journey step                   | Result                            | Product evidence and friction                                                                                                                                                                                                      |
| ------------------------------ | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Find and research company      | Pass                              | Sourced observations clearly separated verified, inferred and unknown state.                                                                                                                                                       |
| Research decision maker        | Pass                              | Role hypothesis and business contact points were sourced; permission remained `not assessed`.                                                                                                                                      |
| Add Company and Contact        | Needs refinement                  | Trying Contact first ended in an alert with no direct recovery action. Company promotion worked. Contact promotion dropped the researched email.                                                                                   |
| Inspect Account/Contact        | Blocker                           | After manually restoring the email, the UI labelled it Provider Supplied. Contact had duplicated primary headings and exposed `Unconfigured CRM mode`.                                                                             |
| Prepare/review outreach        | Pass                              | Specific, concise copy; Why this message linked source context and kept research distinct from customer Evidence.                                                                                                                  |
| Execute outreach               | Pass within current boundary      | Explicit Mock Email simulation; no external action; simulated receipt and cooldown were visible.                                                                                                                                   |
| Create and prepare Interaction | Pass with friction                | Onboarding acknowledgement initially blocked the brief without a direct recovery link. After acknowledgement the 40% completeness and evidence limits were honest.                                                                 |
| Capture what happened          | Blocker in UI; API path completed | Completing the Interaction led to generic post-interaction/Companion failures while the APIs stayed healthy. The bounded typed debrief completed through the same product APIs.                                                    |
| Review/accept Evidence         | Needs refinement                  | Three concise answers produced 13 review candidates, with the same sentence repeated across several categories. All remained clearly `Reported by you`, but review volume inflates evidence and is too heavy for a normal rep.     |
| Revenue Brain                  | Pass                              | Accepted seller-reported Evidence updated the Interaction and Revenue Brain without becoming customer-direct truth.                                                                                                                |
| Methodology                    | Pass                              | Unknown economic buyer, procurement and budget stayed gaps rather than invented completion.                                                                                                                                        |
| Action                         | Pass                              | The security-summary follow-up was concrete and remained a reviewed Action, not autonomous mutation.                                                                                                                               |
| Create Opportunity             | Needs refinement                  | Expected close date entered as 30 October was saved as `Not set`; record/workspace headings and CRM context were duplicated.                                                                                                       |
| Pipeline and stage             | Pass with reliability risk        | Board was understandable, currency-safe and descriptive. Some rich-workspace sections failed to fetch.                                                                                                                             |
| Business Case                  | Pass                              | Deterministic base result preserved a negative first-year case: 240 hours saved, AUD 13,200 labour savings, AUD 61,000 cost, AUD -47,800 net benefit and -78.36% ROI. Conservative/upside and source origins were clear.           |
| Approve Business Case          | Pass                              | Approval and assumptions were explicit; calculation never became customer truth.                                                                                                                                                   |
| Create branded Presentation    | Blocker                           | Review exposed 10 slides/18 claims and Business Case material, but the exported editable PPTX retained source text and the wrong executive name. See Create review below.                                                          |
| Analytics                      | Pass                              | Funnel, stage duration, sales cycle, follow-on and seller-reported Win/Loss were understandable and avoided generic BI.                                                                                                            |
| Targets                        | Pass                              | Personal and organisation Targets remained separate; organisation progress did not become a rep leaderboard.                                                                                                                       |
| Seller Forecast                | Pass                              | Commit/Likely/Possible categories remained judgment without probability.                                                                                                                                                           |
| Manager Forecast/Intelligence  | Pass                              | Independent immutable manager perspective and deterministic deal conditions; no hidden final number, score or people ranking.                                                                                                      |
| Close Won                      | Needs refinement                  | Close completed, but the top record stayed Open/discovery until refresh while the workflow section showed Closed Won.                                                                                                              |
| Actual/Forecast after close    | Pass                              | Actual increased from AUD 370,000 to AUD 465,000; personal Target progress became 46.5% and organisation progress 62%. The closed Opportunity left the open forecast while seller, manager and baseline semantics remained intact. |
| Historical coherence           | Pass with UI risk                 | Closure and forecast history remained; stale multi-component rendering can temporarily present contradictory state.                                                                                                                |

The system loop exists. The dominant weakness is no longer missing domain capability;
it is dependable presentation of the state the system already has.

## Product coherence and Sales Brain centrality

**Does it feel like one product?** Mostly. Shared Account/Contact/Opportunity identity,
provenance, Evidence and Actions make the modules reinforce one another. Prospect
promotes into Sell; Engage starts from reviewed context; Event creates an Interaction;
Business Case and presentation attach to the Opportunity; Analytics/Forecast close the
loop. This is materially simpler than moving data among six disconnected tools.

**Is Sales Brain still the centre?** Yes. Opportunity remains the deal workspace, and
users can see what was reported, what is unknown, methodology gaps, Actions, forecast
judgments and sources without entering an admin-first CRM. Native CRM adds record
administration but does not own intelligence. This gate passes.

The experience does, however, fragment under failure. A coherent information
architecture cannot compensate for a hard-loaded Opportunity, Interaction or Event
that stops at a generic error. Duplicate record/workspace summaries also make the
product feel assembled from components rather than deliberately composed.

## Simplicity scorecard

| Area         | Result                                     | Least-technical-seller assessment                                                                                           |
| ------------ | ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| Home         | **NEEDS REFINEMENT**                       | Clear top-priority concept, but mobile repeats `Deals needing attention` with different content and the page is dense.      |
| Accounts     | **NEEDS REFINEMENT**                       | Purpose is clear; CRM mode/custom-field/source language appears before a seller needs it.                                   |
| People       | **BLOCKER**                                | Promotion recovery is weak and manually entered email can be mislabelled Provider Supplied.                                 |
| Interactions | **BLOCKER**                                | List/detail hard loads fail intermittently; 20+ cards create a long mobile scroll; post-interaction recovery is not useful. |
| Pipeline     | **NEEDS REFINEMENT**                       | Board is strong; large unpaginated payload and duplicate Opportunity state need hardening.                                  |
| Search / Ask | **NEEDS REFINEMENT**                       | Search is understandable and cited Ask is safe, but successful intent matching is too phrase-sensitive.                     |
| Insights     | **PASS desktop / NEEDS REFINEMENT mobile** | Actual/Target/Forecast perspectives are unusually clear; mobile tabs hide Targets and Forecast from normal discovery.       |
| Prospect     | **NEEDS REFINEMENT**                       | Research is trustworthy and clear; promotion flow requires technical recovery and remains mock-only.                        |
| Engage       | **PASS within simulation boundary**        | Review/suppression language is strong and avoids marketing-automation complexity. No real mailbox proposition yet.          |
| Create       | **BLOCKER**                                | Business Case is simple enough; template administration requires expert knowledge and review/download can disagree.         |
| Settings     | **NEEDS REFINEMENT**                       | Correctly separated from seller work, but onboarding recovery and provider/admin concepts require guided setup.             |
| Events       | **NEEDS REFINEMENT**                       | Desktop attendee workflow is coherent; direct load/mobile reliability is poor.                                              |

A new rep can learn the happy-path basics from the UI, but cannot be expected to
diagnose unrecoverable fetch failures, provenance drift or template compatibility.
A manager can understand Targets, Forecast and deal attention without training more
readily than a seller can complete the full capture/Create path.

## Navigation review

Desktop IA remains directionally correct. Home, Find, Accounts, People, Interactions,
Pipeline, Insights, Studio, Search and Settings have clear jobs. Campaigns and Events
appear contextually when enabled. Manager Intelligence correctly lives inside Home,
Pipeline, Insights and Opportunity rather than creating a second manager product.

Do not rewrite navigation. Make three narrow changes:

1. preserve the mobile Today/Interactions/Actions/Search bar, but provide an accessible
   `More`/menu route to Accounts, Pipeline, Insights, Create, Find and enabled add-ons;
2. keep Targets and Forecast discoverable within mobile Insights rather than clipped
   from the visible tab set; and
3. use one Opportunity record summary and one workspace hierarchy, removing duplicate
   primary headings and duplicated CRM/workspace facts.

Prospect/Find, Create, Campaign and Event render acceptably when reached by deep link,
but deep-link capability is not discoverability. Search/Ask language is reasonable;
`Search` in navigation plus `Ask RevenueOS` in content should remain, with a one-line
explanation of the bounded answers it supports.

## Ask RevenueOS assessment

Ask should remain bounded. Do not build a generic chat assistant, arbitrary web
research, text-to-SQL or persistent conversation product.

| Question tested                            | Result                                                                |
| ------------------------------------------ | --------------------------------------------------------------------- |
| Which deals need attention?                | Supported, cited; focused on the overdue security-summary Action.     |
| What do I need to do today?                | Supported, cited; same priority was defensible.                       |
| Which deals do not have an economic buyer? | Partially supported and honest about unknown state.                   |
| What changed after my last meeting?        | Honest no-eligible-history fallback on Northstar.                     |
| What is holding this deal back?            | Unsupported despite visible methodology gaps in the same Opportunity. |
| Which opportunities are at risk?           | Safe fallback rather than fabricated risk.                            |
| What should I follow up now?               | Unsupported.                                                          |
| What is my best next action?               | Unsupported.                                                          |
| What should I do next?                     | Supported and returned two cited actions.                             |

The last three results show brittle phrase-to-intent mapping. WO-039A should add
representative paraphrase coverage and make capability hints visible; it should not
expand the answer taxonomy without product evidence.

## Data-entry reduction and provenance

The product reduces typing once an Interaction is captured: reviewed debrief Evidence
feeds Revenue Brain, Methodology, Actions, Opportunity attention, Forecast and manager
discussion. The deliberate Evidence review is acceptable friction because it prevents
autonomous customer-truth mutation.

| Entry                                              | Classification                           | Recommendation                                                                    |
| -------------------------------------------------- | ---------------------------------------- | --------------------------------------------------------------------------------- |
| Reconfirm promoted Account before Contact          | Acceptable deliberate review             | Add a direct `Add company, then continue` recovery action.                        |
| Re-enter researched business email after promotion | Unnecessary duplication                  | Preserve the reviewed value and its exact field provenance.                       |
| Re-enter expected close date                       | Unnecessary duplication caused by defect | Fix persistence and add regression coverage.                                      |
| Answer bounded debrief questions                   | Acceptable deliberate review             | Deduplicate candidate statements before review.                                   |
| Review Evidence                                    | Acceptable deliberate review             | Group one statement with multiple possible categories instead of repeating cards. |
| Seller and manager Forecast judgments              | Necessary separate judgments             | Keep independent and immutable.                                                   |
| Business Case assumptions                          | Necessary explicit assumptions           | Keep origins and sensitivity visible.                                             |

The broader provenance model passes. Prospect research did not become customer
Evidence; Business Case outputs stayed deterministic calculations; stage did not
become customer commitment; seller and manager Forecast stayed judgment; Target did
not become Forecast; Actual came only from final closure. The Contact email defect is
a local but blocker-level collapse of that otherwise strong contract.

## Module assessments

### Core

Core provides obvious value without add-ons. Interactions, reviewed Evidence, Revenue
Brain, Methodology, Actions, Daily, Opportunity Workspace, Search/Ask, Pipeline,
Analytics, Targets, Forecast and manager review all function with Prospect, Engage,
Create and native CRM entitlements absent. Native CRM remains optional and Sales Brain
remains useful with external CRM mode.

The Airspeed/Gong-style loop is credibly covered in product shape: deliberate browser
capture/manual fallback, structured Interaction intelligence, CRM context, Evidence,
deal attention, transparent forecast, manager review and follow-up Actions. It is not
yet equivalent in production capture breadth, automatic provider ingestion,
reliability, longitudinal corpus depth or operational maturity. RevenueOS is already
better at provenance, explicit uncertainty, non-surveillance manager semantics and
review-before-mutation. It is weaker at effortless capture, integrations, real-time
provider operation, search flexibility and customer-proven quality.

### Prospect

The product journey is coherent and worth testing commercially: company research,
people discovery, sourced professional context, trust states and deliberate promotion
solve a real workflow boundary. It is not yet worth charging for as a live add-on
because all research is deterministic mock data and no provider licence/coverage/
freshness operations have been approved.

Select **Apollo for the first narrow provider qualification/pilot**, not as an
unconditional broad integration. Apollo's official API exposes organisation
enrichment plus people search and people enrichment; people search deliberately does
not return email and enrichment supplies email status, which fits RevenueOS's
search → reviewed enrichment → trust-state boundary. Official references:
[organisation enrichment](https://docs.apollo.io/reference/organization-enrichment),
[people search](https://docs.apollo.io/reference/people-api-search) and
[people enrichment](https://docs.apollo.io/docs/enrich-people-data).

Minimum slice: Australian B2B company match by domain; company name/industry/size/
location; people by company and role; business email only when returned with provider
status; source/provider timestamp and licence metadata; field-level review; quota,
kill switch, correction/deletion and quality telemetry. Exclude phone/mobile, intent,
private traits, bulk list resale, automated enrolment and raw payload retention. Before
commitment, complete terms/licensing, Australian coverage and design-partner match-rate
checks. Hunter remains a focused email-finding fallback, not the best single provider
for the complete company-and-person slice.

### Engage

One-to-one outreach, Campaign and Event feel like a governed sales-engagement
extension, not marketing automation. Review, audience snapshot, suppression,
contactability, cooldown, sending window, stop conditions, no open/click tracking and
seller-reported reply/meeting states are excellent boundaries. Event import correctly
requires an authority attestation and explicitly says attendance does not imply
permission. One attendee was planned, marked met, captured as an Interaction and left
out of Campaign handoff until promoted to a canonical Contact.

Engage is not commercially complete until one mailbox can connect, send, reconcile,
observe replies and process operational failures. **Gmail is the first live provider
and the first live provider overall.** It best matches the current small-business/
HubSpot-first cohort assumption, and the Gmail send API returns a Message resource,
whereas Microsoft Graph `sendMail` returns `202 Accepted` with no body and does not by
itself prove processing or delivery. See the official
[Gmail send response](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send)
and [Microsoft Graph sendMail response](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0).

The choice is an inference from target cohort and receipt semantics, not evidence that
Gmail OAuth or deliverability is intrinsically simpler. Validate actual partner stack
before implementation. Minimum Gmail slice: user-bound OAuth; exact sender identity;
least scopes; preview hash and idempotency; consent/suppression revalidation immediately
before send; durable provider Message/thread receipt; unknown/retry/reconcile state;
reply-based stop; revoke/re-auth; bounce/complaint and unsubscribe intake; quotas and
kill switch. No domain-wide delegation, bulk auto-send, tracking pixels, calendar,
Drive or background autonomous outreach in the first slice.

### Create

The Business Case proposition is strong enough to buy when paired with Create. It
handles approved Value Models, explicit user/organisation inputs, negative outcomes,
scenarios, sensitivity, assumption lineage and approval without inventing optimism.
DOCX proposals are not required before beta.

The presentation proposition fails this gate. The original generated export was not
strictly readable because internal OOXML files serialised the package default
namespace as an `ns0` prefix. The checkpoint made one justified blocker-level defect
fix: preserve the default root namespace during sanitisation and assert it in a
regression test. The regenerated file renders successfully and has no slide overflow.
This is a compatibility correction, not new capability.

A deeper blocker remains. The tested source deck had no usable native placeholder
mappings. The API nevertheless allowed text-placeholder-only approval, generation
review showed Business Case claims, and the downloaded PPTX kept the source slide
content—including `Jordan Lee, Chief Operating Officer` instead of Jane Smith—and did
not contain the approved Business Case values. The system must either reject an
incompatible template before approval or present an explicit locked/reuse-only state;
the claim manifest, preview and bytes must agree. Create is not customer-safe while a
reviewer can approve content that is absent from the deliverable.

### Native CRM and Pipeline

Native CRM is a credible foundation for a five-person team: Accounts, Contacts,
Opportunities, ownership, bounded custom fields, Pipeline, Interactions, Actions,
history, search, archive/restore and organisation export are present. It appropriately
avoids becoming a Salesforce clone.

It is not ready to replace a small company's current CRM operationally. CSV migration,
preview/validation, duplicate resolution/merge and recovery are blockers for a real
native-CRM design partner. Asking five people to retype customer history would destroy
the product's data-entry-reduction promise. Basic export exists through organisation
export; arbitrary bulk edit, custom objects, workflow builder and marketing CRM remain
later or out of scope. Native Action writes can remain deferred until the existing
proposal/revalidation boundary is reused.

### HubSpot

WO-025C is a credible provider-neutral and HubSpot-focused foundation, not a proven
design-partner integration. Real target-environment app registration/OAuth,
connect/revoke, sandbox execution, receipt reconciliation, secret operations and
provider outage evidence are blockers. Inbound change sync and broader object mappings
are later unless a selected partner demonstrates an authority/conflict need. HubSpot's
official authentication guidance confirms scoped OAuth is the customer-installed path,
and webhooks require app-level configuration and authorised CRM scopes:
[authentication](https://developers.hubspot.com/docs/apps/developer-platform/build-apps/authentication/overview)
and [webhooks](https://developers.hubspot.com/docs/api-reference/latest/webhooks/guide).

Do not add Salesforce or widen HubSpot for parity before the current slice passes a
real sandbox/pilot connect → match → reviewed write → reconcile → revoke test.

## Intelligence assessment

### Analytics

The current funnel, stage conversion/duration, sales cycle, mature follow-on and
seller-reported Win/Loss are enough to stop exporting CRM data to Excel for basic
sales reporting. Definitions, filters, currency separation, sparse states and
non-causal wording are unusually clear. Before commercial beta, add export only if
design partners need it and validate cohort/timezone comprehension; do not build a
generic BI/query layer.

### Targets

Targets are explicit, versioned and distinct by personal/organisation scope and
origin. Personal target privacy and organisation summary avoid comparative individual
attainment. This passes the product gate. Admin-as-manager and target visibility must
be revalidated once real roles exist.

### Forecast

Actual, Target, seller Forecast, independent manager Forecast and RevenueOS historical
baseline were immediately understandable in the tested desktop view. Five perspectives
did not create unacceptable load because labels, explanatory copy, data-quality counts
and insufficient-sample states stayed separate. There is no hidden final Forecast,
stage probability, probability field, FX blend or manager override. Keep this model.

### Manager Intelligence and surveillance audit

The manager view helps identify deal conversations, blockers, methodology gaps,
upcoming work and recent changes. It uses deterministic deal conditions and questions,
not rep profiles. Code/UI searches and tests found no leaderboard, people rank, rep
score, health score, behaviour tracking, sentiment/personality assessment or hidden
coaching profile. Forecast category realisation is explicitly not a rep score.

Keep the current deal-centric boundary. Do not add comparative target attainment,
call-style scoring, presence telemetry, employee profiles or a blended final forecast.
Admin-as-manager is acceptable only for the supervised cohort; hierarchy should wait
for observed access-policy need.

## Mobile and accessibility

At 390 × 844:

- the fixed Today/Interactions/Actions/Search navigation is readable and target-sized;
- Home, Search, Prospect, Campaign and Business Case reflow without horizontal
  overflow in the observed screens;
- Pipeline manager review works but is a long vertical experience;
- the Interaction list becomes a very long card stream with no visible pagination;
- rich Opportunity and completed Interaction hard loads often fail;
- Targets and Forecast are not visible in the mobile Insights tab list and Insights is
  not in the fixed navigation;
- Create/Prospect/Campaign are usable by deep link but not naturally discoverable; and
- Event direct load failed on mobile.

Semantic landmarks, named regions, field labels, textual statuses, progress-bar copy
and non-colour-only states are broadly good. Event tabs expose a semantic tablist, and
a keyboard focus check reached the active Follow Up tab. Automated component/E2E
coverage exercises labels, keyboard and responsive states. Blockers are duplicated
`h1`/record headings, unreliable focus/recovery after errors, and hidden mobile
destinations—not colour contrast or chart semantics observed in this pass. A formal
screen-reader and full keyboard session with human assistive-technology users remains
a pre-commercial-beta requirement.

## Security, privacy and compliance

### What is strong

- server-derived organisation context, explicit repository predicates, forced RLS and
  composite tenant keys are pervasive;
- mocks fail closed in production and provider credentials remain server-side behind
  adapters;
- transcripts, prompts and content are excluded from application audit metadata;
- Prospect excludes sensitive/private traits and keeps permission distinct from email
  availability;
- outreach has consent/contactability/suppression checks, audience snapshots and no
  open/click tracking;
- personal Target and manager semantics avoid employee surveillance;
- deterministic financial output, forecast judgments and customer Evidence remain
  different source classes; and
- raw Event CSV is not retained, with row/file bounds and sensitive-column rejection.

### Blockers before real data

1. Verify Clerk token/session and membership handling in the target environment; mock
   auth must remain impossible there.
2. Exercise the actual runtime role against forced RLS across every current tenant
   table, including operational maintenance separation.
3. Rehearse backup and restore, tenant export, retention execution and organisation
   deletion; record owner, duration, evidence and rollback.
4. Fix access logging for signed download URLs. Application structured logs use
   `request.url.path`, but the observed Uvicorn access log included the full download
   query token. Production must disable/redact default access logging or move bearer
   material out of query strings.
5. Correct Contact field provenance and Create manifest/output equivalence.
6. Upgrade or otherwise close current production dependency advisories before accepting
   untrusted PDFs or production credentials.
7. Approve provider terms/licensing, privacy disclosures, subprocessors, transfer/
   residency posture and deletion/correction flows.

### Australia-first legal gate

This review is not legal advice or certification. The current product policy is
directionally aligned but requires launch counsel and operating procedures. ACMA says
commercial electronic messages require consent, accurate sender/contact identity and
a functional unsubscribe, with unsubscribe honoured within five working days. RevenueOS
must store evidence sufficient for the customer to prove consent and must process
suppression before every send. See [ACMA: Avoid sending spam](https://www.acma.gov.au/avoid-sending-spam).

OAIC guidance requires purpose-limited handling of personal information and highlights
opt-out/source obligations where direct marketing uses third-party/public information;
email/SMS commercial messages are additionally governed by the Spam Act. See
[OAIC direct marketing guidance](https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/organisations/direct-marketing)
and [the Australian Privacy Principles](https://www.oaic.gov.au/privacy/australian-privacy-principles/read-the-australian-privacy-principles).

Before launch: settle controller/processor roles, collection notice, source disclosure,
lawful purpose/consent policy, unsubscribe SLA, correction/deletion, provider licence,
cross-border handling, retention schedule, DPA/privacy terms and incident obligations.
Do not market attendance, public availability or a provider-supplied work email as
permission.

## Operational readiness

| Area                       | Status                         | Real-data gate                                                                              |
| -------------------------- | ------------------------------ | ------------------------------------------------------------------------------------------- |
| Production identity        | Not proved                     | Target Clerk tenant, issuer/audience/signature/expiry and removal tests.                    |
| Secrets                    | Foundation only                | Environment secret manager, rotation, least scope and break-glass owner.                    |
| Backups/restore            | Documented, not rehearsed here | Successful timed restore and data-integrity evidence.                                       |
| Monitoring/error reporting | Partial                        | Customer-safe alerts, on-call owner, correlation IDs and SLOs for web/API/worker/provider.  |
| Support                    | Not launch-ready               | Named support route, hours, severity matrix, escalation and customer comms.                 |
| Incident handling          | Runbook foundation             | Tabletop for auth/tenant leak, provider credential, send error and data-loss cases.         |
| Retention/deletion/export  | Implemented foundation         | Target-environment dry run and execution, legal approval and customer-facing process.       |
| Worker/queues              | Appropriate PostgreSQL worker  | Lease/recovery/capacity alert exercise; no Redis/broker required.                           |
| Email operations           | Absent                         | Deliverability, bounce/complaint, unsubscribe, unknown-send reconciliation and kill switch. |
| Rate limits/quotas         | Bounded foundations            | Provider-specific quotas, abuse controls and tenant caps.                                   |
| Feature flags              | Present but docs drift         | Complete current flag inventory, owner, rollout, rollback and production defaults.          |
| Tenant provisioning        | Demo/admin foundation          | Approved real tenant runbook, notice, entitlement and offboarding checks.                   |

The modular monolith remains the right architecture. The checkpoint found no measured
need for microservices, Kubernetes, Redis, a message broker or another datastore.

## Dependency and security debt

`pnpm audit` reported no known Node vulnerabilities across 588 resolved dependencies.
The exported Python lock audit reported 42 advisories in three packages:

| Package        | Current | Finding                                                               | Assessment/action                                                                                                                                                                                                                                                    |
| -------------- | ------- | --------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cryptography` | 46.0.7  | 4 advisories; fixes span 48.0.1–50.0.0                                | Production dependency used for encrypted credentials/JWT crypto. Exploit details do not all match current AES-GCM use, but a supported 50.x upgrade and full auth/credential regression are required before real provider credentials.                               |
| `pypdf`        | 5.9.0   | 37 malformed-PDF resource/infinite-loop advisories; newest fix 6.15.0 | Production risk because customers may upload PDFs. Strict parsing, size/page bounds and active-content rejection reduce but do not remove denial-of-service risk. Upgrade to at least 6.15.0 and add adversarial timeout/resource tests before real document upload. |
| `pytest`       | 8.4.2   | 1 local `/tmp` advisory; fixed 9.0.3                                  | Development/test-only on the current pin. Upgrade in normal maintenance; not a runtime launch blocker by itself.                                                                                                                                                     |

Known Node action deprecation, Starlette/httpx and Alembic cycle warnings should be
tracked if they still appear in CI, but are not product blockers without a failed or
unsafe path. Do not suppress warnings to make the gate green.

## Performance and scale

A temporary local PostgreSQL fixture was created and removed during the review. All
requests returned `200`:

| Read at 1k/5k/1k/10k fixture               | Local API time |  Payload |
| ------------------------------------------ | -------------: | -------: |
| Accounts, 50 rows                          |       32.86 ms |  20.8 KB |
| Contacts, 50 rows                          |       11.58 ms |  23.3 KB |
| Opportunities, 50 rows                     |       36.62 ms |  47.3 KB |
| Pipeline, all 1,000 open deals             |       29.44 ms | 209.3 KB |
| Daily                                      |       69.42 ms |   7.3 KB |
| Insights overview                          |       14.37 ms |   0.5 KB |
| Insights activity over 10,000 Interactions |      210.18 ms |   1.1 KB |
| Forecast, 50 rows                          |       66.87 ms |  62.5 KB |
| Manager deal attention, 20 rows            |      215.12 ms |  32.1 KB |
| Manager summary                            |      150.56 ms |   2.3 KB |

These numbers support private-beta scale on a local machine, not production capacity
or concurrency. The unpaginated Pipeline response is the first scaling concern: API
latency was low, but shipping/rendering every card will degrade on mobile and larger
tenants. Add a bounded rendering/pagination measurement to WO-039A/WO-039C. Do not
change architecture pre-emptively.

## Commercial differentiation and packaging

### Why open it every day

A seller can begin with what matters today, prepare from current evidence, capture a
conversation once, review what changed and let that accepted knowledge flow into the
deal, next Action, Forecast and customer content. A leader pays for a shared,
explainable operating view that reduces CRM archaeology and forecast-deck preparation
without employee scoring.

### Why choose it

- **Small company instead of HubSpot:** when it wants a simple native record/Pipeline
  plus an Interaction-centred Sales Brain and can accept opinionated rather than
  endlessly custom CRM. This claim becomes credible only after import/dedupe and
  reliability hardening.
- **Larger company alongside HubSpot/Salesforce:** RevenueOS can be the reviewable
  Evidence/Revenue Brain/Action/Forecast layer while the external CRM remains
  authoritative. The current focused HubSpot path must first pass live proof.
- **Instead of Gong + CRM + Salesloft + Apollo + PowerPoint + Excel:** not because
  RevenueOS has more features, but because one source/provenance and one Opportunity
  workflow connect research, conversation, truth review, action, forecast, content and
  outcome learning. Today that advantage is product-shaped but not provider-complete.

### Package boundaries

| Package      | Commercial assessment                                                                                                                                                                                                                                                                            |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Core**     | Strong independent proposition: Sales Brain, Interactions, Evidence, Methodology, Actions, Daily, canonical Sell records, Search/Ask, Pipeline, Analytics, Targets, Forecast, Manager Intelligence and Workspace. Keep external-CRM integration foundation with Core; do not require native CRM. |
| **Prospect** | Coherent independent add-on; not chargeable until live licensed provider quality is proven.                                                                                                                                                                                                      |
| **Engage**   | Coherent add-on and likely valuable after one mailbox; Campaign/Event should remain bounded sales workflows.                                                                                                                                                                                     |
| **Create**   | Business Case has independent value; Presentation is not sellable until trusted export equivalence and simpler template setup.                                                                                                                                                                   |
| **CRM**      | Credible optional proposition for small teams after import/dedupe/admin hardening.                                                                                                                                                                                                               |
| **Complete** | Understandable convenience bundle only when every included module independently passes its beta gate. Do not force it to unlock Core.                                                                                                                                                            |

Contextual, infrequent add-on discovery is appropriate. No blocked Core action, modal
upsell or entitlement language should interrupt the seller workflow. Do not invent
prices or implement billing before value, support burden and provider cost evidence.

## Inserted work orders

### WO-039A — Flagship journey coherence and reliability

**Purpose:** make the implemented product dependable and simple enough for observed
seller/manager testing; no new capability.

Scope:

- reproduce and fix hard-load/client-navigation fetch/abort/error-boundary failures;
- provide useful retry/recovery with request ID while preserving safe errors;
- preserve promoted Contact field value and exact provenance;
- persist expected close date and reconcile all Opportunity views after mutation;
- remove duplicate primary headings/record summaries and internal CRM-mode wording;
- deduplicate debrief candidates before Evidence review;
- add Ask paraphrase tests for supported intents and capability hints;
- make mobile Insights/Accounts/Pipeline/Create/Find reachable without replacing the
  four-item fixed bar; and
- measure/guard Pipeline rendering at the reviewed 1,000-deal envelope.

**Remediation update — 31 August 2026:** WO-039A resolved all nine assigned finding
groups and all carried journey gates without a schema change. The reported mobile
Insights clipping was not reproducible at 390 px; the required secondary destination
path and Event-tab containment were still implemented and verified. See the
[completed remediation table](../07-sprints/wo-039a-remediation-checklist.md) and
[verification record](../07-sprints/wo-039a-end-to-end-journey-reliability.md).

Exit: the exact flagship journey completes twice from a fresh browser session without
generic fetch failure, contradictory state, provenance collapse or unexplained dead end.

### WO-039B — Create trust contract and file security

**Purpose:** make approved review state equivalent to the delivered file.

Scope:

- reject or explicitly lock templates that lack usable placeholders;
- prove claim manifest, rendered preview and downloaded PPTX equivalence;
- verify audience names and Business Case values in the bytes, not only the API model;
- retain editable OOXML and render/overflow smoke tests in CI;
- redact/disable signed-query access logging and review bearer-download design;
- upgrade `pypdf` and add malformed-resource timeout tests; and
- document supported template authoring with a non-technical admin path.

Exit: an administrator-supplied representative deck cannot be approved in an
incompatible state, and every approved claim is present in the visually inspected file.

### WO-039C — Real-data design-partner operations and native onboarding

**Purpose:** satisfy the minimum real-data launch boundary; no broad integration.

Scope:

- target Clerk and runtime-role/RLS evidence;
- backup/restore, retention/export/deletion and offboarding rehearsal;
- monitoring, support, incident, feature-flag and tenant-provisioning operations;
- production dependency upgrade, secret rotation and safe-log evidence;
- privacy/DPA/launch-region/provider approval checklist;
- native CRM CSV import with preview, row errors, source mapping, idempotency and
  duplicate review/merge sufficient for a five-person design partner; and
- explicit go/no-go sign-off with named owners and rollback.

Exit: one empty target tenant can be provisioned, safely loaded with representative
synthetic CRM data, backed up/restored/exported/deleted and offboarded with evidence.

## Revised WO-040–045 roadmap

| Work order                          | Decision                                            | Revised role                                                                                                                                                                           |
| ----------------------------------- | --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **WO-040 Microsoft 365**            | **DEFER / REORDER**                                 | Do not begin first. Keep as the second ecosystem candidate only if selected design partners are Microsoft-led. No broad mail+calendar build.                                           |
| **WO-041 Google Workspace**         | **NARROW and REORDER before WO-040**                | Replace first execution with the Gmail-only governed send/reply/reconcile/revoke slice described above. Calendar and wider Workspace remain later evidence-led scope.                  |
| **WO-042 CRM Connectors**           | **DEFER**                                           | First finish real HubSpot registration/sandbox proof within the existing boundary. Add a second CRM or inbound breadth only from partner evidence.                                     |
| **WO-043 Deal Rooms**               | **DEFER**                                           | Current Opportunity Workspace/Create attachments are enough to test. Do not build document management before repeated findability/storage pain.                                        |
| **WO-044 Closed-Won Handover**      | **DEFER**                                           | Valuable extension, but no Customer Success partner evidence and real-data sharing operations are not ready.                                                                           |
| **WO-045 End-to-End Sales OS Beta** | **REPLACE as a release gate, not a feature sprint** | After WO-039A–C and the selected narrow provider, execute reliability, accessibility, security/ops and cohort launch evidence only. Do not bundle every module into one required beta. |

Apollo Prospect provider qualification may run after WO-039C legal/provider controls or
alongside the narrow Gmail discovery, but it must not delay Core synthetic usability
testing. No second mailbox, second CRM, Deal Room or handover should precede observed
cohort evidence.

## Beta entry criteria

### Real-data supervised design partner

All must be true:

- target-environment verified auth/membership and mock-production prohibition;
- forced-RLS/runtime-role cross-tenant suite on migration head `0048` or later;
- no open Critical/High tenant, provenance, export-equivalence or signed-secret log risk;
- production `cryptography` and `pypdf` advisories resolved or formally mitigated with
  tested non-exposure and owner/date;
- backup and restore, tenant export, retention, organisation deletion and file deletion
  exercised in the target environment;
- privacy notice, DPA/terms, subprocessor/cross-border disclosure and Australia-first
  outreach/provider legal review approved;
- customer data source/licence/authority recorded; no production data in mock/demo;
- support route, severity/escalation, incident contact, telemetry/alerts and rollback;
- tenant provisioning/offboarding and feature-flag inventory with owners;
- the flagship journey passes twice with recovery and no contradictory state;
- native CRM partners have safe CSV preview/import/dedupe, or use a separately proven
  external CRM path; and
- any enabled provider passes connect/use/receipt/reconcile/revoke and outage tests.

### Unsupervised beta

Add:

- observed supervised cohort success and stop criteria;
- onboarding a least-technical rep can complete without operator intervention;
- human accessibility review, mobile critical-flow pass and published supported browser;
- measured SLO/capacity at expected concurrency, support rotation and incident tabletop;
- provider quota/deliverability/bounce/complaint/unsubscribe operations;
- customer-facing status/recovery/known-limitations communication; and
- no unresolved high-severity product-reliability or data-integrity defect.

### Commercial beta

Add:

- each advertised module independently meets its release definition;
- commercial terms, privacy, DPA, cancellation/export/deletion and support commitments;
- pricing/cost/usage controls based on customer and provider evidence;
- billing only if required for the offered commercial motion;
- security review/penetration testing proportionate to scope and customer commitments;
- tested rollback/kill switches and executive launch approval; and
- marketing claims limited to observed capability, not category parity by feature count.

## Blockers, should-fix and later

### Blockers before real data or external sending

1. browser fetch/navigation/recovery instability;
2. Contact promotion/provenance corruption;
3. Opportunity date/stale state inconsistency;
4. Create review/download mismatch and signed-token logging;
5. target identity/RLS/backup/retention/deletion/support evidence;
6. production `cryptography`/`pypdf` remediation;
7. native CRM import/dedupe for native-mode partners;
8. provider licence/privacy and mailbox legal/operational approval.

### Should fix during WO-039A–C

- 13-card debrief evidence duplication from three concise answers;
- mobile Insights/add-on discoverability and long Interaction/Pipeline rendering;
- Ask paraphrase brittleness;
- onboarding recovery links and internal terminology;
- documentation drift: index, IA, feature flags and old migration/readiness references;
- explicit current-state list of every feature/provider flag and production default.

### Later, only with evidence

- second mailbox/productivity ecosystem;
- second CRM, broad bidirectional sync or arbitrary field parity;
- Deal Rooms, customer portal or generic document management;
- Closed-Won destination automation/Customer Success Brain;
- DOCX proposals, generic BI, generic chat, workflow builder, custom objects;
- hierarchy, people analytics, scores, leaderboards or autonomous forecast;
- open/click tracking, autonomous SDR, bulk cold outreach or intent surveillance.

## Top risks

### Product

1. customers stop using the product when state is correct in the API but unavailable or
   contradictory in the page;
2. dense review/admin surfaces undermine the promised simplicity and low data entry;
3. module breadth hides the flagship Sales Brain habit before repeated-use evidence.

### Technical/operational

1. unproved target identity/RLS/restore/deletion operations with real customer data;
2. output/provenance or signed-token handling breaks the product's trust contract;
3. production PDF/crypto advisories and immature provider reconciliation create
   availability, credential or external-effect risk.

### Commercial

1. Prospect/Engage cannot be sold credibly while providers are mock/simulation only;
2. Create and CRM impose expert template/data-migration work that destroys margins;
3. attempting to sell Complete before individual module evidence creates support cost
   and a confusing value story.

## Direct answers to the final questions

1. **One product?** Mostly yes on the happy path; failures and duplicate summaries
   still fracture it.
2. **Sales Brain centre?** Yes.
3. **Salesperson without training?** Basic happy paths yes; full flagship journey no.
4. **Manager without training?** Forecast/attention mostly yes; role/access setup no.
5. **Core valuable without add-ons?** Yes, clearly.
6. **Prospect worth paying for?** Product shape yes; not until live provider quality.
7. **Engage worth paying for after mailbox?** Likely yes; validate send/reply/support
   burden with a Gmail pilot.
8. **Create worth paying for?** Business Case yes; Presentation not until export trust.
9. **Native CRM credible?** As a basic product foundation yes; as a real replacement no
   until import/dedupe and reliability.
10. **Airspeed/Gong-style loop?** Credible product coverage, not production parity.
11. **Already better where?** Provenance, uncertainty, review-before-mutation,
    integrated Opportunity workflow and non-surveillance forecast/manager semantics.
12. **Weaker where?** Capture/provider breadth, reliability, integrations, flexible Ask,
    customer onboarding and operational maturity.
13. **What makes a partner stop?** Failed loads, contradictory record state or an
    approved deliverable that does not contain what the review promised.
14. **What makes them open daily?** One evidence-backed priority plus preparation,
    follow-up and Forecast in the same deal context.
15. **Three biggest product risks?** Reliability, simplicity erosion, weak repeated-use
    validation.
16. **Three biggest technical risks?** Production isolation/operations, trust-output
    integrity, dependency/provider operations.
17. **Three biggest commercial risks?** Mock add-ons, services-heavy setup, premature
    Complete packaging.
18. **First live provider?** Gmail, narrowly for governed Engage delivery; Apollo is the
    first Prospect qualification.
19. **Roadmap item to remove/defer?** Defer WO-043 Deal Rooms and WO-044 Handover; treat
    WO-045 as a release gate, not a feature bundle.
20. **Ready to move from building to testing?** Yes for supervised synthetic product
    testing after/while WO-039A begins; no for real-data or commercial beta.

## Screenshot and file evidence

- [Company research](../07-sprints/assets/checkpoint-3/01-northstar-research.png)
- [Outreach review](../07-sprints/assets/checkpoint-3/02-outreach-review.png)
- [Opportunity Workspace](../07-sprints/assets/checkpoint-3/03-opportunity-workspace.png)
- [Approved Business Case](../07-sprints/assets/checkpoint-3/04-approved-business-case.png)
- [Presentation review](../07-sprints/assets/checkpoint-3/05-approved-presentation-review.png)
- [Rendered presentation montage](../07-sprints/assets/checkpoint-3/06-generated-presentation-montage.png)
- [Transparent Forecast](../07-sprints/assets/checkpoint-3/07-transparent-forecast.png)
- [Mobile Home](../07-sprints/assets/checkpoint-3/08-mobile-home.png)
- [Mobile manager view](../07-sprints/assets/checkpoint-3/09-mobile-manager-view.png)
- [Mobile Event failure](../07-sprints/assets/checkpoint-3/10-mobile-event-failure.png)
- [Event follow-up](../07-sprints/assets/checkpoint-3/11-event-follow-up.png)
- [Editable PPTX reviewed](../07-sprints/assets/checkpoint-3/checkpoint-3-northstar-access-review.pptx)

## Validation and delivery record

The complete local gate passed on 30 August 2026:

| Validation                                                     | Result                                                                            |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `pnpm format`, `pnpm lint`, `pnpm typecheck`                   | Passed                                                                            |
| `pnpm test`                                                    | Passed: 60 files, 219 tests                                                       |
| `pnpm test:e2e`                                                | Passed: 62 tests                                                                  |
| `pnpm build:web`                                               | Passed                                                                            |
| `pnpm api:lint`, `pnpm api:format`, `pnpm api:typecheck`       | Passed                                                                            |
| `pnpm api:test`                                                | Passed: 1,021 tests, two existing warnings                                        |
| `pnpm api:migrate`, `pnpm api:migration:check`                 | Passed at migration head `0048_manager_intelligence`; no new migration operations |
| `pnpm build:api`                                               | Passed                                                                            |
| Node dependency audit                                          | Passed with no known vulnerabilities                                              |
| Repository audit, documentation-link check, `git diff --check` | Passed; 1,239 tracked files and 485 documentation files checked                   |

The first API-suite run used the populated browser-review database. It passed 1,020
tests and exposed one downgrade-test collision: the synthetic opportunity audit rows
were valid at the current schema but incompatible with a historical constraint while
the migration test deliberately downgraded the shared database. The exact suite was
rerun against a clean, explicitly named PostgreSQL database and all 1,021 tests passed.
That temporary database and the scale fixture were removed. This was test-environment
contamination, not a current-schema failure, and is recorded rather than hidden.

The two non-blocking warnings remain visible: Starlette's deprecated `httpx`
`TestClient` argument and Alembic's unresolved cycle between `recording_sessions` and
`transcript_versions`. Draft pull-request identity and hosted CI state are recorded in
the final handoff because a document cannot truthfully contain the hash of the commit
that contains itself.

This checkpoint added no production feature. It made one small blocker-level OOXML
compatibility correction with regression coverage so the requested generated file
could be opened and visually inspected. No paid service was activated, no external
provider mutation occurred, and the pull request must remain unmerged.
