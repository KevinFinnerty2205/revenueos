# Checkpoint 2 — Prospect and Engage validation record

- **Date:** 27 August 2026
- **Branch:** `docs/checkpoint-2-prospect-engage-validation`
- **Type:** Product, competitive, design, architecture and roadmap checkpoint
- **Implementation scope:** Documentation and validation only
- **Decision:** **GO** to plan WO-032 Create

## Objective

Validate the completed WO-026–031 Prospect and Engage slice separately and as a
connected top-of-funnel workflow. Decide whether to proceed to WO-032 Create, insert a
smaller provider/foundation work order or stop/rework the product direction.

## Baseline confirmed

- `main` and the review branch began at merge commit `898faf8`.
- WO-026, WO-027, WO-028, WO-029, WO-030 and WO-031 are present in `main` through
  merged pull requests 47–52.
- Alembic has one head, `0040_event_intelligence`.
- The worktree was clean before review.
- The review introduced no production code, migration, dependency, route, provider,
  AI capability, component or runtime behaviour.

## Evidence reviewed

The checkpoint read the current WO-023 platform blueprint, Checkpoint 1B decisions,
WO-026–031 sprint records and the relevant current contracts for:

- RevenueOS Prospect, Engage, Create, Target Markets, Account/Person Research,
  Buying Committee Hypotheses, business-contact trust, personalised outreach,
  Campaigns/Sequences, Events and commercial packaging;
- information architecture, Find/Target Market/Research/Outreach/Campaign/Event/mobile
  experience and the proposed Create experience;
- research, person/contact, provenance, source/citation, outreach, Campaign scheduling,
  Event import/matching, entitlements, file/template and end-to-end platform
  architectures;
- tenant isolation, responsible research/outreach, suppression, auto-send, Event
  authority, retention/export/erasure, private-beta launch and risk controls;
- research, contact and mailbox provider evaluations and deferred reply detection; and
- the current end-to-end roadmap and WO-032/033 dependencies.

Current official product material for Apollo, Clay, LinkedIn Sales Navigator, Outreach,
Salesloft, HubSpot and Gong informed the competitive benchmark. Current Gmail and
Microsoft Graph documentation informed the mailbox recommendation. ACMA and OAIC
guidance informed the Australian outreach operating gate. The checkpoint does not
make a legal certification or feature-parity claim.

## Browser review method

Docker was unavailable in the local environment, so the review used a disposable
SQLite database with no production/customer data. The full migration chain ran to
`0040_event_intelligence`; the API, web app and worker ran with development mock
authentication and deterministic mock providers. Synthetic demo data was seeded with
zero provider calls.

The in-app browser reviewed desktop at 1440 × 900 and mobile at 390 × 844. Committed
WO-028/031 responsive screenshots were inspected where a reproduced local hard-
navigation fetch failure prevented a stable Event/Target Market refresh.

### Browser evidence

- Find provides clear known-company and Target Market starts.
- Target Market results explain fit, missing data, relationship context and source-
  dated developments without implying intent.
- Account and Person briefs clearly separate verified, provider-supplied, inferred and
  unknown context and expose citations.
- Person briefs remain professional-only and label buying roles as hypotheses.
- Company and Contact promotion are explicit and do not create downstream truth.
- Contactability separates address trust from permission before outreach.
- One-to-one outreach exposes sources, exact sender/recipient/content and a conspicuous
  simulation-only confirmation.
- Campaigns remain small, immutable, reviewable and free of open/click tracking.
- Events keep attendee authority, matching, planning, seller notes, promotion and
  outreach boundaries visible.

### Reproduced refinements

- Person promotion before Company promotion returns a safe conflict but no direct
  recovery action.
- Target Market candidates appear as **Research queued** before any research job is
  started.
- Local hard navigation intermittently rendered **Failed to fetch** or incomplete
  capability navigation despite healthy API responses.
- A seeded Campaign displayed a next-send time outside its stated local send window.
- The mobile Event tab row clips its fourth label at 390 pixels.

These are classified as design-partner or beta refinements, not blockers before
Create.

## Decision record

The chosen option is:

> Proceed to WO-032 Create. Keep Prospect and Engage. Do not insert a new foundational
> domain work order. Activate a live Prospect provider in parallel before real
> provider-backed research, and implement the first design-partner-selected mailbox
> slice before any external Engage sending.

Reasons:

1. the source → promotion → outreach → Interaction → Evidence boundary is coherent;
2. tenant, provenance, suppression, approval, Event and fail-closed provider controls
   are strong enough to build on;
3. missing production providers affect live availability and commercial proof, not
   Create’s source/interface foundation;
4. a provider work order without named customer ecosystem/coverage evidence would
   create premature operational commitments; and
5. Create has an independently useful next experiment and its own secure file/source
   gates.

## Outputs

- [Primary Checkpoint 2 decision](../06-roadmap/checkpoint-2-prospect-engage-validation.md)
- [Prospect and Engage product readiness](../01-product/prospect-engage-readiness.md)
- [Prospect and Engage simplicity review](../02-design/prospect-engage-simplicity-review.md)
- [Prospect and Engage foundation review](../03-engineering/prospect-engage-foundation-review.md)
- targeted updates to the end-to-end roadmap, package/module contracts and
  documentation index

## Scope explicitly not authorised

- WO-032 implementation or any production code;
- a research, mailbox, event or other provider adapter;
- production customer-data use or design-partner launch;
- live email, reply detection, open/click tracking or Campaign auto-send;
- a new schema, migration, route, component, dependency or AI capability;
- both mailbox ecosystems, scraping or generic sales automation; and
- merging the checkpoint pull request.

## Validation record

Local validation completed on 27 August 2026:

- Prettier passed for every changed Markdown file; the repository `pnpm format` gate
  passed;
- every relative Markdown link in the changed files resolved;
- both Mermaid diagrams rendered successfully;
- `git diff --check` passed and the staged paths are documentation only;
- web ESLint and TypeScript passed;
- Vitest passed 50 files / 184 tests;
- Playwright passed 46 tests, including the Prospect, Target Market, outreach,
  Campaign and Event journeys;
- Ruff, Python formatting and mypy passed;
- pytest passed 927 tests with four environment-specific skips and one existing
  deprecation warning; pull-request CI supplies the PostgreSQL service evidence;
- the migration chain reached `0040_event_intelligence` and Alembic reported no drift;
  and
- web and API builds passed.

No runtime behaviour is changed by this checkpoint. The draft pull request remains
responsible for the normal GitHub Actions web/PostgreSQL confirmation.
