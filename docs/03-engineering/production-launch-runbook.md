# Oryntela production launch runbook

- Status: repository-ready; all paid/external/public actions blocked pending owner approval
- Baseline release: `d8d50b216bd64726243b06b5ea4f5bd56c59ab54`
- Required migration head: `0061_manual_paid_credit_grant`
- Owner/on-call: Kevin (owner-operated V1; use the controlled operational address, not personal details in public records)
- Customer data: none; WO-045 must pass before onboarding

## 1. Architecture and release boundary

The production candidate is the modular monolith described by [ADR 0077](../08-decisions/0077-australian-managed-modular-monolith-production-topology.md): standalone Next.js web, FastAPI API, one independently supervised worker, managed PostgreSQL 16, private S3-compatible storage and one controlled pre-deploy migration job. The worker contains the AI, recording/transcription, Prospect, Campaign, reviewed action, Create, Microsoft, Google and CRM sync loops. There is no separate laptop cron, message broker or cache.

`infra/digitalocean/app.production.template.yaml` is preparation, not a live deployment. It keeps automatic deployment off, routes the API only on `api.oryntela.com.au`, makes API readiness the traffic gate and gives the worker a non-routable liveness check. App Platform supports liveness probes for workers and restarts a failed component ([DigitalOcean health checks](https://docs.digitalocean.com/products/app-platform/how-to/manage-health-checks/), verified 10 September 2026).

Production publication is fail-closed at two points:

- Next build rejects an unsafe/crossed canonical URL, non-HTTPS origin, mock auth, non-production Clerk public key or committed Privacy/Terms status other than approved.
- `/health/ready` rejects a missing Clerk server secret without returning the missing value or reason. The API readiness rejects unavailable PostgreSQL, incompatible migration, invalid auth/provider/worker configuration and missing production config.

This first deployment may contain synthetic data only. The target manifest intentionally disables real-data mode, cloud export, organisation deletion, live billing, Credits, external Prospect and every external connector.

## 2. Environment model

| Environment | Identity/data | Configuration and indexing | Providers |
| --- | --- | --- | --- |
| Development | labelled mock auth and synthetic local data | local HTTP permitted; normal developer SEO behaviour | deterministic mocks only unless a developer explicitly configures a test provider |
| Test | deterministic isolated fixtures; no external credentials | test runner; robots disallow all | contract-compatible mocks; external credentials never skip tests |
| Preview/staging | separate Clerk development instance, synthetic data and separate database/bucket | `ORYNTELA_ENVIRONMENT=staging`; exact HTTPS origins; global `noindex`; production secrets prohibited | all external execution off unless a bounded sandbox smoke is separately authorised |
| Production | Clerk production instance; no customer data until WO-045 | exact `.com.au` origins; legal status must be approved; mock auth/connectors prohibited | all optional providers off until their individual approval gates pass |

The complete production handoff template is `infra/environments/production.env.example`. Classification:

- Public/build: `ORYNTELA_ENVIRONMENT`, the three `NEXT_PUBLIC_*` origins, Clerk publishable key/template, `AUTH_MODE`, `MOCK_AUTH_ENABLED`, and the explicit HSTS switch. Public values are frozen into the web build.
- Required runtime secrets: Clerk secret; API database URL; Clerk JWKS/issuer/audience values; outreach-suppression HMAC key; private bucket access keys; and object-signing secret.
- Required ordinary API config: environment/auth mode, JIT setting, safe log level, CORS, allowed hosts, storage endpoint/region and worker probe values.
- Initial fail-closed flags: billing, Credits, real data, export, deletion, external Prospect, integrations, action execution, mock connectors and all named connectors.
- Real-data-only secrets/config: legal approval/support references, AES-256 backup key, retention, durable export destination and external-AI approval. Export must remain disabled on App Platform until its local-path implementation is replaced or a durable supported target is chosen.
- Provider-specific secrets: connector master key and each OAuth client secret; Apollo/provider cost/approval references; OpenAI key/model if separately approved; Stripe test fields only in non-production. Do not provision disabled-provider secrets pre-emptively.
- Optional tuning: every bounded timeout, quota, upload size and batch setting in `apps/api/.env.example`; absence uses typed defaults. Review those defaults against the approved launch profile, but they are not secrets.
- Test-only: mock auth, mock connectors, deterministic billing, Stripe `sk_test_`/test prices and mock AI/provider selections. Production validation blocks unsafe combinations and any Stripe secret.

No secret goes into Git, documentation, build arguments, `NEXT_PUBLIC_*`, fixtures, screenshots, support bundles or command arguments. Create values in the provider secret manager with owner/maintainer access restricted. Maintain a private inventory of owner, purpose, creation, last rotation and revocation path; store only safe references in change records.

Generate fresh random values in a private, non-recorded terminal and paste them
directly into the secret manager. The output of each command is the secret: do not
copy it through chat, put it in a ticket or leave it in captured terminal output.

```text
python3 -c 'import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())'
python3 -c 'import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("="))'
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Use the first only for `API_PRIVATE_BETA_BACKUP_ENCRYPTION_KEY`, the second for `API_CONNECTOR_CREDENTIAL_MASTER_KEY`, and separate outputs of the third for suppression and object-signing keys. Never reuse development values or one purpose's key for another.

## 3. Owner-approved infrastructure creation

Do none of this until the owner approves the current cost table and payment method.

1. Create a DigitalOcean project/team with account MFA and minimum roles. Create App Platform, managed PostgreSQL 16 and private Spaces resources in Sydney.
2. Create separate migration/admin and runtime database roles. Runtime must be `NOSUPERUSER NOBYPASSRLS`; grant only database connect, schema use, table DML, sequence use and required application functions. Restrict the cluster to the app plus controlled operator access; use TLS identity verification where supported.
3. Create bucket credentials scoped as narrowly as DigitalOcean supports. Block public access and CDN publication. Object keys/metadata must not contain customer names, emails or sensitive labels.
4. Enter secret values from the template in the control plane. Keep web, API/worker, migration and backup credentials separated; the web must never receive database/provider keys.
5. Configure platform alerts for deployment/domain failure, component restarts, CPU/memory, database health/storage/connection count and failed scheduled jobs. Route to Kevin's controlled operations destination.
6. Create the app from the reviewed spec only after the legal pages are approved. Do not turn on deploy-on-push.

### Clerk production owner sequence (not performed)

Clerk's current production guide requires a separate production instance and
provider-issued DNS/certification steps
([Clerk production deployment](https://clerk.com/docs/guides/development/deployment/production)).
After the owner accepts Hobby's missing MFA/retained-branding limits or separately
approves Pro:

1. In the existing owner-controlled Clerk application, choose **Create production
   instance**, name the application **Oryntela**, and set the root application domain
   to `oryntela.com.au`. Review settings individually; SSO, integrations and paths do
   not copy automatically.
2. Set application access to **Invite-only**, enable Organisations, disallow personal
   accounts and user-created organisations, and keep only `org:admin` and
   `org:member` authority. Oryntela operators provision the matching records first;
   production JIT provisioning stays off.
3. Configure the hosted identity appearance with Oryntela name, approved logo/colours,
   `https://oryntela.com.au`, `support@oryntela.com.au`, and the final Privacy/Terms
   URLs. Accept that Hobby still displays Clerk branding; removing it is not an
   AUD 0 capability.
4. Create the `oryntela-api` JWT template. Set its audience exactly equal to the
   chosen `API_CLERK_AUDIENCE`; preserve the active `org_id` and `org_role` claims
   and the optional `org_name`, `email` and `name` claims. Do not invent a tenant ID
   in the template. Copy the exact production issuer and JWKS URL from Clerk.
5. Restrict the production Frontend API/subdomain allowlist to the exact app origin,
   add only the repository's required sign-in/sign-up/organisation-selection return
   paths, and copy Clerk's generated DNS records into the DNS change for owner review.
6. Put `pk_live_` only in the documented public variable and `sk_live_` only in the
   web secret manager; put issuer/JWKS/audience only in API/worker configuration. No
   development key enters production or staging.
7. With a synthetic organisation, run invite, accept, sign-in, active-organisation
   selection, API token, sign-out/session revocation, disabled-member, protected-route
   and cross-tenant-denial checks. Record safe IDs/results, never JWTs. Production
   auth is not ready until all pass.

### Stripe live preparation record (inactive)

The current Stripe adapter is deliberately test-only: `billing_mode` accepts only
`test`, production rejects Stripe configuration/credentials, and the adapter rejects
non-test Stripe objects. Live use therefore requires a separate authorised engineering
change and review before any console setup or key injection. After that approval:

1. The owner supplies the contracting entity, Australian business verification,
   settlement bank account, support contact and final legal URLs. Set public business
   name/branding to **Oryntela** and request statement descriptor **ORYNTELA**, subject
   to Stripe's validation. Do not put bank or identity evidence in Git/tickets.
2. Resolve GST first. Then create six AUD recurring Prices with consistent tax
   behaviour: Core AUD 200 monthly / AUD 2,000 yearly; Growth AUD 350 / AUD 3,500;
   Complete AUD 500 / AUD 5,000. Enterprise remains custom. Do not activate Stripe
   Tax, coupons or a production Credit pack under this work order.
3. Keep the 14-day Complete trial outside checkout: it is no-card,
   operator-started and does not auto-convert. Do not configure a Stripe trial that
   can generate an automatic charge.
4. Configure the live customer portal only after cancellation, renewal, proration,
   refund, plan-change and GST terms are approved. Initially permit invoice history,
   billing details and payment-method updates; leave plan switching/promotion codes
   off. Set Terms and Privacy links to the approved routes and return to
   `https://oryntela.com.au/settings`. Stripe documents these as separate sandbox and
   live configurations ([Stripe portal configuration](https://docs.stripe.com/customer-management/configure-portal)).
5. Create the exact live webhook endpoint
   `https://api.oryntela.com.au/api/v1/billing/webhooks/stripe` for
   `checkout.session.completed`, `customer.subscription.updated`,
   `customer.subscription.deleted` and relevant `invoice.*` lifecycle events. Store
   its signing secret separately from the API key. Return URLs are the exact values in
   section 8 below.
6. Prove sandbox checkout, six price mappings, signed-event version, replay and stale
   timestamp rejection, failed-payment and cancellation reconciliation, portal return,
   plan change and kill-switch behaviour. Only a separately authorised bounded live
   transaction may prove live settlement; none is permitted by WO-054.

## 4. Database migration and deployment

Before every release:

1. Record commit SHA, migration head, operator/change reference and rollback release. Confirm required CI and secret/dependency audits pass.
2. Confirm a recent recoverable database backup and last restore result. If a migration is not backwards-compatible with the last app release, stop worker claims and schedule downtime.
3. Run `alembic current` and verify the source state. Never edit `alembic_version` manually.
4. Run once using the migration credential: `alembic upgrade head`.
5. Verify `alembic current` is `0061_manual_paid_credit_grant`; run `alembic check`; then run `revenueos-operations production-preflight` from the release image.
6. Deploy the API and require `/health/live` = 200 and `/health/ready` = 200 before traffic. Start the exact same release's single worker and require its private liveness probe. Deploy web and require `/health/ready` = 200.
7. Run the synthetic smoke matrix below. Inspect safe error rate/restarts and queue summaries before marking the release healthy.

If migration fails, keep the new API/worker out of traffic, preserve the database and backup, inspect the exact Alembic/database error with the migration role, then choose a forward fix or restore. Prefer application rollback on a forward-compatible schema. A schema downgrade requires the specific migration's documented data-loss review, explicit owner approval and a verified backup.

## 5. Backup, restore and objectives

Production eventual policy:

- database: provider automatic daily encrypted backups/PITR with its seven-day retained window; named owner checks success daily;
- application logical snapshot: `revenueos-backup create` and `verify` before a risky migration, stored only in an approved durable encrypted destination and deleted under the approved window;
- private objects: automated encrypted copy to a separate approved bucket/provider at least daily; verify counts/checksums without object names; never treat the source Spaces bucket as its own backup;
- secrets/config: provider-controlled recovery/escrow owned separately and never copied into application backup; and
- drill: synthetic before launch, named production environment before customer data, quarterly during beta and after material hosting/schema changes.

DigitalOcean's seven-day managed database retention does not equal the previously proposed 14-day logical archive. The owner must approve one coherent retention statement. Until the object-copy destination and retention are configured, backup status is **BLOCKED for customer data**.

The logical-backup source principal is a dedicated, tightly controlled backup/migration
principal able to read all tenant rows despite forced RLS. Never grant that authority
to the API/worker runtime role. The isolated restore target should be owned by the
migration principal; reapply and verify least-privilege runtime grants before application
smoke testing.

Logical commands (both source and target database credentials injected through the
secret manager/process environment, never as command arguments):

```text
revenueos-backup create --destination <owner-only-durable-directory>
revenueos-backup verify --source <backup-directory>
revenueos-backup restore --source <backup-directory> \
  --target-storage-directory <empty-isolated-directory> \
  --confirm "RESTORE <backup-id> INTO <target-database-name>"
```

The first two commands read `DATABASE_URL`; restore reads the source/verification
configuration from `DATABASE_URL` and the isolated target from
`API_RESTORE_TARGET_DATABASE_URL`. Set those through the protected job environment.
The backwards-compatible `--target-database-url` option is for credential-free local
URLs only because process arguments may be visible in shell history/process listings.

After restore, verify counts/invariants, `alembic current`, `alembic check`, runtime-role/RLS/cross-tenant tests, object reconciliation and API readiness; then destroy test resources. Never restore production data to a developer laptop. V1 recommended RPO is 24 hours and RTO is four hours, internal targets only—not contractual SLAs.

## 6. Monitoring and daily operations

At start and end of the owner-operated support window:

1. Check web `/health/ready`, API `/health/live` and `/health/ready`, last deploy SHA, component restart alerts, worker probe, database status/backups and object-storage availability.
2. For every approved organisation run `revenueos-operations tenant-preflight`, `queue-status` and, when needed, the metadata-only `support-bundle`. Alert on growing pending/retry counts, expired leases, `unknown_external_state`, `unknown_delivery_state`, provider `degraded/rate_limited/needs_reauth`, billing reconciliation required or repeated safe failure codes.
3. Verify the previous scheduled retention/backup/object-copy jobs completed. Maintenance remains tenant-scoped: add one scheduled job per approved organisation only after provisioning, first running `retention --dry-run`; do not place customer UUIDs in this public template.
4. Review API 5xx/error-rate and latency, failed billing webhook counts, provider dashboards only for activated providers, storage/DB capacity and security/auth anomalies. Logs retain 14 days initially unless the owner approves another operational period; never infer a statutory retention period.

Platform probes and logs are the zero-additional-cost launch monitoring baseline. They detect stopped/stale processes, readiness, deploy/domain failure and resource pressure. They do not replace tenant queue checks or a privacy-reviewed error-reporting system. No third-party error-reporting account is created in WO-054; evaluate it from measured need and send no content, tokens, email bodies, Evidence, prompts, object keys, card data or Deal Room tokens.

The Deal Room has a single-instance in-memory limit (default 120 requests/minute per address/token), signed/revocable bearer grants and noindex/no-store headers. Billing webhooks enforce signatures, replay/idempotency, timestamp bounds and a 1 MB body cap. Authenticated/provider actions use tenant quotas, concurrency bounds and provider backoff. Before scaling API replicas or announcing a public high-volume launch, add an edge/distributed public-route limiter; do not pretend the in-memory limiter is global.

## 7. Kill switches and containment

Change server flags in the secret/config control plane, redeploy the matching API and worker, and record the change. Do not mutate queue/database rows manually.

- Stop sending/external mutation: `API_FEATURE_ACTION_EXECUTION_ENABLED=false`; for campaigns also `API_FEATURE_ENGAGE_CAMPAIGNS_ENABLED=false`; stop the worker if outcome contracts are in doubt.
- Stop all connector surfaces: `API_FEATURE_INTEGRATIONS_ENABLED=false`; disable the named Microsoft/Google/HubSpot/Salesforce flag; revoke provider credentials when compromised.
- Stop Prospect cost: `API_FEATURE_PROSPECT_EXTERNAL_PROVIDER_ENABLED=false`, then `API_FEATURE_CREDITS_ENABLED=false`; disable the provider key in its console.
- Stop billing/checkout: `API_FEATURE_BILLING_ENABLED=false`. Continue verified reconciliation under an incident procedure; never discard a valid webhook because UI checkout is disabled.
- Stop customer-content AI: disable `API_FEATURE_OPENAI_PROVIDER_ENABLED` plus the affected content feature; do not substitute mock output in real-data mode.
- Stop capture/binary writes: disable recording, online-meeting, document, visual and Create flags as appropriate; preserve reconciliation metadata.
- Revoke public Deal Room: use the supported publication revocation; do not log the fragment token.

Unknown external/delivery outcomes are never blindly retried. Check the provider with its non-mutating lookup/reconciliation path, record only safe references, then use the supported reconcile operation.

## 8. DNS, TLS and callbacks

Canonical recommendation: `https://oryntela.com.au`; route `www.oryntela.com.au` to the canonical origin. Leave `oryntela.com` unchanged until the owner chooses redirect versus future global use. App Platform automatically redirects HTTP to HTTPS and provisions TLS after domain validation. Do not add HSTS until both web and API TLS/redirect/callback smoke tests are stable; then set both HSTS switches true and verify `max-age=31536000`. The code deliberately omits `includeSubDomains` and `preload`.

Exact DNS record *names* are apex `@`, `www` and `api`; their A/AAAA/CNAME *targets* must be copied from the created App Platform domain instructions because no destination exists yet. Record old TTL/values, lower TTL if approved, add platform verification, validate TLS, then switch. Never invent an IP. Roll back using the captured records.

Exact production callback/endpoints:

- Microsoft: `https://oryntela.com.au/settings/integrations/microsoft/callback`
- Google: `https://oryntela.com.au/settings/integrations/google/callback`
- HubSpot: `https://oryntela.com.au/settings/integrations/hubspot/callback`
- Salesforce: `https://oryntela.com.au/settings/integrations/salesforce/callback`
- Stripe webhook: `https://api.oryntela.com.au/api/v1/billing/webhooks/stripe`
- Stripe success: `https://oryntela.com.au/billing/success`
- Stripe checkout cancel and customer-portal return: `https://oryntela.com.au/settings`
- public legal: `https://oryntela.com.au/privacy` and `/terms`

No localhost redirect may be registered in a production provider app. Use separate test/production apps, clients, secrets, buckets and databases.

## 9. Synthetic smoke matrix

Use a dedicated synthetic Clerk organisation/admin/member and clearly synthetic records. Never charge a card, send email, mutate a customer CRM or use customer/provider data.

| Area | Required assertion | Execution boundary |
| --- | --- | --- |
| Public site | home/platform/pricing/integrations/security/contact/login, canonical, OG, sitemap, headers; approved legal pages only | after legal/DNS approval |
| Auth | sign-up/invite policy, sign-in/out/session, protected routes, disabled membership and cross-tenant denial | production Clerk owner setup required |
| Setup/Core | provision synthetic org; Selling Profile; Native CRM companies/contacts/opportunities/tasks; Pipeline, Forecast, Targets, Analytics, Manager, Business Case, Deal Room, Handover | execute before traffic with synthetic data |
| Trial | operator starts 14-day Complete trial; no card, charge or auto-conversion; inspect commercial state | execute after production auth/database |
| Prospect/Credits | UI truth says inactive; external call and production Credit reservation blocked | no provider use |
| Engage | draft/review/suppression behaviour; delivery remains disabled unless synthetic mailbox separately approved | no real email |
| Create | generate/approve/download synthetic PPTX through private object storage; verify checksum, one-time grant and restart portability | execute after bucket exists |
| Billing | deterministic/Stripe test only outside production; signatures, replay and reconciliation tests | no real money; production remains off |
| Microsoft/Google/HubSpot/Salesforce | UI says activation pending; connection attempts fail closed while disabled | run provider sandbox smoke only after owner credentials/consent |
| Recovery | backup, disposable restore, head/invariants/RLS/object reconciliation, target destruction | synthetic local now; named cloud required pre-customer |

## 10. Support and lifecycle operations

- Trial: inspect commercial state; run `commercial-start-trial` with current lock version, bounded reason/operator and printed exact confirmation. It never creates a card or automatic conversion.
- Commercial change: use `commercial-assign-plan`/`commercial-change-state`; never edit tables. Live billing stays off until an adapter and reconciliation smoke pass.
- Manual paid Credits: follow `manual-paid-credit-grant-runbook.md`; cleared funds and a margin review are mandatory; the grant does not enable provider execution.
- Provider reconnect: disable the named flag if unsafe, inspect safe connection health, revoke/disconnect, rotate client secret/token as needed, reconnect through OAuth, then reconcile before writes.
- Export: approve request/authority, create with `revenueos-beta-maintenance export`, authorise one-time download and purge. On App Platform this remains disabled until durable cloud export storage is implemented/approved.
- Organisation deletion: optional export, disable members, stop queues, revoke connectors, run exact-confirmation deletion, verify database/object/grant/search/worker absence, then let backups age out. Feature remains off until the named-target proof passes.
- Billing: compare Oryntela subscription/invoice event state with Stripe IDs and verified events; reconcile through supported service paths. Never paste card/customer/provider payloads into logs or tickets.

## 11. Rollback and release close

Contain with the narrowest kill switch; pause worker if contract compatibility is uncertain. Redeploy the last validated web/API/worker SHA together only if it supports the current forward schema. Confirm liveness/readiness, worker probe, synthetic tenant, queue states and error rate. Restore the database only when a forward fix/application rollback cannot recover and the recovery owner approves the RPO impact. Restore objects and database to the same recovery point.

After a successful launch window, record SHA, migration head, health/smoke results, any provider actions, spend, incidents and deviations. Public announcement and customer onboarding are separate owner gates and are not part of WO-054.
