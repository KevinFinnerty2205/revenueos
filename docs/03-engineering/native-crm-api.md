# Native CRM API

All routes require authenticated organisation membership. JSON uses camelCase aliases; UUIDs and UTC timestamps follow the existing API contract.

| Method and path                               | Role/policy       | Purpose                                                                       |
| --------------------------------------------- | ----------------- | ----------------------------------------------------------------------------- |
| `GET /api/v1/crm/availability`                | member            | Effective Core/connector access, setup/mode, permission and HubSpot state     |
| `PATCH /api/v1/crm/admin/entitlement`         | admin             | Legacy route; rejects because plan authority owns access                      |
| `PUT /api/v1/crm/settings`                    | admin + Core      | Confirm `native`; external additionally requires CRM connector entitlement    |
| `GET /api/v1/crm/members`                     | member            | Same-organisation owner labels and caller-specific assignment authority       |
| `GET /api/v1/crm/custom-fields`               | member            | Definitions; optional entity/archive filters                                  |
| `POST/PATCH /api/v1/crm/custom-fields`        | admin + entitled  | Create or edit bounded definitions                                            |
| `POST /api/v1/crm/custom-fields/{id}/archive` | admin + entitled  | Reversible definition retirement with values preserved                        |
| `GET /api/v1/crm/records/{type}/{id}`         | member            | Core fields, owner, authority, custom values, bounded activity and history    |
| `PUT .../custom-fields/{definitionId}`        | member + entitled | Strict typed value set/clear with optional optimistic concurrency             |
| `POST .../archive` / `restore`                | admin + entitled  | Reversible canonical record lifecycle; archived records reject field mutation |

Canonical Company/Contact/Opportunity endpoints remain the CRUD source of truth. Their list endpoints accept `includeArchived`; Company/Contact updates accept `expectedUpdatedAt`; Opportunity keeps its existing optimistic edit contract. Duplicate conflicts use `duplicate_company_domain` or `duplicate_contact_email` plus safe `details.entityType/entityId`. External-authoritative core-field writes return `crm_authoritative_field`.

Member options return `active: true` only when both the organisation membership
and the underlying user are active. `canAssign` is true only for those active
options and when the caller is an administrator or is assigning themselves.
Company, Contact, Opportunity and Task assignment endpoints enforce the same
rule server-side. Edit clients omit an unchanged owner or assignee so a historic
inactive owner/assignee does not block unrelated edits; explicit reassignment
still requires an active, same-organisation, caller-authorised member.

Availability states are `available`, `read_only`, `not_in_plan`, `setup_required`
and `temporarily_unavailable`. Native CRM is Core. The `crm` commercial module means
supported external connectors; losing it preserves external history but blocks new
connection, mapping, preview, confirmation and worker execution.

WO-035 Pipeline endpoints are documented in the central [API reference](api.md).
Pipeline definition mutation follows the same admin/Core/native-mode boundary;
direct stage/close/reopen mutation is denied in external mode.
