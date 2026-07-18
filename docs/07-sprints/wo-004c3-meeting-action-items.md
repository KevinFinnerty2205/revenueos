# WO-004C3 — Meeting Action Items Intelligence

## Objective

Add the third genuine Meeting Intelligence path: an authorised user can queue
and view a strict list of transcript-supported committed actions through the
established durable worker and either configured provider.

## Delivered scope

- `action_items` job and artefact types plus narrow migration
  `0009_action_items`;
- immutable Action Items schema v1 with bounded empty success, nullable owner
  and due date, normalised priority, fixed `open` status, confidence and
  paraphrased evidence;
- Action Items prompt v1 with Decisions separation, conservative date rules
  and transcript prompt-injection controls;
- deterministic no-network mock support for populated, empty, nullable,
  relative-date, malformed and invalid cases;
- explicit OpenAI allowlisting through the existing strict Responses API path;
- Action Items executor, pinned source loading, bounded output retries,
  cancellation checks and atomic append-only artefact completion;
- tenant-scoped POST/GET endpoints and safe lifecycle contracts;
- accessible Action Items UI with independent non-overlapping three-second
  polling and terminal cleanup;
- backend, web, Playwright, migration, RLS and regression coverage; and
- product, architecture, API, AI, security, development and deployment
  documentation.

## Security and tenant impact

Organisation is derived from trusted authentication. Explicit tenant
predicates, composite tenant keys and forced RLS remain active. The current
transcript version is pinned, and transcript/prompt/raw-output/action content
is excluded from logs and audits. Only validated Action Items content is
persisted. OpenAI receives transcript content only when an operator explicitly
selects `AI_PROVIDER=openai`; automated tests never make a real provider call.

## Migration and rollback

Existing JSON and trace columns represent the capability, but type checks
required `0009_action_items`. It adds no table, column, RLS policy or prompt
storage. Downgrade deletes Action Items artefacts/jobs and restores the
Decisions-era checks; upgrade, downgrade and re-upgrade preserve existing
trace and immutability triggers.

## Out of scope

No Risks, Blockers, Open Questions, follow-up email, CRM change/integration,
task creation/editing/completion, reminder, calendar/email integration,
memory, recording, transcription, embedding, notification, billing, streaming,
WebSocket, provider settings UI or autonomous agent was introduced.

See [Meeting Action Items intelligence](../03-engineering/meeting-action-items-intelligence.md)
and [ADR 0013](../08-decisions/0013-current-transcript-action-items.md).
