# WO-033 — ROI & Business Case Builder

**Status:** implemented on `feature/epic-14-wo-033-roi-business-case-builder`; draft PR required; not merged.

## Delivered

- migration `0042_roi_business_case` with four forced-RLS tenant tables and Create presentation references;
- strict Value Model/Business Case contracts, repositories, services and APIs;
- `bounded_decimal_v1` parser, dimension validator, canonical AST loader and Decimal evaluator;
- admin model form/version/approval workflow and member Business Case builder/review/approval workflow;
- explicit conservative/base/upside and bounded one-variable sensitivity;
- negative/no-payback handling, source freshness/deletion invalidation and export v23 coverage;
- `approved_business_case` Create context, claim lineage, material assumptions/disclaimer and export revalidation;
- Opportunity entry point, responsive UI, API/engine/integration/web tests and documentation/ADRs.

## Deliberate boundary

No AI number generation, Excel engine/import, arbitrary execution, FX, tax/GST, NPV/IRR, Monte Carlo, benchmark scraping, CPQ, CRM writes, Revenue Brain mutation or Methodology confirmation. Current untyped Evidence/public prose cannot auto-prefill an exact number.

## Validation

The final local gate passed:

- Prettier, ESLint and TypeScript;
- 190 Vitest tests and 51 Playwright tests;
- production Next.js build;
- Ruff lint/format and mypy across 200 API source files;
- 967 pytest tests against PostgreSQL, including forced-RLS isolation and migration coverage;
- PostgreSQL upgrade, verified-empty downgrade/re-upgrade, current-head and Alembic drift checks;
- API source/wheel builds, dependency audit, repository secret/prohibited-path audit,
  documentation links and `git diff --check`.

Pytest reported only the existing Starlette `httpx` deprecation and the known Alembic
table-sort warning for the pre-existing recording/transcript cycle. CI remains the
authoritative remote result and is recorded on the draft pull request.

## Screenshot review

- [Approved Business Case — desktop](assets/wo-033-business-case-desktop.png)
- [Business Case approval — mobile](assets/wo-033-business-case-mobile.png)
- [Value Model administration — desktop](assets/wo-033-value-model-admin.png)

The first narrow-screen pass exposed a horizontally clipped provenance table. The
mobile presentation now uses stacked provenance cards while the larger-screen table
remains available. Negative ROI, unavailable payback, formula disclosure, scenario
labels, material assumptions, source origin, disclaimer and the approval boundary are
all visible. The existing four-item mobile navigation remains unchanged.
