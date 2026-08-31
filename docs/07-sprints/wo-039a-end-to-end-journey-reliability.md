# WO-039A — End-to-End Journey Reliability & UX Coherence

## Scope and outcome

WO-039A hardens the existing end-to-end RevenueOS seller loop. It adds no provider,
new AI capability, mailbox delivery, analytics/forecast logic, CRM breadth or WO-040
work. Migration head remains `0048_manager_intelligence`; no schema change was needed.

The implementation covers bounded read recovery, actionable error states, canonical
Prospect promotion continuity, Opportunity revalidation, debrief deduplication, Ask
paraphrases, mobile destination discovery, Event tab containment, terminology,
first-use guidance, coherent Campaign scheduling and a bounded Pipeline render.

## Verification record

- Baseline: `7a4fb51e7795fc6536f6a3e7ab1401a41290b0bd` on
  `feature/pre-beta-wo-039a-journey-reliability`.
- Database: PostgreSQL migration upgrade and single-head inspection confirmed
  `0048_manager_intelligence`; no migration added.
- Browser: all 11 primary direct routes settled to their intended `h1` in one fresh
  desktop pass with no recovery card or console error. A deliberately observed Event
  transport failure displayed a request ID, Try again and Return to Events, and the
  local retry recovered without refresh.
- Mobile: 390 × 844 checks retained fixed navigation. Event tab bounds were
  24–106.5, 110.5–193, 197–279.5 and 283.5–366 px inside a 390 px viewport.
- Scale: 1,000-Opportunity API payload measured 209.3 KiB; initial rendering is now
  bounded to 100 cards.
- Fixture: Campaign next send is calculated by the production scheduling policy and
  verified inside its displayed Australia/Sydney weekday window.
- Automated gate: Prettier, ESLint and TypeScript passed; Vitest passed 226 tests;
  Playwright passed 63 tests, including the single 40-step flagship journey; Ruff
  and strict mypy passed; pytest passed 1,022 tests with four intentional skips;
  the web and API production builds passed.
- Repository checks: dependency audit reported no known vulnerabilities, the
  repository audit passed 1,275 tracked files, `alembic upgrade head` completed and
  `alembic check` found no new upgrade operations.

## Screenshot index

The full browser review captures the required journey states; the concise evidence
set linked here avoids duplicating every frame in documentation.

| Evidence | File |
| --- | --- |
| Home and mobile destinations | `assets/wo-039a-home-desktop.png`, `assets/wo-039a-home-mobile-more.png` |
| Find and researched Company/Person | `assets/wo-039a-find-desktop.png`, `assets/wo-039a-prospect-company.png`, `assets/wo-039a-prospect-person.png` |
| Canonical Account/Contact and Outreach | `assets/wo-039a-account.png`, `assets/wo-039a-contact-outreach.png` |
| Interaction and accepted Evidence | `assets/wo-039a-interaction-review.png`, `assets/wo-039a-evidence.png` |
| Opportunity, Pipeline and closed state | `assets/wo-039a-opportunity.png`, `assets/wo-039a-pipeline.png`, `assets/wo-039a-opportunity-closed.png` |
| Create and Insights | `assets/wo-039a-create.png`, `assets/wo-039a-insights.png` |
| Target, Forecast and Manager | `assets/wo-039a-target.png`, `assets/wo-039a-forecast.png`, `assets/wo-039a-manager.png` |
| Campaign scheduling and mobile Event containment | `assets/wo-039a-campaign.png`, `assets/wo-039a-event-mobile.png` |
| Representative mobile journey | `assets/wo-039a-search-mobile.png`, `assets/wo-039a-interaction-mobile.png`, `assets/wo-039a-opportunity-mobile.png`, `assets/wo-039a-pipeline-mobile.png`, `assets/wo-039a-insights-mobile.png`, `assets/wo-039a-forecast-mobile.png` |

## Production diff classification

Every production file was reviewed against the work-order categories before hand-off.

| Category | Production files |
| --- | --- |
| Checkpoint 3 finding | `ask_services.py`, `debrief_reasoning.py`, `prospect_contracts.py`, `prospect_services.py`, `packages/shared/src/index.ts`, `find/[id]/page.tsx`, `prospect-find.tsx`, `prospect-people.tsx`, `prospect-research-brief.tsx`, `crm-record-panel.tsx`, `opportunity-list.tsx`, `opportunity-pipeline-panel.tsx`, `opportunity-workspace.tsx`, `manager-deal-review.tsx`, `opportunity-events.ts` |
| Journey test support | `demo_data.py` — deterministic Campaign time repair using the production scheduling policy only |
| Accessibility/reliability fix | `error.tsx`, `api.ts`, `beta-feature-gate.tsx`, `core-navigation.tsx`, `create-studio.tsx`, `event-workspace.tsx`, `interaction-detail.tsx`, `manager-pipeline-view.tsx`, `pre-interaction-brief.tsx`, `settings-experience.tsx` |
| Terminology/coherence fix | `contacts/[id]/page.tsx`, `ask-revenueos.tsx`, `beta-onboarding.tsx`, `contact-outreach-workspace.tsx`, `manager-home-attention.tsx`, `revenue-brain-timeline.tsx` |

No production change falls outside these categories.

## Boundaries and remaining work

- WO-039B: Create template/output compatibility, preview/PPTX equivalence, download
  bearer design, hostile-file limits and `pypdf` remediation.
- WO-039C: production identity/RLS/backup/restore/retention/deletion operations,
  real-tenant onboarding and native CRM import/deduplication/merge.
- Formal human assistive-technology and design-partner usability sessions remain
  release activities; automated semantics, keyboard use and 390 px containment are
  covered here.

See the [final remediation tracker](wo-039a-remediation-checklist.md),
[seller journey](../01-product/end-to-end-revenueos-seller-journey.md),
[reliability contract](../01-product/journey-reliability-contract.md) and
[security review](../03-engineering/wo-039a-security-privacy-review.md).
