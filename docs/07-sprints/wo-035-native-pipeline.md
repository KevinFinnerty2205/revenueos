# WO-035 — Native Pipeline

**Status:** implemented on `feature/epic-15-wo-035-native-pipeline`; draft PR required;
not merged.

## Delivered

- migration `0044_native_pipeline` with bounded tenant-isolated definitions, stable
  typed stages, canonical Opportunity assignment/outcomes, immutable transition events,
  forced RLS and clearly incomplete legacy baselines;
- one default RevenueOS pipeline per organisation, up to five active pipelines and
  twelve stages, exactly one Won/Lost, safe rename/reorder/add/default/archive controls;
- server-authoritative open-stage movement, optimistic stale-state conflict,
  idempotency, close Won/Lost and history-preserving reopen;
- seller-reported controlled outcome reasons, actual close date separate from expected
  close date and CRM field history for stage/status/outcome changes;
- Board/List/Closed experience with bounded filters, concise cards, deterministic
  attention, time tracking, accessible selects/modals and mobile grouped cards;
- grouped multi-currency descriptive summaries with no FX, weighting or probability;
- explicit read-only HubSpot authority and CRM-gated native configuration;
- organisation export v25, parent-lifecycle deletion, synthetic demo assignment,
  security/privacy/retention documents and WO-036/WO-038 contracts.

## Deliberate boundaries

Pipeline is workflow state, not customer Evidence. Movement cannot mutate Methodology
or Revenue Brain. There is no probability, weighted pipeline, forecast, predictive
close, forecast category, deal score, stage gate, workflow automation, required
stage-specific field, bulk move, saved view, target duration, analytics dashboard or
new AI capability.

Stable IDs plus constrained edits were chosen over full definition versions. Snapshot
names/types keep history readable, semantic type cannot change and in-use stages cannot
be archived. External CRM movement remains read-only until a reviewed provider-mapped
path is separately authorised.

## Evidence

![Native Pipeline board after explicit stage movement](assets/wo-035-native-pipeline-board.png)

Chromium scenarios cover Board/List/Closed, multi-currency separation, accessible
stage movement, close Lost, seller-reported outcome, reopen/history, external authority
and 390-pixel overflow. Backend integration covers migration baseline, stale/idempotent
transition, no Methodology mutation, Won/Lost/reopen, archive guard, cross-tenant stage
rejection, export and demo coherence. Standard automated checks make no real provider
call.

## Known limitations

Historical duration before tracking activation is unavailable. External CRM movement
does not yet execute a provider sync. Outcome taxonomies are standard and bounded, not
admin-customisable. There is no drag-and-drop because the explicit select provides the
simpler accessible v1 action. Advanced pipeline analytics remains WO-036 and
forecasting remains WO-038.

## Validation

The local gate passed on 30 August 2026:

- web formatting, ESLint and strict TypeScript checks;
- 203 Vitest tests across 56 files;
- 56 Chromium Playwright scenarios, including three Native Pipeline journeys;
- production Next.js build;
- Ruff lint/format and mypy over 211 API source files;
- 985 pytest tests passed with four environment-dependent skips, followed by both
  PostgreSQL RLS integration tests passing against the migrated local database;
- PostgreSQL upgrade through `0044_native_pipeline`, clean Alembic drift check and API
  source/wheel builds.

The draft pull request records the hosted CI result and remains unmerged.
