# API reference

WO-018 adds `meetingPlatform`, normalised `meetingUrl`, `externalMeetingId`,
`captureSource` and `ingestionState` to online Interaction contracts. It adds:

- `GET /api/v1/interactions/{id}/online-meeting/capabilities`;
- `POST /api/v1/interactions/{id}/online-meeting/transcript`; and
- `GET /api/v1/interactions/{id}/online-meeting/transcripts`.

Recording import continues through the existing recording-session routes. No
native-fetch endpoint is exposed because no provider connection is implemented.

FastAPI's generated OpenAPI document at `/openapi.json` is canonical. Swagger
UI is available at `/docs` outside production; production disables Swagger and
ReDoc. JSON fields use camel case; database and Python fields use snake case.

## Common behaviour

- Business routes are versioned under `/api/v1`.
- Organisation context is derived only from the authenticated user.
- Collection responses contain `items`, `page`, `pageSize`, `total` and `pages`.
- `page` starts at 1; `pageSize` defaults to 20 and is limited to 100.
- String searches are case-insensitive partial matches.
- Create returns `201`; delete returns `204`.
- Updates use `PATCH`, require at least one field and reject null for required fields.
- Errors contain a safe `code`, `message` and `requestId`. Validation errors do not echo customer input.
- Every response includes `X-Request-ID`; a supplied `X-Request-ID` is propagated.
- Transcript writes and every intelligence POST require acknowledgement of the
  current server-owned private-beta notice version.

## Private beta controls

| Method      | Path                                              | Purpose                                                        |
| ----------- | ------------------------------------------------- | -------------------------------------------------------------- |
| `GET`       | `/api/v1/beta/capabilities`                       | Safe server feature flags, notice version and transcript bound |
| `GET`       | `/api/v1/beta/data-notice`                        | Read current notice/acknowledgement state                      |
| `POST`      | `/api/v1/beta/data-notice/acknowledgements`       | Acknowledge the current server version                         |
| `GET/PATCH` | `/api/v1/beta/onboarding`                         | Read/advance/skip persisted user journey                       |
| `POST`      | `/api/v1/beta/feedback`                           | Submit bounded feedback without automatic content attachment   |
| `GET`       | `/api/v1/beta/admin`                              | Admin-only safe organisation overview                          |
| `PATCH`     | `/api/v1/beta/admin/retention`                    | Admin-only 30/90/180/manual setting                            |
| `GET`       | `/api/v1/beta/admin/feedback`                     | Admin-only bounded feedback retrieval                          |
| `PATCH`     | `/api/v1/beta/admin/members/{userId}`             | Admin-only enable/disable membership                           |
| `POST`      | `/api/v1/beta/admin/exports`                      | Queue tenant export request                                    |
| `GET`       | `/api/v1/beta/admin/data-requests`                | Read export/deletion status                                    |
| `GET`       | `/api/v1/beta/admin/exports/{requestId}/download` | Download non-expired restricted export                         |
| `POST`      | `/api/v1/beta/admin/organisation-deletion`        | Queue exact-phrase-confirmed deletion                          |

`GET /health/live` is process liveness. `GET /health/ready` performs bounded
database, migration-head, auth, selected-provider and worker-configuration
checks without an external provider request. See
[private beta readiness](private-beta-readiness.md).

## Companies

| Method   | Path                            | Purpose                  |
| -------- | ------------------------------- | ------------------------ |
| `GET`    | `/api/v1/companies`             | List companies           |
| `POST`   | `/api/v1/companies`             | Create a company         |
| `GET`    | `/api/v1/companies/{companyId}` | Read a company           |
| `PATCH`  | `/api/v1/companies/{companyId}` | Update a company         |
| `DELETE` | `/api/v1/companies/{companyId}` | Delete an unused company |

List parameters: `search`, `status`, `industry`, `sortBy` (`name`, `created_at`, `updated_at`) and `sortOrder`.

## Revenue Brain

| Method | Path                                                       | Purpose                                                          |
| ------ | ---------------------------------------------------------- | ---------------------------------------------------------------- |
| `GET`  | `/api/v1/accounts/{accountId}/brain`                       | List the account's immutable Revenue Brain snapshot compositions |
| `GET`  | `/api/v1/accounts/{accountId}/brain/reported-interactions` | List reviewed salesperson-reported Interaction snapshots         |
| `GET`  | `/api/v1/accounts/{accountId}/brain/visual-evidence`       | List current reviewed visual Interaction snapshots               |
| `POST` | `/api/v1/accounts/{accountId}/brain/reasoning`             | Create or reuse deterministic account comparisons                |
| `GET`  | `/api/v1/accounts/{accountId}/brain/reasoning`             | Read the latest account comparison and bounded history           |

The response is a JSON array ordered by meeting date descending, then snapshot
creation and ID descending. Each item contains the snapshot ownership/trace,
meeting date, schema version and nine artefact IDs. It contains no artefact
content, transcript, prompt, provider/model payload, job/worker state,
comparison or generated reasoning. A cross-tenant or unknown account returns
the same safe `404` response.

Reasoning POST accepts `mode=latest_change` by default or
`mode=recent_history`. It synchronously compares the latest eligible pair or
the adjacent pairs among at most 10 eligible snapshots and reuses an equivalent
immutable insight. GET is read-only and returns `insufficient_history`,
`not_generated` or the current `completed` insight plus up to 10 historical
insights. The stable state enum also reserves `queued`, `running`, `failed` and
`cancelled`.

Reasoning reads only snapshot references, their strict validated artefacts and
safe meeting metadata. It never reads transcript text, re-runs extraction or
calls a provider. The controlled change response includes comparison dates,
qualitative direction and importance, confidence as evidence support, source
capability labels and structured evidence. It contains no outcome score,
probability, forecast, prompt/provider/job fields or raw source content. See
[Revenue Brain longitudinal reasoning](revenue-brain-reasoning.md).

The reported-interactions read returns only accepted, still-available Evidence with
its salesperson-reported source label and recording comparison state. The
visual-evidence read returns source labels and reviewed statements only
while every referenced Evidence row remains verified and available. It never
contains raw image bytes or signed object URLs.

## Contacts

| Method   | Path                           | Purpose                  |
| -------- | ------------------------------ | ------------------------ |
| `GET`    | `/api/v1/contacts`             | List contacts            |
| `POST`   | `/api/v1/contacts`             | Create a contact         |
| `GET`    | `/api/v1/contacts/{contactId}` | Read a contact           |
| `PATCH`  | `/api/v1/contacts/{contactId}` | Update a contact         |
| `DELETE` | `/api/v1/contacts/{contactId}` | Delete an unused contact |

List parameters: `search` across name/email, `companyId`, `sortBy` (`last_name`, `first_name`, `created_at`, `updated_at`) and `sortOrder`.

A contact requires a company in the same organisation and a syntactically valid email address.

## Opportunities

| Method   | Path                                                                        | Purpose                                                        |
| -------- | --------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `GET`    | `/api/v1/opportunities`                                                     | List opportunities                                             |
| `POST`   | `/api/v1/opportunities`                                                     | Create an opportunity                                          |
| `GET`    | `/api/v1/opportunities/{opportunityId}`                                     | Read an opportunity                                            |
| `PATCH`  | `/api/v1/opportunities/{opportunityId}`                                     | Update an opportunity                                          |
| `DELETE` | `/api/v1/opportunities/{opportunityId}`                                     | Delete an unused opportunity                                   |
| `GET`    | `/api/v1/opportunities/{opportunityId}/workspace`                           | Read the latest-meeting Opportunity Workspace                  |
| `POST`   | `/api/v1/opportunities/{opportunityId}/workspace/latest-meeting-navigation` | Record metadata-only navigation to the selected latest meeting |
| `POST`   | `/api/v1/opportunities/{opportunityId}/brain/reasoning`                     | Create or reuse deterministic opportunity comparisons          |
| `GET`    | `/api/v1/opportunities/{opportunityId}/brain/reasoning`                     | Read the latest opportunity comparison and bounded history     |

List parameters: `search`, `companyId`, `stage`, `status`, `sortBy` (`name`, `estimated_value`, `expected_close_date`, `created_at`, `updated_at`) and `sortOrder`. Items include company display name, deterministic latest active meeting date, current qualitative momentum and a bounded Next Best Action preview when valid. The web list defaults to `updated_at DESC`.

Company is optional. Estimated value and currency must either both be null or both be supplied; value is a non-negative fixed-precision decimal and currency is a three-letter uppercase code. Expected close is an optional user-managed date. Updates accept optional `expectedUpdatedAt` and return `409 stale_write` when the record changed. Stages are `qualification`, `discovery`, `evaluation`, `proposal`, `negotiation`, `procurement`, `closed_won`, `closed_lost` and `other`; statuses are `open`, `won`, `lost` and `on_hold`. Probability and forecast categories do not exist.

The workspace returns display metadata, the deterministic latest associated
meeting, at most 20 newest recent associated meetings, product-safe readiness,
the ten existing capability states/results for the latest meeting's current
transcript version, the optional latest validated post-interaction
`reportedIntelligence` composition and the current read-only Revenue Brain reasoning state.
Cancelled and soft-deleted meetings are excluded; ordering is
`meeting_date DESC, meeting UUID DESC`. It never returns transcript text or AI
infrastructure trace and never starts intelligence or reasoning generation. See
[Opportunity Workspace](opportunity-workspace.md) for trace and empty-state
rules.

Opportunity reasoning uses the same modes, strict contract and source boundary
as account reasoning, but both selected snapshots and their meetings must carry
the exact opportunity association. Account and opportunity idempotency scopes
are separate.

## Tasks

| Method   | Path                     | Purpose       |
| -------- | ------------------------ | ------------- |
| `GET`    | `/api/v1/tasks`          | List tasks    |
| `POST`   | `/api/v1/tasks`          | Create a task |
| `GET`    | `/api/v1/tasks/{taskId}` | Read a task   |
| `PATCH`  | `/api/v1/tasks/{taskId}` | Update a task |
| `DELETE` | `/api/v1/tasks/{taskId}` | Delete a task |

List parameters: `search`, `companyId`, `contactId`, `opportunityId`, `assignedUserId`, `status`, `priority`, `sortBy` (`due_at`, `title`, `priority`, `created_at`, `updated_at`) and `sortOrder`.

A task may be general or linked to records. If company, contact or opportunity links are present, they must resolve to one company in the current organisation. The service derives the company from a contact/opportunity when needed. Due timestamps must contain a timezone.

## Interactions

| Method  | Path                                            | Purpose                              |
| ------- | ----------------------------------------------- | ------------------------------------ |
| `GET`   | `/api/v1/interactions`                          | List active tenant Interactions      |
| `POST`  | `/api/v1/interactions`                          | Create a manual Interaction          |
| `GET`   | `/api/v1/interactions/{interactionId}`          | Read an active Interaction           |
| `PATCH` | `/api/v1/interactions/{interactionId}`          | Update metadata/lifecycle            |
| `POST`  | `/api/v1/interactions/{interactionId}/start`    | Idempotently start an Interaction    |
| `POST`  | `/api/v1/interactions/{interactionId}/complete` | Idempotently complete an Interaction |

List filters are `search`, `companyId`, `opportunityId`, `interactionType`,
`status`, timezone-aware `dateFrom`/`dateTo`, `sortBy` and `sortOrder`. Pagination
is bounded and deterministic. Organisation context is server-authoritative;
cross-tenant resources are hidden. See [Interaction API](interaction-api.md) for
the complete contract and lifecycle behaviour.

`phone_call` create/update supports tenant-validated `contactId`, controlled
`callDirection` and controlled completion `callOutcome`. Responses add derived
duration, capture methods, recording availability and intelligence readiness.
Imported call recordings use the recording endpoints below with required controlled
`recordingSource` and authority attestation; there is no telephony-capture endpoint.

### Post-interaction debrief

| Method | Path                                                                      | Purpose                                      |
| ------ | ------------------------------------------------------------------------- | -------------------------------------------- |
| `POST` | `/api/v1/interactions/{interactionId}/debrief`                            | Start/reuse AI Debrief or Voice Journal      |
| `GET`  | `/api/v1/interactions/{interactionId}/debrief/{sessionId}`                | Restore the private session and review state |
| `POST` | `/api/v1/interactions/{interactionId}/debrief/{sessionId}/response`       | Submit one typed answer                      |
| `POST` | `/api/v1/interactions/{interactionId}/debrief/{sessionId}/voice-response` | Submit one bounded voice answer              |
| `POST` | `/api/v1/interactions/{interactionId}/debrief/{sessionId}/finish`         | Extract reviewable candidate Evidence        |
| `POST` | `/api/v1/interactions/{interactionId}/debrief/{sessionId}/review`         | Apply complete accept/edit/reject review     |
| `POST` | `/api/v1/interactions/{interactionId}/debrief/{sessionId}/cancel`         | Cancel the capture                           |

Start requires a completed Interaction, current notice acknowledgement,
safe-driving confirmation, enabled feature and idempotency key. Voice additionally
requires explicit voice-processing acknowledgement and allowlisted base64 audio,
MIME, duration and size. Responses expose product-safe lifecycle, questions, turns,
candidates and resulting snapshot IDs; they never expose audio or provider payloads.
See [AI Debrief](ai-debrief.md).

### Visual evidence

| Method   | Path                                                                       | Purpose                                      |
| -------- | -------------------------------------------------------------------------- | -------------------------------------------- |
| `POST`   | `/api/v1/interactions/{interactionId}/visual-evidence/uploads`             | Create/reuse a private upload grant          |
| `PUT`    | `/api/v1/interactions/{interactionId}/visual-evidence/{visualId}/content`  | Upload bytes in local-storage mode           |
| `GET`    | `/api/v1/interactions/{interactionId}/visual-evidence`                     | List current visual metadata/review state    |
| `GET`    | `/api/v1/interactions/{interactionId}/visual-evidence/{visualId}`          | Read one visual metadata/review record       |
| `GET`    | `/api/v1/interactions/{interactionId}/visual-evidence/{visualId}/content`  | Download with a short-lived private grant    |
| `POST`   | `/api/v1/interactions/{interactionId}/visual-evidence/{visualId}/complete` | Verify, sanitise and finalise an upload      |
| `POST`   | `/api/v1/interactions/{interactionId}/visual-evidence/{visualId}/process`  | Run bounded strict visual analysis           |
| `POST`   | `/api/v1/interactions/{interactionId}/visual-evidence/{visualId}/review`   | Apply complete accept/edit/reject review     |
| `DELETE` | `/api/v1/interactions/{interactionId}/visual-evidence/{visualId}`          | Delete object and invalidate current sources |

Requests accept JPEG/PNG only and enforce checksum, size, dimension, pixel,
source-ownership, consent and idempotency constraints. Relative local upload
URLs require API auth; absolute S3-compatible signed URLs receive no RevenueOS
bearer token. See [Visual Evidence engineering guide](visual-evidence-engineering-guide.md).

### Recording and transcription

The Interaction API exposes consent-gated recording create/start/pause/resume/stop,
resumable chunk create/list/upload/complete, idempotent finalise/cancel/delete and
product-safe transcription status routes. WebM/Opus and MP4/M4A are allowlisted;
bytes remain in private object storage and batch transcription runs in the existing
worker. The complete route table and safe error boundary are documented in
[Interaction API](interaction-api.md) and the
[recording foundation guide](recording-foundation-engineering-guide.md).

## Meetings

Every Meeting is linked one-to-one to an Interaction. Existing request paths,
bodies and IDs remain unchanged; responses add backward-compatible
`interactionId`. Creating, updating, associating or soft-deleting a Meeting keeps
the shared Interaction projection aligned in the same transaction.

| Method   | Path                                       | Purpose                                                               |
| -------- | ------------------------------------------ | --------------------------------------------------------------------- |
| `GET`    | `/api/v1/meetings`                         | List active meetings                                                  |
| `POST`   | `/api/v1/meetings`                         | Create a meeting, optionally with initial participants and transcript |
| `GET`    | `/api/v1/meetings/{meetingId}`             | Read an active meeting                                                |
| `PATCH`  | `/api/v1/meetings/{meetingId}`             | Update meeting metadata                                               |
| `PATCH`  | `/api/v1/meetings/{meetingId}/opportunity` | Associate or disassociate one same-tenant opportunity                 |
| `DELETE` | `/api/v1/meetings/{meetingId}`             | Soft-delete a meeting and its active children                         |
| `GET`    | `/api/v1/meetings/{meetingId}/history`     | List content-minimised audit events                                   |

List parameters: `search`, `companyId`, `status`, `meetingType`, `dateFrom`, `dateTo`, `sortBy` (`meeting_date`, `title`, `created_at`, `updated_at`) and `sortOrder`. Dates must include a timezone. `meetingType` is `remote`, `phone`, `in_person` or `other`; status is `scheduled`, `completed` or `cancelled`.

Company and owner are optional/defaulted as documented by the schema, but any supplied relationship must resolve inside the trusted organisation. Meeting create is transactional across initial meeting, participant, transcript and audit rows. The opportunity association body contains nullable `opportunityId` and required timezone-aware `expectedUpdatedAt`; it locks the meeting, rejects stale or cross-company/cross-tenant writes and audits metadata only.

## Meeting participants

| Method   | Path                                                        | Purpose                   |
| -------- | ----------------------------------------------------------- | ------------------------- |
| `GET`    | `/api/v1/meetings/{meetingId}/participants`                 | List active participants  |
| `POST`   | `/api/v1/meetings/{meetingId}/participants`                 | Add a participant         |
| `GET`    | `/api/v1/meetings/{meetingId}/participants/{participantId}` | Read a participant        |
| `PATCH`  | `/api/v1/meetings/{meetingId}/participants/{participantId}` | Update a participant      |
| `DELETE` | `/api/v1/meetings/{meetingId}/participants/{participantId}` | Soft-delete a participant |

A participant requires at least one of a same-tenant contact, display name or valid email. Attendance is `invited`, `attended`, `absent` or `unknown`; role is `host` or `attendee`.

## Meeting transcript

| Method   | Path                                      | Purpose                          |
| -------- | ----------------------------------------- | -------------------------------- |
| `GET`    | `/api/v1/meetings/{meetingId}/transcript` | Read the active transcript       |
| `POST`   | `/api/v1/meetings/{meetingId}/transcript` | Create or restore a transcript   |
| `PATCH`  | `/api/v1/meetings/{meetingId}/transcript` | Correct transcript text/language |
| `DELETE` | `/api/v1/meetings/{meetingId}/transcript` | Soft-delete the transcript       |

There is at most one current transcript row per meeting. Plain text is required and
limited to one million characters. Source is `manual`, `upload`, `recorded_audio`,
`uploaded_audio` or `imported_audio`; `upload` means the web form read a
user-selected `.txt` file. Every current revision has an immutable
`transcript_versions` history record; recorded versions may also have ordered
timestamp segments and Recording Session traceability. `PATCH` requires the current
positive `version`, increments it on success and returns
`409 transcript_version_conflict` for stale writes. Transcript permissions are
inherited from the active tenant-scoped meeting.

## Unified Meeting Intelligence

| Method | Path                                                 | Purpose                                                                                  |
| ------ | ---------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `GET`  | `/api/v1/meetings/{meetingId}/intelligence`          | Read all ten current-version capability states and content through one product-safe view |
| `POST` | `/api/v1/meetings/{meetingId}/intelligence/generate` | Create or reuse missing extraction work and conditionally queue both composers           |

GET returns a derived overall state, generation/retry availability, last activity
time, deterministic progress counts and the ten ordered capability views. Valid
empty lists are completed with `emptyResult=true`. The response excludes job and
artefact IDs, transcript/prompts, provider/model and schema configuration, worker
fields, internal error codes and raw errors.

Later polling reads may include the optional safe query metadata
`previousOverallState` and `pollingEvent=started|continued`. These values are
validated enums used only for metadata-only transition and polling lifecycle
logs; they do not alter the aggregate result.

POST reuses the eight extraction request services and creates only
missing/failed/cancelled work for the current transcript. It queues Next Best
Action after all eight artefacts are complete and Follow-up Email after matching
Executive Summary, Decisions, Action Items and Open Questions artefacts are
complete. New work returns `202`; complete reuse returns
`200`. The endpoint never calls a provider inline. All individual endpoints below
remain supported. See
[Unified Meeting Intelligence](unified-meeting-intelligence.md) for state
precedence, idempotency, polling and privacy rules.

## Executive Summary intelligence

| Method | Path                                                          | Purpose                               |
| ------ | ------------------------------------------------------------- | ------------------------------------- |
| `POST` | `/api/v1/meetings/{meetingId}/intelligence/executive-summary` | Queue or return equivalent generation |
| `GET`  | `/api/v1/meetings/{meetingId}/intelligence/executive-summary` | Read current safe state/result        |

POST verifies the trusted tenant meeting and a non-empty current transcript of
at most 50,000 trimmed characters. It never generates inline. A newly queued job
returns `202`; an equivalent pending/running/completed job returns `200`.
Equivalence includes transcript, job type, prompt version and schema version.
Failed/cancelled work can be retried with a new job, and a transcript correction
requires a new version-specific job.

GET returns `empty`, `queued`, `running`, `completed`, `failed` or `cancelled`,
generation availability, safe timestamps/message and completed schema content
when available. It never exposes worker identity, leases, prompt text, provider
payload, raw errors or transcript text.

## Buying Signals and Deal Momentum intelligence

| Method | Path                                                       | Purpose                                              |
| ------ | ---------------------------------------------------------- | ---------------------------------------------------- |
| `POST` | `/api/v1/meetings/{meetingId}/intelligence/buying-signals` | Queue or return equivalent Buying Signals generation |
| `GET`  | `/api/v1/meetings/{meetingId}/intelligence/buying-signals` | Read current safe state/result                       |

POST requires trusted tenant access and a non-empty current transcript of at
most 50,000 trimmed characters. New asynchronous work returns `202`; an
equivalent pending, running or completed prompt/schema v1 job returns `200`.
Failed/cancelled work follows the established ordinal retry rule and a
transcript correction permits a new version-bound job.

GET returns the established lifecycle state, generation availability, safe
timestamps/message and validated `buyingSignals` content. A successful result
may contain no signals with `insufficient_evidence`. The result contains only
normalised signals, qualitative current-meeting momentum, a grounded summary
and evidence confidence. It contains no close probability, forecast or deal
score, and excludes all internal/provider/worker/prompt/transcript fields. See
[Buying Signals and Deal Momentum intelligence](buying-signals-intelligence.md).

## Objections & Competitive Signals intelligence

| Method | Path                                                                       | Purpose                                                            |
| ------ | -------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `POST` | `/api/v1/meetings/{meetingId}/intelligence/objections-competitive-signals` | Queue or return equivalent objection/competitive-signal generation |
| `GET`  | `/api/v1/meetings/{meetingId}/intelligence/objections-competitive-signals` | Read current safe state/result                                     |

POST requires trusted tenant access and the non-empty current transcript, capped
at 50,000 trimmed characters without truncation. New asynchronous work returns
`202`; an equivalent pending, running or completed prompt/schema v1 job returns
`200`. Failed/cancelled work follows the established ordinal retry rule, while a
transcript correction permits a new version-bound job.

GET returns the established lifecycle state, generation availability, safe
timestamps/message and validated `objectionsCompetitiveSignals` content. Empty
objection and competitor lists are successful. The result contains qualitative
current-meeting objection pressure, not close/loss probability, a forecast or a
numeric score, and excludes internal/provider/worker/prompt/transcript fields.
See [Objections & Competitive Signals intelligence](objections-competitive-signals-intelligence.md).

## Stakeholder Intelligence

| Method | Path                                                     | Purpose                                                        |
| ------ | -------------------------------------------------------- | -------------------------------------------------------------- |
| `POST` | `/api/v1/meetings/{meetingId}/intelligence/stakeholders` | Queue or return equivalent Stakeholder Intelligence generation |
| `GET`  | `/api/v1/meetings/{meetingId}/intelligence/stakeholders` | Read current safe stakeholder state/result                     |

POST requires trusted tenant access and the non-empty current transcript, capped
at 50,000 trimmed characters without truncation. New asynchronous work returns
`202`; an equivalent pending, running or completed prompt/schema v1 job returns
`200`. Failed/cancelled work follows the ordinal retry rule and a transcript
correction permits a new version-bound job.

GET returns the established lifecycle state, generation availability, safe
timestamps/message and validated `stakeholderIntelligence` content. An empty
stakeholder list is successful. Content contains evidence-backed current-meeting
roles, qualitative influence/stance/engagement, six fixed coverage states and
confidence. It contains no relationship history, graph, CRM identity, MEDDICC/
BANT or predictive score, and excludes internal/provider/worker/prompt/
transcript fields. See [Stakeholder Intelligence](stakeholder-intelligence.md).

## Next Best Action Intelligence

| Method | Path                                                         | Purpose                                                       |
| ------ | ------------------------------------------------------------ | ------------------------------------------------------------- |
| `POST` | `/api/v1/meetings/{meetingId}/intelligence/next-best-action` | Queue or return equivalent validated-intelligence composition |
| `GET`  | `/api/v1/meetings/{meetingId}/intelligence/next-best-action` | Read current safe recommendation state/result                 |

POST requires all eight validated extraction artefacts for the current trusted
tenant, meeting and transcript trace. It queues durable work with
`next_best_action` prompt/schema v1 and returns `202`; equivalent pending,
running or completed work returns `200`. Missing, stale, invalid or mismatched
sources fail closed with `next_best_action_sources_required`.

GET returns the established lifecycle state, safe generation availability,
timestamps/message and validated `nextBestAction` content. Content contains one
overall recommendation, priority, confidence, grounded reasoning and one to
five ordered recommended actions with constrained source dependencies. It
contains no transcript, Follow-up Email source, prompt/provider/worker details
or operational control. See
[Next Best Action Intelligence](next-best-action-intelligence.md).

## Decisions intelligence

| Method | Path                                                  | Purpose                                         |
| ------ | ----------------------------------------------------- | ----------------------------------------------- |
| `POST` | `/api/v1/meetings/{meetingId}/intelligence/decisions` | Queue or return equivalent Decisions generation |
| `GET`  | `/api/v1/meetings/{meetingId}/intelligence/decisions` | Read current safe state/result                  |

POST authenticates, derives the active organisation and requires the current
same-tenant transcript to be non-empty and at most 50,000 trimmed characters.
A new asynchronous job returns `202`; an equivalent pending, running or
completed Decisions job returns `200`. Equivalence includes transcript version,
job type, prompt v1 and schema v1. Failed/cancelled work can create an ordinal
retry; a corrected transcript permits a new job. Executive Summary remains
independent.

GET returns `empty`, `queued`, `running`, `completed`, `failed` or `cancelled`,
generation availability, product-safe reason/message, safe timestamps and the
latest completed `decisions` object. An empty decisions list is a successful
completed result. Responses exclude worker/lease fields, internal error codes,
prompt/transcript content, provider configuration and raw responses. See
[Meeting Decisions intelligence](meeting-decisions-intelligence.md) for schema
v1, polling, idempotency and privacy details.

## Action Items intelligence

| Method | Path                                                     | Purpose                                            |
| ------ | -------------------------------------------------------- | -------------------------------------------------- |
| `POST` | `/api/v1/meetings/{meetingId}/intelligence/action-items` | Queue or return equivalent Action Items generation |
| `GET`  | `/api/v1/meetings/{meetingId}/intelligence/action-items` | Read current safe state/result                     |

POST derives the tenant from authentication, requires the current same-tenant
transcript to be non-empty and at most 50,000 trimmed characters, and never
generates inline. A new job returns `202`; an equivalent pending, running or
completed job for Action Items prompt/schema v1 returns `200`. Failed or
cancelled work may receive a new ordinal retry, and a transcript correction
permits a new version-bound job. Summary and Decisions remain independent.

GET supports `empty`, `queued`, `running`, `completed`, `failed` and
`cancelled`, with generation availability, safe timestamps/message and the
latest completed `actionItems` object. An empty list is successful. Responses
exclude worker/lease fields, internal error codes, prompt/transcript content,
provider configuration and raw responses. See
[Meeting Action Items intelligence](meeting-action-items-intelligence.md) for
schema, date, polling, idempotency and privacy rules.

## Risks & Blockers intelligence

| Method | Path                                                       | Purpose                                                |
| ------ | ---------------------------------------------------------- | ------------------------------------------------------ |
| `POST` | `/api/v1/meetings/{meetingId}/intelligence/risks-blockers` | Queue or return equivalent Risks & Blockers generation |
| `GET`  | `/api/v1/meetings/{meetingId}/intelligence/risks-blockers` | Read current safe state/result                         |

POST derives the tenant from authentication, requires the current same-tenant
transcript to be non-empty and at most 50,000 trimmed characters, and never
generates inline. New work returns `202`; an equivalent pending, running or
completed job for prompt/schema v1 returns `200`. Failed/cancelled work may be
retried and transcript changes permit a new version-bound job. Existing
intelligence jobs remain independent.

GET supports all six existing lifecycle states and returns safe timestamps,
messages and the latest completed `risksBlockers` object. An empty `risks`
list is successful. Worker/lease fields, prompts, transcripts, raw errors,
provider responses and internal configuration are excluded. See
[Meeting Risks & Blockers intelligence](meeting-risks-blockers-intelligence.md).

## Open Questions intelligence

| Method | Path                                                       | Purpose                                              |
| ------ | ---------------------------------------------------------- | ---------------------------------------------------- |
| `POST` | `/api/v1/meetings/{meetingId}/intelligence/open-questions` | Queue or return equivalent Open Questions generation |
| `GET`  | `/api/v1/meetings/{meetingId}/intelligence/open-questions` | Read current safe state/result                       |

POST derives the tenant from authentication, requires the current same-tenant
transcript to be non-empty and at most 50,000 trimmed characters, and never
generates inline. New work returns `202`; an equivalent pending, running or
completed job for prompt/schema v1 returns `200`. Failed/cancelled work may be
retried and transcript changes permit a new version-bound job. Existing
intelligence jobs remain independent.

GET supports all six lifecycle states and returns safe timestamps, messages and
the latest completed `openQuestions` object. An empty `openQuestions` list is
successful. Worker/lease fields, prompts, transcripts, raw errors, provider
responses and internal configuration are excluded. See
[Meeting Open Questions intelligence](meeting-open-questions-intelligence.md).

## Follow-up Email Composer

| Method | Path                                                        | Purpose                                                        |
| ------ | ----------------------------------------------------------- | -------------------------------------------------------------- |
| `POST` | `/api/v1/meetings/{meetingId}/intelligence/follow-up-email` | Queue, reuse or regenerate a validated-artefact-grounded draft |
| `GET`  | `/api/v1/meetings/{meetingId}/intelligence/follow-up-email` | Read current safe state/draft                                  |

POST accepts `tone` as exactly `professional`, `friendly` or `executive`
(`professional` by default). Generation is available only when validated
Executive Summary, Decisions, Action Items and Open Questions artefacts exist
for the same current transcript version. It never loads transcript text and
never consumes Risks & Blockers. New work returns `202`; an equivalent pending
or running job returns `200`. Completed work may be deliberately regenerated as
a new append-only job/artefact.

GET supports `empty`, `queued`, `running`, `completed`, `failed` and
`cancelled`. It returns generation availability, a safe unavailability reason
or message, safe timestamps, tone and completed `followUpEmail` content. The
strict result contains subject, greeting, summary, decision/action/open-
question arrays, closing, tone and confidence. It excludes source artefacts,
transcript, risks, evidence, prompts, raw errors, worker fields and provider
payloads. See [Follow-up Email Composer](follow-up-email-composer.md).

## AI Companion preparation

| Method | Path                                                          | Purpose                                                   |
| ------ | ------------------------------------------------------------- | --------------------------------------------------------- |
| `GET`  | `/api/v1/interactions/{interactionId}/companion/brief`        | Read latest safe brief state, content and bounded history |
| `POST` | `/api/v1/interactions/{interactionId}/companion/brief`        | Deterministically create or reuse an equivalent brief     |
| `POST` | `/api/v1/interactions/{interactionId}/companion/brief/review` | Idempotently append review user/time metadata             |

The active tenant is server-derived. Generation requires `aiCompanion`, the
current data-notice acknowledgement and available daily generation quota. Version
1 is bounded synchronous application work with no provider/worker call. Responses
contain product-safe source labels but no raw source IDs, transcript, raw artefact,
prompt, schema-registry, provider or worker metadata. See the
[Pre-Interaction Brief guide](pre-interaction-brief.md).

## Document and email evidence

All routes require the trusted active organisation; callers never supply an
organisation ID.

| Method | Route                                     | Behaviour                                                              |
| ------ | ----------------------------------------- | ---------------------------------------------------------------------- |
| GET    | `/api/v1/evidence/capabilities`           | Flags, supported media and honest connector availability               |
| POST   | `/api/v1/evidence/documents`              | Deliberate PDF/TXT upload with checksum and authority acknowledgements |
| GET    | `/api/v1/evidence/documents/{id}`         | Metadata, processing state and candidates; no content                  |
| GET    | `/api/v1/evidence/documents/{id}/content` | Authenticated short-lived private download                             |
| POST   | `/api/v1/evidence/documents/{id}/process` | Bounded parse/extract transition                                       |
| POST   | `/api/v1/evidence/documents/{id}/review`  | Complete accept/edit/reject review                                     |
| DELETE | `/api/v1/evidence/documents/{id}`         | Object-first deletion and lineage removal                              |
| POST   | `/api/v1/evidence/emails`                 | Deliberate plain-text paste with source/direction                      |
| GET    | `/api/v1/evidence/emails/{id}`            | Metadata and candidates; no body                                       |
| POST   | `/api/v1/evidence/emails/{id}/process`    | Normalised strict extraction                                           |
| POST   | `/api/v1/evidence/emails/{id}/review`     | Complete accept/edit/reject review                                     |
| DELETE | `/api/v1/evidence/emails/{id}`            | Body clearing and lineage removal                                      |
| GET    | `/api/v1/evidence/opportunities/{id}`     | Reviewed accepted source evidence                                      |
| GET    | `/api/v1/evidence/accounts/{id}/brain`    | Immutable reviewed source snapshots                                    |

Create requests require an idempotency key, source time, at least one association,
`authorityConfirmed=true` and `externalProcessingAcknowledged=true`. Review must
decide every pending candidate, including an explicit empty decision list for a
zero-finding source. Safe errors contain a code, message and request ID.

## Live Interaction Intelligence

| Method | Route                                                            | Behaviour                                               |
| ------ | ---------------------------------------------------------------- | ------------------------------------------------------- |
| GET    | `/api/v1/interactions/{id}/live-intelligence`                    | Availability/current provisional state                  |
| POST   | `/api/v1/interactions/{id}/live-intelligence/start`              | Explicit start against an authorised progressive source |
| POST   | `/api/v1/interactions/{id}/live-intelligence/process`            | Idempotent bounded incremental update                   |
| POST   | `/api/v1/interactions/{id}/live-intelligence/stop`               | User-controlled stop/freeze                             |
| POST   | `/api/v1/interactions/{id}/live-intelligence/{signalId}/dismiss` | Dismiss one tenant-owned provisional signal             |
| POST   | `/api/v1/interactions/{id}/live-intelligence/reconcile`          | Persist final comparison outcomes                       |

All routes derive tenant context from verified authentication. Process accepts only a
bounded idempotency key; transcript version, cursor and windows are server-owned.
Public responses contain no raw transcript, internal fingerprints or provider data.
The feature flag defaults off and unavailable sources return a Debrief fallback.

## Scope boundary

There are no generic AI job/artefact, provider configuration/model listing,
cancellation, external live-provider, question-answering, real email sending,
calendar/CRM mutation, billing, worker-control or automation
endpoints. Mock/OpenAI selection and beta flags are server-side configuration
and do not create generic provider control endpoints. Clerk tokens are verified
by the API; production fails closed without complete configuration.

## Action Layer routes

- `POST /api/v1/opportunities/{opportunity_id}/actions/generate`
- `GET /api/v1/opportunities/{opportunity_id}/actions?status=...`
- `GET|PATCH /api/v1/actions/{action_id}`
- `POST /api/v1/actions/{action_id}/approve`
- `POST /api/v1/actions/{action_id}/reject`
- `POST /api/v1/actions/{action_id}/complete`

Payloads are strict discriminated unions. Review mutations require
`expectedVersion`. Approval reports `not_executed`; no route dispatches an external
action. Generation/listing derive the organisation from verified auth context.

## Simulation integration and execution routes

| Method | Route | Behaviour |
| --- | --- | --- |
| `GET` | `/api/v1/integrations` | Server-owned mock connector catalog |
| `GET` | `/api/v1/integrations/connections` | Tenant connection metadata |
| `POST` | `/api/v1/integrations/connections` | Administrator enables one mock connector |
| `GET` | `/api/v1/integrations/connections/{id}` | Read tenant connection |
| `POST` | `/api/v1/integrations/connections/{id}/test` | Administrator runs no-network readiness test |
| `DELETE` | `/api/v1/integrations/connections/{id}` | Administrator revokes and invalidates pending work |
| `GET` | `/api/v1/actions/{id}/execution-options` | Server-derived active connection and capability options for the approved Action |
| `POST` | `/api/v1/actions/{id}/execution-preview` | Reconstruct exact approved content and fingerprint preview |
| `POST` | `/api/v1/actions/{id}/execute` | Confirm only preview, connection and literal true |
| `GET` | `/api/v1/actions/{id}/executions` | Read tenant-scoped simulation history |
| `GET` | `/api/v1/executions/{id}` | Read status and immutable attempts |

Connection management is administrator-only; active members may use an active
connection. Responses expose simulation labels and safe metadata only. No route
accepts credentials, provider tokens, Action content at confirmation, a live-mode
switch or arbitrary connector capabilities.

## Sales Methodology routes

| Method | Route | Behaviour |
| --- | --- | --- |
| `GET` | `/api/v1/methodologies` | Standards, tenant custom definitions, current default and safe limits |
| `GET` | `/api/v1/methodologies/current` | Effective organisation selection |
| `PATCH` | `/api/v1/methodologies/current` | Administrator selects standard, custom or none |
| `POST` | `/api/v1/methodologies/custom` | Administrator creates immutable custom v1 |
| `PATCH` | `/api/v1/methodologies/custom/{id}` | Administrator creates the next version |
| `DELETE` | `/api/v1/methodologies/custom/{id}` | Administrator archives; history remains |
| `POST` | `/api/v1/opportunities/{id}/methodology/generate` | Idempotently project current validated sources |
| `GET` | `/api/v1/opportunities/{id}/methodology` | Current view or safe refresh/empty state |
| `GET` | `/api/v1/opportunities/{id}/methodology/history` | Bounded immutable summaries |
| `POST` | `/api/v1/opportunities/{id}/methodology/{fieldKey}/review` | Immutable interpretation review/clarification |

All payloads are strict and product-safe. The API never accepts organisation IDs,
arbitrary rules/prompts, source conclusions, provider choices or scores. Current
reads hide a stale projection's conclusions when the source fingerprint changes.
