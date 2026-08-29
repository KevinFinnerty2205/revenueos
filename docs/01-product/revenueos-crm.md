# RevenueOS CRM

- **Status:** Native CRM Foundation implemented by WO-034; Pipeline expansion remains WO-035
- **Principle:** RevenueOS works with your CRM—or it can be your intentionally simple sales CRM.

For small organisations, existing Company, Contact and Opportunity records now provide the native system-of-record foundation. For larger organisations, the same local canonical graph works alongside HubSpot with explicit field authority. CRM enriches Accounts, People and Pipeline; it is not a separate top-level application and it does not displace Sales Brain.

Core retains basic relationship/deal CRUD because Sales Brain needs it. The CRM add-on unlocks explicit RevenueOS system-of-record configuration and bounded custom-field administration/mutation, with richer record history now visible in the canonical workspaces. Entitlement loss preserves Core and existing custom values read-only. No billing implementation is implied.

Current v1 includes one-person ownership, short Account/Contact/Opportunity forms, exact domain/business-email dedupe, archive/restore, six optional typed custom-field types, human-readable field history and bounded activity composed from existing Interactions, Outreach, Actions, Events and Opportunities. External HubSpot-authoritative fields are visibly read-only and still protected by WO-025C service policy.

There is no Lead object/conversion, CRM Task/Note/Activity, custom object, formula, workflow engine, destructive merge, bulk edit, team ownership, territory routing, product catalogue or CPQ. Tags are deferred in favour of optional single-select custom fields. Pipeline definitions, stages, board and stage history belong to WO-035.

Operational CSV import/export and native reviewed-Action execution are deliberately deferred behind documented safety designs. Organisation export version 24 includes the new CRM settings/custom values/history. Importing future Contact data will never imply Engage permission. AI cannot mutate CRM in WO-034.

See [Native CRM product guide](native-crm.md), [Native CRM UX](../02-design/native-crm-ux.md), [architecture](../03-engineering/native-crm-architecture.md) and [source-of-truth rules](../03-engineering/crm-source-of-truth.md).
