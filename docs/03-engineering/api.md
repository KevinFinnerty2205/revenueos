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

## Scope boundary

There are no recording, media upload/storage, transcription, AI, email, calendar, CRM, billing, worker or automation endpoints. Clerk token verification is not connected.
