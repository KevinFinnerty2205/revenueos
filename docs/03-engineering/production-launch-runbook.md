# Oryntela production launch runbook

- Status: repository-ready; all paid/external/public actions blocked pending owner approval
- Reviewed source baseline: `3fdf567e2f103abd312fee7e7297af996532c910`; deploy only the immutable post-review merge SHA recorded in the launch evidence
- Required migration head: `0063_terms_acceptance`
- Owner/on-call: Kevin (owner-operated V1; use the controlled operational address, not personal details in public records)
- Customer data: none; WO-045 must pass before onboarding

## 1. Architecture and release boundary

The production candidate is the modular monolith described by [ADR 0077](../08-decisions/0077-australian-managed-modular-monolith-production-topology.md): standalone Next.js web, FastAPI API, one independently supervised worker, managed PostgreSQL 16, private S3-compatible storage and one controlled pre-deploy migration job. The API image installs PostgreSQL client 16 explicitly so `pg_dump`/`pg_restore` match the selected server major. The worker contains the AI, recording/transcription, Prospect, Campaign, reviewed action, Create, Microsoft, Google and CRM sync loops. There is no separate laptop cron, message broker or cache.

`infra/digitalocean/app.production.template.yaml` is preparation, not a live deployment. It keeps automatic deployment off, declares the externally managed apex/`www`/API domains without granting DigitalOcean DNS control, routes the API only on `api.oryntela.com.au`, makes API readiness the traffic gate and gives the worker a non-routable liveness check. App Platform supports liveness probes for workers and restarts a failed component ([DigitalOcean health checks](https://docs.digitalocean.com/products/app-platform/how-to/manage-health-checks/), verified 10 September 2026).

Production activation is fail-closed at distinct infrastructure and commercial points:

- Next build rejects an unsafe/crossed canonical URL, non-HTTPS origin, mock auth or non-production Clerk public key. This permits the production identity shell and synthetic infrastructure proof before legal approval; it does not authorise a trial, paid checkout, customer data or public launch.
- `/health/ready` rejects a missing Clerk server secret or missing/non-40-hex `ORYNTELA_RELEASE_SHA` without returning the missing value or reason. The API readiness rejects unavailable PostgreSQL, incompatible migration, invalid auth/provider/worker configuration and missing production config. `production-preflight` also fails until the owner-approved Terms version and effective date are locked for acceptance.
- The API's Terms service keeps acceptance unavailable while either legal document is draft. Trial activation and paid checkout recheck that server-owned authority before any provider or billing side effect and remain denied until the approved, effective-dated release is current.

This first deployment may contain synthetic data only. The target manifest intentionally disables real-data mode, cloud export, organisation deletion, live billing, Credits, external Prospect and every external connector.

## 2. Environment model

| Environment     | Identity/data                                                                    | Configuration and indexing                                                                                                                                                | Providers                                                                          |
| --------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Development     | labelled mock auth and synthetic local data                                      | local HTTP permitted; normal developer SEO behaviour                                                                                                                      | deterministic mocks only unless a developer explicitly configures a test provider  |
| Test            | deterministic isolated fixtures; no external credentials                         | test runner; robots disallow all                                                                                                                                          | contract-compatible mocks; external credentials never skip tests                   |
| Preview/staging | separate Clerk development instance, synthetic data and separate database/bucket | `ORYNTELA_ENVIRONMENT=staging`; exact HTTPS origins; global `noindex`; production secrets prohibited                                                                      | all external execution off unless a bounded sandbox smoke is separately authorised |
| Production      | Clerk production instance; no customer data until WO-045                         | exact `.com.au` origins; identity and synthetic proof may run while legal copy is draft, but trial/checkout/public launch remain blocked; mock auth/connectors prohibited | all optional providers off until their individual approval gates pass              |

The complete production handoff template is `infra/environments/production.env.example`. Classification:

- Public/build: `ORYNTELA_ENVIRONMENT`, the three `NEXT_PUBLIC_*` origins, Clerk publishable key/template, `AUTH_MODE`, `MOCK_AUTH_ENABLED`, and the explicit HSTS switch. Public values are frozen into the web build.
- Required runtime secrets: Clerk secret; API database URL and provider CA; Clerk JWKS/issuer/audience values; outreach-suppression HMAC key; private bucket access keys; and object-signing secret.
- Required ordinary API config: environment/auth mode, JIT setting, safe log level, CORS, allowed hosts, storage endpoint/region and worker probe values.
- Initial fail-closed flags: billing, Credits, real data, export, deletion, external Prospect, integrations, action execution, mock connectors and all named connectors.
- Real-data-only config: legal approval/support references, retention, durable tenant-scoped S3 export storage and external-AI approval. Production exports never use the container filesystem and are served only through the authenticated API while the 24-hour grant remains valid.
- Backup-job-only secrets/config: source database URL and CA, source Spaces credentials, independent destination S3 credentials and a fresh AES-256-GCM key. These values are prohibited from the web, API, worker and migration components.
- Provider-specific secrets: connector master key and each OAuth client secret; Apollo/provider cost/approval references; OpenAI key/model if separately approved; and, only after the live Stripe activation gate, the mode-matched Stripe API/webhook secrets. Do not provision disabled-provider secrets pre-emptively.
- Optional tuning: every bounded timeout, quota, upload size and batch setting in `apps/api/.env.example`; absence uses typed defaults. Review those defaults against the approved launch profile, but they are not secrets.
- Test-only: mock auth, mock connectors, deterministic billing, Stripe `sk_test_`/test Prices and mock AI/provider selections. Production rejects test billing and accepts Stripe configuration only as explicit `live` mode with every fail-closed prerequisite.

No secret goes into Git, documentation, build arguments, `NEXT_PUBLIC_*`, fixtures, screenshots, support bundles or command arguments. Create values in the provider secret manager with owner/maintainer access restricted. Maintain a private inventory of owner, purpose, creation, last rotation and revocation path; store only safe references in change records.

Generate fresh random values in a private, non-recorded terminal and paste them
directly into the secret manager. The output of each command is the secret: do not
copy it through chat, put it in a ticket or leave it in captured terminal output.

```text
python3 -c 'import base64,secrets; print(base64.b64encode(secrets.token_bytes(32)).decode())'
python3 -c 'import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("="))'
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Use the first only for `API_BACKUP_ENCRYPTION_KEY`, the second for `API_CONNECTOR_CREDENTIAL_MASTER_KEY`, and separate outputs of the third for suppression and object-signing keys. Never reuse development values or one purpose's key for another. Store a separately controlled offline recovery copy of the backup key; loss of the only copy makes every encrypted backup unusable.

## 3. Owner-approved infrastructure creation

Do none of this until the owner approves the current cost table and payment method.

1. Create a DigitalOcean project/team with account MFA and minimum roles. Create App Platform, a two-node highly available managed PostgreSQL 16 cluster and private Spaces resources in Sydney. A single-node database is not approved for paid/customer-data production.
2. Create separate migration/admin and runtime database roles. Runtime must be `NOSUPERUSER NOBYPASSRLS`; grant only database connect, schema use, table DML, sequence use and required application functions. Restrict the cluster to the app plus controlled operator access. Use `verify_full_custom_ca` with DigitalOcean's provider CA for runtime, migration and backup connections; `require` encryption without hostname/certificate verification is insufficient.
3. Create bucket credentials scoped as narrowly as DigitalOcean supports. Block public access and CDN publication. Object keys/metadata must not contain customer names, emails or sensitive labels.
4. Enter secret values from the template in the control plane. Keep web, API/worker, migration and backup credentials separated; the web must never receive database/provider keys.
5. Configure platform alerts for deployment/domain failure, component restarts, CPU/memory, database health/storage/connection count and failed scheduled jobs. Route to Kevin's controlled operations destination.
6. Create the app from the reviewed spec for synthetic infrastructure and identity proof. Keep trial activation, paid checkout, customer data and public launch blocked until the legal pages are approved. Do not turn on deploy-on-push.

### Clerk production owner sequence (not performed)

Clerk's current production guide requires a separate production instance and
provider-issued DNS/certification steps
([Clerk production deployment](https://clerk.com/docs/guides/development/deployment/production)).
Clerk Pro is required for paid/customer-data production because Hobby does not provide
the required MFA/passkey and operational-log posture. After the owner approves Pro:

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
   URLs.
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

WO-054B makes the adapter production-capable but does not activate it. The checked-in
production template deliberately remains `API_FEATURE_BILLING_ENABLED=false`,
`API_BILLING_PROVIDER_NAME=deterministic`, `API_BILLING_MODE=test`, GST unresolved and
all live Stripe references empty. The following owner sequence must be performed in
order under separate activation authority:

1. Owner/accounting resolves GST presentation and Stripe tax treatment, records the
   durable policy reference, and approves the final Privacy Notice and Service Terms.
2. Owner creates and verifies the Stripe business account, including contracting
   entity, Australian business verification, settlement bank account and support
   contact. Do not put identity or bank evidence in Git or tickets.
3. Configure Oryntela branding, approved legal URLs and a Stripe-accepted statement
   descriptor. Keep the existing 14-day Complete trial outside Stripe: no card, no
   automatic conversion and no automatic charge.
4. Create the exact live Products/Prices below. Enterprise stays a manual commercial
   process; do not create a self-service Enterprise Price, production Credit pack,
   coupon or unapproved Stripe Tax configuration.

   | Environment reference               | Amount/recurrence    | Required Price metadata                                         |
   | ----------------------------------- | -------------------- | --------------------------------------------------------------- |
   | `API_STRIPE_PRICE_CORE_MONTHLY`     | AUD 200 every month  | `oryntela_plan_version_id=ee299a7d-3f12-5845-847e-3425f78ed6f2` |
   | `API_STRIPE_PRICE_CORE_ANNUAL`      | AUD 2,000 every year | `oryntela_plan_version_id=ee299a7d-3f12-5845-847e-3425f78ed6f2` |
   | `API_STRIPE_PRICE_GROWTH_MONTHLY`   | AUD 350 every month  | `oryntela_plan_version_id=2d8aa6a4-30aa-52e8-8273-3859210a8406` |
   | `API_STRIPE_PRICE_GROWTH_ANNUAL`    | AUD 3,500 every year | `oryntela_plan_version_id=2d8aa6a4-30aa-52e8-8273-3859210a8406` |
   | `API_STRIPE_PRICE_COMPLETE_MONTHLY` | AUD 500 every month  | `oryntela_plan_version_id=43cb5fa7-1b0b-5ca7-b5a3-740bd3e063a0` |
   | `API_STRIPE_PRICE_COMPLETE_ANNUAL`  | AUD 5,000 every year | `oryntela_plan_version_id=43cb5fa7-1b0b-5ca7-b5a3-740bd3e063a0` |

5. Put only references in configuration: the exact verified `acct_` account ID as
   `API_STRIPE_ACCOUNT_ID`, the six Price IDs above, `sk_live_` secret as
   `API_STRIPE_SECRET_KEY`, `API_BILLING_TAX_TREATMENT=inclusive|exclusive`, the
   approved `API_BILLING_TAX_POLICY_REFERENCE`, exact HTTPS return URLs and
   `API_STRIPE_API_VERSION=2026-02-25.clover`. Keep the feature flag false.
6. Configure the live webhook at
   `https://api.oryntela.com.au/api/v1/billing/webhooks/stripe`, pin it to
   `2026-02-25.clover`, and subscribe only to `checkout.session.completed`,
   `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`,
   `invoice.payment_failed`, `invoice.finalized`, `invoice.voided` and
   `invoice.marked_uncollectible`. Store its `whsec_` value only as
   `API_STRIPE_WEBHOOK_SECRET`.
7. Configure a separate live customer portal. Initially allow invoice history,
   billing details and payment-method updates; keep plan switching and promotion codes
   off; set approved legal links and `https://oryntela.com.au/settings` as the return
   URL. Store its live `bpc_` ID as `API_STRIPE_PORTAL_CONFIGURATION_ID`.
8. Set `API_BILLING_PROVIDER_NAME=stripe` and `API_BILLING_MODE=live`, still with the
   feature flag false, then run `revenueos-operations production-preflight` from the
   exact release. It performs read-only retrieval of the authenticated Account, every
   Price and portal configuration and fails closed on account identity, charge/payout
   readiness, portal action policy, ID, mode, activity, AUD amount, recurrence or
   plan-version metadata mismatch.
9. Only after separate written authority, run one synthetic/minimum live smoke using
   an owner-controlled test identity: admin starts server-owned Core monthly checkout,
   Stripe-hosted collection settles the minimum authorised real transaction, the
   webhook establishes the paid item period/latest paid invoice, the success page
   confirms only after reconciliation, portal loads, end-of-period cancellation and
   reactivation reconcile, and duplicate/stale delivery causes no second effect.
10. Confirm the database's mode-scoped account/subscription/invoice/receipt projection,
    `paid_through`, commercial transition, support view and Stripe dashboard agree;
    capture safe identifiers/results only and refund only under separately approved
    policy.
11. Only then enable `API_FEATURE_BILLING_ENABLED=true` for the paid-customer path and
    monitor failed webhooks, reconciliation-required operations and payment failures.

This sequence is a runbook, not permission. None of its external steps has been
performed. Raw card data stays entirely in Stripe-hosted Checkout/portal surfaces;
Oryntela does not claim PCI certification.

## 4. Database migration and deployment

Before every release:

1. Record commit SHA, migration head, operator/change reference and rollback release. Confirm required CI and secret/dependency audits pass.
2. Confirm a recent recoverable database backup and last restore result. If a migration is not backwards-compatible with the last app release, stop worker claims and schedule downtime.
3. Run `alembic current` and verify the source state. Never edit `alembic_version` manually.
4. Run once using the migration credential: `alembic upgrade head`.
5. Verify `alembic current` is `0063_terms_acceptance`; run `alembic check`; then run `revenueos-operations production-preflight` from the release image. Require `terms_acceptance_release=pass`; a draft release must keep the overall result blocked.
6. Deploy the API and require `/health/live` = 200 and `/health/ready` = 200 before traffic. Start the exact same release's single worker and require its private liveness probe. Deploy web and require `/health/ready` = 200.
7. Run the synthetic smoke matrix below. Inspect safe error rate/restarts and queue summaries before marking the release healthy.

If migration fails, keep the new API/worker out of traffic, preserve the database and backup, inspect the exact Alembic/database error with the migration role, then choose a forward fix or restore. Prefer application rollback on a forward-compatible schema. A schema downgrade requires the specific migration's documented data-loss review, explicit owner approval and a verified backup.

## 5. Backup, restore and objectives

Production policy, pending owner-funded target creation and proof:

- database: DigitalOcean automatic encrypted backups/PITR plus the independent logical bundle; named owner checks managed-backup health daily;
- application logical bundle: the scheduled App Platform job runs daily at 03:30 Australia/Sydney, streams `pg_dump` plus every source Spaces object through AES-256-GCM, authenticates the format-v2 manifest with a domain-separated HMAC-SHA256 key, uploads each encrypted payload to private AWS S3 Standard in Sydney, uploads the manifest last only after remote size/SHA-256 metadata verification, then downloads and cryptographically verifies the committed bundle before reporting success;
- retention: enable AWS versioning and apply
  `infra/aws/independent-backup-lifecycle.json`; current backup keys expire after
  14 days, any noncurrent versions expire one day after becoming noncurrent,
  incomplete multipart uploads expire after one day, and a separate rule removes
  expired delete markers. S3 evaluates lifecycle asynchronously, so 14 days is a
  rotation threshold rather than a deletion-to-the-second guarantee;
- secrets/config: provider-controlled recovery/escrow owned separately and never copied into the bundle; maintain a separately controlled offline copy of the backup encryption key; and
- drill: synthetic before launch, named cloud restore before customer data, quarterly during beta and after material hosting/schema changes.

The repository now contains the scheduled remote backup/verify/restore implementation,
but that is not evidence that an AWS bucket, lifecycle policy, alert route or successful
cloud restore exists. Those remain **BLOCKED for customer data** until WO-054C/D.

The logical-backup source principal is a dedicated, tightly controlled backup/migration
principal able to read all tenant rows despite forced RLS. Never grant that authority
to the API/worker runtime role. The isolated restore target should be owned by the
migration principal; reapply and verify least-privilege runtime grants before application
smoke testing.

Remote commands (all source/destination/target credentials injected through the
dedicated job environment, never as command arguments):

```text
revenueos-backup create-remote
revenueos-backup verify-remote --backup-id <backup-id>
revenueos-backup restore-remote --backup-id <backup-id> \
  --confirm "RESTORE <backup-id> TO CONFIGURED NAMED TARGET"
```

Before the first backup, the owner applies and reads back the checked-in lifecycle
policy from a private authenticated AWS session. Replace only the bucket placeholder;
the policy itself contains no account identifier or secret:

```text
aws s3api put-bucket-versioning --bucket <independent-backup-bucket> \
  --versioning-configuration Status=Enabled
aws s3api put-bucket-lifecycle-configuration \
  --bucket <independent-backup-bucket> \
  --lifecycle-configuration file://infra/aws/independent-backup-lifecycle.json
aws s3api get-bucket-versioning --bucket <independent-backup-bucket>
aws s3api get-bucket-lifecycle-configuration \
  --bucket <independent-backup-bucket>
```

Require the read-back to match the reviewed policy. This does not prove expiry until
an aged synthetic object, its noncurrent version and its expired delete marker have
each disappeared; record that later observation as owner-controlled recovery evidence.

Create reads the dedicated source database/Spaces variables and writes only to the
independent destination. Restore reads the isolated target from the
`API_BACKUP_RESTORE_TARGET_*` variables. The local `create`, `verify` and `restore`
commands remain available for synthetic development drills only.

After restore, verify counts/invariants, `alembic current`, `alembic check`, runtime-role/RLS/cross-tenant tests, object reconciliation and API readiness; then destroy test resources. Never restore production data to a developer laptop. V1 recommended RPO is 24 hours and RTO is four hours, internal targets only—not contractual SLAs.

## 6. Monitoring and daily operations

At start and end of the owner-operated support window:

1. Check web `/health/ready`, API `/health/live` and `/health/ready`, last deploy SHA, component restart alerts, worker probe, database status/backups and object-storage availability.
2. For every approved organisation run `revenueos-operations tenant-preflight`, `queue-status` and, when needed, the metadata-only `support-bundle`. Alert on growing pending/retry counts, queue oldest age over five minutes twice, expired leases, `unknown_external_state`, `unknown_delivery_state`, provider `degraded/rate_limited/needs_reauth`, billing reconciliation required or repeated safe failure codes.
3. Verify the previous scheduled retention and remote-backup jobs completed. Because App Platform does not supply a native scheduled-job-failure alert in this specification, configure an external freshness check for the manifest-last backup proof. Maintenance remains tenant-scoped: add one scheduled job per approved organisation only after provisioning, first running `retention --dry-run`; do not place customer UUIDs in this public template.
4. Review API 5xx/error-rate and latency, failed billing webhook counts, provider dashboards only for activated providers, storage/DB capacity and security/auth anomalies. Logs retain 14 days initially unless the owner approves another operational period; never infer a statutory retention period.

Platform probes and logs are the zero-additional-cost launch monitoring baseline. They detect stopped/stale processes, readiness, deploy/domain failure and resource pressure. They do not replace tenant queue checks or a privacy-reviewed error-reporting system. No third-party error-reporting account is created in WO-054; evaluate it from measured need and send no content, tokens, email bodies, Evidence, prompts, object keys, card data or Deal Room tokens.

The Deal Room has a single-instance in-memory limit (default 120 requests/minute per address/token), signed/revocable bearer grants and noindex/no-store headers. Billing webhooks enforce signatures, replay/idempotency, timestamp bounds and a 1 MB body cap. Authenticated/provider actions use tenant quotas, concurrency bounds and provider backoff. Before scaling API replicas or announcing a public high-volume launch, add an edge/distributed public-route limiter; do not pretend the in-memory limiter is global.

## 7. Kill switches and containment

Change server flags in the secret/config control plane, redeploy the matching API and worker, and record the change. Do not mutate queue/database rows manually.

- Stop sending/external mutation: `API_FEATURE_ACTION_EXECUTION_ENABLED=false`; for campaigns also `API_FEATURE_ENGAGE_CAMPAIGNS_ENABLED=false`; stop the worker if outcome contracts are in doubt.
- Stop all connector surfaces: `API_FEATURE_INTEGRATIONS_ENABLED=false`; disable the named Microsoft/Google/HubSpot/Salesforce flag; revoke provider credentials when compromised.
- Stop Prospect cost: `API_FEATURE_PROSPECT_EXTERNAL_PROVIDER_ENABLED=false`, then `API_FEATURE_CREDITS_ENABLED=false`; disable the provider key in its console.
- Stop billing/checkout: `API_FEATURE_BILLING_ENABLED=false`. This prevents new
  checkout, portal and subscription mutations without rewriting paid authority.
  Continue accepting verified mode-matched webhooks and reconcile all pending/unknown
  operations and invoices before rotating or revoking the Stripe key/webhook. If a
  secret is compromised, disable checkout first, rotate the affected credential in
  Stripe and the secret manager, then prove signature/read-only reconciliation before
  restoring mutations. Never discard a valid webhook because UI checkout is disabled.
- Stop customer-content AI: disable `API_FEATURE_OPENAI_PROVIDER_ENABLED` plus the affected content feature; do not substitute mock output in real-data mode.
- Stop capture/binary writes: disable recording, online-meeting, document, visual and Create flags as appropriate; preserve reconciliation metadata.
- Revoke public Deal Room: use the supported publication revocation; do not log the fragment token.

Unknown external/delivery outcomes are never blindly retried. Check the provider with its non-mutating lookup/reconciliation path, record only safe references, then use the supported reconcile operation.

## 8. DNS, TLS and callbacks

Canonical recommendation: `https://oryntela.com.au`; route `www.oryntela.com.au` to the canonical origin. Leave `oryntela.com` unchanged until the owner chooses redirect versus future global use. App Platform automatically redirects HTTP to HTTPS and provisions TLS after domain validation. Do not add HSTS until both web and API TLS/redirect/callback smoke tests are stable; then set both HSTS switches true and verify `max-age=31536000`. The code deliberately omits `includeSubDomains` and `preload`.

Exact DNS record _names_ are apex `@`, `www` and `api`; their A/AAAA/CNAME _targets_ must be copied from the created App Platform domain instructions because no destination exists yet. Record old TTL/values, lower TTL if approved, add platform verification, validate TLS, then switch. Never invent an IP. Roll back using the captured records.

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

| Area                                | Required assertion                                                                                                                                                               | Execution boundary                                              |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Public site                         | home/platform/pricing/integrations/security/contact/login, canonical, OG, sitemap, headers; approved legal pages only                                                            | after legal/DNS approval                                        |
| Auth                                | sign-up/invite policy, sign-in/out/session, protected routes, disabled membership and cross-tenant denial                                                                        | production Clerk owner setup required                           |
| Setup/Core                          | provision synthetic org; Selling Profile; Native CRM companies/contacts/opportunities/tasks; Pipeline, Forecast, Targets, Analytics, Manager, Business Case, Deal Room, Handover | execute before traffic with synthetic data                      |
| Trial                               | operator starts 14-day Complete trial; no card, charge or auto-conversion; inspect commercial state                                                                              | execute only after legal approval and production auth/database  |
| Prospect/Credits                    | UI truth says inactive; external call and production Credit reservation blocked                                                                                                  | no provider use                                                 |
| Engage                              | draft/review/suppression behaviour; delivery remains disabled unless synthetic mailbox separately approved                                                                       | no real email                                                   |
| Create                              | generate/approve/download synthetic PPTX through private object storage; verify checksum, one-time grant and restart portability                                                 | execute after bucket exists                                     |
| Billing                             | deterministic/Stripe test only outside production; signatures, replay and reconciliation tests                                                                                   | no real money; production remains off                           |
| Microsoft/Google/HubSpot/Salesforce | UI says activation pending; connection attempts fail closed while disabled                                                                                                       | run provider sandbox smoke only after owner credentials/consent |
| Recovery                            | backup, disposable restore, head/invariants/RLS/object reconciliation, target destruction                                                                                        | synthetic local now; named cloud required pre-customer          |

## 10. Support and lifecycle operations

- Trial: first obtain the customer's organisation-admin acceptance through the authenticated UI; support cannot provide it. Then inspect commercial state and run `commercial-start-trial` with current lock version, bounded reason/operator and printed exact confirmation. It never creates a card or automatic conversion.
- Commercial change: use `commercial-assign-plan`/`commercial-change-state`; never edit tables. Live billing stays off until an adapter and reconciliation smoke pass.
- Manual paid Credits: follow `manual-paid-credit-grant-runbook.md`; cleared funds and a margin review are mandatory; the grant does not enable provider execution.
- Provider reconnect: disable the named flag if unsafe, inspect safe connection health, revoke/disconnect, rotate client secret/token as needed, reconnect through OAuth, then reconcile before writes.
- Export: approve request/authority, create with `revenueos-beta-maintenance export`, authorise one-time download and purge. Production generation streams through an ephemeral temporary file to a tenant-scoped private S3 object, verifies size/SHA-256, and serves it only through authenticated membership/expiry checks. Keep the flag off until target preflight proves write/read/delete and cross-tenant denial.
- Organisation deletion: optional export, disable members, stop queues, revoke connectors, run exact-confirmation deletion, verify database/object/grant/search/worker absence, then let backups age out. Feature remains off until the named-target proof passes.
- Billing: compare Oryntela subscription/invoice event state with Stripe IDs and verified events; reconcile through supported service paths. Live billing stays off until every GST, account, Price, webhook, portal, preflight and separately authorised smoke gate passes. Never paste card/customer/provider payloads into logs or tickets.

## 11. Rollback and release close

Contain with the narrowest kill switch; pause worker if contract compatibility is uncertain. Redeploy the last validated web/API/worker SHA together only if it supports the current forward schema. Retain migrations `0062_live_stripe_billing` and `0063_terms_acceptance` during application rollback so paid-through and acceptance evidence remain authoritative. The billing downgrade refuses to run while live authority exists; do not delete or relabel billing or Terms evidence to force a downgrade. Confirm liveness/readiness, worker probe, synthetic tenant, queue states and error rate. Restore the database only when a forward fix/application rollback cannot recover and the recovery owner approves the RPO impact. Restore objects and database to the same recovery point.

After a successful launch window, record SHA, migration head, health/smoke results, any provider actions, spend, incidents and deviations. Public announcement and customer onboarding are separate owner gates and are not part of WO-054.
