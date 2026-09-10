# WO-054 production deployment and launch operations

- **Baseline:** `d8d50b216bd64726243b06b5ea4f5bd56c59ab54`
- **Branch:** `codex/wo-054-production-launch-operations`
- **Date:** 10 September 2026 (Australia/Sydney)
- **Status:** implemented to the AUD 0 owner boundary; engineering review and owner actions remain
- **Customer data:** none
- **Feature freeze:** preserved
- **Migration:** none; current head verified as `0061_manual_paid_credit_grant`

This is the canonical WO-054 launch checklist. It supersedes older target-cost and
launch-head assumptions for production-operations decisions, without converting any
recommendation into an owner approval. The implementation does not create hosting,
provider accounts, OAuth apps, DNS records, production secrets, charges or customer
data.

## Delivered repository controls

- A minimal Sydney DigitalOcean target specification for separate standalone Next.js,
  FastAPI and worker components, one pre-deploy migration job, managed PostgreSQL and
  private S3-compatible storage. It is inert and has deploy-on-push disabled.
- Multi-stage, non-root web and API images. Application persistence never uses the
  container filesystem.
- Four explicit environments: development, test, staging and production. Staging is
  synthetic-only/noindex; production web builds fail closed on canonical origins,
  HTTPS, Clerk production keys, mock auth and unapproved Privacy/Terms content.
- Generic web readiness and private worker liveness. The API's existing readiness
  remains the database, migration, auth, provider and configuration traffic gate.
- HSTS is now an explicit post-TLS switch. The app does not set `includeSubDomains` or
  `preload`; the existing CSP, frame, MIME, referrer, permissions and no-store controls
  remain in place.
- A classified production environment handoff, safe secret-generation process,
  per-secret rotation procedures, launch/rollback/recovery/monitoring/support runbook,
  incident procedure, factual legal drafting input, provider/cost research and an
  owner-only approval package.
- Public plan truth now says provider-backed research, external sending and CRM
  connections remain unavailable until activated. Plan amounts and the no-card trial
  are unchanged.

## Canonical launch checklist

Only `PASS`, `BLOCKED`, `OWNER ACTION` and `NOT REQUIRED` are statuses in this table.
A repository `PASS` is not proof that a cloud environment or external provider exists.

| Launch item | Status | Evidence / condition |
| --- | --- | --- |
| Clean exact baseline and topic branch | PASS | Baseline SHA and branch recorded above |
| Current architecture audit | PASS | Next.js web, FastAPI API, PostgreSQL and one combined durable worker; no laptop cron, Redis or broker required |
| Production topology decision | PASS | [ADR 0077](../08-decisions/0077-australian-managed-modular-monolith-production-topology.md) and inert DigitalOcean spec |
| Development/test/staging/production separation | PASS | Typed web/API gates, production handoff template and staging noindex tests |
| Production required-config fail-closed | PASS | Web build/runtime and API `Settings` validation reject unsafe/missing production values |
| Test/mock provider isolation | PASS | Production rejects mock auth/connectors, live billing, Credits and unapproved content/provider combinations |
| Canonical and callback URL validation | PASS | Exact `.com.au` origin/callback inventory; provider adapters require bounded HTTPS production redirects |
| Secret absence and storage strategy | PASS | Placeholders only; no production secret created or committed; rotation runbook exists |
| Credential-envelope production key | OWNER ACTION | Fresh 32-byte key must be generated directly into the approved secret manager; online master-key re-encryption still needs named-target proof before connector activation |
| Filesystem portability | PASS | App images are ephemeral; binary/Create data uses S3-compatible storage; local export remains disabled in the target |
| Web/API liveness and readiness | PASS | Generic endpoints exist and do not expose configuration values |
| Worker liveness and duplicate safety | PASS | Private freshness probe plus database leases, locks, idempotency and unknown-outcome handling; baseline count is one worker |
| Queue/provider/billing monitoring design | PASS | Content-free platform probes plus daily tenant queue/preflight checks in the launch runbook |
| Production monitoring/alert destination | OWNER ACTION | Configure target alerts to Kevin's controlled operational route after hosting exists |
| PostgreSQL migration head/drift | PASS | `0061_manual_paid_credit_grant`; synthetic restored target also passed `alembic check` |
| Forced RLS in restored database | PASS | 173 tables reported `ENABLE` and `FORCE RLS`; temporary `NOSUPERUSER NOBYPASSRLS` role saw 28 in-tenant core rows and zero cross-tenant rows |
| Encrypted local synthetic backup/restore | PASS | Evidence below; database plus three private objects restored and verified |
| Automated production database backups | OWNER ACTION | Included seven-day managed database window starts only after the paid cluster is created |
| Independent object backup and approved retention | BLOCKED | Spaces has no built-in backup; select/fund a separate destination and reconcile the seven-day/14-day retention decision |
| Named-cloud restore drill | BLOCKED | Run after owner-funded target exists and before any customer data |
| RPO/RTO operating targets | PASS | Recommended internal V1 objectives: 24-hour RPO and four-hour RTO; not an SLA |
| Privacy Notice | OWNER ACTION | Factual draft exists; qualified review, owner approval and published final copy required |
| Service Terms | OWNER ACTION | Factual skeleton exists; qualified drafting and owner approval required |
| GST presentation | OWNER ACTION | Confirm registration/treatment and choose inclusive or exclusive language consistently; current public copy remains unchanged |
| Production hosting/API/worker | OWNER ACTION | Approve minimum USD 50/month infrastructure before any resource is created |
| Production database/storage | OWNER ACTION | Included in target purchase; create separate migration/runtime roles and private bucket |
| Clerk production auth | OWNER ACTION | Create/configure separate production instance, domain, JWT template, invite policy, branding and smoke matrix; decide Hobby versus Pro |
| Production secrets | OWNER ACTION | Create and inject through control plane after target/account approvals |
| DNS/TLS | OWNER ACTION | Create target first, copy provider-issued targets, approve `@`/`www`/`api` records and validate TLS before HSTS |
| Primary domain | PASS | Canonical recommendation is `https://oryntela.com.au`; leave `oryntela.com` unchanged pending owner decision |
| Oryntela system/support email | PASS | Existing Zoho sender/routes and SPF/DKIM/DMARC proof remain valid; Clerk will own identity mail when configured |
| Public marketing routes/SEO assets | PASS | Routes, canonical, sitemap and OpenGraph exist; legal routes intentionally remain non-indexed GAP pages |
| Public production publication | BLOCKED | Legal, GST, hosting, auth, backup, monitoring, secrets, DNS/TLS and target smoke have not passed |
| Production customer onboarding | BLOCKED | WO-045 is not started and no named-target/partner gate is complete |
| Customer-data migration | NOT REQUIRED | No customer data exists |
| Public launch announcement | NOT REQUIRED | Explicitly outside WO-054 |
| Live Stripe | NOT REQUIRED | Core can launch with manual/admin-assisted commercial operations; current adapter is test-only and live production use remains prohibited |
| Live Prospect provider/Credits | NOT REQUIRED | A Core/Native CRM launch can omit Prospect; Growth/Complete provider-backed research must not be sold as active until licensed/economically approved |
| Microsoft/Google/HubSpot/Salesforce | NOT REQUIRED | Optional connector modes can launch disabled and must continue to display activation-pending truth |

## Synthetic restore evidence

The final drill ran on local PostgreSQL 16.15 with deliberately synthetic data and no
network/provider calls. An ephemeral 32-byte encryption key was held only in the
process environment.

1. Created a disposable source database and migrated from empty to head.
2. Provisioned one synthetic organisation/admin through the supported operator path,
   seeded the deterministic complete demo and added one explicit synthetic core Task.
3. Created and authenticated an AES-256-GCM backup of PostgreSQL plus local private
   object storage. Backup ID: `20260910T081954Z-6675b7df4be1`; object count: 3.
4. Destroyed the source database, created a separate empty target and restored the
   encrypted database/object archives.
5. Matched source/target counts: 1 organisation, 2 companies, 3 contacts, 21
   opportunities and 1 task. The target reported head
   `0061_manual_paid_credit_grant`; migration drift check passed.
6. Verified 173 forced-RLS tables. A temporary non-login role with
   `rolsuper=false` and `rolbypassrls=false` saw all 28 selected in-tenant rows and
   zero rows for another tenant.
7. Removed both databases, the temporary role, working files and ephemeral key. A
   post-cleanup inventory found no remaining `revenueos_wo054_*` databases or
   `wo054_restore_runtime_*` roles.

Result: **PASS locally**. This is not a claim that production backups exist; the
named DigitalOcean/object-backup drill remains blocked until the owner creates the
target.

## Provider readiness and launch classification

| Capability | Classification | Current truth |
| --- | --- | --- |
| Native Oryntela CRM/Core | MUST HAVE FOR V1 LAUNCH | Repository-ready; target/auth/legal/WO-045 gates remain |
| Microsoft 365 | CAN LAUNCH DISABLED | Built, production-inactive; use exact OAuth callback after owner app registration and synthetic mailbox proof |
| Google Workspace | CAN LAUNCH DISABLED | Built, production-inactive; restricted Gmail read scope makes verification/CASA a paid external boundary |
| HubSpot | CAN LAUNCH DISABLED | Built, production-inactive; public OAuth app/test account not created |
| Salesforce | CAN LAUNCH DISABLED | Built, production-inactive; use an External Client App and synthetic Developer Edition org |
| Prospect | CAN LAUNCH DISABLED | No provider has approved SaaS rights/economics; Apollo requires a custom contract for this usage |
| Live Stripe | CAN LAUNCH DISABLED | Current adapter/config is test-only; manual trial/commercial operations remain available with no checkout |
| OpenAI intelligence | CAN LAUNCH DISABLED | Implemented external provider but separately approval-, data-flow- and usage-cost-gated; Core can run without external AI |
| Dedicated error reporting | OPTIONAL POST-LAUNCH | Platform logs/probes are the zero-incremental-cost baseline; reassess from measured need |
| Database HA | OPTIONAL POST-LAUNCH | Single node is the minimum launch baseline; HA raises the planning baseline to USD 95/month |

The launch must be positioned as Core/Native CRM until optional capabilities are
actually activated. Growth/Complete trials may be provisioned only with an explicit
feature-availability disclosure; provider-backed research, external delivery and CRM
connections must remain unavailable rather than falling back to mocks.

## Consolidated owner action package

Prices are current as of 10 September 2026 and must be rechecked at purchase. `Quote
required` means no public exact price exists; it is not authority to accept a quote.

| Action | Why | Provider | Exact known cost | Card required | Auto-renew | Credential/role required | What it unlocks | Can launch without it? | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Approve/create Sydney production target | Required runtime | DigitalOcean | USD 50/month baseline plus tax/FX | Yes | Recurring service | Owner/team billing admin with MFA | Web, API, worker, PostgreSQL and active object storage | No | Approve a monthly AUD cap at or above AUD 70 plus tax/FX; do not use a hobby free tier |
| Approve independent object-backup destination/retention and upload work | Spaces is not backed up | AWS S3 Standard Sydney candidate | USD 0 fixed; USD 0.025/GB-month plus requests/transfer | Yes | Ongoing usage billing | AWS billing/IAM admin plus engineering review | Automated daily encrypted bundle copy and customer-data recovery gate | No for customer data | Use a separate private `ap-southeast-2` account/bucket, implement scheduled upload without logging keys and run a named restore before onboarding |
| Create/configure production Clerk | Required identity | Clerk | Hobby USD 0; Pro USD 25 monthly or USD 20/month billed annually | No for Hobby; payment for Pro | Pro recurring | Clerk owner/admin with MFA | Production sign-in/invite/session/org proof and Oryntela hosted branding | No | Prefer Pro for MFA/logs if separately approved; otherwise explicitly accept Hobby limits for supervised V1 |
| Approve Privacy/Terms and publishing facts | Public legal gate | Qualified adviser + owner | Quote required | Depends | No assumption | Owner/legal authority | Production web build and public provider legal URLs | No | Obtain qualified review; do not publish the draft as approved copy |
| Confirm GST treatment | Prices/invoices/Stripe must agree | Accountant/legal + owner | Quote required if advice is needed | Depends | No assumption | Entity tax records and owner authority | Inclusive/exclusive wording and tax configuration | No | Confirm registration and exact display before any public sale |
| Create production secrets and least-privilege roles | Required fail-closed config | DigitalOcean/Clerk/database | No incremental provider fee stated | Covered by hosting | No separate | Secret-manager admin, DB admin | Readiness, Clerk verification, RLS runtime, backup and signing | No | Generate directly into secret manager; never reuse dev/test values |
| Approve DNS/TLS cutover and `.com` disposition | Public routing | VentraIP + DigitalOcean | AUD 0 incremental; existing renewal unchanged | No new card | Existing domain renewal only | DNS owner MFA | Canonical `@`, `www`, `api`, TLS and later HSTS | No | Use provider-issued targets; redirect `www`; leave `.com` unchanged until decided |
| Configure production alerts | Owner-operated on-call | DigitalOcean | USD 0 incremental in baseline | Covered by hosting | No separate | Project admin and controlled operations inbox | Availability/restart/database/deploy alert delivery | No | Route to Kevin's controlled operational address; keep payloads content-free |
| Complete WO-045 | Required before customer onboarding | Internal engineering/owner | No external price determined | No | No | Product/engineering owner | Named partner onboarding authority | No for customer onboarding | Do not start under WO-054 |
| Approve OpenAI real-data profile and cap, if wanted | Enables Sales Brain external intelligence | OpenAI | Variable; `gpt-5.6-terra` USD 2/M input and USD 12/M output tokens | Billing method required | Usage-based | OpenAI org/project owner; privacy approval | Approved bounded customer-content AI | Yes | Keep off for Core launch; if approved, use separate project/key and AUD 50 alert-and-stop amount |
| Authorise a live billing implementation then create Stripe live catalogue | Current adapter is test-only | Stripe | AUD 0 fixed; 1.7% + AUD 0.30 domestic card, 3.5% + AUD 0.30 international, +2% FX; Billing 0.7% volume | Bank/business verification, not a purchase card | Usage-based | Stripe owner; business/bank/legal data | Live checkout, portal, signed webhook and automated reconciliation | Yes | Launch manual first; commission adapter review before any live key/product/charge |
| Obtain Prospect SaaS licence and landed-cost quote | Shared provider model needs commercial rights | Apollo | Custom contract/quote required | Likely | Contract-dependent | Contracting/billing owner | Existing Apollo adapter plus priceable Credit actions | Yes | Do not activate Apollo; seek written redistribution rights or assess PDL in a later adapter work order |
| Approve proposed Credit policy | Required before any variable-cost action | Oryntela owner | Proposed: AUD 0.10 face value; packs 500/AUD 50, 1,250/AUD 120, 3,000/AUD 270; 70% margin floor | No activation yet | No | Owner plus GST/provider-contract evidence | Versioned action prices and prepaid execution | Yes | Approve only with exact landed provider costs/GST/failed-action terms; current production values remain none |
| Register Microsoft multitenant app and synthetic smoke | Optional mailbox/calendar | Microsoft Entra/Graph | USD 0 Oryntela baseline; customer M365 licence | No Oryntela mailbox authorised | No Oryntela subscription | Entra Cloud Application Admin/owner MFA; synthetic mailbox admin | Microsoft OAuth/read/send/calendar activation | Yes | Defer until legal URLs and target exist; use exact scopes and publisher domain |
| Create Google project/client, verify consent and obtain CASA quote | Optional Gmail/calendar | Google + approved assessor | Google API baseline USD 0; CASA quote unavailable/paid annually if required | Assessor payment required | Annual assessment likely | Cloud project owner/domain admin/assessor; synthetic Workspace account | Google OAuth with restricted Gmail read | Yes | Keep disabled unless customer demand justifies verification and annual assessment |
| Create HubSpot public OAuth app/test account and smoke | Optional CRM | HubSpot | USD 0 Oryntela developer baseline; customer licence/limits apply | No paid Oryntela licence required for test | No | Developer account/Super Admin | HubSpot OAuth/read/write/reconciliation | Yes | Defer; use only synthetic test account |
| Create Salesforce Developer org and External Client App smoke | Optional CRM | Salesforce | USD 0 developer baseline; customer API entitlement applies | No paid Oryntela licence required for dev test | No | Salesforce org admin/owner | Salesforce OAuth/read/write/reconciliation | Yes | Defer; do not create a legacy Connected App |

See the dated [cost and Credit economics](../04-commercial/wo-054-production-cost-and-credit-economics.md),
[legal drafting input](../00-company/wo-054-draft-privacy-and-terms.md),
[production launch runbook](../03-engineering/production-launch-runbook.md) and
[incident/rotation runbook](../03-engineering/production-incident-and-secret-rotation.md)
for the supporting detail.

## External actions and spend

- Read-only official provider documentation and pricing research: performed.
- Provider account/app/project created: none.
- Deployment/database/bucket created: none.
- DNS/domain/TLS change: none.
- Provider API/OAuth/test connection: none.
- Customer data, email, CRM mutation or payment: none.
- Spend: AUD 0; USD 0; free credits consumed 0; card used no; subscription started
  no; auto-renew enabled no.

## Validation

The synthetic restore proof above passed. The final local gate ran on 10 September
2026:

- `pnpm format`, `pnpm lint`, `pnpm typecheck`, `pnpm build:web`, `pnpm api:format`,
  `pnpm api:lint`, `pnpm api:typecheck` and `pnpm build:api`: PASS.
- `pnpm test`: 78 files / 353 tests passed. `pnpm test:e2e`: 90 passed.
- `pnpm api:test`: 1,286 passed, 11 skipped, with 299 existing deprecation/schema
  reflection warnings and no failure.
- `pnpm api:migrate` and `pnpm api:migration:check`: PASS from an empty disposable
  PostgreSQL database through head `0061`; the database was removed afterwards.
- The pre-existing default local `revenueos` database claimed head `0060` before
  this gate but lacked elements owned by historical migrations `0054`, `0058` and
  `0060`. After applying `0061`, its drift check therefore failed. That local data
  was not destroyed, stamped or manually repaired. The clean-database pass proves
  the committed migration chain; the local environment requires a separately
  authorised rebuild or recovery if it is to be reused.
- `pnpm audit`: no known JavaScript vulnerabilities. `pip-audit 2.10.1` over the
  locked production-only Python export: no known vulnerabilities. The broad
  development-environment audit separately identified advisories in its old `pip`
  and dev-only `pytest`; neither is installed by the API runtime image.
- `python3 scripts/ci_audit.py`: PASS for 1,732 tracked/new files. `git diff
  --check`, changed-diff secret/personal-path scan and deployment YAML
  parse/invariants: PASS.
- Local Docker image execution: not run because this host has no Docker executable.
  The existing GitHub Web/API jobs now build both Dockerfiles without pushing; the
  draft PR owns that evidence.

GitHub CI results are recorded on the draft PR after the release commit is pushed.

WO-054 is implemented to owner boundaries and awaits engineering review plus the
explicit owner actions above. WO-045 is not started. No merge, public deployment,
customer onboarding or launch announcement is authorised by this record.
