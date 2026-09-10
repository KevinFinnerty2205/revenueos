# Production incident and secret-rotation runbook

Status: V1 owner-operated procedure. It is not legal advice and does not invent notification obligations or deadlines.

## Incident flow

1. Detect and timestamp using health/alert state, request IDs, release SHA, safe error codes and aggregate queue counts. Do not copy customer content into the incident channel.
2. Contain using the narrow feature/provider kill switch, membership/session revocation, worker stop or traffic stop. Suspected tenant crossing, credential disclosure, unauthorised external send/write or incorrect charge is high severity.
3. Preserve platform/provider audit logs and relevant immutable application event IDs under access control. Do not collect raw transcripts, email bodies, Evidence, prompts, card data, bearer tokens or full provider payloads merely for convenience.
4. Notify Kevin through the controlled operations route. Engage the relevant hosting/auth/provider owner. Qualified privacy/legal review decides whether customer/regulator notification is required and its timing.
5. Eradicate/recover: revoke compromised credentials first, rotate, deploy the reviewed release, reconcile unknown provider outcomes, restore only when required, and verify tenant isolation plus synthetic smoke.
6. Close with impact window, affected tenants/data categories, safe evidence references, recovery point/time, notification decision owner, root cause and corrective actions. Do not declare backups, deletion or notifications complete without proof.

Provider outage: keep local state, stop new external mutations and use backoff/reconciliation. Database/migration outage: readiness removes traffic; stop worker and do not bypass head checks. Object outage: disable binary/Create writes and downloads, preserve metadata, reconcile after recovery. Auth outage: do not enable mock; restrict access until Clerk verification works. Billing webhook failure: stop checkout if integrity is uncertain, keep endpoint/signature verification available, replay verified Stripe events only through the supported idempotent path.

## Rotation rules

All rotations use separate non-secret change references, dual control for high-impact production secrets where practical, a synthetic verification, revocation of old material, log review and inventory update. Never reveal old/new values in tickets, Git, screenshots or shell command arguments. A database or signing/encryption-key rotation is not complete until dependent processes restart and evidence is verified.

| Secret | Rotation sequence | Special caution |
| --- | --- | --- |
| Clerk secret/JWKS config | create/reveal replacement in Clerk with owner MFA; update web secret and API issuer/JWKS/audience as one change; deploy; test sign-in/session/disabled membership; revoke old key/session as incident requires | never fall back to mock; public publishable key is not secret but must match the production instance |
| Database runtime password | create a new least-privilege runtime role/password or provider-rotate; update API/worker; verify ready and RLS; drain old connections; revoke old role | migration/admin credential is separate and never sent to app runtime |
| Database migration credential | rotate in operator/pre-deploy job only; run read-only connectivity/head check; revoke old | do not grant `BYPASSRLS` to runtime to simplify deployment |
| Stripe API/webhook secrets | roll endpoint signing secret with overlap only if Stripe supports it; update test/live separately; deploy and verify signed test event/idempotency; revoke old API key | current code rejects live Stripe, so rotation is test-only until a reviewed live adapter exists |
| Microsoft client secret | add new Entra credential; update secret manager; synthetic OAuth/refresh/send-readonly smoke as authorised; remove old credential | customer tokens may require reconnect; owner/admin MFA/consent boundary |
| Google client secret | create OAuth secret; update; verify synthetic OAuth and restricted-scope configuration; revoke old | verification/CASA remains required; do not broaden scopes during rotation |
| HubSpot client secret | rotate developer-app secret; update; synthetic OAuth/refresh/read smoke; revoke old; reconcile connections | provider may invalidate grants; keep write-back disabled until verified |
| Salesforce secret | rotate External Client App credential; update; synthetic dev-org OAuth/read smoke; revoke old | use External Client App, not a new Connected App; customer API entitlement is separate |
| Prospect key | disable external Prospect and Credits; issue new key after commercial rights/cost approval; update; health/no-charge synthetic check if provider permits; revoke old | no provider is approved, so no production key exists |
| Object access key | create new least-privilege key; update API/worker; preflight write/read/delete synthetic object; revoke old | Spaces keys may cover multiple buckets—review blast radius |
| Object-signing/suppression HMAC | deploy new value in a controlled cutover and invalidate/reissue affected short-lived grants where needed | rotation can invalidate live signed downloads/suppressions; do not reuse keys |
| Connector credential master key | disable connectors and worker; decrypt/re-encrypt every credential in a separately reviewed migration or require reconnect; verify; revoke old key | current runtime exposes one key and no online key-ring rotation; connector activation is blocked until this procedure is implemented/tested for the named target |
| Backup encryption key | create a new 32-byte base64 key; retain old key in controlled recovery escrow for every unexpired backup; use new key for new archives; test restore; destroy old key only after its last archive expires | losing the old key makes retained backups unrecoverable; reuse across environments is prohibited |
| OpenAI key | disable external AI; issue scoped replacement; update; bounded synthetic request; revoke old; monitor | real customer-content processing requires separate approval and disclosure |

## Verification evidence

For every rotation record only: change/incident ID, safe key fingerprint or provider key ID, roles, timestamps, affected components, synthetic check result, revocation confirmation and rollback disposition. Never record the secret value. Follow [the production launch runbook](production-launch-runbook.md) for kill switches, recovery and smoke tests.
