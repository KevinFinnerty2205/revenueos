# WO-039A pre-change remediation checklist

- **Work order:** WO-039A — End-to-End Journey Reliability & UX Coherence
- **Baseline:** `7a4fb51e7795fc6536f6a3e7ab1401a41290b0bd`
- **Branch:** `feature/pre-beta-wo-039a-journey-reliability`
- **Recorded:** 31 August 2026, before production-code changes
- **Authority:** [Checkpoint 3](../06-roadmap/checkpoint-3-end-to-end-beta-readiness.md)
- **Initial status:** every item is `TO REPRODUCE`; implementation starts only after browser evidence is recorded

This checklist separates the nine finding groups explicitly assigned to WO-039A by
Checkpoint 3 from the carried Checkpoint 2 and work-order verification gates. A
finding that is not reproducible on the current baseline will be marked
`NOT REPRODUCED` with evidence instead of being changed speculatively.

## Checkpoint 3 findings assigned to WO-039A

| ID | Finding | Current behaviour reported by Checkpoint 3 | Desired behaviour | Severity | Owner | Planned implementation | Planned test | Screenshot |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A01 | Hard-load and client-navigation reliability | Major routes intermittently stop at generic `Failed to fetch` although underlying requests return `200`; Interaction post-capture, Opportunity, Create, Target Market and Event were observed | Refresh, direct load, browser history and contextual navigation reliably settle to content or a safe recoverable state | Blocker | WO-039A | Reproduce fetch/abort/error-boundary cause; make request lifecycle deterministic without polling or new infrastructure | Direct-load and client-navigation browser matrix; flagship journey twice from fresh sessions; critical read failure tests | Desktop and 390 px affected routes |
| A02 | Useful read-error recovery | Generic failure states provide no local retry, request ID or useful next step; focus/recovery is unreliable | State what happened, expose a safe request ID when supplied and provide a local retry or valid destination without leaking internals | Blocker | WO-039A | Shared bounded recovery treatment consistent with current route architecture; preserve safe API errors | 500, 404, timeout and feature-disabled browser/component coverage on prioritised routes | Representative desktop/mobile recovery states |
| A03 | Contact promotion value and provenance | Person-first promotion has no direct Company recovery; promoted researched email was dropped; manually restoring it displayed as Provider Supplied | Offer `Save Company first`, return to the same Person, preserve the reviewed email and retain exact field provenance | Blocker | WO-039A | Repair promotion hand-off and field-source mapping only; retain canonical Company-before-Contact invariant and duplicate protection | API/service/component/E2E promotion, duplicate and return-context regressions | Person prerequisite and promoted Contact |
| A04 | Opportunity mutation coherence | Expected close date was saved as `Not set`; close/stage state could disagree across record header, workflow and dependent views until refresh | Persist the supplied close date and deliberately revalidate every Opportunity, Pipeline, Analytics, Target, Forecast and manager consumer after stage, close and reopen | Blocker | WO-039A | Correct payload/state mapping and targeted cache invalidation/refetch; no new forecast or analytics logic | Form regression, stale-write case, stage/close/reopen browser assertions and flagship final-state assertions | Opportunity before/after close plus Pipeline/Forecast |
| A05 | Duplicate hierarchy and internal CRM wording | Contact and Opportunity showed duplicate primary headings/record summaries and ordinary seller UI exposed `Unconfigured CRM mode` or repeated CRM/workspace facts | One page `h1`, one clear record summary, progressive seller-first detail and customer language | High | WO-039A | Remove duplicated composition and translate/hide internal mode language without changing domain architecture | Heading hierarchy, accessible-name and seller-language component/E2E assertions | Account, Contact and Opportunity |
| A06 | Debrief candidate duplication | Three concise answers produced 13 cards with the same statement repeated across categories | Deduplicate candidate statements before review and present category ambiguity without multiplying identical evidence | High | WO-039A | Deterministic normalisation/grouping before candidate review; preserve source class and human review | Service/API regression for repeated answers plus browser candidate count/content assertion | Evidence review |
| A07 | Ask paraphrase reliability and capability hints | Supported next-action intent matched `What should I do next?` but rejected close paraphrases; supported scope was not obvious | Representative paraphrases resolve to the existing supported intent; unsupported questions stay honest; visible hints explain bounded authorised sales-data questions | High | WO-039A | Extend existing deterministic intent phrases only and add concise capability copy; no generic chat or new answer taxonomy | Unit/API/E2E questions from Checkpoint 3 and work order, including unsupported/unknown cases | Search/Ask desktop and mobile |
| A08 | Mobile destination discoverability | Fixed four-item bar works, but Accounts, Pipeline, Insights, Create, Find and enabled add-ons were deep-link-only; Targets and Forecast were clipped/hidden within mobile Insights | Preserve Today/Interactions/Actions/Search and add one accessible secondary destination path; make all Insights tabs reachable at 390 px | High | WO-039A | Minimal `More`/menu or existing-shell disclosure and accessible overflow treatment; no fifth bottom item or navigation rewrite | Keyboard/focus/role tests plus 390 px containment and destination E2E | Home/menu, Insights tabs and enabled add-ons |
| A09 | Pipeline rendering envelope | Pipeline returned and rendered every open card; reviewed 1,000-deal payload was 209.3 KB and mobile/list views were long | Measure and guard the reviewed 1,000-deal envelope; avoid unbounded DOM work while preserving the current product and API contract unless evidence requires a bounded change | High | WO-039A (measurement shared with WO-039C) | Add deterministic scale/render measurement and the smallest evidenced guard; do not pre-emptively change architecture | 1,000-deal API/render measurement, no N+1 regression, mobile containment | Large-fixture Pipeline if a visible change is required |

## Carried and work-order verification gates

| ID | Finding | Current behaviour to verify | Desired behaviour | Severity | Owner | Planned implementation | Planned test | Screenshot |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V01 | Truthful research state | Checkpoint 2 showed `Research queued` before any durable run existed | `Ready to research`, `Researching`, `Research complete`, `Partially complete`, `Research unavailable` or `Research failed` must reflect real state | High | WO-039A | Copy/state translation only if reproduced | Component/E2E state matrix | Find and research detail |
| V02 | Campaign fixture time consistency | Seeded next-send time was outside the displayed Australia/Sydney send window | Every deterministic Campaign date/time obeys the displayed policy | High | WO-039A | Correct synthetic fixture clock/window relationship only if reproduced | Fixture/API/browser assertion | Campaign detail |
| V03 | Event mobile tab and direct load | Follow Up tab clipped at 390 px and Event direct load failed | Four semantic tabs remain visible/reachable and keyboard operable; direct load recovers safely; bottom navigation obscures nothing | High | WO-039A | Accessible horizontal overflow/compact treatment and shared load fix as evidenced | 390 px viewport, keyboard tablist and direct-load regression | Event desktop/mobile |
| V04 | First-use recovery and wording | Interaction brief could be blocked by onboarding acknowledgement without a direct recovery link; five-step onboarding may contain stale routes/copy | A fresh member can reach Account → Contact → Interaction → Evidence → Opportunity/Sales Brain with direct next steps | High | WO-039A | Repair only stale copy/routes and contextual recovery | Fresh-organisation member/admin E2E | First-use and blocked brief |
| V05 | Interaction workflow simplicity | Completed Interaction recovery failed and long mobile detail/list streams could obscure the primary path | Preserve Prepare → Capture → Review → Follow through with one obvious `Capture what happened` path and secondary alternatives | High | WO-039A | Simplify competing CTAs and long-state presentation only where reproduced | Heading/primary CTA, mobile containment and flagship capture assertions | Prepare, Capture and Review |
| V06 | Home and Opportunity seller hierarchy | Mobile Home repeated `Deals needing attention`; Account/Opportunity admin detail could crowd seller work | One obvious page purpose and primary action; Opportunity leads with deal, what matters, Methodology gaps, Evidence/Revenue Brain, Actions, Forecast and Create; manager/admin detail is disclosed | Medium | WO-039A | Remove duplicated presentation and reorder/disclose existing content only | Member/admin snapshots, headings and primary-action assertions | Home and Opportunity desktop/mobile |
| V07 | Search/Ask purpose and deep links | Search was understandable but Ask scope and major contextual links require systematic verification | Search finds records; Ask answers bounded authorised sales-data questions; Daily/Search/Ask/Pipeline/Insights/Forecast/Manager/Prospect/Create deep links use current canonical IDs/routes | High | WO-039A | Copy/link correction only; no generic retrieval | Major deep-link E2E matrix and stale-ID recovery | Search/Ask plus representative destination |
| V08 | Feature, entitlement and role recovery | Optional routes and admin actions can expose raw unavailable/denied states or remain undiscoverable | Disabled, unentitled and temporarily unavailable modules fail securely with customer language; members do not see actions guaranteed to fail; admins retain configuration/manager access | High | WO-039A | Presentation-layer availability/error mapping and role-aware controls; no access weakening or upsell | Member/admin plus enabled/disabled/unentitled E2E and API denial assertions | Representative Create/Prospect/manager states |
| V09 | Loading, duplicate-submit and stale-write UX | Critical forms and transitions require systematic in-flight and conflict review | Controls disable in flight; repeated click causes one effect; success is clear; stale writes say `This changed since you opened it. Refresh and review the latest version.` | High | WO-039A | Reuse current mutation primitives/idempotency; translate safe conflicts; targeted invalidation | Account, Contact, Opportunity, Evidence, Action, stage, Target, seller/manager Forecast, promotion, Outreach and Create form tests as applicable | Representative mutation/conflict state |
| V10 | Back/return context and terminal destinations | Cross-module hand-offs and terminal flows were not exercised as one coherent path | Context is preselected and preserved; back/return links are sensible; terminal states lead to the next canonical destination | High | WO-039A | Safe query/referrer context only where current routing needs it; no navigation state machine | Flagship hand-off assertions across Prospect → Close | Representative cross-module returns |
| V11 | Customer terminology and Settings disclosure | Seller surfaces include mixed Company/Account, duplicated Contact/People language and technical Settings concepts | Use Account, Contact, Opportunity, Interaction, Evidence, Revenue Brain/Sales Brain, Methodology, Action, Pipeline, Target, Forecast and Manager view consistently; hide engineering concepts behind admin disclosure | Medium | WO-039A | UI translation/copy and minimal Settings grouping/disclosure; no enum/domain rename | Repository copy audit plus member/admin UI assertions | Settings and canonical workspaces |
| V12 | Accessibility and 390 px containment | Duplicate `h1`s, recovery focus and hidden destinations are blocker-level findings; formal human assistive-tech review remains later | Semantic headings/landmarks/labels, associated errors, focus restoration/trap, named states, 44 px touch targets, reduced motion and no horizontal page overflow on required routes | High | WO-039A | Straightforward blocker fixes in touched/current critical surfaces | RTL semantic checks, keyboard browser pass and viewport containment suite | Required desktop/mobile screenshot index |
| V13 | Deterministic flagship organisation | Existing demonstrations span Northstar but must be proven as one internally consistent journey | The same synthetic Account, Contact, Interaction, Evidence, Opportunity, Business Case, Target, Forecast and manager records have coherent dates, amounts, ownership and relationships | Blocker | WO-039A test support | One canonical synthetic fixture; no production data, external provider or database repair | Single flagship Playwright suite covering steps 1–40 and final retained history | Required journey screenshot index |
| V14 | Scope boundaries | Create output trust belongs to WO-039B; real-data operations/import belong to WO-039C | WO-039A changes navigation, reliability, recovery and coherence only; no WO-040/provider/new-AI/product breadth | Blocker | WO-039A review | Categorise every production diff and remove unrelated work | Prohibited-scope audit and final diff review | Not applicable |

## Pre-change baseline evidence

- Branch, `HEAD`, local `main`, `origin/main` and fetched `main` all resolve to
  `7a4fb51e7795fc6536f6a3e7ab1401a41290b0bd`.
- The worktree was clean before this checklist was added.
- Checkpoint 3 and WO-039 are merged.
- `0048_manager_intelligence` declares `0047_transparent_forecast` as its parent and
  is the only apparent migration tip in the checked-in graph. Executable Alembic
  validation remains pending until the repository's bundled Python runtime is loaded.
- The Checkpoint 3 OOXML correction is present in
  `apps/api/src/revenueos/create_pptx.py` and has a regression assertion that the
  default content-types namespace does not serialise as `ns0:Types`.

## Explicit dependencies left outside WO-039A

- **WO-039B:** template compatibility policy, manifest/preview/PPTX equivalence,
  audience and Business Case byte verification, signed-download logging/bearer design,
  `pypdf` remediation and hostile-file resource limits.
- **WO-039C:** target production identity/RLS/backup/restore/retention/deletion/support
  proof, dependency/secret operations, real tenant provisioning/offboarding, feature
  inventory operations and native CRM CSV import/deduplication/merge.
- **After WO-039A–C only:** selected live provider work. WO-040 is not authorised.

## Completion remediation table

| Checkpoint finding | Status | Implementation | Tests | Visual evidence | Remaining limitation | Next owner |
| --- | --- | --- | --- | --- | --- | --- |
| A01 Hard-load and client navigation | **FIXED** | Removed unnecessary read preflights; added request IDs, three-attempt GET-only transient recovery, abort handling and route/local recovery | API-client unit tests; 11-route direct-load matrix twice; flagship route hand-offs | Home, Find, Account, Interaction, Opportunity, Event | Human testing across design-partner networks remains a release activity | WO-039C operations |
| A02 Useful read-error recovery | **FIXED** | Safe request IDs plus Try again/return actions on the route boundary and prioritised workspaces | Network/abort/write retry units; live Event failure/recovery; component assertions | Event recovery and mobile Event | Not every secondary card has a dedicated return link; the route boundary remains the final safety net | Future evidenced UX work |
| A03 Contact promotion and provenance | **FIXED** | Company-first prerequisite links back to the same Person; promotion preserves business email/provenance and opens canonical Contact | Person/contact service regressions; business form/provenance and browser promotion assertions | Prospect Person, Contact/Outreach | Bulk enrichment/import remains outside scope | WO-039C if selected |
| A04 Opportunity mutation coherence | **FIXED** | Expected close date remains populated; confirmed stage/close/reopen dispatch targeted revalidation to mounted consumers | Form regression; workspace/pipeline/list/component regressions; flagship final convergence | Opportunity, Pipeline, Forecast, closed Opportunity | No new cache platform or analytics/forecast logic was introduced | None |
| A05 Duplicate hierarchy/internal CRM wording | **FIXED** | One page `h1`; secondary Account intelligence/Contact/deal headings; “RevenueOS record” replaces internal mode copy | Accessible-heading and seller-language component tests; browser page audit | Account, Contact, Opportunity | Advanced admin documentation still uses precise architecture terms | None |
| A06 Debrief candidate duplication | **FIXED** | Compound answers split into unique normalised clauses and assign one review category per statement | API debrief regression including repeated clauses | Evidence review | Semantic paraphrase clustering beyond deterministic normalisation would be new AI behaviour | Not authorised |
| A07 Ask paraphrases and hints | **FIXED** | Added close deterministic synonyms and expanded visible capability hints; unsupported intent remains honest | Ask service/component tests for next-action, follow-up and economic-buyer phrases | Search/Ask review | Ask remains deliberately bounded, not generic chat | Future evidenced Ask order |
| A08 Mobile destination discoverability | **FIXED** | Accessible More destinations disclosure; Event tabs use four contained columns | Shell/component keyboard semantics; 390 px browser bounds | Mobile Home menu, Insights, Event | Reported Insights tab clipping was **NOT REPRODUCED**; no speculative CSS change | Formal accessibility session |
| A09 Pipeline rendering envelope | **FIXED** | Initial DOM bounded to 100 of 1,000 records with explicit next batch; API contract unchanged | 1,000-record render regression and measured 209.3 KiB/29.44 ms API response | Pipeline | Server pagination is intentionally deferred until production evidence | WO-039C if needed |

## Carried-gate result summary

| Gate | Status | Result |
| --- | --- | --- |
| V01 truthful research | **FIXED** | No durable run now displays “Ready to research”; active/complete/partial/failure labels map to real state. |
| V02 Campaign fixture | **FIXED** | Seed and repair use the same production send-window calculation; verified at 15:45 Australia/Sydney inside 08:30–17:00. |
| V03 Event direct/mobile | **FIXED** | Direct error is recoverable; all four tabs fit at 390 px. |
| V04 first use | **FIXED** | Five steps describe the canonical path; blocked preparation links to onboarding. |
| V05 Interaction simplicity | **FIXED** | Prepare → Capture → Review → Follow through remains the dominant sequence; recovery is local. |
| V06 Home/Opportunity hierarchy | **FIXED** | Duplicate Home heading and duplicate primary workspace headings removed; Sales Brain hierarchy retained. |
| V07 Search/Ask/deep links | **FIXED** | Search and Ask purposes are explicit; primary direct-route matrix uses canonical IDs. |
| V08 feature/role recovery | **FIXED** | Availability uncertainty no longer falsely hides destinations; server-disabled and role-denied states still fail closed. |
| V09 loading/duplicate/stale writes | **FIXED** | Existing in-flight/idempotency/version controls retained; safe network recovery never replays writes. |
| V10 return context | **FIXED** | Person Company-first flow and promoted Contact retain return/canonical context; terminal recovery destinations added. |
| V11 terminology | **FIXED** | Canonical terminology guide recorded; seller-facing infrastructure language removed from touched workspaces. |
| V12 accessibility/390 px | **FIXED** | Heading hierarchy, semantic disclosure, tab containment, focus styles and touch targets validated in touched paths. |
| V13 deterministic flagship | **FIXED** | One synthetic Northstar identity is retained through the 40-step Playwright journey and final Won convergence. |
| V14 scope boundaries | **FIXED** | Diff audit contains only Checkpoint finding, journey support, accessibility/reliability or terminology/coherence changes. |

Screenshot paths and the concise evidence index are in the
[WO-039A record](wo-039a-end-to-end-journey-reliability.md). WO-039B, WO-039C and
WO-040 boundaries above remain unchanged.
