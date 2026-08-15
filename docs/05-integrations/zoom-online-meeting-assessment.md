# Zoom online-meeting assessment

**Reviewed:** 2026-08-15 against official Zoom documentation. **Decision:**
documented production path only; no Zoom app, credential, SDK or webhook exists.

A production adapter would use the account model chosen with the design partner,
request only meeting/cloud-recording read capabilities, discover an explicitly
eligible completed meeting, and import the selected recording or transcript through
the shared pipeline. Availability depends on the host account, recording settings,
plan and artefact retention. Webhook events may reduce polling but would introduce
signature verification, replay/idempotency, tenant mapping and reconciliation
obligations.

Zoom download references are time-sensitive secrets and must remain server-side.
The adapter would respect provider rate limits, reconcile unknown retrieval outcomes
before retry and expose revoked/expired connection state. RevenueOS deletion removes
its copy; it does not delete Zoom's cloud recording by default.

Primary references: [Zoom app integrations and
OAuth](https://developers.zoom.us/docs/integrations/), [app creation and security
review](https://developers.zoom.us/docs/integrations/create/), [OAuth
scopes](https://developers.zoom.us/docs/integrations/oauth-scopes/), and [meeting
events](https://developers.zoom.us/docs/api/meetings/events/).
