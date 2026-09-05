# Private-beta target-environment options

- **Assessment date:** 2 September 2026 (Australia/Sydney)
- **Status:** **RECOMMENDATION ONLY — NO ACCOUNT, PURCHASE OR DEPLOYMENT AUTHORISED**
- **Scale:** first 1–5 supervised design partners; no high-availability or enterprise-residency claim

RevenueOS needs three continuously running application processes—Next.js web,
FastAPI API and the durable worker—plus PostgreSQL, private object storage, HTTPS,
secrets, Clerk, backup/restore and content-safe monitoring. The simplest appropriate
target is one small Sydney app host with managed data services. It is deliberately
not designed for 100,000 users.

## Primary: AWS-SYD-PRIVATE-BETA-V1

Use AWS Asia Pacific (Sydney), `ap-southeast-2`, for all RevenueOS-controlled
customer-data infrastructure:

| Layer | Target | Required configuration |
| --- | --- | --- |
| Public edge and HTTPS | Caddy or equivalent reverse proxy on one 4 GB Amazon Lightsail Linux instance | Exact web/API hosts; automatic certificate renewal; only 80/443 public; redirect HTTP; safe access logs |
| Web, API and worker | Three containers or system services from one immutable release on that instance | Separate process supervision/restart policy and health checks; worker is long-running, not a request task; web never receives database/admin credentials |
| PostgreSQL | Lightsail managed PostgreSQL 16, 2 GB encrypted Standard plan, same Sydney region, public mode off | TLS; separate migration/admin and non-`BYPASSRLS` runtime roles; migration head `0054_credits_variable_cost`; automated seven-day point-in-time recovery plus portable backups |
| Private files | Two private Amazon S3 buckets in Sydney: active objects and encrypted backup artefacts | Block public access; server-only least-privilege credentials; encryption at rest; versioning/checksum/lifecycle; tenant-scoped keys; no browser database/storage privilege |
| Secrets | AWS Systems Manager Parameter Store or Secrets Manager, chosen within the owner cap | Server-only values; separate web/API/worker scope; documented rotation and break-glass owner; never in images, Git or logs |
| Backup | Lightsail automatic database backup plus daily RevenueOS encrypted portable database/object backup to the separate backup bucket | 14-day lifecycle; AES-256-GCM application backup key kept outside the backup; quarterly and pre-partner isolated restore drill |
| Monitoring | Lightsail instance/database metrics and alarms, CloudWatch logs/metric alarms, HTTPS health check and email/SMS notification route | Health, readiness, worker heartbeat/queue age, database/storage, backup age, HTTP 5xx and resource pressure; metadata only; 14-day log lifecycle |
| Identity | Separate Clerk production instance | Production keys, exact domain/origins, invitation-only organisations, public organisation creation off, JIT off, active-organisation claims, revocation and two-tenant synthetic proof |

AWS documents Sydney as a supported regional destination and Lightsail supports
managed PostgreSQL, same-region private connectivity and seven-day automatic
point-in-time recovery. Current official pricing and backup behaviour are linked in
the [cost model](target-environment-cost-model.md). The exact PostgreSQL blueprint
must still be checked before purchase; AWS currently documents PostgreSQL 16 as
available.

### Why this is primary

- one infrastructure supplier holds the application, database, files, backups,
  metrics and logs in Sydney;
- managed PostgreSQL removes database operating-system and patch management;
- S3 gives private durable storage and an explicit 14-day lifecycle that matches the
  repository tools;
- a single host is easy to understand, stop and recreate for a supervised cohort;
- the fixed base is predictable and the complete target proof can run without
  redesigning the application.

The trade-off is deliberate: the application host is a single point of failure and
its operating system/container runtime needs patching. It is suitable only while the
beta is supervised, internal RTO is one business day and no availability SLA is
offered. Database High Availability can later replace Standard for an extra USD 30
per month, but is not recommended before observed need.

### Data location and cross-border boundary

When configured exactly as above, the primary application processing, PostgreSQL
data, S3 active files, encrypted backups and customer-content application logs are
stored in Sydney. This is an **Australia-first infrastructure configuration**, not a
claim that every service datum stays in Australia:

- AWS account, billing, DNS/control-plane, support and security metadata may be
  processed outside Australia under AWS terms;
- Clerk handles identity/contact/session data under its own locations and
  subprocessors; its DPA permits processing wherever Clerk or subprocessors operate;
- OpenAI is a separate conditional cross-border flow. Its Australian endpoint can
  provide regional storage only for eligible approved projects and does not provide
  Australian inference processing;
- an owner-selected support mailbox may process correspondence in its provider's
  locations.

Do not publish “Australian data residency” without legal review of every enabled
service and the exact contracts/settings.

### Safe shutdown

Pause new logins and worker claims, take and verify a final encrypted backup, export
or delete each tenant under authority, revoke Clerk/provider access, preserve only
the approved 14-day encrypted backup window, then stop the app host. Delete the
database/buckets/accounts only under a separate exact-target approval. Lightsail
automatic backups disappear with a deleted database, so a verified portable backup
and any approved manual snapshot must precede deletion.

## One alternative: FLY-SUPABASE-SYD-V1

Use three Fly.io Machines in `syd`—web, API and independently supervised worker—and
one Supabase Pro project explicitly pinned to the specific Sydney
`ap-southeast-2` region for PostgreSQL and private S3-compatible storage. Store a
second encrypted portable backup in a private AWS S3 Sydney bucket.

| Layer | Target | Main difference from primary |
| --- | --- | --- |
| Web/API/worker | Separate Fly.io Machines in Sydney | Less host patching and better process separation; Fly becomes another subprocessor and spend varies by machine/runtime/egress |
| PostgreSQL/files | Supabase Pro Micro project in exact Sydney region | Managed PostgreSQL and storage for USD 25/month; Pro automatic backup and log retention are only seven days, so the repository's 14-day portable backup remains necessary |
| Backup | Private AWS S3 Sydney bucket | Adds AWS as a third infrastructure supplier but separates the portable backup failure domain |
| Monitoring | Fly metrics/logs plus external or self-hosted alert routing; Supabase logs | More monitoring integration work; paid log drains are disproportionate for the first cohort |

Fly officially lists Sydney for Machines and Managed Postgres, while Supabase lists
Sydney as a specific region and says the selected region determines primary project
data location. This option reduces operating-system work and isolates processes, but
it creates more vendor and incident boundaries. Fly/Supabase control-plane,
support/telemetry and identity/provider processing still prevent a blanket Australian
residency claim.

## Plain-English choice

Choose **AWS-SYD-PRIVATE-BETA-V1** if Kevin wants the fewest infrastructure suppliers,
one Sydney data boundary and the most direct backup/monitoring proof. Choose
**FLY-SUPABASE-SYD-V1** only if avoiding app-host patching is worth the extra supplier
and monitoring complexity. Do not combine or expand the designs before the first
partner provides evidence.

## Clerk deployment requirements common to both

The setup proof must eventually create/configure a dedicated Clerk production
instance using `pk_live_` and `sk_live_` keys in the target secret manager, not test
keys. It must record the exact issuer, JWKS URL and API audience, and make the web
custom token carry active `org_id`, user and role/permission claims that the API
validates. Configure:

- exact production root domain, frontend/API origins, callbacks and authorised
  parties—no wildcard or preview origin;
- invitation-only access and operator-created organisations; disable public
  organisation creation and keep RevenueOS JIT provisioning false;
- one approved admin and member role model, session lifetime, revocation and MFA;
- synthetic admin/member, second-tenant denial, stale/revoked session and membership
  disablement evidence; and
- Clerk DPA/subprocessor/cross-border approval and an operator-owned recovery path.

Clerk's [production guide](https://clerk.com/docs/guides/development/deployment/production)
requires production-instance keys and domain/DNS configuration. Its current
[pricing](https://clerk.com/pricing) includes organisations and invitations on Hobby,
but Pro adds MFA, custom session lifetime and seven-day application logs. Pro is the
recommended private-beta plan; no plan is activated by this document.

## Sources checked

- [AWS Lightsail pricing](https://aws.amazon.com/lightsail/pricing/)
- [AWS Lightsail database backup and availability behaviour](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-faq-databases.html)
- [AWS Lightsail PostgreSQL engine choices](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-choosing-a-database.html)
- [Fly.io regions](https://fly.io/docs/reference/regions/)
- [Fly.io resource pricing](https://fly.io/docs/about/pricing/)
- [Supabase regions](https://supabase.com/docs/guides/platform/regions)
- [Supabase pricing](https://supabase.com/pricing)
- [Clerk production deployment](https://clerk.com/docs/guides/development/deployment/production)
- [Clerk DPA](https://clerk.com/legal/dpa)

Prices, plans and regions are time-sensitive. Recheck them in a read-only estimate
immediately before the owner approves spend.
