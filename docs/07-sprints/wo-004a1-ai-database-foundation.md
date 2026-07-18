# WO-004A1 — AI Database Foundation

## Objective

Create the durable, tenant-isolated database and ORM foundation for future AI processing without executing AI or exposing any new application capability.

## Delivered scope

- `AIJob` ORM model and `ai_jobs` table with the five approved lifecycle states.
- `AIArtifact` ORM model and append-oriented `ai_artifacts` table.
- Exact organisation/meeting/transcript/transcript-version trace constraints.
- Tenant-safe requester membership and job/artefact composite foreign keys.
- Non-negative attempts, token, cost and duration constraints plus positive version constraints.
- Integer minor-unit cost storage with separate currency.
- Tenant-scoped idempotency and logical artefact-version uniqueness.
- Database overwrite guard allowing only a one-way artefact supersession marker.
- Useful lookup, scheduling, lease, trace and version indexes.
- Enabled and forced PostgreSQL RLS for both tables.
- ORM, constraint, migration, rollback, drift and PostgreSQL 16 RLS tests.
- Architecture, security and schema documentation plus ADR 0005.

## Migration

Apply `0004_ai_database_foundation`. Downgrade to `0003_meeting_domain` drops AI artefacts before jobs and removes the additional transcript trace uniqueness. Downgrade destroys AI foundation rows; back up data before an environment rollback.

## Security

Organisation ownership is non-null. Composite foreign keys reject cross-tenant or mismatched meeting/transcript/requester/job relationships. Forced RLS uses the existing transaction-local tenant setting. No raw transcript, prompt, secret or full provider response is added to job metadata or audit history.

## Known limitations

- Transcript versions are counters on one mutable row, not immutable source snapshots.
- A null idempotency key permits multiple rows at the database layer; a future service must require a key.
- Typed `content_json` validation is deferred to the separately authorised service/processing work.
- Production identity, retention/export/erasure and operational controls remain incomplete.

## Explicitly not delivered

No repositories, services, lifecycle transition service, worker, claiming, retry execution, provider abstraction, mock provider, OpenAI integration, prompt registry, output parser, API route, frontend, polling, summary, decision, action, risk, question, follow-up email, CRM feature, integration, recording, transcription, embedding, memory, automation, billing or autonomous agent was added.

Do not use production customer data. This pull request must remain unmerged until review and CI complete.
