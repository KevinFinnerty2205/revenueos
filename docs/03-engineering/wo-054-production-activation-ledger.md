# WO-054 production activation boundary ledger

- Evidence date: 11 September 2026 (Australia/Sydney)
- Reviewed main: `3fdf567e2f103abd312fee7e7297af996532c910`
- Migration head: `0063_terms_acceptance`
- State: ready for owner account/payment actions; no production resource exists in
  repository evidence
- Spend in this activation pass: AUD 0 / USD 0
- Customer data: none

This is the resumption ledger for the owner-boundary pass. It records only facts
verified without creating an account, accepting a contract, entering credentials or
starting billable usage. The detailed execution and rollback procedure remains the
[production launch runbook](production-launch-runbook.md).

## Selected topology and current cost boundary

The selected Sydney topology remains one 1 GiB web service, one 1 GiB API service,
one 1 GiB worker, one two-node 2 GiB highly available PostgreSQL 16 cluster, one
private Spaces subscription and one Clerk Pro subscription. The migration and daily
backup jobs run only when invoked. AWS S3 Standard in `ap-southeast-2` is the
independent encrypted backup destination and has no fixed monthly minimum.

| Item | Exact selection | Current displayed price | Billing boundary |
| --- | --- | ---: | --- |
| Web | DigitalOcean `apps-s-1vcpu-1gb-fixed` | USD 10/month | billed per second, one-minute minimum, capped using the provider's monthly component rules |
| API | DigitalOcean `apps-s-1vcpu-1gb-fixed` | USD 10/month | same |
| Worker | DigitalOcean `apps-s-1vcpu-1gb-fixed` | USD 10/month | same |
| Database | DigitalOcean PostgreSQL HA, 2 GiB/1 vCPU primary plus one matching standby | USD 60/month | USD 30/node/month; database billing hourly with a one-hour minimum |
| Application objects | DigitalOcean Spaces Standard, Sydney | USD 5/month | starts with the first bucket; prorated hourly after all buckets are destroyed |
| Independent backup | AWS S3 Standard, Sydney | USD 0 fixed | USD 0.025/GB-month first 50 TB; USD 0.0055/1,000 PUT/COPY/POST/LIST; USD 0.0044/10,000 GET/other, plus transfer |
| Authentication | Clerk Pro, month-to-month | USD 25/month | recurring subscription; USD 20/month only with annual billing |

The fixed total is **USD 120/month** before tax and usage. At the RBA observation of
1 AUD = USD 0.7172 on 11 September 2026, that is approximately **AUD 167.32/month**.
It leaves AUD 52.68 of the AUD 220 planning ceiling before GST/tax, card FX spread,
backup usage and other variable charges. No displayed SKU price changed from the 10
September review; only the planning exchange rate changed. The provider invoice and
card conversion remain authoritative.

For a 1–10 GB average retained AWS backup footprint and about 30 uploads per month,
storage plus upload requests is approximately USD 0.03–0.26/month before transfer
and tax. This range is not included in the fixed total. It must be replaced with
observed storage, request, transfer and job-duration charges after the synthetic
backup and restore drill.

Sources verified on the evidence date: [DigitalOcean App Platform pricing](https://docs.digitalocean.com/products/app-platform/details/pricing/),
[DigitalOcean PostgreSQL pricing](https://docs.digitalocean.com/products/databases/postgresql/details/pricing/),
[DigitalOcean Spaces pricing](https://docs.digitalocean.com/products/spaces/details/pricing/),
[AWS S3 pricing](https://aws.amazon.com/s3/pricing/), [Clerk pricing](https://clerk.com/pricing)
and [RBA exchange rates](https://www.rba.gov.au/statistics/frequency/exchange-rates.html).

## Account and provider reconciliation

Direct dashboard navigation in the in-app browser produced a signed-out login page
for every account below. This proves only that the browser profile has no usable
session; it does not prove that an account does or does not exist. No login method,
credential, recovery flow, account creation or purchase was attempted.

| Provider | Account/resource evidence | Launch classification |
| --- | --- | --- |
| DigitalOcean | owner login required; resources uninspected | not configured |
| AWS | owner login required; resources uninspected | not configured |
| Clerk | owner login required; application/plan uninspected | not configured |
| Stripe | owner login required; account/live-mode state uninspected | not configured |
| OpenAI API | owner login required; organisation/project/billing uninspected | not configured |
| Zoho Mail | existing owner register plus live MX/SPF/DMARC evidence; do not reconfigure | active/existing |
| Prospect, Microsoft 365, Google Workspace, HubSpot, Salesforce | no production credentials or activation authorised | not configured; must remain disabled |

PR 88 is still open and draft. It remains untouched. The provider facts are not
stable enough to finalise the Privacy Notice or perform publication steps 5–10.

## Secret and recovery inventory

No value was generated because no production secret manager is available. Never
create a value in a captured terminal merely to hold it locally. After the owner
creates the DigitalOcean control plane, generate each application secret in a
private non-recorded terminal and paste it directly into the correct secret scope,
then record only its safe provider/key identifier and rotation metadata.

**Core required:** `CLERK_SECRET_KEY`; `DATABASE_URL` runtime credential;
`API_DATABASE_CA_CERTIFICATE_BASE64`; Clerk JWKS/issuer/audience configuration;
`API_OUTREACH_SUPPRESSION_HMAC_KEY`; private Spaces bucket/access credentials; and
`API_VISUAL_STORAGE_SIGNING_SECRET`. The migration job gets a separate migration
database URL. The scheduled backup job alone gets its separate source database/CA,
source Spaces credentials, destination AWS credentials and
`API_BACKUP_ENCRYPTION_KEY`.

**Stripe required only after its gate:** `API_STRIPE_SECRET_KEY`,
`API_STRIPE_WEBHOOK_SECRET`, account/portal IDs and the six exact live Price IDs.

**OpenAI required only after its gate:** `OPENAI_API_KEY` plus ordinary config
`OPENAI_MODEL=gpt-5.6-terra`, timeout/output limits and the explicit approval/feature
flags. Core production boots with `AI_PROVIDER=mock` and the OpenAI feature flag
false, without this secret.

**Optional/disabled:** connector credential master key; Microsoft, Google, HubSpot
and Salesforce OAuth secrets; and a Prospect provider key. Do not provision or add
these to Core merely to satisfy an inventory.

The backup encryption key must also have a separately controlled offline recovery
copy. It must never be inside the database, Spaces bucket, S3 backup, Git, a ticket
or a screenshot. Recovery ownership, rotation and revocation sequences are in the
[incident and secret-rotation runbook](production-incident-and-secret-rotation.md).

## OpenAI AUD 50 control

The intended model remains `gpt-5.6-terra`, standard short-context processing at
USD 2/million input and USD 12/million output tokens on the evidence date. No paid
request is authorised by this ledger.

- Set the dedicated project's monthly notification threshold to the owner-approved
  USD planning equivalent and configure a lower early-warning alert. A notification
  is not a stop.
- If the account exposes enforceable organisation/project hard-spend controls, set
  the narrow project control no higher than the current USD equivalent of AUD 50.
  Confirm the UI labels it as enforced; do not infer this from a budget alert.
- If the account uses prepaid billing, buy only the separately approved amount and
  turn **auto-recharge off**. Prepaid exhaustion can still overshoot during provider
  processing delay, so it is not an instantaneous hard cap.
- The application stop is `API_FEATURE_OPENAI_PROVIDER_ENABLED=false` together with
  the affected customer-content feature flags and worker claim stop. Never replace
  real-customer output with mock intelligence. The 50 generations/75 attempts daily
  tenant limits bound volume but are not monetary caps.

New prepaid API accounts require an initial USD 5 minimum purchase; credits expire
after one year and are non-refundable. That purchase, payment details, project/key
creation and any synthetic paid request are separate owner boundaries.

## DNS and continuation boundary

No DNS record changed. The apex and `www` still resolve to the existing site,
`api.oryntela.com.au` has no target, and existing Zoho MX, SPF, DKIM, DMARC and
verification records remain authoritative. Exact new apex/`www`/API values cannot be
prepared until DigitalOcean and Clerk issue their targets. Apply only additive or
targeted record changes; leave `oryntela.com` unchanged. Enable HSTS only after
production HTTPS is stable; do not preload.

After the owner supplies authenticated sessions and explicit purchasing authority,
resume at the resource-creation section of the launch runbook. Create company-owned
resources, keep automatic deploy off, place secrets without exposing them, create
separate migration/runtime roles, migrate through `0063_terms_acceptance`, prove RLS
and synthetic cross-tenant denial, configure backup/monitoring, perform the
named-cloud synthetic restore, and only then prepare provider facts for the owner's
later PR 88 publication decision.

## Owner-only blockers

1. Sign into or create the company-controlled DigitalOcean account, enable MFA and
   approve the exact USD 95/month fixed resource set plus metered job usage.
2. Sign into or create the company-controlled AWS account, enable MFA/payment
   controls and approve the private Sydney S3 usage range above.
3. Sign into the owner-controlled Clerk workspace, confirm the existing application,
   enable MFA and approve Pro month-to-month at USD 25/month recurring.
4. Sign into or create the company-controlled Stripe account and complete the
   business, identity and Australian bank/payout verification. This starts no fixed
   subscription and authorises no real charge.
5. Sign into or create the OpenAI API organisation and decide whether to approve the
   minimum USD 5 prepaid purchase with auto-recharge off and the AUD 50 control
   profile. Do not create a production key or run a paid request under this pass.

Completing a login is not permission for Codex to purchase, deploy, create live
payment objects, create API keys or accept provider terms. Kevin must return with the
specific account/resource authority to cross each boundary.
