# WO-028 — Territory & ICP Intelligence

## Outcome

Implemented versioned Target Markets and bounded, explainable account discovery on
the WO-026/027 Prospect foundation. Sellers can understand why a company fits, where
data is missing and whether RevenueOS already has an Account or active Opportunity.

## Shipped

- migration `0037_territory_icp` with six forced-RLS tenant tables and immutable
  definition/candidate/reason history;
- guided administrator builder, archive/edit revisioning and historical run views;
- provider-neutral company discovery contract plus six-company deterministic mock;
- categorical matching with explicit exclusions, missing-data handling, origins and
  trust states—no numeric score or intent claim;
- exact-domain Account/open-Opportunity whitespace context with no downstream truth mutation;
- fresh-result reuse, explicit refresh lineage, idempotency and tenant/user daily quotas;
- per-user save, not-relevant and restore actions;
- reuse of WO-026 Account Research and Prospect Research Target identity;
- privacy export schema 18, retention protection and complete organisation deletion;
- desktop/mobile UI, synthetic demo data, API/UI/E2E/migration/RLS coverage and docs.

## Provider decision

Apollo, People Data Labs and Crunchbase were reviewed from official documentation.
No live provider, paid plan or trial was activated. Standard tests and demo data make
no real external request; the mock fails closed in production.

## Boundary confirmation

WO-028 does not add scoring, predictive conversion, purchase intent, scraping,
sensitive targeting, outreach, campaigns, background monitoring, automatic Company,
Contact, Opportunity, Evidence, Methodology, Stakeholder, Revenue Brain or Action
creation, or user-facing bulk export.

## Validation and screenshots

The exact validation commands, desktop/mobile screenshot review and CI result are
recorded in the draft pull request. Assets use the `docs/07-sprints/assets/wo-028-*`
prefix.
