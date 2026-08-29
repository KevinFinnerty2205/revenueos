# CRM source of truth

## Two distinct questions

**Record authority** answers which system may edit a canonical CRM field. **Evidence provenance** answers where a value or claim came from and how trustworthy it is. Native mode makes RevenueOS authoritative for editable record state; it does not magically verify manually entered or provider-supplied data.

## Authority rules

1. Native mode defaults core fields to `revenueos_authoritative`.
2. External mode reads active WO-025C HubSpot mappings.
3. `crm_authoritative` is shown read-only and rejected server-side.
4. `review_before_sync` remains editable only through the existing reviewed sync boundary where applicable.
5. A disconnected external mode becomes setup-required; stale local records remain readable.
6. An admin cannot switch to native mode while active field mappings exist and cannot select external mode without an active HubSpot connection.

Authority keys use the canonical snake_case field names already used by HubSpot mapping (`first_name`, `estimated_value`, and so on). The browser only improves explanation; API service policy remains authoritative.

## Origins and history

CRM history sources are bounded: `manual_user_entry`, `crm_import`, `prospect_promotion`, `event_promotion`, `external_crm`, `reviewed_action` and `system`. WO-034 writes manual and promotion history, while the remaining enum values reserve a compatible lineage vocabulary for approved future writers. Contact provenance continues to store per-field provider/public/manual origin in `contact_field_sources`; CRM history does not replace it.

## AI boundary

Revenue Brain may suggest work but cannot call CRM repositories. Native reviewed-Action execution is deferred until the Action intent can be routed provider-neutrally, previewed against current state, revalidated for authority/concurrency and applied idempotently with `reviewed_action` history. `create_activity` will not target native CRM because the canonical Interaction already is the activity.
