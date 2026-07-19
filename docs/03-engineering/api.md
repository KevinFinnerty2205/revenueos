# API reference

FastAPI's generated OpenAPI document at `/openapi.json` is canonical. Swagger UI is available at `/docs` in the current application configuration. JSON fields use camel case; database and Python fields use snake case.

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

## Companies

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/companies` | List companies |
| `POST` | `/api/v1/companies` | Create a company |
| `GET` | `/api/v1/companies/{companyId}` | Read a company |
| `PATCH` | `/api/v1/companies/{companyId}` | Update a company |
| `DELETE` | `/api/v1/companies/{companyId}` | Delete an unused company |

List parameters: `search`, `status`, `industry`, `sortBy` (`name`, `created_at`, `updated_at`) and `sortOrder`.

## Contacts

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/contacts` | List contacts |
| `POST` | `/api/v1/contacts` | Create a contact |
| `GET` | `/api/v1/contacts/{contactId}` | Read a contact |
| `PATCH` | `/api/v1/contacts/{contactId}` | Update a contact |
| `DELETE` | `/api/v1/contacts/{contactId}` | Delete an unused contact |

List parameters: `search` across name/email, `companyId`, `sortBy` (`last_name`, `first_name`, `created_at`, `updated_at`) and `sortOrder`.

A contact requires a company in the same organisation and a syntactically valid email address.

## Opportunities

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/opportunities` | List opportunities |
| `POST` | `/api/v1/opportunities` | Create an opportunity |
| `GET` | `/api/v1/opportunities/{opportunityId}` | Read an opportunity |
| `PATCH` | `/api/v1/opportunities/{opportunityId}` | Update an opportunity |
| `DELETE` | `/api/v1/opportunities/{opportunityId}` | Delete an unused opportunity |

List parameters: `search`, `companyId`, `stage`, `sortBy` (`name`, `value`, `probability`, `expected_close_date`, `created_at`, `updated_at`) and `sortOrder`.

Values are non-negative fixed-precision decimals. Currency is a three-letter uppercase code and probability is 0–100.

## Tasks

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/tasks` | List tasks |
| `POST` | `/api/v1/tasks` | Create a task |
| `GET` | `/api/v1/tasks/{taskId}` | Read a task |
| `PATCH` | `/api/v1/tasks/{taskId}` | Update a task |
| `DELETE` | `/api/v1/tasks/{taskId}` | Delete a task |

List parameters: `search`, `companyId`, `contactId`, `opportunityId`, `assignedUserId`, `status`, `priority`, `sortBy` (`due_at`, `title`, `priority`, `created_at`, `updated_at`) and `sortOrder`.

A task may be general or linked to records. If company, contact or opportunity links are present, they must resolve to one company in the current organisation. The service derives the company from a contact/opportunity when needed. Due timestamps must contain a timezone.

## Meetings

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/meetings` | List active meetings |
| `POST` | `/api/v1/meetings` | Create a meeting, optionally with initial participants and transcript |
| `GET` | `/api/v1/meetings/{meetingId}` | Read an active meeting |
| `PATCH` | `/api/v1/meetings/{meetingId}` | Update meeting metadata |
| `DELETE` | `/api/v1/meetings/{meetingId}` | Soft-delete a meeting and its active children |
| `GET` | `/api/v1/meetings/{meetingId}/history` | List content-minimised audit events |

List parameters: `search`, `companyId`, `status`, `meetingType`, `dateFrom`, `dateTo`, `sortBy` (`meeting_date`, `title`, `created_at`, `updated_at`) and `sortOrder`. Dates must include a timezone. `meetingType` is `remote`, `phone`, `in_person` or `other`; status is `scheduled`, `completed` or `cancelled`.

Company and owner are optional/defaulted as documented by the schema, but any supplied relationship must resolve inside the trusted organisation. Meeting create is transactional across initial meeting, participant, transcript and audit rows.

## Meeting participants

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/meetings/{meetingId}/participants` | List active participants |
| `POST` | `/api/v1/meetings/{meetingId}/participants` | Add a participant |
| `GET` | `/api/v1/meetings/{meetingId}/participants/{participantId}` | Read a participant |
| `PATCH` | `/api/v1/meetings/{meetingId}/participants/{participantId}` | Update a participant |
| `DELETE` | `/api/v1/meetings/{meetingId}/participants/{participantId}` | Soft-delete a participant |

A participant requires at least one of a same-tenant contact, display name or valid email. Attendance is `invited`, `attended`, `absent` or `unknown`; role is `host` or `attendee`.

## Meeting transcript

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/meetings/{meetingId}/transcript` | Read the active transcript |
| `POST` | `/api/v1/meetings/{meetingId}/transcript` | Create or restore a transcript |
| `PATCH` | `/api/v1/meetings/{meetingId}/transcript` | Correct transcript text/language |
| `DELETE` | `/api/v1/meetings/{meetingId}/transcript` | Soft-delete the transcript |

There is at most one transcript row per meeting. Plain text is required and limited to one million characters. Source is `manual` or `upload`; `upload` means the web form read a user-selected `.txt` file, not that RevenueOS stored a file. `PATCH` requires the current positive `version`, increments it on success and returns `409 transcript_version_conflict` for stale writes. Transcript permissions are inherited from the active tenant-scoped meeting.

## Executive Summary intelligence

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/meetings/{meetingId}/intelligence/executive-summary` | Queue or return equivalent generation |
| `GET` | `/api/v1/meetings/{meetingId}/intelligence/executive-summary` | Read current safe state/result |

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

## Decisions intelligence

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/meetings/{meetingId}/intelligence/decisions` | Queue or return equivalent Decisions generation |
| `GET` | `/api/v1/meetings/{meetingId}/intelligence/decisions` | Read current safe state/result |

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

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/meetings/{meetingId}/intelligence/action-items` | Queue or return equivalent Action Items generation |
| `GET` | `/api/v1/meetings/{meetingId}/intelligence/action-items` | Read current safe state/result |

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

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/meetings/{meetingId}/intelligence/risks-blockers` | Queue or return equivalent Risks & Blockers generation |
| `GET` | `/api/v1/meetings/{meetingId}/intelligence/risks-blockers` | Read current safe state/result |

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

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/meetings/{meetingId}/intelligence/open-questions` | Queue or return equivalent Open Questions generation |
| `GET` | `/api/v1/meetings/{meetingId}/intelligence/open-questions` | Read current safe state/result |

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

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/meetings/{meetingId}/intelligence/follow-up-email` | Queue, reuse or regenerate a validated-artefact-grounded draft |
| `GET` | `/api/v1/meetings/{meetingId}/intelligence/follow-up-email` | Read current safe state/draft |

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

## Scope boundary

There are no generic AI job/artefact, provider configuration/model listing,
cancellation, recording, media upload/storage, transcription, later
intelligence, question-answering, email sending, calendar, CRM, billing,
worker-control or automation
endpoints. Mock/OpenAI selection is server-side worker configuration and does not
change this API contract. Clerk token verification is not connected.
