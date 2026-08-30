# CRM data migration and portability playbook

## Schema rollout (`0043_native_crm`)

1. Back up the database using the normal private-beta procedure.
2. Before deployment, query organisation-scoped duplicate `companies.normalized_domain` and case-normalised non-null `contacts.email` groups. The migration repeats this check without logging values and stops if any exist.
3. Reconcile duplicates manually with authorised customer context. Do not invent an automated merge: related Evidence, Interactions, Opportunities, Outreach, Prospect, Campaign and Event lineage makes destructive re-parenting unsafe.
4. For a WO-034-only release, run `alembic upgrade 0043_native_crm`; in the current
   baseline run `alembic upgrade head` and verify `0044_native_pipeline`, new
   indexes/tables and forced RLS.
5. Smoke-test Core record reads before enabling the global flag or any CRM entitlement.
6. Enable `API_FEATURE_NATIVE_CRM_ENABLED`, grant `crm` to the chosen synthetic/design-partner organisation, then have an admin explicitly choose its mode.

Downgrade to `0042_roi_business_case` removes CRM settings/custom fields/history and archive/location/status additions, so it is destructive for newly entered CRM metadata. Prefer feature/entitlement disable as operational rollback. Only downgrade after export/backup and confirmation that those rows may be discarded.

## Switching source of truth

WO-034 is not an external-CRM migration tool. Selecting external requires active HubSpot. Selecting native is blocked while active field mappings exist. Operators must inventory mappings, export/backup, agree field ownership, disable mappings and only then confirm native mode. No records or external IDs are copied/deleted by the mode operation.

## Current portability

Organisation data export version 25 includes canonical Company/Contact/Opportunity
fields, `crmSettings`, `crmCustomFieldDefinitions`, `crmCustomFieldValues`,
`crmRecordChanges`, native pipeline definitions and immutable Opportunity stage events.
It excludes secrets/provider tokens and follows the existing authorised maintenance
boundary.

## Deferred operational CSV

User-facing CRM CSV import/export is explicitly deferred. A compliant follow-up must reuse hardened parsing and provide admin-only access, explicit authority attestation, UTF-8/null-byte/size/row/column limits, no raw-file retention, preview and mapping, exact duplicate skip/review, idempotent confirmation, formula-injection-safe exports, canonical/custom fields only, and safe results. Account import should precede Contact linking; Opportunity import should follow WO-035. Imported Contact data must never grant Engage contactability or outreach permission.
