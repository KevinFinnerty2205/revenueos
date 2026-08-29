# Native CRM API

All routes require authenticated organisation membership. JSON uses camelCase aliases; UUIDs and UTC timestamps follow the existing API contract.

| Method and path                               | Role/policy       | Purpose                                                                          |
| --------------------------------------------- | ----------------- | -------------------------------------------------------------------------------- |
| `GET /api/v1/crm/availability`                | member            | Effective flag, entitlement, setup/mode, permission and HubSpot connection state |
| `PATCH /api/v1/crm/admin/entitlement`         | admin             | Private-beta CRM grant; no billing implication                                   |
| `PUT /api/v1/crm/settings`                    | admin + entitled  | Confirm `native` or `external`, with connection/mapping safety checks            |
| `GET /api/v1/crm/members`                     | member            | Active/inactive same-organisation owner labels                                   |
| `GET /api/v1/crm/custom-fields`               | member            | Definitions; optional entity/archive filters                                     |
| `POST/PATCH /api/v1/crm/custom-fields`        | admin + entitled  | Create or edit bounded definitions                                               |
| `POST /api/v1/crm/custom-fields/{id}/archive` | admin + entitled  | Reversible definition retirement with values preserved                           |
| `GET /api/v1/crm/records/{type}/{id}`         | member            | Core fields, owner, authority, custom values, bounded activity and history       |
| `PUT .../custom-fields/{definitionId}`        | member + entitled | Strict typed value set/clear with optional optimistic concurrency                |
| `POST .../archive` / `restore`                | admin + entitled  | Reversible canonical record lifecycle; archived records reject field mutation    |

Canonical Company/Contact/Opportunity endpoints remain the CRUD source of truth. Their list endpoints accept `includeArchived`; Company/Contact updates accept `expectedUpdatedAt`; Opportunity keeps its existing optimistic edit contract. Duplicate conflicts use `duplicate_company_domain` or `duplicate_contact_email` plus safe `details.entityType/entityId`. External-authoritative core-field writes return `crm_authoritative_field`.

Availability states are `available`, `not_in_plan`, `setup_required` and `temporarily_unavailable`. Core endpoints do not fail merely because CRM is not entitled.
