# ADR 0007 — PostgreSQL-backed AI worker queue

**Status:** Accepted

**Date:** 2026-07-18

## Context

WO-004A1/A2 established tenant-owned AI jobs, strict artefacts and lifecycle policy but intentionally did not execute work. WO-004B1 requires concurrent-safe claiming, crash recovery, retries and cancellation without adding Redis, a provider layer or an API/UI surface. All tenant-owned tables use forced PostgreSQL RLS.

## Decision

- Run the AI worker as a separately deployable backend process, never inside FastAPI.
- Keep `ai_jobs` in PostgreSQL as the durable queue and source of truth.
- Claim one tenant-scoped pending row with `FOR UPDATE SKIP LOCKED`, then commit before execution.
- Add only `worker_id` and `heartbeat_at`; reuse `lease_expires_at`.
- Consume one attempt when entering `running`.
- Heartbeat with an exact tenant/job/worker/running predicate.
- Recover expired running jobs with row locks; retry with deterministic bounded exponential backoff when attempts remain and fail permanently otherwise.
- Check cancellation before claim and again in the locked completion transaction.
- Persist validated artefact, audit events and completed job state in one transaction.
- Route execution through a small job-type registry with one deterministic infrastructure-test executor.
- Use a fixed, narrowly scoped security-definer function to discover only opaque organisation IDs with queue work. Re-enter normal forced RLS for every tenant transaction; never expose arbitrary cross-tenant rows or disable RLS.
- Keep worker telemetry structured and metadata-only.

## Alternatives considered

- **In-memory queue:** rejected because process restarts would lose work and concurrent API/worker replicas would not share state.
- **Redis/Celery or a message broker:** rejected as unnecessary operational complexity for the authorised scope.
- **Run work in FastAPI:** rejected because background execution must not share the HTTP request lifecycle.
- **Global privileged AI-job query:** rejected because it would expose cross-tenant rows and weaken forced RLS.
- **Configured static tenant list:** rejected because it would miss newly eligible tenants and require unsafe operational synchronisation.
- **Hold a claim transaction during execution:** rejected because long locks reduce throughput and make crash handling harder.
- **Complete before artefact commit:** rejected because a completed job without its promised artefact is inconsistent.
- **Random retry jitter:** deferred; deterministic bounded backoff is simpler and sufficient for this infrastructure-test stage.

## Consequences

Positive:

- job ownership is durable and safe across concurrent replicas;
- crashes become recoverable after a bounded lease;
- database and application tenancy controls remain layered;
- completion has an exact, reviewable artefact trace; and
- future executor types have a narrow seam without prematurely introducing provider architecture.

Trade-offs:

- the scheduler function reveals opaque eligible organisation IDs to the database worker role;
- sequential processing per process prioritises simplicity over local concurrency;
- PostgreSQL is both application database and queue, so queue load must be monitored before scaling genuine AI work;
- automated audit events use the requesting user plus worker metadata until a system-actor design is approved; and
- no user/API visibility exists yet.

## Follow-up triggers

Create or update an ADR before adding provider-backed execution, prompts, more job types, transcript snapshots, per-process parallelism, a broker, a system audit actor, public lifecycle/cancellation APIs or operator controls.

ADR 0008 records the subsequently approved mock-only provider abstraction. Real
provider execution and prompts remain follow-up triggers.

## Related documents

- [AI worker and durable job queue](../03-engineering/ai-worker-queue.md)
- [AI domain services](../03-engineering/ai-domain-services.md)
- [WO-004B1 sprint record](../07-sprints/wo-004b1-ai-worker-queue.md)
- [ADR 0008: provider-neutral AI execution](0008-provider-neutral-ai-execution.md)
- [Security and privacy](../03-engineering/security-and-privacy.md)
