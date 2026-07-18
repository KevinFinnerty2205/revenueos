# ADR 0005 — tenant-owned AI database foundation

- **Status:** Accepted
- **Date:** 2026-07-18
- **Scope:** WO-004A1

## Context

Future Meeting Intelligence needs durable job lifecycle and structured artefact storage. WO-004A1 authorises only database and ORM foundations. It does not authorise execution, providers, prompts, repositories, services, API/UI work or real intelligence.

Sprint 3 has one mutable transcript row per meeting with an optimistic version counter. The new foundation must use that source of truth, prevent cross-tenant relationships and avoid claiming historical source retention.

## Decision

- Add tenant-owned `ai_jobs` and `ai_artifacts` tables in Alembic revision `0004_ai_database_foundation`.
- Store approved job states and initial `infrastructure_test` types in string columns backed by Python enums and database check constraints.
- Pin every job to an organisation, meeting, transcript and positive transcript version.
- Add a composite transcript uniqueness key so the database proves the transcript belongs to that meeting and organisation without preventing later version increments.
- Validate the pinned version against the current transcript on job insertion and prevent later job trace changes with database triggers.
- Require the requester to be a member of the same organisation.
- Store estimated money only as integer minor units with a separate currency.
- Use a nullable tenant-scoped idempotency unique key. Multiple nulls remain possible; a future service must require a key.
- Require every artefact's organisation, meeting, transcript and transcript version to match its job through one composite foreign key.
- Uniquely version logical artefacts by organisation, meeting, transcript, transcript version, type and artefact version.
- Enforce append-oriented artefact content with a database overwrite trigger. Permit only a one-way `superseded_at` marker.
- Enable and force the existing transaction-local tenant RLS policy on both tables.
- Add only indexes justified by tenant/meeting lookup, lifecycle scheduling, stale-lease recovery, idempotency, transcript trace, job lookup and latest-version access.

## Alternatives considered

- **Store only meeting and transcript IDs:** rejected because it cannot prove which transcript version produced an artefact.
- **Reference transcript version in a foreign key:** rejected because Sprint 3 mutates the same transcript row; such a key would prevent legitimate later corrections.
- **Create transcript snapshot storage now:** rejected because it is outside WO-004A1 and changes the Sprint 3 aggregate.
- **Mutable artefact rows:** rejected because future results must be reviewable as versions rather than silently overwritten.
- **Use decimal or floating-point cost:** floating point was rejected for money; integer minor units are simpler than introducing a second monetary convention.
- **Application-only tenancy:** rejected because composite tenant foreign keys and forced RLS provide independent database enforcement.
- **Add repositories, services or a worker now:** rejected as explicitly out of scope.

## Consequences

Positive:

- future execution can persist durable lifecycle metadata without a schema redesign;
- every artefact is traceable to one tenant, meeting, transcript, version and job;
- duplicate non-null idempotent requests and duplicate logical artefact versions fail safely;
- database constraints and forced RLS protect tenant boundaries independently of future application code; and
- artefact content cannot be overwritten.

Trade-offs:

- exact version identity does not preserve the historical transcript body;
- nullable idempotency keys require a future service rule;
- adding future job/artefact types requires an additive migration to their check constraints;
- the overwrite guard adds PostgreSQL/SQLite trigger DDL; and
- no user can request or view a job until separately authorised application layers exist.

## Follow-up triggers

Create or update an ADR before adding transcript snapshots, repository/service lifecycle policy, durable worker claims, provider execution, prompt registry, validated output schemas, AI API/UI access, retention/erasure behaviour or new artefact types.

## Related documents

- [AI database foundation](../03-engineering/ai-database-foundation.md)
- [WO-004A1 sprint record](../07-sprints/wo-004a1-ai-database-foundation.md)
- [Application architecture](../03-engineering/architecture.md)
- [Security and privacy](../03-engineering/security-and-privacy.md)
