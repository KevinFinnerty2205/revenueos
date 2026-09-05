# Native CRM architecture

- **Status:** Implemented by WO-034
- **Migration:** `0043_native_crm`
- **Principle:** Company, Contact and Opportunity are the CRM records; Sales Brain remains the product centre.

## Product boundary

RevenueOS supports one canonical sales graph in two organisation modes:

- **RevenueOS-native:** local canonical fields are authoritative and normal record editing needs no connector.
- **External CRM:** local canonical records remain available to Sales Brain, while active HubSpot mappings retain the WO-025C field-authority rules.

There is no `CRMAccount`, `CRMContact`, `CRMOpportunity`, Lead, CRM Task, CRM Note or CRM Activity model. Accounts are `companies`; People are `contacts`; Actions are existing tasks/proposals; recent activity is a bounded read model over Interactions, Outreach, Tasks, Event encounters and Opportunities.

## Current data model

| Storage                                  | Purpose                                               | Guardrails                                                                         |
| ---------------------------------------- | ----------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `companies`, `contacts`, `opportunities` | Canonical CRM records                                 | Organisation-scoped repositories and forced RLS; archive timestamp; existing owner |
| `organisation_crm_settings`              | One explicit system-of-record choice per organisation | `native` or `external`; external v1 is HubSpot; admin only                         |
| `crm_custom_field_definitions`           | Bounded schema metadata                               | Account/Contact/Opportunity only; 25 active fields per type; immutable key/type    |
| `crm_custom_field_values`                | One strictly typed value per record/definition        | Text, number, date or boolean columns; no executable/arbitrary JSON value          |
| `crm_record_changes`                     | Human-readable field change history                   | Field, safe old/new value, actor, source and timestamp; never operationally logged |

All new tables include organisation scope in keys and relationships and use PostgreSQL forced RLS. The polymorphic record ID in custom values/history is checked by the tenant-scoped service before write; definitions and actor membership have composite tenant FKs.

## Core-record evolution

WO-034 adds Company location, Contact employment status (`active` or `left_company`) and soft archive timestamps. Existing Opportunity stage/status/value/currency/close-date fields are reused; WO-035 owns pipeline definitions, board movement and stage history. Strong partial unique indexes enforce organisation plus normalised Company domain and organisation plus case-normalised Contact business email. Names are never auto-merged.

The `0043` migration performs a metadata-only duplicate preflight before creating these indexes. If existing strong duplicates exist, deployment stops with a content-free remediation message. There is no automatic destructive merge.

## Policy and entitlement

Canonical record create/read/update, Native CRM setup, custom fields, activity/history
and archive/restore are Core under `API_FEATURE_NATIVE_CRM_ENABLED`. The `crm`
commercial entitlement now means supported external CRM connectors, not Native CRM.
External mode and new HubSpot connection/sync actions require it; downgrade preserves
external history as read-only. Only administrators configure mode or field definitions
and archive/restore records; plan access is operator-owned. Archived records reject
all field mutation.

Owners are active organisation members. Administrators may assign any active member; members may assign only themselves. Disabled owners remain readable historical references and can be reassigned; no owner change cascades to related records.

## Authority and provenance

Native mode defaults core fields to `revenueos_authoritative`. External mode reuses enabled HubSpot field mappings with `crm_authoritative`, `revenueos_authoritative` or `review_before_sync`. A CRM-authoritative mapped field is visually marked read-only, omitted by the web edit form and rejected by the API if submitted. Mode change requires confirmation; external mode requires an active HubSpot connection, and native mode is blocked while active mappings remain.

Record authority is separate from evidence provenance. Manual, Prospect promotion, Event promotion, external CRM and future reviewed-Action origins remain distinguishable. Promoted Contact field provenance continues to use the WO-027 field-source model.

## Custom fields

Supported v1 types are `short_text`, `number`, `date`, `boolean`, `single_select` and `url`. Single-select has at most 50 unique bounded options; URL values must be HTTP(S); text is rendered as text; fields are optional and secondary in the workspace. Definitions are admin-owned, reserved core keys are rejected, labels/order/options may be edited, and archive preserves values/history. Retired select values remain readable rather than being silently rewritten. Currency, multi-select, formula, relation, required, rich-text and executable field types are deliberately absent.

## Change history and activity

Manual canonical edits, record creation, archive/restore, custom-field changes and explicit Prospect/Event promotion hooks append field-level history with actor and source. The history store is tenant data, not an application log. The activity projection reads existing sources, applies their module/feature availability, orders them by occurrence and returns at most 50 items. It does not copy customer content or create a second activity ledger.

## Concurrency and failures

Company, Contact and Opportunity edit contracts accept `expectedUpdatedAt`; custom-value writes accept `expectedRecordUpdatedAt`. A stale value returns a safe `stale_write` conflict. Database duplicate races resolve to safe 409 responses with an existing-record identifier where available. Errors contain code, safe message, request ID and bounded metadata, never field contents.

## Deliberate deferrals

- Native reviewed-Action execution is not wired in WO-034. The existing executor is provider/connection-oriented; adding a local path without a provider-neutral intent/revalidation contract would risk bypassing human review. AI cannot mutate CRM state.
- Operational CRM CSV import/export is deferred. The current organisation export is
  version 25 and includes CRM settings, definitions, typed values and history plus the
  WO-035 pipeline state/history, so data is not held hostage. A future operational CSV
  flow must add preview, attestation, duplicate review, formula escaping and
  no-outreach-permission semantics before release.
- Tags are deferred because bounded single-select custom fields cover categorisation without adding another taxonomy.
- Merge, bulk edit, custom objects/workflows, team ownership, round robin, territories and custom-field search/filtering are not implemented.

## Related documents

- [Native CRM product guide](../01-product/native-crm.md)
- [Native CRM UX](../02-design/native-crm-ux.md)
- [CRM source of truth](crm-source-of-truth.md)
- [Native CRM API](native-crm-api.md)
- [Native CRM security review](native-crm-security-privacy-review.md)
- [Migration and portability playbook](crm-data-migration-playbook.md)
- [ADR 0054](../08-decisions/0054-canonical-record-native-crm.md)

## WO-035 extension

Native Pipeline reuses the same `Opportunity`, Core commercial access/CRM mode, owner, field
history and external authority model. Stable pipeline/stage IDs and append-only events
augment rather than replace the legacy stage/status compatibility fields. Native
definition administration is CRM-gated; the descriptive board/history remains a Core
consumer. See [Native Pipeline architecture](native-pipeline-architecture.md).
