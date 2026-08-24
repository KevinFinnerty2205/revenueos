# CRM object mapping guide

`crm_entity_mappings` is the tenant-scoped external-reference boundary:

| RevenueOS | HubSpot | WO-025C use |
| --- | --- | --- |
| Company | company | explicit search/link architecture; no writes |
| Contact | contact | explicit link required before a Contact update |
| Opportunity | deal | explicit link for field update and activity association |
| Interaction | meeting | external result is recorded on execution; no domain ID replacement |
| Action | task | model shape reserved; task capability not advertised by HubSpot |

Mappings store organisation and connection IDs, RevenueOS entity type/ID,
provider object type/ID, safe updated/sync timestamps and state. They do not store
provider payloads. Composite uniqueness prevents one RevenueOS record mapping to
two provider records or one provider record mapping to two RevenueOS records
inside the same tenant connection.

Link creation is always explicit. Search is bounded to ten provider results. The
selected provider object is fetched by exact ID before persistence. Names, email,
domain, phone and fuzzy similarity never auto-link or merge records. Contact
creation is deliberately deferred; missing Contact mappings fail with clear
guidance. An external 404 blocks linking/execution; future inbound reconciliation
may mark `external_missing`.

Repository predicates and forced RLS include organisation scope. Cross-tenant
connection IDs and entities return no mapping. Disconnect deletes mapping records
through the connection cascade but never deletes or undoes any HubSpot record.
