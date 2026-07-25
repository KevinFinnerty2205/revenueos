# ADR 0023: Persist Revenue Brain as immutable artefact compositions

- **Status:** Accepted
- **Date:** 2026-07-25

## Context

Meeting Intelligence now persists nine validated capabilities needed for an
account-level history. Copying their JSON into another table would create a
second source of truth, broaden sensitive-content storage and make corrections
or schema provenance ambiguous. Re-running a prompt or analysing a transcript
would also introduce reasoning that WO-008A does not authorise.

The current transcript model has one stable transcript UUID and a mutable
positive version counter, rather than an immutable transcript-version row with
its own UUID. WO-007 gives each meeting one optional, audited, tenant-safe
opportunity association.

## Decision

- Add a tenant-owned `revenue_brain_snapshots` table containing only ownership,
  meeting/revision identity, creation/version metadata and nine artefact IDs.
- Require Executive Summary, Buying Signals, Objections & Competitive Signals,
  Stakeholder Intelligence, Decisions, Action Items, Risks & Blockers, Open
  Questions and Next Best Action. Exclude Follow-up Email.
- Revalidate each latest non-superseded artefact against its completed matching
  job, exact trace, deployed schema version and strict content model before
  composing.
- Derive a stable transcript-version UUID from the transcript UUID and integer
  version. Store no transcript body or duplicate version content.
- Enforce one snapshot per organisation, meeting and derived transcript-version
  identity with a database unique key.
- Serialize readiness checks with the existing meeting row lock and perform
  snapshot creation inside the worker's atomic completion transaction. Reuse
  the existing queue and worker process.
- Use composite tenant foreign keys, explicit organisation predicates and
  forced PostgreSQL RLS for defence in depth.
- Reject all snapshot updates and deletes with database triggers. Earlier
  snapshots remain append-only when a later transcript version becomes ready.
- Copy the meeting's explicit `opportunity_id` reference into the composition
  when present. Keep it nullable and never infer an opportunity from account
  data.
- Expose a reference-only ordered array at
  `GET /api/v1/accounts/{accountId}/brain` and a meeting-date-only account
  timeline.

## Alternatives

- **Copy artefact JSON into each snapshot:** rejected because it duplicates
  validated content and expands privacy and consistency risk.
- **Run a Revenue Brain prompt after each meeting:** rejected because WO-008A
  authorises persistence composition only, not new reasoning or provider use.
- **Create a new queue or worker:** rejected because snapshot readiness is a
  small transactional extension of existing completion.
- **Choose another opportunity from the account:** rejected because selection
  would be ungrounded inference; only the meeting's audited association is
  eligible.
- **Store only the transcript UUID:** rejected because transcript corrections
  reuse that UUID and must be independently idempotent.
- **Allow snapshot correction in place:** rejected because it would erase the
  exact historical composition and weaken traceability.

## Consequences

RevenueOS gains a tenant-safe account timeline without duplicating customer
content or adding provider exposure. Snapshot creation waits for complete,
valid current-revision intelligence and therefore fails closed on partial,
failed, cancelled or stale work. A corrected transcript can append a new
composition while existing snapshots cannot be rewritten or deleted.

The derived transcript-version UUID is an application identity rather than a
foreign key to a transcript-version table. If a future authorised sprint adds
immutable transcript-version rows, it must provide an explicit migration and
compatibility decision. Revenue Brain reasoning and cross-snapshot comparison
remain separate decisions.
