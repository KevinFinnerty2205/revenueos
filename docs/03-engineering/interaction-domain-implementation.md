# Interaction domain implementation

## Current boundary

WO-011 implements a tenant-owned Interaction aggregate inside the existing FastAPI
modular monolith. It is a metadata foundation and small product timeline, not an AI
or capture-processing system. The mature Meeting aggregate remains supported as a
one-to-one compatibility projection.

## Interaction model

`Interaction` owns:

- organisation, optional company and optional opportunity;
- one controlled interaction type;
- lifecycle status;
- title;
- optional scheduled and actual start/end timestamps;
- optional IANA-style timezone label;
- creation origin;
- creator and audit timestamps; and
- soft-deletion time.

The ten implemented types are `online_meeting`, `face_to_face_meeting`,
`presentation`, `workshop`, `site_visit`, `executive_lunch`, `phone_call`,
`conference_interaction`, `trade_show_interaction` and `manual_interaction`.
Creation origin is `manual`, `meeting_compatibility` or `imported_external`.
The current API creates only `manual`; `imported_external` is a controlled schema
extension point, not an implemented connector.

All API timestamps must include an offset. Pydantic normalises them to UTC at the
boundary; range checks exist in both application policy and database constraints.

## Lifecycle

| Current | Allowed next state |
| --- | --- |
| `planned` | `in_progress`, `completed`, `cancelled` |
| `in_progress` | `completed`, `cancelled` |
| `completed` | none |
| `cancelled` | none |

Writing the current state again is idempotent. The dedicated completion action is
also idempotent and retains the original completion time on repeated calls.
Lifecycle mutation locks the Interaction row, validates the transition and commits
the audit event and any Meeting projection atomically.

## Source of truth and compatibility

Interaction is authoritative for fields shared with Meeting: title, company,
opportunity, type/status equivalents, scheduled start and soft deletion. The
compatibility adapter maps Meeting `remote`, `phone`, `in_person` and `other` to
Interaction `online_meeting`, `phone_call`, `face_to_face_meeting` and
`manual_interaction`. Meeting `scheduled`, `completed` and `cancelled` map to
Interaction `planned`, `completed` and `cancelled`; Interaction `in_progress`
projects as Meeting `scheduled`.

A linked Interaction cannot change to a type without a Meeting representation.
Meeting-specific description, participants, transcript, Meeting audit events,
AI jobs/artefacts and intelligence routes are not moved or copied. Opportunity
association writes update both records in the same transaction. Meeting soft delete
soft-deletes the linked Interaction so normal list/read APIs remain aligned.

## Service and repository boundary

The route layer owns HTTP parsing and camel-case contracts. The service owns
relationship validation, lifecycle policy, row locks, compatibility projection,
safe audit and commits. The repository owns SQL and applies an explicit
`organisation_id` predicate to every read. The request dependency also proves an
active membership and applies the trusted transaction-local tenant context.

Stable list ordering combines the selected sort value with UUID as a deterministic
tie-breaker. Filters support title search, company, opportunity, type, lifecycle
status and timezone-aware date range.

## Audit and observability

`interaction_audit_events` records `created`, `updated`, `completed`, `cancelled`,
`deleted` and `meeting_linked`, actor UUID, changed field names and timestamp. It
has no content field. Structured logs use safe event names and IDs/type/status only;
titles, relationship content, transcript text and evidence are excluded.

## Explicitly not implemented

There is no Capture Session execution, evidence body/API, recording, microphone,
camera, upload, storage object, OCR, transcription, diarisation, debrief, Voice
Journal, live intelligence, generic Interaction Intelligence or new AI job type.
