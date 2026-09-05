# Native CRM operations

## Enable a design-partner organisation

1. Confirm deployment head is `0052_commercial_plans_trial`, `API_FEATURE_NATIVE_CRM_ENABLED=true` and `API_FEATURE_NATIVE_PIPELINE_ENABLED=true`.
2. Confirm the organisation has active Core commercial access using the reviewed commercial operator workflow.
3. In Settings → CRM, explicitly choose RevenueOS. Connected HubSpot additionally requires the commercial CRM connector entitlement.
4. Create one synthetic Account, Contact and Opportunity; confirm owner, record overview, history, archive/restore, strong duplicate handling and a real default Pipeline assignment/event.
5. For external mode, verify the connector is active and a mapped authoritative field is read-only. Do not make a live provider call during smoke testing.

## Safe failure states

- `not_in_plan`: the required Core or external CRM connector access is absent; retained data remains readable where policy permits.
- `setup_required`: admin must choose a mode, or reconnect HubSpot for external mode.
- `temporarily_unavailable`: global flag is disabled; preserve reads/Core.
- `crm_mode_conflict`: resolve active mappings before selecting native.
- `stale_write`: refresh and compare; never blindly retry with a new timestamp.
- `stale_pipeline_state`: refresh the Opportunity stage; do not create a second move key for the stale transition.
- `external_stage_authority`: use the reviewed mapped CRM path; never bypass with a generic Opportunity PATCH.
- duplicate domain/email: open the returned existing record; do not bypass the unique index.

## Rollback and recovery

For an operational stop, disable the relevant global feature or use the reviewed
commercial operator state command; both are non-destructive. Restore an accidentally
archived record through its record page/API. Database restore uses the standard
private-beta backup process. A schema downgrade deletes CRM metadata and must only
occur after export/backup and explicit approval; see the migration playbook.

Monitor safe counts of CRM availability states, response codes, conflict/stale-write rates and endpoint latency. Never add record names, email/domain values, custom-field values or history diffs to metrics/logs.

## Supervised import and merge

Use Settings → CRM → Data import in the order Accounts, Contacts, open
Opportunities. Start with the approved subset, explicitly map or ignore every header,
map owners/stages without fuzzy matching, preview, review duplicate/invalid row numbers
and confirm only `new` rows. Retry the same batch rather than creating another when the
result is uncertain. A stale duplicate snapshot requires a fresh preview. Do not retain
the source CSV or create a failed-row data file.

Merge one Account/Contact pair from the record's **Merge duplicate** panel. Review the
survivor, relationship counts and every field conflict, then use the explicit
irreversible confirmation. External mapping/provenance blockers require containment,
not database surgery. Verify the source tombstone, survivor relationships, suppression
and export history after completion.
