# Interaction API

All routes use `/api/v1`, require an authenticated active organisation membership,
derive the tenant from verified server context and return camel-case JSON. Supplying
`organisationId` is rejected. Missing or cross-tenant resources return the same safe
not-found response and cannot be enumerated.

## Endpoints

| Method  | Path                                                   | Purpose                                                     |
| ------- | ------------------------------------------------------ | ----------------------------------------------------------- |
| `GET`   | `/interactions`                                        | List active Interactions with stable pagination and filters |
| `POST`  | `/interactions`                                        | Create one manual Interaction                               |
| `GET`   | `/interactions/{interactionId}`                        | Read one active Interaction                                 |
| `PATCH` | `/interactions/{interactionId}`                        | Update supplied fields and lifecycle                        |
| `POST`  | `/interactions/{interactionId}/complete`               | Idempotently complete an Interaction                        |
| `GET`   | `/interactions/{interactionId}/companion/brief`        | Read product-safe preparation state/result                  |
| `POST`  | `/interactions/{interactionId}/companion/brief`        | Create or reuse a deterministic brief                       |
| `POST`  | `/interactions/{interactionId}/companion/brief/review` | Mark the latest completed brief reviewed                    |
| `POST`  | `/interactions/{interactionId}/visual-evidence/uploads` | Create/reuse a private visual upload grant                  |
| `PUT`   | `/interactions/{interactionId}/visual-evidence/{visualId}/content` | Upload bytes through the local private adapter      |
| `POST`  | `/interactions/{interactionId}/visual-evidence/{visualId}/complete` | Verify and sanitise the uploaded image             |
| `POST`  | `/interactions/{interactionId}/visual-evidence/{visualId}/process` | Produce bounded review candidates                   |
| `POST`  | `/interactions/{interactionId}/visual-evidence/{visualId}/review` | Accept/edit/reject every candidate                  |
| `GET`   | `/interactions/{interactionId}/visual-evidence`          | List visual metadata and review state                        |
| `GET`   | `/interactions/{interactionId}/visual-evidence/{visualId}` | Read one visual metadata/review record                      |
| `GET`   | `/interactions/{interactionId}/visual-evidence/{visualId}/content` | Download through a short-lived private grant      |
| `DELETE` | `/interactions/{interactionId}/visual-evidence/{visualId}` | Delete bytes and invalidate current lineage                |

There is deliberately no generic public Capture Session or Evidence endpoint.
Visual routes expose the narrow reviewed workflow only; they never expose a
freely supplied organisation ID or durable storage key.

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
joined into the list.

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
