# Checkpoint 1B — Core readiness before Prospect

- **Type:** Documentation-only product, competitive, architecture and design review
- **Date:** 24 August 2026
- **Branch:** `docs/checkpoint-1b-core-readiness`
- **Decision:** **GO** to begin WO-026 Account & Lead Research
- **Design-partner readiness:** **READY WITH RESTRICTIONS**
- **Product code/schema/dependency change:** None

## Objective

Review the merged RevenueOS Core baseline through WO-025C and decide whether the
product is strong enough to begin Prospect, whether any Core capability or
foundational architecture work must move earlier, and under what conditions a small
supervised design-partner cohort may use it.

## Baseline reviewed

The branch started from the merged `main` commit containing WO-011 through WO-025C.
The review covered the Interaction and Evidence platform, Revenue Brain, Opportunity
Workspace, Action/Execution foundations, Sales Methodology, RevenueOS Daily,
WO-025A experience readiness, WO-025B Ask RevenueOS and WO-025C HubSpot Focused CRM
Sync.

The latest application migration is `0034_crm_sync`. The ordered upgrade chain was
checked in an isolated development database. This does not replace PostgreSQL/RLS or
target-environment validation.

## Work performed

- read the current product, design, engineering, AI, integration, security, privacy,
  decision, roadmap and sprint records relevant to Core and Prospect;
- inspected current desktop and 390-pixel mobile product surfaces using synthetic
  data and deterministic/local capability paths;
- reviewed preparation, capture, post-interaction, methodology, Daily, Search/Ask,
  Action and exact HubSpot preview/confirmation states;
- compared current Core breadth and differentiation with current official Airspeed
  platform, CRM automation, forecasting, seller and integration material, plus the
  manager/coaching/forecast expectations visible in current Gong and Clari material;
- assessed whether forecast, coaching, manager visibility, win/loss, analytics,
  targets, Salesforce or another Core work order must move before Prospect; and
- documented the design-partner, launch, provider, mail-delivery and Stage B gates.

No product code, API contract, route, component, dependency, schema, migration,
provider configuration or runtime behaviour was changed.

## Deliverables

- [Checkpoint 1B decision](../06-roadmap/checkpoint-1b-core-readiness.md)
- [Core go-to-Prospect product readiness](../01-product/core-go-to-prospect-readiness.md)
- [Prospect foundation engineering readiness](../03-engineering/prospect-foundation-readiness.md)
- [Core post-WO-025C simplicity review](../02-design/core-post-025c-simplicity-review.md)
- this sprint record

The documentation index and end-to-end roadmap were updated to make the decision
discoverable and to replace the conditional Checkpoint 1B placeholder with its result.

## Findings

### Core loop

Core is a coherent active-opportunity product: Daily → prepare → deliberate capture →
review/correct → Opportunity/methodology → next Action → reviewed HubSpot update →
Daily. Ask provides a safe bounded access path over the same authorised knowledge.

### Competitive position

RevenueOS is competitive on active-opportunity intelligence and stronger on explicit
provenance, correction, no-recording field work and review-first execution. It is
behind Airspeed on automatic capture/CRM breadth, forecasting, manager/coaching,
win/loss and automation. Those gaps are acknowledged rather than relabelled.

### Architecture

Prospect can reuse the current modular monolith, tenant/RLS, canonical entity,
Evidence, provider, worker, Revenue Brain and Action boundaries. WO-026 needs a
separate tenant-owned research/source/finding/promotion lifecycle, but no pre-emptive
rearchitecture or pre-WO-026 migration.

### Experience

The primary desktop/mobile hierarchy is understandable and focused. Small
terminology, Settings diagnostic-language, completed-Interaction action-label and
copy issues remain non-blocking refinements.

### Launch boundary

Product readiness is not production launch approval. Synthetic supervised use is
possible now. Real customer data remains prohibited until target-environment
identity, RLS, privacy, provider, retention, export/deletion, backup/restore and
operational gates are complete. HubSpot additionally requires target OAuth and live
sandbox connect/revoke/preview/confirm/reconcile evidence.

## Decisions

1. **GO to WO-026.** No missing Core capability blocks Prospect foundations.
2. Keep forecast at WO-038 and coaching/manager visibility at WO-039.
3. Keep analytics at WO-036, Win/Loss at WO-036B and targets at WO-037.
4. Keep HubSpot first; Salesforce remains a conditional WO-042 expansion.
5. Insert no additional Core work order before WO-026.
6. Keep the Stage B order WO-026–031, but do not allow WO-029 live send until one mail
   ecosystem is selected, approved and implemented behind the Action boundary; it may
   remain draft-only otherwise.
7. Run controlled Core partner validation and target-environment launch evidence in
   parallel with bounded Prospect engineering.
8. Stop at Checkpoint 2 before Stage C.

## Honest market boundary

The broad claim “Finish the meeting. RevenueOS handles the admin.” is not ready
without qualification. The current supported form is:

> Finish the meeting. RevenueOS prepares the follow-through and applies the HubSpot
> update you review and confirm.

Forecast, automatic rep coaching, general CRM autofill, Salesforce, automatic mail
send, background recording and autonomous revenue execution remain future.

## Required validation after this review

The next evidence should measure unaided first-journey completion, time to useful
brief/review/action, correction and unsupported-claim rates, Ask supported/cited/
correct-refusal outcomes, HubSpot match/confirm/retry/conflict/recovery, admin minutes
saved, partner return/willingness to pay, Prospect source trust and accepted-promotion
rate, and all security/privacy/support incidents.

## Validation record

Local validation completed on 24 August 2026:

- targeted Prettier check over all seven changed documents — passed;
- local Markdown target check — 353 links checked, all targets present;
- `python3 scripts/ci_audit.py` — passed for 782 tracked files;
- `git diff --check` — passed;
- `pnpm format`, `pnpm lint`, `pnpm typecheck` — passed;
- `pnpm test` — 162 tests passed;
- `pnpm test:e2e` — 31 Playwright tests passed;
- `pnpm build:web` — passed;
- `pnpm api:lint`, `pnpm api:format`, `pnpm api:typecheck` — passed;
- `pnpm api:test` — 834 passed, 4 skipped, with one upstream deprecation warning;
- `pnpm api:migrate` against an isolated `sqlite+aiosqlite` database — the complete
  `0001_initial_schema` through `0034_crm_sync` chain passed;
- `pnpm api:migration:check` — no new upgrade operations detected; and
- `pnpm build:api` — source distribution and wheel built successfully.

The migration check emitted the repository's existing SQLAlchemy warning about the
mutually dependent recording-session/transcript-version tables. It did not report
schema drift. CI status is recorded on the draft pull request.

## Completion boundary

This checkpoint is complete when these documents are internally consistent, indexed,
validated, committed, pushed and reviewed through a draft pull request. It authorises
only the decision to begin planning/implementing WO-026 through a separate approved
work order. It does not authorise WO-027–045, a production launch or a design partner
to process customer data outside the stated gates.
