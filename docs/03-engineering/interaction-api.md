# Interaction API

All routes use `/api/v1`, require an authenticated active organisation membership,
derive the tenant from verified server context and return camel-case JSON. Supplying
`organisationId` is rejected. Missing or cross-tenant resources return the same safe
not-found response and cannot be enumerated.

## Endpoints

| Method   | Path                                                                               | Purpose                                                       |
| -------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| `GET`    | `/interactions`                                                                    | List active Interactions with stable pagination and filters   |
| `POST`   | `/interactions`                                                                    | Create one manual Interaction                                 |
| `GET`    | `/interactions/{interactionId}`                                                    | Read one active Interaction                                   |
| `PATCH`  | `/interactions/{interactionId}`                                                    | Update supplied fields and lifecycle                          |
| `POST`   | `/interactions/{interactionId}/complete`                                           | Idempotently complete an Interaction                          |
| `POST`   | `/interactions/{interactionId}/start`                                              | Idempotently enter the Companion DURING phase                 |
| `GET`    | `/interactions/{interactionId}/companion/brief`                                    | Read product-safe preparation state/result                    |
| `POST`   | `/interactions/{interactionId}/companion/brief`                                    | Create or reuse a deterministic brief                         |
| `POST`   | `/interactions/{interactionId}/companion/brief/review`                             | Mark the latest completed brief reviewed                      |
| `POST`   | `/interactions/{interactionId}/companion/markers`                                  | Create/reuse a controlled metadata-only quick marker          |
| `GET`    | `/interactions/{interactionId}/companion/markers`                                  | List active quick-marker metadata                             |
| `DELETE` | `/interactions/{interactionId}/companion/markers/{markerId}`                       | Soft-delete a marker before Interaction completion            |
| `POST`   | `/interactions/{interactionId}/visual-evidence/uploads`                            | Create/reuse a private visual upload grant                    |
| `PUT`    | `/interactions/{interactionId}/visual-evidence/{visualId}/content`                 | Upload bytes through the local private adapter                |
| `POST`   | `/interactions/{interactionId}/visual-evidence/{visualId}/complete`                | Verify and sanitise the uploaded image                        |
| `POST`   | `/interactions/{interactionId}/visual-evidence/{visualId}/process`                 | Produce bounded review candidates                             |
| `POST`   | `/interactions/{interactionId}/visual-evidence/{visualId}/review`                  | Accept/edit/reject every candidate                            |
| `GET`    | `/interactions/{interactionId}/visual-evidence`                                    | List visual metadata and review state                         |
| `GET`    | `/interactions/{interactionId}/visual-evidence/{visualId}`                         | Read one visual metadata/review record                        |
| `GET`    | `/interactions/{interactionId}/visual-evidence/{visualId}/content`                 | Download through a short-lived private grant                  |
| `DELETE` | `/interactions/{interactionId}/visual-evidence/{visualId}`                         | Delete bytes and invalidate current lineage                   |
| `POST`   | `/interactions/{interactionId}/recordings`                                         | Create/reuse an explicitly consented recording session        |
| `GET`    | `/interactions/{interactionId}/recordings`                                         | List recording session state without storage/provider secrets |
| `GET`    | `/interactions/{interactionId}/recordings/{recordingId}`                           | Read one recording state                                      |
| `POST`   | `/interactions/{interactionId}/recordings/{recordingId}/start`                     | Mark browser capture started                                  |
| `POST`   | `/interactions/{interactionId}/recordings/{recordingId}/pause`                     | Record a metadata-only browser pause event                    |
| `POST`   | `/interactions/{interactionId}/recordings/{recordingId}/resume`                    | Record a metadata-only browser resume event                   |
| `POST`   | `/interactions/{interactionId}/recordings/{recordingId}/stop`                      | Mark capture stopped and uploading                            |
| `POST`   | `/interactions/{interactionId}/recordings/{recordingId}/chunks`                    | Create/reuse one bounded chunk grant                          |
| `GET`    | `/interactions/{interactionId}/recordings/{recordingId}/chunks`                    | Read the resumable verified manifest                          |
| `PUT`    | `/interactions/{interactionId}/recordings/{recordingId}/chunks/{chunkId}/content`  | Upload local-adapter bytes                                    |
| `POST`   | `/interactions/{interactionId}/recordings/{recordingId}/chunks/{chunkId}/complete` | Verify checksum and receipt                                   |
| `POST`   | `/interactions/{interactionId}/recordings/{recordingId}/finalize`                  | Reject gaps and idempotently queue batch transcription        |
| `POST`   | `/interactions/{interactionId}/recordings/{recordingId}/cancel`                    | Cancel capture and schedule object deletion                   |
| `GET`    | `/interactions/{interactionId}/recordings/{recordingId}/transcription`             | Read product-safe processing/final transcript state           |
| `DELETE` | `/interactions/{interactionId}/recordings/{recordingId}`                           | Perform object-first recording deletion                       |

There is deliberately no generic public Capture Session or Evidence endpoint.
Visual routes expose the narrow reviewed workflow only; they never expose a
freely supplied organisation ID or durable storage key.

## Browser Companion contract

The Companion route is a web orchestration surface; the API continues to expose
narrow capability endpoints. Start stores the first actual start time and is
idempotent once `in_progress`. Markers use a controlled type, creator/time and
optional recording offset, with no free text. They can be created/deleted only
while `in_progress`, never create evidence automatically, and remain read-only
after completion. See the [Companion lifecycle guide](companion-state-lifecycle-guide.md).

## Recording contract

Recording creation is server-flagged and requires notice version, consent method,
user authority attestation and an idempotency key. The server normalises MIME,
derives tenant storage scope and returns short-lived exact-object upload grants.
Finalisation locks the session, validates a contiguous verified manifest and is
idempotent. Transcription happens only in the existing worker. Public responses
exclude storage keys, signatures, provider request IDs and credentials. Cross-tenant
IDs are hidden as not found. See the
[recording foundation guide](recording-foundation-engineering-guide.md).

For a non-live recording, create additionally requires `recordingSource` as one of
`customer_call_recording`, `business_phone_recording`,
`user_uploaded_recording` or `external_provider_recording`. Live browser recording
must not supply an imported source. The authority acknowledgement remains mandatory.

## Visual evidence contract

The browser supplies one authorised JPEG/PNG (10 MB default maximum), explicit
visual type/ownership/context, timezone-aware capture time, SHA-256 checksum and
idempotency key. Completion verifies actual bytes, MIME, dimensions and pixel
count; rewrites a metadata-minimised image; and rejects polyglots or unsafe
structure. Processing returns `ai_inferred`, initially unreviewed candidates.
Every candidate must be accepted, edited or rejected before completion.

Only reviewed eligible claims create schema-v2 Interaction Intelligence and
Revenue Brain snapshots. Seller-created deck material is context only,
business-card candidates never create a Contact, and site-photo claims use the
`observed` support label. See the
[Visual Evidence engineering guide](visual-evidence-engineering-guide.md).

## Create and update fields

`title` is required on create and is trimmed, non-empty and at most 200 characters.
`interactionType` uses the controlled ten-value taxonomy. `lifecycleStatus`
defaults to `planned`. Optional `companyId` and `opportunityId` must resolve in the
active tenant and must not conflict. Optional `scheduledStartAt`, `scheduledEndAt`,
`actualStartAt` and `actualEndAt` require timezone offsets and are stored/returned in
UTC. End values cannot precede starts. `timezone` is an optional label up to 64
characters.

For `phone_call`, optional `contactId` must resolve in the active tenant and agree
with the selected company/opportunity. `callDirection` is `inbound`, `outbound` or
`unknown` and defaults to `unknown`. Completion may set `callOutcome` to
`connected`, `no_answer`, `voicemail` or `cancelled`. These fields are rejected for
other Interaction types. Association changes are rejected after final Interaction
Intelligence exists. No phone number or provider call identifier is copied onto the
Interaction.

The server owns `id`, `organisationId`, `creationOrigin`, `createdByUserId`,
timestamps and the optional compatibility `meetingId`. Patch accepts only mutable
domain fields. Complete accepts optional timezone-aware `actualEndAt`; when omitted,
the server uses the current UTC time.

## List contract

List responses use `{items, page, pageSize, total, pages}`. `page` starts at 1 and
`pageSize` is 1–100. Supported filters are:

- `search` (title);
- `companyId`;
- `opportunityId`;
- `interactionType`;
- `status`;
- timezone-aware `dateFrom` and `dateTo`; and
- `sortBy=start_at|title|created_at|updated_at`, `sortOrder=asc|desc`.

Sorting always adds the Interaction UUID as a stable tie-breaker. Soft-deleted rows
are hidden. Each item also returns `briefState` (`unavailable`, `not_generated` or
`completed`) and nullable `briefGeneratedAt`; no brief body or internal trace is
joined into the list. Items additionally project derived `durationSeconds`,
`captureMethods`, `intelligenceState` and `recordingAvailable`; the projection
contains no transcript, recording URL or provider internals.

## Preparation brief contract

The completed brief contains interaction ID/type/version, headline, account
context, bounded recent changes, objectives, questions, stakeholder focus, open
commitments, risks, success criteria, interaction guidance and source-completeness
confidence. Unknown fields, predictive scores and automation actions are rejected.

Equivalent context is reused; changed validated context appends a version. GET
returns bounded prior-version metadata and product-safe source labels. Review is
idempotent metadata only. Deterministic v1 has no queued worker execution and no
provider call. See [Pre-Interaction Brief engineering](pre-interaction-brief.md).

## Compatibility behaviour

For a Meeting-backed record, `meetingId` is returned and the Interaction type must
stay Meeting-compatible. Updating shared fields or completing the Interaction
updates the existing Meeting projection atomically. Creating or updating through
the existing Meeting API performs the inverse projection and returns the same stable
Meeting ID plus additive `interactionId`.

## Safe errors

Validation failures use the existing safe `{code, message, requestId}` envelope.
Examples include `invalid_request`, `invalid_time_range`,
`invalid_date_range`, `invalid_lifecycle_transition`,
`incompatible_interaction_type`, `company_not_found`,
`opportunity_not_found`, `interaction_not_found` and
`persistence_unavailable`. Responses and logs contain no database details,
transcript, evidence body, prompt, provider response or raw exception.

## Live Interaction Intelligence

| Method | Path                                                             | Purpose                                                |
| ------ | ---------------------------------------------------------------- | ------------------------------------------------------ |
| `GET`  | `/api/v1/interactions/{id}/live-intelligence`                    | Read availability or persisted live state              |
| `POST` | `/api/v1/interactions/{id}/live-intelligence/start`              | Explicitly enable for an in-progress authorised source |
| `POST` | `/api/v1/interactions/{id}/live-intelligence/process`            | Idempotently process the next bounded segment window   |
| `POST` | `/api/v1/interactions/{id}/live-intelligence/stop`               | Disable and freeze this Interaction’s live state       |
| `POST` | `/api/v1/interactions/{id}/live-intelligence/{signalId}/dismiss` | Dismiss one tenant-owned provisional signal            |
| `POST` | `/api/v1/interactions/{id}/live-intelligence/reconcile`          | Compare frozen live state with final intelligence      |

Responses expose possible signals, brief progress and exact source sequence ranges,
but no transcript text, fingerprints, prompt, provider/model/request metadata or
confidence score. The tenant and cursor are always server-derived. See the
[signal schema](live-intelligence-signal-schema.md).
