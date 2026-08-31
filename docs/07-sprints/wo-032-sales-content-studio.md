# WO-032 — RevenueOS Create: Sales Content Studio

- **Branch:** `feature/epic-14-wo-032-sales-content-studio`
- **Status:** implemented for draft PR; not merged
- **Migration:** `0041_create_studio`
- **Export schema:** v22
- **Boundary:** approved-template, Account-bound, review-first editable PPTX generation

## Outcome

WO-032 adds the separately entitled Create Studio. Administrators upload an authorised
PPTX, review every slide and approve an immutable template version. Sellers choose an
Account, optional Opportunity, objective, audience, approved template and optional
focus; inspect and adjust a deterministic plan; generate through the durable worker;
review exact claim provenance; make bounded text edits; approve; and obtain a private
editable PPTX download.

Migration `0041_create_studio` adds seven tenant-owned forced-RLS tables and a bounded
worker eligibility function. The API adds strict contracts, explicit tenant
repositories, a customer-safe context builder, claim/source revalidation, atomic
quotas and private storage. The existing worker processes template manifests and
presentation versions. Export v22, object-first organisation deletion and storage
reconciliation cover source and derived assets.

## Security and scope

PPTX ingestion rejects malicious/unsupported ZIP/XML, active/embedded/external
content, embedded fonts, SVG and resource exhaustion. Hidden slides, notes and
comments never enter generated output. The typed context allow-list excludes raw
transcripts, notes, recordings, financials, probability/forecast, methodology score,
internal risk/coaching, contactability and suppression. Public research stays
distinct from customer Evidence. Claim manifests and human approval are mandatory;
edits invalidate approval.

No AI provider, generated imagery, logo scraping, pricing, ROI, proposal/DOCX/PDF,
speaker-note generation, external send, Office execution, blank-canvas design or
second service/datastore was added. The parser is not described as an antivirus
scanner. Production data and launch still require repository-wide target-environment
privacy and operational approval.

## Experience evidence

- [desktop Create Studio](assets/wo-032-create-studio.png)
- [desktop plan review](assets/wo-032-plan-review.png)
- [desktop claim review](assets/wo-032-claim-review.png)
- [synthetic customer deck](assets/wo-032-synthetic-customer-deck.pptx)
- [synthetic deck montage](assets/wo-032-synthetic-customer-deck-montage.webp)

The UI keeps Create in entitled desktop navigation and preserves the existing four-
item compact mobile navigation. Account and Opportunity workspaces provide contextual
entry points. Structured review is accessible without a pixel preview; generated PPTX
is the authoritative visual output.

## Verification

The complete local gate passes: formatting, web/API lint, strict TypeScript/mypy,
188 web component tests, 939 API tests (four intentionally skipped in the ordinary
suite), both PostgreSQL RLS integration tests with every Create table populated, all
48 Playwright journeys, web/API builds, PostgreSQL Alembic upgrade and autogenerate
check, repository security audit and `git diff --check`. The synthetic 10-slide PPTX
additionally passes the presentation overflow checker.

## Rollback

Disable `API_FEATURE_CREATE_ENABLED` for environment-wide containment or the tenant's
`create` entitlement for organisation-specific containment; both preserve retained
records. Downgrade below `0041_create_studio` only after an approved export and object
retention/deletion decision because it removes the Create schema.

## WO-039B trust hardening

WO-039B supersedes the original template/output/download trust assumptions without
expanding Create's product scope. Migration `0049_create_trust` adds versioned
compatibility/output-validation metadata and tenant-owned one-time download grants.
Editable slides now require usable mapped placeholders; generated decks are reparsed
against exact render expectations; and authenticated download is server-mediated,
single-use and approval/checksum bound. See the
[WO-039B record](wo-039b-create-trust-security.md) and
[supported profile](../01-product/create-powerpoint-trust-guide.md).
