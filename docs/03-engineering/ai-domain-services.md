# AI domain services

## Current boundary

WO-004A2 adds an internal application layer for the `infrastructure_test` AI job and artefact types introduced by migration `0004`. It can create and inspect tenant-scoped jobs, validate lifecycle transitions, and persist typed, append-only infrastructure-test artefacts. The service layer has no API or UI surface. WO-004B1 now consumes it from a separate deterministic worker described in [AI worker and durable job queue](ai-worker-queue.md).

Migration `0005_ai_domain_services` extends the existing meeting audit event with a metadata-only JSON object, expands its action/entity checks and widens the action column for the new event names.

## Repository responsibilities

`AIJobRepository` provides:

- create and organisation-scoped retrieval by ID;
- latest-job lookup and paginated meeting history;
- idempotency lookup by organisation, meeting, transcript version, job type and key;
- explicit lifecycle metadata updates;
- deterministic pending-eligibility and stale-running queries; and
- the shared transaction and meeting-audit boundary.

`AIArtifactRepository` provides:

- append-only creation and organisation-scoped retrieval by ID;
- latest artefact lookup by meeting, transcript version and type;
- logical version and per-job listings; and
- calculation of the next logical artefact version.

Repositories always require an organisation ID and add an explicit organisation predicate. They do not claim work, lock rows, schedule retries or overwrite artefacts.

## Service responsibilities

`AIJobService`:

- resolves only the organisation and actor in trusted `TenantContext`;
- requires an active same-tenant meeting and transcript;
- proves the transcript belongs to the meeting and captures its exact current version;
- creates a pending `infrastructure_test` job;
- enforces a trimmed, 1–200 character idempotency key;
- returns the existing job for an identical request, including after a concurrent uniqueness conflict;
- permits a deliberate new job when the key differs;
- validates lifecycle transitions and timestamp/error metadata; and
- emits `intelligence_requested`, `ai_job_created` and `ai_job_status_changed`.

`AIArtifactService`:

- requires a same-tenant job and matching meeting/transcript/version trace;
- accepts only `infrastructure_test`, schema version 1;
- persists only the Pydantic-validated JSON representation;
- assigns the next logical version without overwriting prior artefacts;
- retries one concurrent logical-version conflict before returning a safe conflict; and
- emits `ai_artifact_created`.

Cross-tenant identifiers are indistinguishable from missing resources. Services return safe domain codes and messages and never expose database/provider exception text.

## Idempotency

The identity of an idempotent request is:

```text
organisation + meeting + transcript version + job type + normalised key
```

An identical request returns the existing job and records another metadata-only `intelligence_requested` event. A different key intentionally creates a different job. Job creation and its audit events commit atomically. If the database uniqueness constraint wins a concurrent race, the service rolls back the losing transaction, re-reads through the tenant-scoped repository and returns the winner.

## Lifecycle transition matrix

| From | To | Behaviour |
| --- | --- | --- |
| `pending` | `running` | Sets `started_at`, clears stale execution/error metadata and increments `attempt_count` |
| `pending` | `cancelled` | Sets `cancellation_requested_at` and `cancelled_at` |
| `running` | `completed` | Sets `completed_at` and clears lease/retry state |
| `running` | `failed` | Clears lease state and stores only bounded safe error code/message |
| `running` | `cancelled` | Sets cancellation timestamps and clears lease/retry state |
| `failed` | `pending` | Prepares a future retry by preserving attempts and clearing stale execution/error metadata |

`completed` and `cancelled` are terminal. All transitions not listed above fail with `invalid_lifecycle_transition`. Each move to `running` consumes one attempt; retry preparation preserves the count so a later `pending` to `running` consumes the next attempt. This layer does not calculate backoff, set a future retry schedule or execute work.

## Infrastructure-test artefact schema

Schema version 1 is:

```json
{
  "status": "ok",
  "message": "AI processing infrastructure is operational."
}
```

`status` is the literal `ok`. `message` is trimmed, non-empty and limited to 500 characters. Unexpected fields are rejected. This is a deterministic infrastructure contract, not provider output parsing or meeting intelligence.

## Artefact version assignment

Logical versions are scoped by organisation, meeting, transcript, transcript version and artefact type. The repository reads the current maximum and assigns the next positive integer. The database unique constraint prevents two writers from keeping the same version. On one concurrent conflict the service rolls back the full artefact/audit unit, recalculates and retries once; persistent contention returns `persistence_conflict`.

## Transactions and audit metadata

The following units are atomic:

- new job plus `intelligence_requested` and `ai_job_created`;
- repeated intelligence request plus its audit event;
- lifecycle transition plus `ai_job_status_changed`; and
- validated artefact plus `ai_artifact_created`.

Allowed metadata is limited to identifiers, type, status, transcript/artefact/schema version, and optional prompt/provider/model identifiers. Audit metadata never includes transcript or artefact content, prompt/model bodies, provider secrets, participant data, or raw exception text.

## Tenant isolation

Every service starts with trusted `TenantContext`. Every repository read/write has an explicit organisation predicate, while the existing forced PostgreSQL RLS policies and composite tenant foreign keys remain independent enforcement layers. Tests run repositories and services through a restricted PostgreSQL role with transaction-local tenant context and prove cross-tenant reads, transitions and artefact attachment fail closed.

## Known limitations and extension points

- No API route or UI can request, inspect or transition AI work.
- Worker claiming, leases, retry scheduling and cancellation execution now exist only for the deterministic infrastructure test.
- WO-004B2 routes this existing infrastructure-test contract through a
  deterministic mock provider, and WO-004B3 adds one immutable versioned
  prompt/schema pair plus strict output validation. No real provider,
  customer-content prompt, model call or genuine meeting intelligence exists.
- Lifecycle transitions do not use row locks; future worker work must define concurrency/claim semantics before execution.
- The transcript version identifies the current mutable transcript row but does not preserve a historical text snapshot.
- Production identity, retention, export, erasure and operational controls remain incomplete; production customer data is prohibited.

A later, separately approved real provider/intelligence layer can use the
provider port and register further immutable prompt/schema pairs without
changing the tenant trace, transaction, safe-error or append-only rules.
