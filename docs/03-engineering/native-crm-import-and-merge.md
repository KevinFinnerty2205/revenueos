# Native CRM import and merge architecture

## Import boundary

`POST /api/v1/crm/imports/preview` and `/confirm` accept strict base64-wrapped UTF-8 comma CSV solely for the bounded admin flow. Limits are 5 MB decoded, 5,000 data rows and 100 columns. Duplicate/blank headers, malformed quoting, NUL/control characters, invalid dates/decimals/currencies/emails/domains and oversized values fail with safe codes. BOM and quoted standard CSV are supported; XLS/XLSX, archives, formulas, delimiter detection and executable transformations are not. Formula-leading cells remain literal text.

Mappings are a strict source-header-to-canonical/custom-field map; `null` means explicitly ignored. Owner and stage source values map to active same-tenant UUIDs. Custom fields must already exist and type-check. Accounts require name; Contacts require name/business email and a deliberate Account reference when supplied; Opportunities require a canonical Account, owner, pipeline/stage, decimal amount, ISO currency and ISO date. V1 accepts open Opportunities only.

Preview parses and validates without canonical mutation. A content-free `crm_import_batches` row stores type, state, source/mapping/snapshot fingerprints, counts, actor and expiry; `crm_import_rows` stores row number, deterministic idempotency key, disposition, safe issue code and resulting canonical ID only. The raw file and values are not persisted. Confirm resends the bytes/mapping, binds to the batch hashes, locks the batch, reparses and revalidates current duplicates/relationships. A changed duplicate snapshot blocks affected rows for a new preview. Repeating confirmation returns the same canonical IDs.

Strong matches are exact normalised Account domain or Contact business email and default to skip. Exact canonical Account name, Account-plus-Contact full name and Account-plus-open-Opportunity name are only possible duplicates. There is no fuzzy/AI match and no automatic update/merge. `do_not_contact=true` may add a restrictive suppression; false never removes one and CSV never creates a permission basis, Campaign enrolment, Prospect entity, Evidence, Methodology, Action, Brain or forecast judgment.

Imported records use CRM source `imported` and batch/row provenance. Imported open Opportunities receive exactly one `import_baseline` stage event with no invented prior transition or stage-entry time. Analytics/forecast history before import remains incomplete.

## Merge boundary

`POST /api/v1/crm/merges/preview` and `/confirm` support admin-only same-type,
same-tenant Account or Contact merges under active Core commercial access and Native
CRM mode. Preview fingerprints both records and enumerates permitted field conflicts.
Confirmation requires a survivor/source choice and explicit value selections, then
locks both records in sorted UUID order and revalidates fingerprints.

The transaction moves the complete inspected canonical relationship graph, resolves safe unique collisions, applies selected fields/custom values, preserves source/history snapshots, archives the source and writes immutable `crm_record_merges` metadata. The source ID resolves as a tombstone with survivor deep link; restore/edit is blocked. Repeating the same merge is idempotent; inverse/double/stale/cross-tenant attempts fail.

Incompatible active external CRM object mappings block. Campaign/provenance collisions that cannot be represented safely block. Historical Evidence speaker/participant snapshots, outreach recipient facts and customer statements are not rewritten. Prospect/contact provenance is preserved. Contact suppression hashes for both identities move/retain conservatively and the survivor receives the most restrictive contactability state; a merge can never make an address contactable.

## Security, retention and audit

All new rows carry organisation scope, composite tenant relationships where applicable, forced PostgreSQL RLS and explicit repository predicates. Batch/merge mutation uses transactions; merge history and provisioning history have immutable database triggers. Audit material is identifiers, actor, type, state/counts and safe codes only—never names, email, amount, CSV cells or field conflict values.

Export v29 includes safe batch/row/merge metadata. Retention expires unconfirmed previews. Organisation deletion removes import/merge rows, canonical records and relevant objects through the established dependency graph. There is no import rollback or merge undo; recovery from an infrastructure failure is idempotent retry, while an erroneous human-confirmed merge requires incident containment and, only if approved, isolated backup recovery.
