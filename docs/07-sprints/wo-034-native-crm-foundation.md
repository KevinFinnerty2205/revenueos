# WO-034 — Native CRM Foundation

**Status:** implemented on `feature/epic-15-wo-034-native-crm-foundation`; draft PR required; not merged.

## Delivered

- migration `0043_native_crm` with organisation CRM settings, bounded typed custom fields, field history, core record extensions, strong duplicate indexes and forced RLS;
- explicit RevenueOS/native or HubSpot/external mode with admin confirmation, entitlement/feature availability and guarded switching;
- canonical Account/Contact/Opportunity CRUD enrichment, tenant-safe one-person ownership, short forms/lists, optimistic concurrency and archive/restore;
- exact domain/business-email duplicate prevention with Open existing UX and no name merge;
- record overview, source-authority cues, custom values, bounded canonical activity and human-readable history in existing workspaces;
- preserved Prospect/Event promotion origins, Contact provenance and WO-025C external field authority;
- organisation export v24/deletion coverage, security/operations/migration documentation and deterministic API/web/migration/RLS/Playwright coverage.

## Deliberate boundary

Operational CRM CSV import/export is deferred; authorised organisation export provides portability. Native reviewed-Action execution is deferred until provider-neutral intent/revalidation exists, so AI cannot mutate CRM. Tags are covered by bounded select fields for now. Pipeline/stages/board remain WO-035. There is no Lead, CRM Task/Note/Activity, custom object/workflow, merge, bulk edit, team ownership, round robin, territory routing, CPQ, service or marketing CRM.

## Evidence

Automated tests make no real provider call. Sales Brain and its canonical relationship graph remain the centre of the product.

### Screenshot review

- [bounded Accounts list](assets/wo-034-accounts-list-desktop.png)
- [Account workspace with secondary CRM details](assets/wo-034-account-workspace-desktop.png)
- [CRM Settings and custom-field administration](assets/wo-034-crm-settings-desktop.png)
- [human-readable record history](assets/wo-034-record-history-desktop.png)
- [short Opportunity edit form](assets/wo-034-opportunity-edit-desktop.png)
- [strong duplicate warning and Open existing action](assets/wo-034-duplicate-warning-desktop.png)
- [HubSpot-managed field authority](assets/wo-034-hubspot-managed-field-desktop.png)
- [mobile Contact overview](assets/wo-034-contact-mobile.png)
- [mobile CRM details disclosure](assets/wo-034-contact-details-mobile.png)
- [mobile custom-fields disclosure](assets/wo-034-custom-fields-mobile.png)

The review reduced CRM prominence after the core overview: custom fields and record history now use disclosures, relationship activity remains visible, owner/mode stay clear and internal owner UUIDs are never shown. Accounts use six purposeful list columns, create/edit forms remain short, exact duplicate resolution is one action, and the 390-pixel Contact workspace has no horizontal overflow. There is no Lead conversion, duplicated Task/Note/Activity object or implementation-consultant setup path.

### Validation

- `pnpm audit`: no known vulnerabilities.
- `pnpm format`, `pnpm lint`, `pnpm typecheck`: pass.
- `pnpm test`: 54 files and 196 tests pass.
- `pnpm test:e2e`: 53 Chromium scenarios pass.
- `pnpm build:web`: production build passes.
- `pnpm api:lint`, `pnpm api:format`: Ruff passes; 310 files formatted.
- `pnpm api:typecheck`: strict mypy passes for 206 source files.
- `pnpm api:test`: 979 pass; four PostgreSQL-only tests are environment-gated in the default run; the same four pass separately against an isolated local PostgreSQL database.
- `pnpm api:migrate`, `pnpm api:migration:check`: a fresh PostgreSQL database upgrades through `0043_native_crm` with no model drift; `0043_native_crm` is the single head.
- `pnpm build:api`: source distribution and wheel build successfully.

The existing Starlette `TestClient` deprecation warning and the known Alembic sort warning for the pre-existing `recording_sessions`/`transcript_versions` cycle remain non-failing. Both isolated PostgreSQL validation databases were removed after use.
