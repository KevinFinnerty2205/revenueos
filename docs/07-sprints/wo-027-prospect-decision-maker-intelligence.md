# WO-027 — Prospect and Decision-Maker Intelligence

## Outcome

Implemented the smallest company-scoped, professional and source-backed Prospect Person workflow on the WO-026 foundation. Sellers can find a bounded set of relevant people, research one person, review buying-role hypotheses and explicitly create/link a canonical Contact.

## Shipped

- `0036_prospect_people`, including five forced-RLS tenant tables and nullable Contact email for honest unknown promotion;
- Prospect Person/domain enums, typed provider contracts, deterministic Northstar fixtures and strict validation;
- versioned person runs using the existing worker/source/observation pipeline;
- buying-role hypotheses and source links;
- contact points with field-level trust, verification method, expiry and export permission;
- explicit, conservative duplicate-safe Contact promotion and separate Contact research link;
- provider expiry, organisation retention/export/deletion and export schema 17;
- desktop/mobile People and person-research UX with no photos or outreach;
- API, repository, worker, migration, RLS, privacy-boundary, UI and Playwright tests.

## Provider decision

Apollo, Hunter, People Data Labs and Crunchbase were reviewed from official material. No production provider was approved; no paid service or trial credit was activated. All standard tests are deterministic and make no real external provider calls.

## Boundary confirmation

Prospect research remains separate from customer Evidence, Methodology, Stakeholder Intelligence, Revenue Brain and Ask RevenueOS. Promotion mutates only Contact and provenance. WO-028 owns ICP/territory; WO-029 owns future reviewed outreach.

## Validation and screenshots

Focused API, migration, UI and seven-scenario Prospect E2E suites pass. The final full gate and CI result are recorded in the draft pull request. Reviewed assets use the `docs/07-sprints/assets/wo-027-*` prefix.

## Known limitations

Discovery is company-scoped and mock-only. There is no global people database, scraping, sensitive/personality inference, bulk list/export, outreach, campaign enrolment, automatic Contact/Opportunity/stakeholder creation, background monitoring, score, native CRM expansion or provider-backed production coverage.
