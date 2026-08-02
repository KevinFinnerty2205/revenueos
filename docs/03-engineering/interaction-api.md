# Interaction API

All routes use `/api/v1`, require an authenticated active organisation membership,
derive the tenant from verified server context and return camel-case JSON. Supplying
`organisationId` is rejected. Missing or cross-tenant resources return the same safe
not-found response and cannot be enumerated.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/interactions` | List active Interactions with stable pagination and filters |
| `POST` | `/interactions` | Create one manual Interaction |
| `GET` | `/interactions/{interactionId}` | Read one active Interaction |
| `PATCH` | `/interactions/{interactionId}` | Update supplied fields and lifecycle |
| `POST` | `/interactions/{interactionId}/complete` | Idempotently complete an Interaction |

There is deliberately no delete, Capture Session or Evidence endpoint in WO-011.

## Create and update fields

`title` is required on create and is trimmed, non-empty and at most 200 characters.
`interactionType` uses the controlled ten-value taxonomy. `lifecycleStatus`
defaults to `planned`. Optional `companyId` and `opportunityId` must resolve in the
active tenant and must not conflict. Optional `scheduledStartAt`, `scheduledEndAt`,
`actualStartAt` and `actualEndAt` require timezone offsets and are stored/returned in
UTC. End values cannot precede starts. `timezone` is an optional label up to 64
characters.

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
are hidden.

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
