# Action Layer security and privacy review

## Controls implemented

- verified tenant context and explicit organisation predicates on every repository read;
- composite tenant foreign keys and forced PostgreSQL RLS on all Action tables;
- strict discriminated payloads, bounded text and controlled lifecycle transitions;
- immutable proposal revisions and metadata-only immutable audit events;
- current-source validation at generation and approval;
- no reads from provisional signals and no raw transcript access;
- no provider request or live external execution path; WO-022 simulations are
  isolated behind a separately confirmed server preview;
- configurable feature flags, daily generation limit and active-proposal cap;
- Action content included in tenant export and removed by retention/organisation deletion;
- safe errors and logs containing identifiers/status metadata rather than customer content.

## Residual risks

Recommendations may still be incomplete or wrong, and user-edited customer content
can still be inappropriate. Human review, clear source context and simulation-only execution are
the primary mitigations. JSON source references cannot enforce foreign keys to every
source type, so approval performs application-level source validation. PostgreSQL RLS
integration tests remain mandatory in CI.

## Out of scope

Live connector credentials, delegated scopes, webhooks, delivery receipts, outbound
content scanning, autonomous execution, undo across external systems and production
execution incident response are not implemented. See the dedicated
[WO-022 integration security review](integration-security-review.md).
