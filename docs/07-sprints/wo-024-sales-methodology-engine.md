# WO-024 — Sales Methodology Engine

**Status:** Implemented and application-validated on
`feature/epic-11-wo-024-sales-methodology-engine`. RevenueOS Core. PostgreSQL
runtime migration/RLS validation remains a CI/environment check because no local
PostgreSQL service is available in this workspace.

## Delivered

- Immutable code registry for MEDDIC, MEDDPICC, BANT and SPICED.
- Tenant-owned bounded custom definitions with immutable versions and one
  organisation default or none.
- Deterministic canonical-fact projection over current validated Evidence, final
  Interaction Intelligence, Revenue Brain and safe Opportunity state.
- Explicit confirmed, partially supported, unknown, conflicting and stale states;
  source lineage, freshness, conflict references and immutable projection history.
- Review/correction with additive salesperson-reported clarification Evidence.
- Opportunity Deal and Settings UX with progressive disclosure, mobile layout,
  accessible controls, instructional empty/error states and no new navigation item.
- Bounded Pre-Interaction Brief/debrief questions and final-source Action Layer
  candidates. A typed gap context is available to the existing Next Best Action
  boundary; provisional Live Intelligence is excluded.
- Migration `0033_sales_methodology`, forced RLS, export schema 14, retention,
  opportunity/organisation deletion and deterministic BANT→MEDDPICC demo history.

## UX evidence

- [Desktop Opportunity Deal view](assets/wo-024-methodology-deal.png)
- [Mobile Opportunity Deal view](assets/wo-024-methodology-mobile.png)

## Deliberate decisions

Standard v1 definitions remain immutable code configuration; only custom definitions
need database version rows. Structured JSON keeps fields/sources inside immutable
projection content to avoid seven small tables while retaining traceability and
strict validation. Source fingerprints mark current views for refresh rather than
creating a second worker or blocking final intelligence. The v1 path is entirely
deterministic and makes no external provider calls.

## Not delivered

No Opportunity/team/user override, automatic queue, Daily, manager dashboard,
forecasting, qualification/completeness score, stage blocking, rep comparison,
employee surveillance, arbitrary rule engine, external connector or autonomous
action. Historical drill-down is intentionally light in the normal UI.

## Rollback

Disable `API_FEATURE_SALES_METHODOLOGY_ENABLED` to hide generation while retaining
data. Application rollback is compatible while `0033` remains applied. Database
downgrade removes methodology triggers/policies/tables only after export/backup and
must not be used while the application still serves WO-024 routes.
