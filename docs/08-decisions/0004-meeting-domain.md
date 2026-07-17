# ADR 0004 — tenant-owned Meeting Domain

- **Status:** Accepted
- **Date:** 2026-07-17
- **Scope:** Sprint 3

## Context

Sprint 3 needs a stable non-AI aggregate for meeting metadata, attendees and user-supplied transcript text. It must follow the Sprint 2 repository/service pattern, prevent cross-organisation attachment, support correction and soft deletion, and expose useful audit activity without duplicating customer content.

WO-003 explicitly includes Transcript CRUD and supersedes ADR 0003's earlier proposal to defer transcript content. It does not authorise recording, media ingestion, transcription or AI.

## Decision

- Add Meeting, MeetingParticipant, Transcript and MeetingAuditEvent to the existing modular-monolith API.
- Put a non-null `organisation_id` on all four tables and every repository predicate.
- Enable and force PostgreSQL RLS using the request's transaction-local trusted tenant setting.
- Use composite `(organisation_id, id)` foreign keys for meeting/company/contact/member relationships.
- Require an active organisation membership on Meeting Domain requests. Keep equal member CRUD access until product approves a finer role matrix.
- Model meeting type, meeting status, attendance, participant role, transcript source and audit action with string columns, Python enums and database check constraints.
- Allow an optional same-tenant company and optional participant contact. Require each participant to have a contact, display name or valid email.
- Store at most one transcript row per meeting. Lock the meeting aggregate root for mutations, lock transcript rows during correction, require optimistic `version`, increment after every successful edit or restoration, and fail stale writes.
- Soft-delete meetings, participants and transcripts. Soft-deleting a meeting applies one timestamp to its active children in the same transaction.
- Store append-only audit metadata for service mutations: actor, action, entity identity, changed field names and transcript version. Never copy raw transcript, participant names or emails into audit events.
- Let the web form read an explicitly selected `.txt` file into the plain-text field. Do not add object storage, file ingestion or transcription.

## Alternatives considered

- **Application predicates without RLS:** rejected because tenant controls require defence in depth.
- **Child rows without organisation ownership:** rejected because inherited tenancy alone cannot support direct RLS and composite relationship enforcement safely.
- **Hard delete:** rejected because the work order requires soft deletion and audit history.
- **Event sourcing or immutable transcript snapshots now:** rejected as unnecessary complexity. The version counter preserves an explicit future seam without claiming content history.
- **Store transcript files:** rejected because media/object-storage ingestion is outside Sprint 3.
- **Put meeting rules in generic Sprint 2 components/services:** rejected because nested participants, singular transcript versioning and soft deletion have distinct state.

## Consequences

Positive:

- service validation, composite constraints and RLS independently protect tenant boundaries;
- future intelligence can bind output to an exact meeting/transcript version;
- soft deletion and metadata-only audit make lifecycle changes reviewable;
- the API and UI stay truthful about user-supplied text and absent recording/AI capability; and
- the existing modular-monolith pattern remains unchanged.

Trade-offs:

- transcript `version` is not immutable snapshot history;
- soft deletion is not regulatory erasure;
- all members currently have equal transcript access;
- editing nested resources uses multiple API calls after the meeting update; and
- field-name audit records support activity review but not forensic content reconstruction.

## Follow-up triggers

Create or update a decision record before adding:

- AI artefacts, model/provider calls or source citations;
- transcript snapshots, segments, speaker resolution or generated transcripts;
- recording, object storage, ingestion jobs or consent evidence;
- role-specific transcript visibility;
- hard deletion, export, retention or legal hold behaviour; or
- provider/calendar/CRM relationships.

## Related documents

- [Sprint 3 record](../07-sprints/sprint-03-meeting-domain.md)
- [Application architecture](../03-engineering/architecture.md)
- [Security and privacy baseline](../03-engineering/security-and-privacy.md)
- [API reference](../03-engineering/api.md)
