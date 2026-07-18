# AI worker and durable job queue

## Current boundary

WO-004B1 adds a separately runnable backend worker for the existing internal `infrastructure_test` job type. PostgreSQL remains the durable queue and source of truth. The worker claims jobs, maintains leases, retries bounded failures, recovers abandoned work, honours cancellation and creates the existing schema-version-1 test artefact.

The executor is deterministic. It does not read transcript text, make a network request or perform genuine Meeting Intelligence. There is no provider abstraction, OpenAI/Anthropic integration, prompt registry, API route, web UI or polling.

## Process and startup

The worker entry point is:

```bash
pnpm dev:worker
```

This runs `revenueos-ai-worker`, mapped to `revenueos.worker:main`. It is a separate long-running process from FastAPI. Local development uses three terminals:

```bash
pnpm dev:api
pnpm dev:web
pnpm dev:worker
```

`API_DATABASE_URL` or `DATABASE_URL` must point to a migrated PostgreSQL database. `SIGINT` and `SIGTERM` stop new polling; the deterministic in-progress execution is allowed to finish while its heartbeat continues. A process crash is handled by lease expiry and recovery.

Production must deploy the API and worker independently from the same immutable release, use a non-RLS-bypass runtime role, apply migrations before starting either process, and supervise/restart the worker. Horizontal worker replicas are supported by database row locking.

## Claiming algorithm

Each polling cycle:

1. calls the narrowly scoped `revenueos_ai_worker_eligible_organisations` PostgreSQL function, which returns only opaque organisation IDs that currently have pending, cancellation-requested or stale work;
2. opens a short transaction for one organisation and sets transaction-local `app.organisation_id`;
3. settles pending cancellations and recovers expired leases;
4. selects one eligible pending job using `FOR UPDATE SKIP LOCKED`;
5. transitions it to `running`, increments `attempt_count`, records `worker_id`, heartbeat and lease, and writes a metadata-only status audit; and
6. commits before execution begins.

The discovery function is `SECURITY DEFINER` because `organisations` and `ai_jobs` use forced RLS and there is intentionally no cross-tenant application query. Its fixed SQL body exposes only distinct organisation UUIDs for queue scheduling, accepts no organisation or arbitrary query input, caps results at 1,000 and never returns customer/job/meeting/transcript data. Every subsequent operation re-enters ordinary forced RLS for exactly one discovered organisation.

PostgreSQL row locks are the concurrency arbiter. Two workers can poll the same organisation, but a locked job is skipped and can be owned by only one worker.

## Leases and heartbeats

Migration `0006_ai_worker_queue` adds nullable `worker_id` and `heartbeat_at`; it reuses `lease_expires_at`.

- A claim sets all three ownership fields.
- The owning worker extends `heartbeat_at` and `lease_expires_at` in a short transaction.
- The update requires the exact organisation, job, `running` status and worker ID.
- Another worker and a terminal job cannot refresh the lease.
- Completion, final failure, cancellation and recovery clear ownership.
- Execution never holds a database transaction open while work runs.

## Retry and attempt semantics

Entering `running` consumes one attempt. A retryable failure records only a bounded safe code/message, transitions through `failed`, then returns to `pending` with:

```text
delay = min(base_retry_delay × 2 ^ (attempt_count - 1), maximum_retry_delay)
```

The delay is deterministic and has no jitter in WO-004B1. `next_attempt_at` is the eligibility gate. Safe failure metadata remains visible while the retry is pending and is cleared by the next successful claim. When `attempt_count == max_attempts`, the job remains `failed`. A non-retryable failure remains failed immediately.

`max_attempts` on each persisted job is authoritative. `API_WORKER_DEFAULT_MAX_ATTEMPTS` is the default for job producers; WO-004B1 adds no public job-creation route.

## Abandoned-job recovery

A running job is abandoned when its lease exists and has expired. Recovery also uses `FOR UPDATE SKIP LOCKED`, so concurrent workers cannot recover the same row twice. The recovering worker:

- records safe `worker_lease_expired` failure metadata;
- clears the stale worker, heartbeat and lease;
- emits status-change audit events;
- returns the job to pending with the normal backoff when attempts remain; or
- leaves it failed when attempts are exhausted.

Active, completed and cancelled jobs are not modified.

## Cancellation

- Pending jobs with `cancellation_requested_at` are cancelled before claiming.
- A running worker rechecks cancellation in the locked completion transaction before adding an artefact.
- A cancelled job creates no new artefact.
- Cancellation records `cancelled_at`, preserves the original request timestamp, clears retry/ownership fields and emits a status audit.
- Completed and already-cancelled jobs remain terminal.

WO-004B1 deliberately adds no cancellation API.

## Execution and transactions

`AIExecutorRegistry` maps `infrastructure_test` to `InfrastructureTestExecutor`. The executor ignores transcript content and returns the existing strict Pydantic contract:

```json
{
  "status": "ok",
  "message": "AI processing infrastructure is operational."
}
```

Unknown job types produce bounded `unsupported_job_type` failure metadata and are not retried. The successful completion transaction:

- verifies current tenant, running state and worker ownership under a row lock;
- rechecks cancellation;
- validates and stages the exact-trace artefact through `AIArtifactService`;
- records zero input/output tokens, zero estimated cost, `AUD` and processing duration;
- transitions the job to completed; and
- commits artefact, artefact audit, job state and status audit together.

If artefact validation fails, the transaction rolls back and the job fails safely without retry because identical content cannot become valid later. A database persistence failure is retryable. The job cannot become completed without its artefact.

## Configuration

| Environment variable | Default | Constraint |
| --- | ---: | --- |
| `API_WORKER_POLL_INTERVAL_SECONDS` | `1` | Greater than zero, at most 60 |
| `API_WORKER_LEASE_DURATION_SECONDS` | `60` | 10–3,600 |
| `API_WORKER_HEARTBEAT_INTERVAL_SECONDS` | `20` | Shorter than the lease |
| `API_WORKER_BASE_RETRY_DELAY_SECONDS` | `5` | 1–3,600 |
| `API_WORKER_MAX_RETRY_DELAY_SECONDS` | `300` | At least base delay, at most 86,400 |
| `API_WORKER_DEFAULT_MAX_ATTEMPTS` | `3` | 1–20 |

## Telemetry and privacy

Structured logs cover worker start/stop, claim, heartbeat, completion, failure, retry, exhaustion, cancellation, recovery and duration. Allowed fields are organisation/job/type/worker identifiers, attempt, duration, safe error code and retryability. Logs never include transcript/artefact/prompt content, participants, secrets, credentials, raw exception messages or database URLs.

Automated audit events use the original requesting user as the actor because the existing meeting audit schema requires a tenant member. `worker_id` and transition metadata show that execution was automated. A dedicated system-actor model is a future decision, not part of this work order.

## Known limitations and extension points

- Only the deterministic infrastructure test executes.
- Work is processed sequentially within one worker process; scale is achieved with additional worker replicas.
- Tenant discovery is capped at 1,000 eligible organisations per cycle; deployments approaching that many simultaneously active tenants need an approved pagination/fairness extension.
- There is no operator dashboard, API/UI lifecycle access, cancellation endpoint or user polling.
- There is no provider, prompt, model parsing, transcript snapshot, genuine intelligence, notification or external action.
- The current transcript version pin does not preserve a historical transcript body.
- Production identity, consent evidence, retention/export/erasure, deployment monitoring and incident controls remain incomplete. Production customer data is prohibited.

Future provider-backed executors can implement the same small executor interface only after a separately approved provider/prompt work order. They must preserve exact trace validation, short transactions, safe errors, forced RLS and atomic artefact-before-completion semantics.
