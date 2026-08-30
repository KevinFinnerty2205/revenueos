# WO-038 — Transparent Forecasting

- **Status:** Implemented; local validation passed
- **Branch:** `feature/epic-16-wo-038-transparent-forecasting`
- **Date:** 30 August 2026

## Outcome

WO-038 adds Core Forecast under Insights and an Opportunity Workspace entry point.
The product compares canonical Actual, matching Target, inclusive seller cases and a
separate empirical historical baseline without fixed stage probability or AI/ML.

## Delivered

- migration `0047_transparent_forecast`: tenant periods, judgments and immutable
  revisions with forced RLS, composite tenant relationships and maintenance triggers;
- `/api/v1/forecast` metadata/read/review/history/calibration contracts;
- 730-day exact-stage final-outcome model, minimum sample 10, no fallback;
- owner-only period-specific seller review with optimistic revisions and stale facts;
- category realization calibration, sample-gated and explicitly not rep scoring;
- WO-036 `SalesMetricService` Actual and WO-037 Target service reuse;
- organisation/member scope, currency separation, pagination, export v27 and demo
  reset/deletion support;
- responsive Forecast, deal history, calibration and Opportunity entry point;
- deterministic synthetic data and desktop/mobile Playwright evidence; and
- product/design/engineering/security/ADR documentation.

## Boundaries

No Opportunity probability, stage weights, predicted close date, FX, fiscal calendar,
manager override, hierarchy, CRM forecast sync, target-triggered Action, scoring,
ranking, LLM/provider, ML, Evidence mutation, Methodology weighting or Revenue Brain
weighting was added. WO-039 owns independent manager judgment/coaching.

## Validation

The complete API, web unit and browser suites passed alongside formatting, lint,
type-checking, production builds, migration apply/drift checks and dependency audit.
CI results are recorded in the draft pull request. Screenshots are
`assets/wo-038-forecast-desktop.png` and `assets/wo-038-forecast-mobile.png`.
