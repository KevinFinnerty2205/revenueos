# WO-054 production activation boundary ledger

- Initial evidence date: 11 September 2026 (Australia/Sydney)
- Latest Stripe control-plane evidence: 15 September 2026 (Australia/Sydney)
- Latest OpenAI control-plane evidence: 15 September 2026 (Australia/Sydney)
- Latest owner build-only boundary: 24 October 2026 (Australia/Sydney)
- Pre-gate main baseline: `4facc04`
- Current repository migration head: `0071_assignment_tombstones`
- Deployed pre-build migration head: `0064_deauthorisation`
- State: downsized synthetic-only production healthy; Stripe live configuration bound and verified;
  exact legal release owner-approved and published; OpenAI project funded and its
  least-privilege secret bound while execution remains disabled; customer checkout
  and Credits disabled; paid-customer resilience gate pending review and deployment
- Stripe fixed spend in this activation pass: AUD 0 / USD 0; no transaction fee
- Customer data: none

This is the resumption ledger for the owner-boundary pass. It records only facts
verified without creating an account, accepting a contract, entering credentials or
starting billable usage. The detailed execution and rollback procedure remains the
[production launch runbook](production-launch-runbook.md).

## Selected topology and current cost boundary

The owner-approved pre-launch Sydney topology is one 512 MiB web service, one
512 MiB API service, one 512 MiB worker, one single-node 1 GiB PostgreSQL 16 cluster
and one private Spaces subscription. The migration and daily backup jobs run only
when invoked. AWS S3 Standard in `ap-southeast-2` is the independent encrypted backup
destination and has no fixed monthly minimum. This configuration is synthetic-only
and is not approved as the first paid-customer or customer-data resilience profile.

| Item                | Exact selection                                                   | Current displayed price | Billing boundary                                                                                                |
| ------------------- | ----------------------------------------------------------------- | ----------------------: | --------------------------------------------------------------------------------------------------------------- |
| Web                 | DigitalOcean `apps-s-1vcpu-0.5gb`                                 |             USD 5/month | billed per second, one-minute minimum, capped using the provider's monthly component rules                      |
| API                 | DigitalOcean `apps-s-1vcpu-0.5gb`                                 |             USD 5/month | same                                                                                                            |
| Worker              | DigitalOcean `apps-s-1vcpu-0.5gb`                                 |             USD 5/month | same                                                                                                            |
| Database            | DigitalOcean PostgreSQL, 1 GiB/1 shared vCPU/10 GiB, primary only |         USD 15.15/month | prorated provider monthly rate; no standby in the pre-launch profile                                            |
| Application objects | DigitalOcean Spaces Standard, Sydney                              |             USD 5/month | starts with the first bucket; prorated hourly after all buckets are destroyed                                   |
| Independent backup  | AWS S3 Standard, Sydney                                           |             USD 0 fixed | USD 0.025/GB-month first 50 TB; USD 0.0055/1,000 PUT/COPY/POST/LIST; USD 0.0044/10,000 GET/other, plus transfer |

The current fixed DigitalOcean total is **USD 35.15/month** before tax and short-lived
job usage. The former fixed DigitalOcean total was USD 95.90/month, so the approved
pre-launch reduction saves USD 60.75/month. Before a first real customer, reassess
capacity, high availability, load and recovery evidence and obtain explicit owner
approval for the resulting production cost. No amount in this ledger pre-approves
that future spend.

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

The initial 11 September pass produced signed-out provider pages and therefore proved
only that the browser profile had no usable session. Stripe and OpenAI reflect later
authenticated control-plane evidence; DigitalOcean, AWS and Clerk reflect subsequent
owner-confirmed state and the current build-only boundary. This owner-demo branch does
not independently re-verify or change any provider control plane.

| Provider                                                       | Account/resource evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Launch classification                                                                                                                   |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| DigitalOcean                                                   | existing Sydney web, API, worker, single-node PostgreSQL and private Spaces resources; owner-confirmed healthy at USD 35.15/month fixed before tax and short-lived jobs; no customer data                                                                                                                                                                                                                                                                                                                              | active synthetic-only pre-launch profile; unchanged and not approved for first-customer resilience                                      |
| AWS                                                            | existing independent-backup schedule and retention must be preserved; this build-only pass does not create, delete, purchase or re-test AWS resources                                                                                                                                                                                                                                                                                                                                                                  | existing control retained; current delivery/recovery evidence remains a separate operations gate                                        |
| Clerk                                                          | existing production identity configuration is preserved; this build-only pass neither changes identity settings nor onboards a customer                                                                                                                                                                                                                                                                                                                                                                                | production activation state unchanged; named-customer/session proof remains a separate gate                                             |
| Stripe                                                         | Australian live account `acct_1UFXmNEAHCYYkWOg`; Core/Growth/Complete live Products and six exact recurring AUD Prices; live webhook `we_1UFYbZEAHCYYkWOgz2zpW3Ox`; bounded portal `bpc_1UFYdFEAHCYYkWOg309ZjGMV`; encrypted runtime-only API and webhook secrets bound to API and worker; read-only `live_stripe_billing` preflight passed; owner completed the Stripe Services Agreement certification; Stripe reports no active verification tasks and Payments/Payouts active; no customer, charge or subscription | configured and provider-activated; checkout and Credits disabled under the separate billing gate                                        |
| OpenAI API                                                     | owner-controlled `Personal` organisation; project `Oryntela Production` (`proj_fb1vGtmPRjlbzlMamBvJbPKf`); USD 5 prepaid balance with auto-reload off; organisation and project hard limits each USD 5/month; only `gpt-5.6-terra` allowed at 10,000 TPM / 1 RPM; 90-day service-account key restricted to Responses write and bound as an encrypted runtime secret to API and worker                                                                                                                                  | configured but execution remains fail-closed; the current build-only direction authorises no paid request or synthetic production smoke |
| Zoho Mail                                                      | existing owner register plus live MX/SPF/DMARC evidence; do not reconfigure                                                                                                                                                                                                                                                                                                                                                                                                                                            | active/existing                                                                                                                         |
| Prospect, Microsoft 365, Google Workspace, HubSpot, Salesforce | no production credentials or activation authorised                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | not configured; must remain disabled                                                                                                    |

On 15 September 2026 the owner approved the exact PR #88 Terms and Privacy Policy,
selected effective date `2026-09-15`, and authorised publication. The legal-release
commit binds those canonical bytes, versions and fingerprints. The owner-approved
pages are published; the current repository candidate adds their public index and
sitemap integration, but this build-only work does not deploy that candidate.

### Stripe live control-plane evidence — 15 September 2026

- Oryntela is the customer-facing brand for Management Services Australia Pty. Ltd.
  (ABN 15 113 119 556) on the Australian live Stripe account above.
- The canonical catalogue contains no Enterprise self-service Price and no Credit
  pack. The six recurring Prices are GST-inclusive totals: Core AUD 200/month or
  AUD 2,000/year, Growth AUD 350/month or AUD 3,500/year, and Complete AUD 500/month
  or AUD 5,000/year.
- The webhook targets
  `https://api.oryntela.com.au/api/v1/billing/webhooks/stripe`, uses
  `2026-08-26.dahlia`, and receives only the eight approved Checkout,
  subscription and invoice events. Its signing secret and the live API key are
  encrypted, runtime-only DigitalOcean component secrets. A replacement API key was
  verified by preflight before the superseded exposed key was expired; exactly one
  labelled production runtime key remains active.
- The portal permits invoice history, customer-information updates and payment-method
  updates. Portal subscription changes and cancellations are disabled. Stripe Tax
  and Climate are off; Radar Lite is the selected baseline protection.
- On 15 September 2026 the owner personally completed Stripe's `Agree and submit`
  certification for the displayed company, representative, control and payout facts.
  Stripe then reported no active verification tasks and listed Payments and Payouts
  as active. This provider activation does not override the Oryntela legal or feature
  gates and is not authority for a customer transaction.
- Production API and worker use Stripe live mode and the exact live references while
  `API_FEATURE_BILLING_ENABLED=false` and
  `API_FEATURE_CREDITS_ENABLED=false`. The read-only production preflight reported
  `live_stripe_billing=pass`; the approved legal release makes
  `terms_acceptance_release=pass`, while incomplete real-data and billing approvals
  continue to block customer checkout.
- No live-money smoke was performed. Customers, charges, subscriptions and refunds
  remain none, and this Stripe configuration incurred no fixed or transaction fee.

## Secret and recovery inventory

The initial evidence pass generated no value because no production secret manager
was then available. DigitalOcean encrypted component variables are now the production
secret store. Never create a value in a captured terminal merely to hold it locally;
place each value directly into its encrypted least-privilege scope and record only
the variable name, safe provider/key identifier and rotation metadata. On
15 September the live Stripe API and webhook secrets were bound to the API and
worker as runtime-only encrypted variables. Read-only reconciliation proved the
replacement API key before the superseded exposed key was expired.

On 15 September the OpenAI service-account key was bound directly to the API and
worker as `OPENAI_API_KEY`, encrypted and runtime-only. It expires on 14 December
2026 and is restricted to write access on `/v1/responses`; all other API resources
are denied. The first generated value entered an automation trace and was therefore
treated as exposed, revoked immediately and never bound or used. The replacement
value was transferred directly without being read and is the only active key for
this production project.

**Core required:** `CLERK_SECRET_KEY`; `DATABASE_URL` runtime credential;
`API_DATABASE_CA_CERTIFICATE_BASE64`; Clerk JWKS/issuer/audience configuration;
`API_OUTREACH_SUPPRESSION_HMAC_KEY`; private Spaces bucket/access credentials; and
`API_VISUAL_STORAGE_SIGNING_SECRET`. The migration job gets a separate migration
database URL. The scheduled backup job alone gets its separate source database/CA,
source Spaces credentials, destination AWS credentials and
`API_BACKUP_ENCRYPTION_KEY`.

**Stripe already bound but use-gated:** `API_STRIPE_SECRET_KEY`,
`API_STRIPE_WEBHOOK_SECRET`, account/portal IDs and the six exact live Price IDs are
already present in the production secret/configuration boundary. Billing, checkout,
Credits and transactions remain disabled and separately gated.

**OpenAI already bound but execution-gated:** `OPENAI_API_KEY` is already present in
the production secret boundary, with ordinary config for
`OPENAI_MODEL=gpt-5.6-terra`, timeout/output limits and explicit approval/feature
flags. Core production continues to run with `AI_PROVIDER=mock` and the OpenAI feature
flag false; the bound secret does not authorise or cause a request.

**Optional/disabled:** connector credential master key; Microsoft, Google, HubSpot
and Salesforce OAuth secrets; and a Prospect provider key. Do not provision or add
these to Core merely to satisfy an inventory.

The backup encryption key must also have a separately controlled offline recovery
copy. It must never be inside the database, Spaces bucket, S3 backup, Git, a ticket
or a screenshot. Recovery ownership, rotation and revocation sequences are in the
[incident and secret-rotation runbook](production-incident-and-secret-rotation.md).

## OpenAI synthetic-proof controls

The selected production model is `gpt-5.6-terra`, using the Responses API with
strict structured output and `store=false`. Published pricing on the evidence date
is USD 2/million input tokens and USD 12/million output tokens for standard
processing. The owner separately confirmed the provider's minimum USD 5 prepaid
purchase plus USD 0.50 tax. The account now displays a USD 5 API credit balance and
auto-reload is off.

- The organisation and `Oryntela Production` project each enforce a USD 5 monthly
  hard limit with alerts at 20%, 80% and 100%. The provider warns that enforcement
  is not instantaneous and final usage can exceed the threshold by a small amount.
- Project model usage permits only `gpt-5.6-terra`; the saved project rate limit is
  10,000 tokens/minute and one request/minute.
- The application stop remains `AI_PROVIDER=mock` together with
  `API_FEATURE_OPENAI_PROVIDER_ENABLED=false`. Production must remain in that state
  even though the encrypted key remains bound. Any future synthetic smoke window
  requires a new, explicit owner approval.
- The deployment contract allows at most ten generation jobs and ten OpenAI requests
  per tenant per UTC day, one structured-output attempt, one durable worker attempt,
  a 30-second OpenAI timeout and 2,048 output tokens.
- The published Privacy Policy says OpenAI is not enabled in production. Therefore
  the key and controls are configuration evidence only: no customer-content call is
  authorised, and permanent provider enablement requires a separately approved legal
  and real-data release.

The earlier authority for one paid synthetic Sales Brain request was superseded on
24 October 2026. The current build-only direction authorises no OpenAI request, paid
provider call or production activation. No such proof ran under this work.

## DNS and continuation boundary

No DNS record changes are part of the owner-demo completion work. Preserve the
existing working production DNS/TLS and Zoho MX, SPF, DKIM, DMARC and verification
records exactly as they are; this branch does not re-verify or modify the control
plane. Leave `oryntela.com` unchanged and do not enable HSTS preload as part of this
work.

Additional production expansion is paused. Alembic migrations through the current
repository head `0071_assignment_tombstones` may reach production only through a
separately approved deployment. Do not resize
services, add a standby, create paid
test/restore resources, activate a provider, enable checkout/Credits, release real
customer data or begin WO-045 under this build instruction.

## Current owner-only boundaries

1. Approve a fresh capacity, high-availability, bounded-load and recovery assessment
   plus the resulting fixed cost before the first paid customer or real customer data.
2. Separately approve a reviewed production deployment of the eventual merged Git
   revision containing Alembic head `0071_assignment_tombstones`; the owner-demo
   branch itself must not deploy.
3. Separately approve the real-data release and named-customer/Clerk session evidence.
4. Separately approve any OpenAI, Prospect, Microsoft, Google, HubSpot or Salesforce
   production activation and its bounded synthetic smoke. No paid provider call is
   authorised here.
5. Separately approve live checkout, billing and Credits after their current gates;
   no real charge, refund, subscription or paid-Credit grant is authorised here.
6. Begin WO-045 only after those applicable launch gates pass and the owner explicitly
   authorises it.

Completing a login is not permission for Codex to purchase, deploy, create live
payment objects, create API keys or accept provider terms. Kevin must return with the
specific account/resource authority to cross each boundary.
