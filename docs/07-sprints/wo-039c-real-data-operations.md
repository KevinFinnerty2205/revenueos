# WO-039C — Real-Data Operations & Native Onboarding

- **Branch:** `feature/pre-beta-wo-039c-real-data-operations`
- **Baseline:** `5f0a61c`
- **Status:** implemented; local validation and synthetic drill evidence below; draft PR remains unmerged
- **Migration:** `0050_real_data_operations`
- **Data/provider boundary:** synthetic data only; no real external mutation or paid service

## Outcome

WO-039C moves the repository from synthetic-only operations to a controlled supervised real-data design-partner implementation. Production identity fails closed unless an operator has provisioned the Clerk organisation/member. Real-data configuration rejects unsafe origin/host/log/storage/auth/mock-provider combinations. Preflight proves migration, runtime-role/RLS reset and private storage. Encrypted PostgreSQL plus object backup/restore, v29 export/deletion coverage, tenant/support/queue reports and operational runbooks make normal lifecycle work possible without database surgery.

Native CRM now provides a separate admin-only, explicit-map CSV preview/confirm path for Accounts, Contacts and open Opportunities plus deliberate Account/Contact merge. Raw CSV is re-sent on confirmation and never retained. Strong duplicates skip; possible matches are visible; no fuzzy auto-merge exists. Imported contact data never grants outreach permission, and open Opportunity stage state begins at `import_baseline` without invented history. Merge preserves historical provenance, applies the strictest suppression and blocks incompatible provider identities.

## Schema and contracts

Migration `0050` adds `operator_provisioning_events`, `crm_import_batches`, `crm_import_rows` and `crm_record_merges`; extends CRM record source and opportunity stage-source checks; applies composite tenant relationships, indexes, forced RLS and immutable-event triggers; and has a reversible downgrade. OpenAPI/shared contracts add templates, preview/confirm import and preview/confirm merge. Export schema is v29.

## Synthetic evidence

Automated evidence covers:

- production configuration matrices, security headers, no-JIT auth, provisioning/member idempotency and content-free diagnostics;
- PostgreSQL forced RLS across every material tenant table, missing-context/cross-tenant denial and connection reset; worker repositories set transaction-local tenant context on every claim/execution;
- migration upgrade/downgrade/re-upgrade and one-head/drift/identifier constraints;
- real `pg_dump`/`pg_restore` command shape, encryption, secret exclusion, object checksum recovery, source-target guards and corruption rejection;
- export v29, retention expiry, organisation deletion graph, membership/grant denial and cross-tenant boundaries;
- Account/Contact/Opportunity import mapping, limits, raw-content absence, preview-no-write, duplicate/retry/stale/concurrency behaviour, DNC restriction, custom fields and `import_baseline`;
- Account/Contact graph merge, stale/cross-tenant/member rejection, idempotency, custom conflicts, tombstone link, external mapping/provenance blockers and conservative suppression; and
- Settings import and CRM record merge browser components, keyboard-labelled controls and product-safe results.

The isolated drill provisioned and seeded one synthetic tenant, migrated both source and restore databases to `0050`, encrypted and verified a real `pg_dump` plus three private objects, restored into a distinct empty database/storage root, and compared selected high-risk table counts and every object hash. Source and restore each contained 2 Companies, 3 Contacts, 21 Opportunities, 20 Interactions, 17 Evidence items, 3 Targets and 4 Forecast judgements. The restored database passed the all-table forced-RLS proof across 137 tenant tables. A temporary non-superuser, non-`BYPASSRLS` runtime role then passed production-profile migration, tenant-context-reset, export-permission, object write/read/delete and approval preflight checks. No external provider was called.

The content-safe [drill evidence manifest](assets/wo-039c/drill-evidence.json) records timestamps, counts and encrypted archive hashes. Screenshots are synthetic and stored under `docs/07-sprints/assets/wo-039c/`; operational commands never capture customer content. The same drill remains mandatory in the named target environment, with observed RPO/RTO timing recorded there.

Reviewed visual evidence:

- [explicit-map import preview](assets/wo-039c/crm-import-preview-desktop.png);
- [confirmed import result](assets/wo-039c/crm-import-confirmed-desktop.png);
- [irreversible merge preview](assets/wo-039c/crm-merge-preview-desktop.png); and
- [merged source tombstone](assets/wo-039c/crm-merged-tombstone-desktop.png).

## Dependency decision

`cryptography` is constrained to the supported `>=50.0.1,<51.0.0` line and locked at 50.0.1. This removes the older production dependency gate while preserving AES-GCM connector/backup and Clerk JWT regressions. The workspace also overrides the transitive `browserslist` dependency to patched 4.28.7 after the final production audit identified the newly published 4.28.6 advisories. The exact production audit output belongs in the PR evidence; development-only findings do not silently become production exemptions.

## Frozen validation gate

Completed locally on 2 September 2026:

- `pnpm format`, `pnpm lint`, `pnpm typecheck` and `pnpm build:web` passed;
- `pnpm test`: 62 files and 230 tests passed;
- `pnpm test:e2e`: 67 journeys passed, including Account, Contact and open-Opportunity explicit-map import plus irreversible merge/tombstone flows;
- `pnpm api:lint`, `pnpm api:format` and `pnpm api:typecheck` passed (357 Ruff-formatted files; 238 mypy source files);
- `pnpm api:test`: 1,059 tests passed and 4 environment-specific tests skipped; the existing Starlette `httpx` deprecation warning remained non-failing;
- `pnpm api:migrate` advanced PostgreSQL from `0049` to `0050`; `pnpm api:migration:check` found no drift, with only the existing `recording_sessions`/`transcript_versions` sort warning;
- `pnpm build:api` produced the source distribution and wheel;
- the repository secret/prohibited-scope audit passed for 1,353 tracked/untracked files;
- production JavaScript and Python dependency audits reported no known vulnerabilities; and
- all relative links in the 19 changed/new Markdown files resolved locally.

Focused PostgreSQL proof also passed migration downgrade/re-upgrade and forced-RLS isolation. The isolated synthetic backup/restore/preflight results are recorded in the manifest above; the temporary databases were dropped and storage roots moved to Trash after verification.

## Readiness decision

Repository decision: **GO WITH RESTRICTIONS for one supervised real-data design partner**. This is conditional, not current blanket launch approval. For the named partner, owner/counsel must approve legal/privacy/DPA/subprocessor/data-location and AI decisions; the target must pass production preflight, Clerk/session proof, runtime-role RLS proof, encrypted backup plus measured isolated restore, alert/support verification and feature-profile review before any real data is entered.

Unsupervised beta: **NO-GO**. Commercial beta: **NO-GO**. HubSpot, external AI and every live provider remain individually gated; live Prospect and mailbox delivery are unavailable. No SLA, enterprise SSO/SCIM, billing or cross-tenant support UI is claimed.

## Recommendation and handoff

Choose **Option 2**: start a tightly supervised design-partner test using Native CRM with live email/research disabled, only after the named launch gates pass. Observe onboarding/support/import evidence before authorising a narrow Gmail delivery slice. If Gmail is later authorised, it must bind the exact seller mailbox, reviewed recipient/content, receipt/uncertain-state reconciliation, revoke/re-auth, unsubscribe/suppression and bounce/complaint operations; Campaign auto-send and open/click tracking remain out. Apollo qualification remains a separate owner-approved discovery covering licensing, DPA, Australian coverage, verification semantics, retention/deletion and unit economics. Do not start either in WO-039C.

WO-040 remains blocked. No Gmail, Apollo, Microsoft Graph, Salesforce, new AI, billing, generic ETL/workflow platform or paid service was added, and no external provider mutation occurred.
