# ADR 0015: Current-transcript Open Questions execution

- **Status:** Accepted
- **Date:** 2026-07-19

## Context

Executive Summary, Decisions, Action Items and Risks & Blockers already prove
the tenant-scoped Meeting Intelligence path. WO-004C5 requires a fifth,
independent capability that identifies genuinely unresolved questions after
examining the whole current transcript. It must not answer questions, duplicate
other intelligence types or expand into assignment, reminders, follow-up email
or CRM work.

The database check constraints enumerate supported AI job and artefact types,
so `open_questions` cannot be persisted without a migration.

## Decision

- Add `open_questions` as an independent job and artefact type.
- Pin the current usable transcript ID/version and use prompt/schema key
  `open_questions`, version 1.
- Use a strict frozen schema containing at most 25 questions with required
  question, nullable owner, normalised importance, finite confidence and brief
  paraphrased evidence. A question must end in `?`; unknown fields are rejected.
- Require whole-transcript inspection and exclude answered-later, rhetorical,
  conversational, resolved-confirmation, action-request, AI-directed and
  prompt-injection questions.
- Reuse the existing provider port, bounded structured-output retries, durable
  worker, cancellation check, atomic artefact/completion transaction and
  metadata-only audit events.
- Add only meeting-scoped POST/GET routes and one terminating three-second
  polling panel; do not add generic AI APIs or WebSockets.
- Add migration `0011_open_questions` only to widen type constraints. Existing
  tenant keys, forced RLS policies and repository predicates remain unchanged.

## Alternatives

- **Embed questions in Risks & Blockers:** rejected because a missing answer and
  a threatening condition are different product concepts and lifecycle units.
- **Answer or recommend answers:** rejected as unsupported inference and later
  scope.
- **Create assignment/resolution state now:** rejected because the work order
  authorises extraction and viewing only.
- **Store rendered prompts or raw provider output:** rejected for privacy,
  security and unnecessary retention.
- **Add WebSockets:** rejected because bounded polling already satisfies the
  lifecycle and operational requirements.

## Consequences

Users can generate and view transcript-grounded unresolved questions through
the deterministic mock or explicitly configured OpenAI adapter. Jobs remain
idempotent per organisation, meeting, transcript, type and prompt/schema
version; artefacts remain append-only. OpenAI selection transmits the selected
transcript externally. Question quality remains transcript- and provider-
limited, owner may be null, historical transcript bodies are not retained and
production customer data remains prohibited.
