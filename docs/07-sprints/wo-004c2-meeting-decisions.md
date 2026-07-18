# WO-004C2 — Meeting Decisions Intelligence

## Objective

Add the second genuine Meeting Intelligence path: an authorised user can queue
and view a strictly structured list of transcript-supported decisions through
the established durable worker and either configured provider.

## Delivered scope

- `decisions` job and artefact types plus narrow migration `0008_decisions`;
- immutable Decisions schema v1 with a valid bounded empty list;
- Decisions prompt v1 with decision/Action Item separation and transcript
  prompt-injection controls;
- deterministic mock support for populated, empty, malformed and invalid
  output;
- explicit OpenAI allowlisting using the existing strict Responses API path;
- Decisions executor, pinned transcript loading, output retries, cancellation
  checks and atomic append-only artefact completion;
- tenant-scoped POST/GET endpoints and safe lifecycle contracts;
- accessible Decisions UI with independent non-overlapping three-second
  polling and terminal cleanup;
- backend, web, Playwright, migration, RLS and regression coverage; and
- product, architecture, API, AI, security, development and deployment
  documentation.

## Security and tenant impact

The capability derives organisation from trusted auth context, retains explicit
tenant predicates and forced RLS, pins the current transcript version and keeps
transcript/prompt/output content out of logs and audits. Only validated
Decisions content is persisted. OpenAI receives transcript content only when an
operator explicitly selects `AI_PROVIDER=openai`; automated tests never make a
real provider request.

## Migration and rollback

The existing columns already represent content and traceability, but database
type checks required revision `0008_decisions`. It adds no table, column, RLS
policy or prompt storage. Downgrade deletes Decisions artefacts/jobs and restores
the Executive Summary-era type checks. Application rollback should normally
select the mock provider and deploy matching API/web/worker code before any
database downgrade.

## Out of scope

No Action Items, due dates, Risks, Open Questions, follow-up email, CRM change,
memory, recording, transcription, embeddings, notification, billing, streaming,
WebSocket, provider settings UI or autonomous agent was introduced.

See [Meeting Decisions intelligence](../03-engineering/meeting-decisions-intelligence.md)
and [ADR 0012](../08-decisions/0012-current-transcript-decisions.md).
