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
5. a two-node highly available managed PostgreSQL 16 cluster in Sydney, with a non-superuser/non-`BYPASSRLS` runtime role, certificate- and hostname-verifying TLS, trusted-source restrictions and a fourteen-connection application cap across the initial API and worker;
6. one private Sydney Spaces bucket for evidence, generated assets and authenticated tenant exports; and
7. one daily scheduled backup job that streams encrypted PostgreSQL and Spaces payloads to a separate private AWS S3 Standard bucket in Sydney, verifies remote metadata and publishes the manifest last.

The inert target spec is `infra/digitalocean/app.production.template.yaml`. `deploy_on_push` is false. Production is not created under WO-054 because the owner authorised AUD $0 and App Platform bills even short-lived resources. DNS is not included in the spec until the platform has issued its exact destination and the owner approves the record change.

The baseline runs exactly one worker to control cost. Correctness does not depend on process singleton status: database leases and idempotency protect overlapping instances and restarts. A failed or stale worker liveness probe causes a platform restart; queue/provider/unknown-outcome checks remain tenant-scoped operator checks. One process is acceptable only for a supervised, low-volume first partner. The launch spec bounds uploaded PPTX files to 20 MB, expanded PPTX content to 100 MB and any media member to 5 MB; the full Create suite measured about 300 MiB maximum resident memory on the review host, which is directional rather than a cloud load test. Split, resize or scale the worker when queue oldest age exceeds five minutes twice, memory exceeds 80% for ten minutes, provider work repeatedly approaches the worker-freshness window, or more than one partner needs concurrent service. Adding replicas improves throughput/recovery but does not create logical queue-class isolation; that would require a later engineering change.

App Platform and PostgreSQL run in Sydney. Edge traffic passes through DigitalOcean's global CDN, which DigitalOcean states can present US-based IPs; therefore no marketing claim of exclusively Australian processing or data residency is authorised.

## Recovery decision

Managed PostgreSQL provides daily backups, seven-day retention and restore/PITR into a new cluster. It encrypts cluster data at rest and requires TLS in transit ([PostgreSQL backup restore](https://docs.digitalocean.com/products/databases/postgresql/how-to/restore-from-backups/), [PostgreSQL security](https://docs.digitalocean.com/products/databases/postgresql/how-to/secure/), verified 10 September 2026).

That does not back up Spaces. DigitalOcean explicitly says Spaces has no built-in backup. The repository therefore supplies a dedicated scheduled remote backup/verify/restore path: database and object payloads stream through bounded temporary files, are encrypted with AES-256-GCM, uploaded to independent AWS S3, remotely size/SHA-verified and committed by uploading the manifest last. The job receives backup-only credentials and key material. Before customer data is enabled, the owner must create and approve the target, versioning/lifecycle policy, external failure/freshness alert, separately controlled key escrow and complete a named-environment restore drill. App Platform's ephemeral filesystem is never the durable destination.

Recommended operating objectives, not contractual SLAs, are a 24-hour RPO and four-hour RTO for V1. A customer-data launch cannot pass until both database and object recovery meet those objectives.

## Alternatives considered

- Static/free hosting is rejected because the web runtime performs server-side authentication and the API, worker and PostgreSQL cannot run on App Platform's static free tier.
- One unmanaged virtual machine is cheaper in some configurations but adds OS patching, database operation, TLS, process supervision and backup ownership at the first launch.
- AWS Sydney remains viable but adds more configuration and cost-model complexity than needed for a single modular monolith.
- Kubernetes, Redis and a message broker add no required capability at this scale and remain prohibited without measured need and a separate decision.

## Consequences

The application components are intentionally single-instance, but the paid/customer-data database baseline is highly available because DigitalOcean recommends single-node clusters for preliminary development/testing. App services can scale when measurements justify switching from fixed to scalable plans or resizing. Production web builds remain intentionally impossible until approved Privacy and Terms release records include approved status, version, effective date and SHA-256 fingerprint. No deployment, account, domain, subscription or spend is created by this decision.
