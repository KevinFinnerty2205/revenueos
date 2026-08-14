# WO-012 — AI Companion and Pre-Interaction Brief

## Delivered

WO-012 implements the first user-facing AI Companion capability: preparation before
all ten initial Interaction types. It adds deterministic source construction and
composition, strict immutable contracts, versioned persistence, idempotent
generation, optional metadata-only review, Interaction readiness, a responsive
mobile-first UI and deterministic face-to-face, phone and presentation demo briefs.

Migration `0022_pre_interaction_brief` directly revises
`0021_interaction_foundation` and is the single Alembic head. It creates the
tenant-owned brief table, composite foreign keys, idempotency/version constraints,
indexes, forced RLS and immutability guards.

## Design decisions

- Deterministic composition is used; no prompt, AI job, worker or provider call is
  added.
- Structured current-version intelligence is authoritative. Transcript text is
  never selected or passed through the service.
- Same fingerprint reuses a result and does not consume quota; changed context
  appends a new version.
- Confidence labels source completeness only.
- Presentation material is context, never customer evidence.

## Cross-cutting integration

The `aiCompanion` server feature flag, data-notice acknowledgement and daily
generation guardrail apply. Briefs participate in retention dry runs and deletion,
Interaction/organisation deletion, JSON export version 3, and tenant-scoped demo
reset. Metadata-only events cover request, context build, start, reuse, completion,
safe failure, view, review and insufficient context.

## Not delivered

Live Companion, AI Debrief, Voice Journal, recording, transcription, phone
integration, dialling, visual capture, document/email ingestion, calendar
integration, notification, live intelligence and external action remain out of
scope.
