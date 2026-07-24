# AI domain services

## Current boundary

WO-004A2 adds the internal tenant-scoped job/artefact application layer.
WO-004C1 extends it with Executive Summary; WO-004C2 adds independent
current-transcript Decisions; WO-004C3 adds Action Items; WO-004C4 adds
Risks & Blockers; WO-004C5 adds Open Questions; WO-006A adds Buying Signals;
WO-006B adds Objections & Competitive Signals and WO-006C adds Stakeholder
Intelligence request/state rules and typed
append-only artefacts. WO-004C6 adds Follow-up Email request/state rules
over four validated source artefacts, with no transcript-content query. Only those
product-safe capabilities are exposed through the
meeting-scoped API/UI; generic lifecycle APIs remain
internal.

Migration `0005_ai_domain_services` extends the existing meeting audit event with a metadata-only JSON object, expands its action/entity checks and widens the action column for the new event names.

## Repository responsibilities

`AIJobRepository` provides:

- create and organisation-scoped retrieval by ID;
- latest-job lookup and paginated meeting history;
- Follow-up Email active-equivalence/count lookup and current transcript audit-
  version metadata lookup;
- idempotency lookup by organisation, meeting, transcript version, job type and key;
- explicit lifecycle metadata updates;
- deterministic pending-eligibility and stale-running queries; and
- the shared transaction and meeting-audit boundary.

`AIArtifactRepository` provides:

- append-only creation and organisation-scoped retrieval by ID;
- latest artefact lookup by meeting, transcript version and type;
- exact four-artefact Follow-up Email source loading and source-version lookup;
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
- accepts only registered `infrastructure_test`, `executive_summary`,
  `buying_signals`, `objections_competitive_signals`, `decisions`,
  `action_items`, `risks_blockers`, `open_questions` or `follow_up_email`,
  schema version 1;
- persists only the Pydantic-validated JSON representation;
- assigns the next logical version without overwriting prior artefacts;
- retries one concurrent logical-version conflict before returning a safe conflict; and
- emits `ai_artifact_created`.

The Follow-up Email service requires current, same-version Executive Summary,
Decisions, Action Items and Open Questions artefacts. It checks transcript audit
version metadata without reading transcript content, validates each source
against its strict schema, excludes Risks & Blockers, persists the selected
tone and queues composition. Equivalent active work is reused; a completed
draft can create a deliberate new append-only job. Completion validates the
strict Follow-up Email schema and pinned job trace without calling the ordinary
transcript-content trace loader.

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

Executive Summary schema version 1 is documented in
[Executive Summary intelligence](executive-summary-intelligence.md). It
contains only the summary, meeting type, sentiment and finite confidence.
Decisions schema version 1 is documented in
[Meeting Decisions intelligence](meeting-decisions-intelligence.md). It
contains only a bounded list of decision, nullable supported owner, normalised
status, finite confidence and brief paraphrased evidence.
Buying Signals and Objections & Competitive Signals schemas are documented in
[Buying Signals & Deal Momentum intelligence](buying-signals-intelligence.md)
and [Objections & Competitive Signals intelligence](objections-competitive-signals-intelligence.md).
Stakeholder Intelligence schema version 1 is documented in
[Stakeholder Intelligence](stakeholder-intelligence.md).

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

- Generic AI lifecycle work remains internal; only the Executive Summary,
  Buying Signals, Objections & Competitive Signals, Stakeholder Intelligence, Decisions, Action Items,
  Risks & Blockers, Open Questions and Follow-up Email
  request/state resources are public.
- Worker claiming, leases, retry scheduling and cancellation execution support
  infrastructure tests, Executive Summary, Buying Signals, Objections &
  Competitive Signals, Stakeholder Intelligence, Decisions, Action Items, Risks & Blockers, Open
  Questions and Follow-up Email.
- The configured provider may be mock or OpenAI; there is no email-send
  integration or later Meeting Intelligence capability.
- The transcript version identifies the current mutable transcript row but does not preserve a historical text snapshot.
- Production identity, retention, export, erasure and operational controls remain incomplete; production customer data is prohibited.

A later, separately approved provider/intelligence layer can register another
adapter or immutable prompt/schema pair without changing the tenant trace,
transaction, safe-error or append-only rules.
