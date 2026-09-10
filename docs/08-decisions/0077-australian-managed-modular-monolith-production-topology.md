# ADR 0077: Australian managed modular-monolith production topology

- Status: proposed for owner purchase approval; repository implementation complete
- Date: 10 September 2026
- Decision owners: product owner and engineering reviewer
- Scope: WO-054 only

## Context

The repository is one Next.js web runtime, one FastAPI runtime and PostgreSQL. A single Python worker process coordinates the durable AI, Prospect, Create, Campaign, reviewed-action, Microsoft, Google and CRM connector queues. It uses database leases, retry bounds, idempotency keys and unknown-outcome states; it does not require Redis or a message broker. Tenant maintenance commands are explicit per organisation. Binary evidence and generated presentations use the existing private `VisualStorage` interface and production validation already requires S3-compatible storage.

The production target needs an Australian region, managed TLS, simple process supervision, health-gated releases, PostgreSQL 16 features (including forced RLS and transaction-local tenant context), and recoverability. DigitalOcean App Platform containers do not have persistent filesystems, so application data cannot be stored there ([App Platform limits](https://docs.digitalocean.com/products/app-platform/details/limits/), verified 10 September 2026).

## Decision

The smallest credible target is DigitalOcean Sydney:

1. one 1 GiB App Platform web service running the standalone Next.js image;
2. one 1 GiB App Platform API service, with `/health/live` for liveness and `/health/ready` as its traffic/deployment gate;
3. one 1 GiB non-routable worker, with a private HTTP liveness probe and a single baseline instance;
4. one pre-deploy Alembic job, using the migration credential only for that job;
5. a separately managed PostgreSQL 16 cluster in Sydney, with a non-superuser/non-`BYPASSRLS` runtime role, TLS and trusted-source restrictions; and
6. one private Sydney Spaces bucket for evidence and generated assets.

The inert target spec is `infra/digitalocean/app.production.template.yaml`. `deploy_on_push` is false. Production is not created under WO-054 because the owner authorised AUD $0 and App Platform bills even short-lived resources. DNS is not included in the spec until the platform has issued its exact destination and the owner approves the record change.

The baseline runs exactly one worker to control cost. Correctness does not depend on process singleton status: database leases and idempotency protect overlapping instances and restarts. A failed or stale worker liveness probe causes a platform restart; queue/provider/unknown-outcome checks remain tenant-scoped operator checks.

App Platform and PostgreSQL run in Sydney. Edge traffic passes through DigitalOcean's global CDN, which DigitalOcean states can present US-based IPs; therefore no marketing claim of exclusively Australian processing or data residency is authorised.

## Recovery decision

Managed PostgreSQL provides daily backups, seven-day retention and restore/PITR into a new cluster. It encrypts cluster data at rest and requires TLS in transit ([PostgreSQL backup restore](https://docs.digitalocean.com/products/databases/postgresql/how-to/restore-from-backups/), [PostgreSQL security](https://docs.digitalocean.com/products/databases/postgresql/how-to/secure/), verified 10 September 2026).

That does not back up Spaces. DigitalOcean explicitly says Spaces has no built-in backup. Before customer data is enabled, the owner must approve and configure an automated encrypted copy of objects to a separate destination and complete a named-environment restore drill. The current AES-256-GCM backup tool remains valid for controlled logical snapshots and local synthetic drills, but App Platform's ephemeral filesystem is not a backup destination. Real-data mode, export and organisation deletion therefore stay off in the initial target configuration.

Recommended operating objectives, not contractual SLAs, are a 24-hour RPO and four-hour RTO for V1. A customer-data launch cannot pass until both database and object recovery meet those objectives.

## Alternatives considered

- Static/free hosting is rejected because the web runtime performs server-side authentication and the API, worker and PostgreSQL cannot run on App Platform's static free tier.
- One unmanaged virtual machine is cheaper in some configurations but adds OS patching, database operation, TLS, process supervision and backup ownership at the first launch.
- AWS Sydney remains viable but adds more configuration and cost-model complexity than needed for a single modular monolith.
- Kubernetes, Redis and a message broker add no required capability at this scale and remain prohibited without measured need and a separate decision.

## Consequences

The baseline is intentionally single-instance and not highly available. The managed database can be upgraded with a standby later. App services can scale when measurements justify it. Production web builds remain intentionally impossible until approved Privacy and Terms content replaces the committed GAP routes. No deployment, account, domain, subscription or spend is created by this decision.
