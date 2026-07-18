# WO-004B1 — AI Worker and Durable Job Queue

## Objective

Add the first separately runnable execution layer for the existing `infrastructure_test` AI job while keeping PostgreSQL authoritative and preserving forced tenant isolation.

## Delivered

- migration `0006_ai_worker_queue` with worker identity, heartbeat and narrow tenant scheduling function;
- separately runnable `revenueos.worker:main` process;
- PostgreSQL `FOR UPDATE SKIP LOCKED` claiming;
- configurable leases and owner-checked heartbeats;
- bounded exponential retries and attempt exhaustion;
- concurrency-safe abandoned-job recovery;
- pending/running cancellation handling;
- deterministic executor registry and schema-validated infrastructure-test artefact;
- atomic artefact/audit/job completion;
- metadata-only structured worker telemetry;
- SQLite behavioural/migration tests and PostgreSQL concurrency/forced-RLS tests; and
- architecture, security, development, roadmap and decision documentation.

## Security and tenancy

The scheduler database function returns only opaque organisation UUIDs for tenants with work; it cannot return job or customer data. Each claim/recovery/heartbeat/completion transaction then sets one transaction-local tenant context. Queue queries also require an explicit organisation predicate. Forced RLS, tenant composite keys and append-only artefact guards remain active. Safe database/audit/log metadata excludes transcript text, artefact content, prompts, participant data, secrets and raw exceptions.

## Validation

The complete repository gate covers Ruff, formatting, mypy, Pytest, PostgreSQL 16 migrations/RLS/concurrency, Alembic drift, web lint/type/unit/browser tests, production builds and the repository secret/scope audit. CI is authoritative for PostgreSQL-only tests.

## Explicitly out of scope

No real AI provider, provider abstraction, OpenAI, Anthropic, prompt registry/template, response parsing, API endpoint, Intelligence UI, polling/WebSocket, summary, decision, action, risk, question, email, CRM action, recording, transcription, embedding, vector search, memory, notification, billing, autonomous agent, Redis, Celery, Kafka or RabbitMQ was added.

## Known limitations

- The worker exposes no product-facing lifecycle or cancellation surface.
- Only deterministic infrastructure-test jobs run.
- The existing transcript version does not preserve historical transcript text.
- Automated audits attribute the original requester and include worker metadata; there is no dedicated system actor.
- Production customer data remains prohibited until production identity and operational privacy controls are complete.

See [worker architecture](../03-engineering/ai-worker-queue.md) and [ADR 0007](../08-decisions/0007-postgresql-ai-worker-queue.md).
