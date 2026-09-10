# WO-054 production deployment and launch operations

- **Baseline:** `d8d50b216bd64726243b06b5ea4f5bd56c59ab54`
- **Branch:** `codex/wo-054-production-launch-operations`
- **Date:** 10 September 2026 (Australia/Sydney)
- **Status:** repository implementation independently reviewed and remediated; owner decisions and external proof remain
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
- A 40-hex release identity is required by both production runtimes and is bound from
  App Platform's immutable `${_self.COMMIT_HASH}` value. Component CPU, memory and
  restart alerts plus termination drain/grace periods are explicit in the target spec.
- Runtime, migration and backup database connections use certificate- and
  hostname-verifying TLS. API/worker connection pools are bounded to seven
  connections per process; the initial two-process runtime caps at fourteen.
- Production exports stream to tenant-scoped private S3 objects and are downloaded
  only through authenticated, expiring API grants. The container filesystem is not a
  durable export target.
- A dedicated scheduled job streams encrypted PostgreSQL and Spaces payloads to
  independent AWS S3 daily, verifies remote size/SHA metadata, uploads its authenticated
  manifest last, then downloads and cryptographically verifies the committed bundle.
  Its source/destination credentials and encryption key are not shared with the
  application components.
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
| Filesystem portability | PASS | App images are ephemeral; binary/Create data and production exports use tenant-scoped S3-compatible storage; preflight proves write/read/delete |
| Web/API liveness and readiness | PASS | Generic endpoints exist and do not expose configuration values |
| Worker liveness and duplicate safety | PASS | Private freshness probe plus database leases, locks, idempotency and unknown-outcome handling; baseline count is one worker |
| Queue/provider/billing monitoring design | PASS | Content-free platform probes, component alerts, termination controls, daily tenant queue/preflight checks and external scheduled-backup freshness requirement |
| Production monitoring/alert destination | OWNER ACTION | Configure target alerts to Kevin's controlled operational route after hosting exists |
| PostgreSQL migration head/drift | PASS | `0061_manual_paid_credit_grant`; synthetic restored target also passed `alembic check` |
| Forced RLS in restored database | PASS | 173 tables reported `ENABLE` and `FORCE RLS`; temporary `NOSUPERUSER NOBYPASSRLS` role saw 28 in-tenant core rows and zero cross-tenant rows |
| Encrypted local synthetic backup/restore | PASS | Evidence below; database plus three private objects restored and verified |
| Automated production database backups | OWNER ACTION | Managed backup/PITR begins only after the paid HA cluster is created and its dashboard evidence is captured |
| Independent logical/object backup implementation | PASS | Dedicated daily job streams AES-256-GCM database/object payloads to independent S3, verifies remote metadata and publishes manifest last |
| Independent backup target, lifecycle and alert | OWNER ACTION | Create private Sydney S3 bucket; expire current/noncurrent versions/delete markers within 14 days; configure failure/freshness alert |
| Named-cloud restore drill | BLOCKED | Run after owner-funded target exists and before any customer data |
| RPO/RTO operating targets | PASS | Recommended internal V1 objectives: 24-hour RPO and four-hour RTO; not an SLA |
| Privacy Notice | OWNER ACTION | Factual draft exists; qualified review, owner approval and published final copy required |
| Service Terms | OWNER ACTION | Factual skeleton exists; qualified drafting and owner approval required |
| GST presentation | OWNER ACTION | Confirm registration/treatment and choose inclusive or exclusive language consistently; current public copy remains unchanged |
| Production hosting/API/worker | OWNER ACTION | Approve USD 120/month fixed paid/customer-data baseline before any resource is created |
| Production database/storage | OWNER ACTION | Included in target purchase; create separate migration/runtime roles and private bucket |
| Clerk production auth | OWNER ACTION | Approve Clerk Pro; create/configure separate production instance, domain, JWT template, invite policy, branding and smoke matrix |
| Production secrets | OWNER ACTION | Create and inject through control plane after target/account approvals |
| DNS/TLS | OWNER ACTION | Create target first, copy provider-issued targets, approve `@`/`www`/`api` records and validate TLS before HSTS |
| Primary domain | PASS | Canonical recommendation is `https://oryntela.com.au`; leave `oryntela.com` unchanged pending owner decision |
| Oryntela system/support email | PASS | Existing Zoho sender/routes and SPF/DKIM/DMARC proof remain valid; Clerk will own identity mail when configured |
| Public marketing routes/SEO assets | PASS | Routes, canonical, sitemap and OpenGraph exist; legal routes intentionally remain non-indexed GAP pages |
| Public production publication | BLOCKED | Legal, GST, hosting, auth, backup, monitoring, secrets, DNS/TLS and target smoke have not passed |
| Production customer onboarding | BLOCKED | WO-045 is not started and no named-target/partner gate is complete |
| Customer-data migration | NOT REQUIRED | No customer data exists |
| Public launch announcement | NOT REQUIRED | Explicitly outside WO-054 |
| Paid subscription path | BLOCKED | Current Stripe adapter is test-only; operator commercial-state commands do not record cleared funds, paid-through/renewal/expiry or invoice evidence. Paid launch needs live Stripe engineering or a separately authorised manual-subscription ledger |
| Live Prospect provider/Credits | NOT REQUIRED | A Core/Native CRM launch can omit Prospect; Growth/Complete provider-backed research must not be sold as active until licensed/economically approved |
| Microsoft/Google/HubSpot/Salesforce | NOT REQUIRED | Optional connector modes can launch disabled and must continue to display activation-pending truth |

## Synthetic restore evidence

The original comprehensive drill ran on local PostgreSQL 16.15 with deliberately
synthetic data and no network/provider calls. An ephemeral 32-byte encryption key was
held only in the process environment.

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

The independent review then upgraded the backup format to v2 so the manifest itself,
including source fingerprint, counts and release SHA, is authenticated with HMAC-SHA256.
A fresh current-format smoke migrated an empty source to `0061`, backed up one
synthetic private object, verified the bundle,
restored it into a distinct PostgreSQL database/object root, byte-compared the object
and confirmed 173 forced-RLS tables. Temporary databases, objects and the ephemeral
key were removed.

Result: **PASS locally for current format**. This is not a claim that production
backups exist; the named DigitalOcean/AWS drill remains blocked until the owner
creates the targets.

## Provider readiness and launch classification

| Capability | Classification | Current truth |
| --- | --- | --- |
| Native Oryntela CRM/Core | MUST HAVE FOR V1 LAUNCH | Repository-ready; target/auth/legal/WO-045 gates remain |
| Microsoft 365 | CAN LAUNCH DISABLED | Built, production-inactive; use exact OAuth callback after owner app registration and synthetic mailbox proof |
| Google Workspace | CAN LAUNCH DISABLED | Built, production-inactive; restricted Gmail read scope makes verification/CASA a paid external boundary |
| HubSpot | CAN LAUNCH DISABLED | Built, production-inactive; public OAuth app/test account not created |
| Salesforce | CAN LAUNCH DISABLED | Built, production-inactive; use an External Client App and synthetic Developer Edition org |
| Prospect | CAN LAUNCH DISABLED | No provider has approved SaaS rights/economics; Apollo requires a custom contract for this usage |
| Live Stripe | MUST HAVE FOR PAID LAUNCH UNLESS A SAFE MANUAL LEDGER IS BUILT; CAN LAUNCH DISABLED FOR SYNTHETIC/FREE LEVELS | Current adapter/config is test-only; operator trial/commercial-state commands are not payment evidence |
| OpenAI intelligence | MUST HAVE FOR ADVERTISED PAID SALES BRAIN; CAN LAUNCH DISABLED FOR SYNTHETIC/EXPLICIT NO-AI PROFILE | Implemented provider remains approval-, data-flow- and usage-cost-gated; deterministic Native CRM works without it but is a materially narrower offer |
| Dedicated error reporting | OPTIONAL POST-LAUNCH | Platform logs/probes are the zero-incremental-cost baseline; reassess from measured need |
| Database HA | MUST HAVE FOR PAID/CUSTOMER-DATA LAUNCH | DigitalOcean recommends single-node clusters for preliminary development/testing; use the USD 60 primary-plus-standby baseline |

A synthetic or no-external-AI profile can launch without OpenAI, but it cannot be sold
as the advertised Sales Brain proposition. A first paid customer therefore requires
the approved bounded OpenAI profile unless the offering and agreement explicitly sell
only the deterministic Native CRM surface. Growth/Complete trials may be provisioned
only with exact feature-availability disclosure; unavailable providers never fall
back to mocks.

## Consolidated owner action package

Prices are current as of 10 September 2026 and must be rechecked at purchase. `Quote
required` means no public exact price exists; it is not authority to accept a quote.

### BATCH A — LEGAL / COMMERCIAL DECISIONS

**ACTION:** Approve final Privacy Notice, Service Terms, contracting/publishing facts and subprocessor schedule after qualified review. **WHY:** the build and all public/customer-data levels fail closed without versioned, effective, fingerprinted legal releases. **COST:** UNKNOWN/quote required. **CARD REQUIRED:** UNKNOWN. **AUTO-RENEW:** UNKNOWN. **OWNER CREDENTIAL/ROLE:** contracting owner and qualified Australian legal/privacy adviser. **UNLOCKS:** legal release records and public provider URLs. **CAN LAUNCH WITHOUT IT:** NO for every public or customer-data level. **RECOMMENDATION:** resolve the factual gaps; do not approve the draft as legal advice.

**ACTION:** Confirm GST registration/treatment and choose the paid-customer payment implementation: reviewed live Stripe or a separately authorised durable manual-subscription ledger. **WHY:** ABN does not establish GST status, and current commercial-state commands do not evidence cleared payment, paid-through dates, renewal/expiry or invoices. **COST:** advice/engineering UNKNOWN; Stripe has AUD 0 fixed standard fee plus researched transaction/Billing fees. **CARD REQUIRED:** NO for the decision; Stripe requires business/bank verification to activate. **AUTO-RENEW:** usage-based if Stripe; UNKNOWN for another path. **OWNER CREDENTIAL/ROLE:** entity/tax records, accountant/legal authority and product owner. **UNLOCKS:** truthful price/tax language and a reviewable paid-sale path. **CAN LAUNCH WITHOUT IT:** YES for private synthetic/free design-partner work; NO for paid launch. **RECOMMENDATION:** prefer reviewed Stripe rather than an informal manual workaround.

**ACTION:** Approve the minimum fixed production budget and first-customer provider profile. **WHY:** paid/customer-data production needs HA PostgreSQL and Clerk Pro; the advertised Sales Brain profile needs an approved AI provider. **COST:** USD 120/month fixed month-to-month before tax/FX, plus S3/job usage and any OpenAI spend; proposed OpenAI stop amount AUD 50/month. **CARD REQUIRED:** YES. **AUTO-RENEW:** YES for DigitalOcean/Clerk; usage-based for AWS/OpenAI. **OWNER CREDENTIAL/ROLE:** owner/billing authority plus privacy approval for OpenAI. **UNLOCKS:** Batch B and a precise no-AI versus bounded-AI offer. **CAN LAUNCH WITHOUT IT:** NO for external production activation; OpenAI alone can be omitted only from an explicitly reduced synthetic/no-AI offer. **RECOMMENDATION:** approve an AUD 220/month platform ceiling before tax/FX with the OpenAI stop amount separately stated; keep Prospect disabled.

### BATCH B — CORE INFRASTRUCTURE PURCHASE

**ACTION:** Authorise the Sydney DigitalOcean target and Clerk Pro subscription within the approved cap. **WHY:** web, API, worker, scheduled job, HA database, active storage and production identity do not exist. **COST:** DigitalOcean USD 95/month fixed plus variable job/overage; Clerk Pro USD 25 month-to-month or USD 20/month billed annually. **CARD REQUIRED:** YES. **AUTO-RENEW:** YES. **OWNER CREDENTIAL/ROLE:** DigitalOcean team billing admin and Clerk owner, both with MFA. **UNLOCKS:** core production configuration. **CAN LAUNCH WITHOUT IT:** NO. **RECOMMENDATION:** use month-to-month Clerk initially unless the owner knowingly accepts the annual commitment.

**ACTION:** Authorise a private AWS S3 Standard backup bucket in `ap-southeast-2`. **WHY:** Spaces is active storage, not its own independent backup. **COST:** USD 0 fixed minimum; USD 0.025/GB-month plus requests/transfer. **CARD REQUIRED:** YES. **AUTO-RENEW:** usage billing continues while data/resources exist. **OWNER CREDENTIAL/ROLE:** AWS billing/IAM owner with MFA. **UNLOCKS:** scheduled encrypted off-provider backup and named-cloud restore proof. **CAN LAUNCH WITHOUT IT:** YES only for synthetic/no-customer-data level; NO for customer data. **RECOMMENDATION:** approve S3 Standard, versioning and a 14-day current/noncurrent/delete-marker lifecycle; do not use a minimum-duration archive class.

### BATCH C — CORE PRODUCTION CONFIGURATION

**ACTION:** Supply controlled access and accountable production operators for secrets, DNS, alerts and recovery-key escrow. **WHY:** Codex can configure and prove the target after authorisation but cannot invent credentials, DNS authority, alert recipients or a second-controlled key custodian. **COST:** no additional known fixed fee beyond Batch B; external backup-freshness monitoring cost is UNKNOWN until selected. **CARD REQUIRED:** depends on selected freshness control. **AUTO-RENEW:** UNKNOWN. **OWNER CREDENTIAL/ROLE:** project/DB/Clerk/DNS administrators; named primary and backup on-call; independent recovery-key custodian. **UNLOCKS:** least-privilege roles, verified TLS, migration, storage/export, production Clerk, monitoring, scheduled backup, restore drill and DNS/TLS smoke. **CAN LAUNCH WITHOUT IT:** NO. **RECOMMENDATION:** grant time-bounded least privilege and require content-free alert tests before data entry.

### BATCH D — OPTIONAL PROVIDERS

**ACTION:** Approve only the optional provider demanded by the signed first-partner profile: Microsoft, Google, HubSpot, Salesforce or a future licensed Prospect provider. **WHY:** every connector adds credentials, customer authority, data flow and support burden; Google restricted Gmail read likely adds an annual external assessment. **COST:** Microsoft/HubSpot/Salesforce Oryntela test baseline USD 0 with customer entitlements; Google assessor and Prospect licence UNKNOWN. **CARD REQUIRED:** provider-dependent. **AUTO-RENEW:** provider-dependent. **OWNER CREDENTIAL/ROLE:** provider/app/domain admin, partner authority and privacy/legal approval. **UNLOCKS:** only that connector after synthetic proof. **CAN LAUNCH WITHOUT IT:** YES. **RECOMMENDATION:** defer all; keep Google and Prospect disabled until demand justifies their external cost/compliance work.

### BATCH E — WO-045 FINAL ACCEPTANCE

**ACTION:** After WO-054C/D evidence is complete, separately authorise and accept WO-045 for the named first partner. **WHY:** production activation does not authorise customer onboarding, real data, a payment or a public announcement. **COST:** UNKNOWN; depends on the chosen commercial/provider profile. **CARD REQUIRED:** depends on the approved paid/provider path. **AUTO-RENEW:** depends on the approved paid/provider path. **OWNER CREDENTIAL/ROLE:** product/contracting owner and named partner authority. **UNLOCKS:** the separately reviewed first-customer launch. **CAN LAUNCH WITHOUT IT:** NO for customer onboarding. **RECOMMENDATION:** do not begin WO-045 until WO-054D recovery/smoke evidence passes.

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
- `pnpm test`: 78 files / 355 tests passed. `pnpm test:e2e`: 90 passed.
- `pnpm api:test`: 1,290 passed, 11 skipped, with 299 existing deprecation/schema
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
- `python3 scripts/ci_audit.py`: PASS for 1,733 tracked/new files. `git diff
  --check`, changed-diff secret/personal-path scan and deployment YAML
  parse/invariants: PASS.
- The full Create test file passed while `/usr/bin/time -l` measured approximately
  300 MiB maximum resident memory on the review host. The target therefore uses
  conservative 20 MB compressed / 100 MB expanded / 5 MB media-member PPTX limits;
  this is directional sizing evidence, not a production load test.
- Local Docker image execution: not run because this host has no Docker executable.
  The existing GitHub Web/API jobs now build both Dockerfiles without pushing; the
  draft PR owns that evidence.

GitHub CI results are recorded on the draft PR after the release commit is pushed.

WO-054A repository preparation is implemented and independently reviewed to owner
boundaries. WO-054B owner decisions, WO-054C external activation and WO-054D named
smoke/recovery proof remain. WO-045 is not started. No public deployment, customer
onboarding or launch announcement is authorised by this record.
