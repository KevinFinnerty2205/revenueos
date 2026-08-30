# Focused CRM Sync implementation guide

**Status:** Implemented by WO-025C for HubSpot only.

## Product boundary

The complete server-enforced path is:

`final validated intelligence → versioned Action → review/edit → approval → live CRM read/preview → explicit confirmation → durable worker → HubSpot → verification/reconciliation`

Final intelligence may prepare an opportunity update, a bounded next-step update,
or “Log this interaction in CRM”. It cannot call a connector. Approval also does
not queue work. Confirmation accepts only a stored preview ID and connection ID;
the server reconstructs the exact approved Action version and target mapping.

## Delivered surface

- HubSpot OAuth connection, test, reauthorisation and revocation in Settings.
- `update_opportunity`, `update_contact` and `create_activity` capabilities only.
- Explicit Company, Contact and Opportunity external-reference records; contextual
  Opportunity search/link UI. No fuzzy or automatic link.
- Typed Opportunity field mapping for stage, status, close date, amount, next step
  and description; typed Contact mapping for first/last name, stored business email
  and job title.
- Explicit RevenueOS-stage to HubSpot pipeline/stage mapping.
- Exact current/new values and authority in execution preview.
- Decimal-safe amount handling and currency comparison with no conversion.
- Expected-current-value protection, provider updated timestamp in preview and a
  second read in the worker before write.
- Meeting activity creation from final Executive Summary plus up to eight final
  Action Items. Raw transcripts and private Evidence are excluded.
- Idempotent confirmation, durable attempts, read-after-write verification,
  unknown-state reconciliation, bounded retry and safe provider receipts.

## API

- `POST /api/v1/integrations/hubspot/oauth/start`
- `POST /api/v1/integrations/hubspot/oauth/callback`
- existing connection list/get/test/delete routes
- `GET /api/v1/integrations/connections/{id}/crm/search`
- `GET|DELETE /api/v1/integrations/connections/{id}/crm/entities/{type}/{id}`
- `PUT /api/v1/integrations/crm/entities/{type}/{id}`
- `GET|PUT /api/v1/integrations/connections/{id}/crm/fields...`
- `GET|PUT /api/v1/integrations/connections/{id}/crm/stages`
- existing Action preview/execute/history routes
- `POST /api/v1/executions/{id}/reconcile`

Pydantic/OpenAPI remains canonical. Access tokens, refresh tokens, credential
references, fingerprints, provider request bodies and raw responses are absent
from browser contracts.

## Grouping and Methodology

WO-025C keeps each field update atomic. Activity logging is separate. This avoids
partial grouped writes and preserves one field’s provenance per Action. Methodology
custom-field sync is supported by the authority and typed property architecture,
but no methodology fields are enabled in this work order; an admin cannot create
arbitrary scripts or fields.

## Limits

No second CRM, bulk import, full inbound sync, webhook platform, autonomous write,
contact creation, task creation, company-association mutation or native CRM
expansion is included. The Opportunity page does not contact HubSpot until the
user opens the contextual link control.

## WO-034 compatibility

The native CRM layer does not replace the HubSpot connector or its review, preview,
confirmation, worker, idempotency and reconciliation path. External mode simply
projects existing field authority into the canonical record experience and blocks
direct writes to CRM-authoritative fields. Native mode requires active mappings to be
resolved first. Standard CRM tests seed connection/mapping records locally and make
no provider request.

## WO-035 Pipeline authority

The Pipeline board does not turn native definitions into a second HubSpot stage
registry. When organisation CRM mode is external it may display canonical mirrored
state, labels the source `Managed in HubSpot` and rejects direct stage, close and reopen
requests. WO-035 does not call HubSpot or add inbound sync. A future reviewed/mapped
provider change must enter the canonical Pipeline service with `external_crm` source,
expected-current-stage protection and one immutable event.
