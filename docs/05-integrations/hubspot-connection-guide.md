# HubSpot connection and operations guide

## Provider app configuration

Create one HubSpot OAuth app on the 2026.03 developer platform. Register the exact
RevenueOS callback URI and the scopes listed in the
[OAuth security guide](../03-engineering/crm-oauth-credential-security.md). Use a
HubSpot developer test account for manual proof; never run standard tests against
a real account.

Configure:

```text
API_FEATURE_INTEGRATIONS_ENABLED=true
API_FEATURE_ACTION_LAYER_ENABLED=true
API_FEATURE_ACTION_EXECUTION_ENABLED=true
API_FEATURE_HUBSPOT_CRM_ENABLED=true
API_HUBSPOT_CLIENT_ID=...
API_HUBSPOT_CLIENT_SECRET=...
API_HUBSPOT_OAUTH_REDIRECT_URI=https://<web-host>/settings/integrations/hubspot/callback
API_CONNECTOR_CREDENTIAL_MASTER_KEY=<base64url 32-byte key>
```

The production API base must be `https://api.hubapi.com`; authorisation uses
`https://app.hubspot.com/oauth/authorize`. Feature flags default off. Mock
connectors remain prohibited in production.

## Connection lifecycle

1. Admin opens Settings → Integrations and selects **Connect HubSpot**.
2. HubSpot shows the requested permissions; a HubSpot Super Admin installs.
3. RevenueOS validates one-time state, exchanges the code server-side, verifies
   scopes/account and stores an encrypted token envelope.
4. Settings shows account, last verified, capabilities and mapping disclosure.
5. **Test connection** refreshes if necessary and verifies account identity without
   returning customer data.
6. **Reconnect** repeats OAuth when scopes/auth change and must resolve to the same
   HubSpot account. RevenueOS rejects an account switch so dormant record mappings
   cannot be rebound to a different tenant account.
7. **Disconnect** attempts provider revocation, invalidates work and deletes the
   local credential envelope. Dormant mapping metadata is retained for a reviewed
   same-account reconnect; it cannot execute while disconnected. Disconnect never
   deletes HubSpot records.

## Failure runbook

- `reauthorisation_required`: reconnect; do not edit the database reference.
- missing/reduced scope: correct the HubSpot app config and reconnect.
- rate limited: worker respects bounded backoff; reduce repeated manual operations.
- property/stage unavailable: open mapping and select a current compatible value.
- stale external state: create a fresh preview and let the user decide.
- unknown external state: use **Reconcile HubSpot outcome** once; do not enqueue a
  replacement until the read-only result is known.
- lost encryption key: tokens cannot safely be decrypted; rotate configuration and
  require reconnect.

Provider monitoring should alert on safe failure-code rates only. Never attach raw
OAuth/provider payloads or customer CRM values to logs or support tickets.
