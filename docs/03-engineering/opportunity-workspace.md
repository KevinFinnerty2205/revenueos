# Opportunity Workspace

## Purpose and current boundary

WO-007 adds the first opportunity-centred product read model. It combines
manually managed opportunity metadata with stored, validated intelligence from
the latest associated meeting so a salesperson can understand the current
commercial context quickly.

The workspace does not create intelligence. Opening or refreshing it performs
tenant-scoped database reads only: it does not read transcript text, render a
prompt, create an AI job or call a provider. All intelligence wording is
explicitly scoped to the latest meeting; it is not longitudinal opportunity
reasoning.

## Opportunity domain

`Opportunity` remains a tenant-owned business entity with these current fields:

- UUID identity and non-null `organisation_id`;
- nullable same-organisation `company_id`;
- required name;
- stage: `qualification`, `discovery`, `evaluation`, `proposal`,
  `negotiation`, `procurement`, `closed_won`, `closed_lost` or `other`;
- status: `open`, `won`, `lost` or `on_hold`;
- nullable `estimated_value` stored as non-negative `NUMERIC(18,2)`;
- nullable three-letter uppercase currency;
- nullable date-only expected close date;
- an owner backed by an active membership in the same organisation;
- nullable description; and
- UTC created and updated timestamps.

Value and currency form one optional pair. Both must be supplied together or
both must be null; currency without value is invalid. RevenueOS does not derive
value, currency or close date from meeting content. Calendar-invalid dates are
rejected by the API. No probability, forecast category or pipeline target is
stored or calculated.

Create and update operations resolve company and owner inside the authenticated
organisation. Updates may include `expectedUpdatedAt`; a changed timestamp
returns `409 stale_write` so an older browser cannot silently replace newer
metadata. Created, updated and deleted events use the established metadata-only
audit convention. Existing safe delete behaviour remains available, but no new
line-item or CRM lifecycle was introduced.

## Meeting association

`meetings.opportunity_id` is a nullable UUID. This is the smallest safe model
for the current one-meeting-to-zero-or-one-opportunity relationship and avoids
duplicating transcripts or intelligence.

The foreign key is composite on `organisation_id` and `opportunity_id`, so the
database cannot attach a meeting to an opportunity in another organisation.
The association service also applies explicit organisation predicates, rejects
company conflicts, locks the meeting row and compares `expectedUpdatedAt`.
Association and disassociation write content-minimised Meeting and Opportunity
audit events in the same transaction. The events contain identifiers, changed
field names and association state only; they contain no opportunity,
transcript or generated content.

Users associate or disassociate meetings from the Opportunity Workspace. The
selector is populated by the existing tenant-scoped Meetings API and excludes
meetings assigned to another opportunity. Meeting Detail shows a direct link
back to the associated opportunity. There is no automatic or AI-based matching.

## Latest meeting and recent meetings

The latest relevant meeting is selected from active meetings that match both
the authenticated organisation and opportunity. Soft-deleted and cancelled
meetings are excluded. The deterministic order is:

1. `meeting_date DESC`;
2. meeting UUID `DESC` as the tie-breaker.

The same order supplies at most 20 recent meetings. One bounded query returns
meeting metadata, company name, participant count and transcript ID/version
metadata; it never selects transcript text. Each recent item reports transcript
availability and a product-safe intelligence readiness count. This is a
deliberately bounded v1 view rather than meeting-history pagination.

## Intelligence selection and aggregation

For the one latest meeting, the aggregate response composes the existing ten
Meeting Intelligence capability contracts. A capability is eligible only when:

- its artefact, job, meeting and opportunity belong to the authenticated
  organisation;
- the artefact belongs to the latest meeting;
- its transcript version equals that meeting's current transcript version;
- the job completed successfully;
- job and artefact prompt key/version and schema version match the current
  registered capability; and
- the stored content still passes the capability's strict Pydantic validator.

The latest completed valid equivalent result is preferred, so a later failed
attempt cannot hide earlier completed current-version content. Valid empty
outputs remain successful results. Failed, cancelled, malformed, old-transcript,
other-meeting, cross-tenant or trace-inconsistent artefacts are excluded. The
Follow-up Email therefore retains its established source-trace consistency.
Capabilities are never mixed across meetings or transcript versions.

The list read model uses four bounded query groups: opportunity rows, total,
latest meeting per opportunity through a window function, and current Buying
Signals/Next Best Action preview artefacts. The workspace uses a fixed set of
bounded reads for opportunity metadata, recent meetings, readiness artefacts
and the latest meeting's existing jobs/artefacts. Query count does not grow per
opportunity, meeting, participant or capability; there is no N+1 loop.

## API contracts

- `GET /api/v1/opportunities` returns the paginated enriched list. It accepts
  `search`, `companyId`, `stage`, `status`, `sortBy` and `sortOrder`; the UI
  defaults to `updated_at DESC`.
- `POST /api/v1/opportunities` creates tenant-owned metadata.
- `GET /api/v1/opportunities/{opportunityId}` reads editable metadata.
- `PATCH /api/v1/opportunities/{opportunityId}` updates metadata and supports
  the optimistic timestamp.
- `GET /api/v1/opportunities/{opportunityId}/workspace` returns opportunity
  display metadata, latest meeting, up to 20 recent meetings, the latest
  product-safe Meeting Intelligence view, available-section count, partial
  state and a generated timestamp.
- `POST /api/v1/opportunities/{opportunityId}/workspace/latest-meeting-navigation`
  validates the current latest active meeting and records the content-free
  navigation telemetry event.
- `PATCH /api/v1/meetings/{meetingId}/opportunity` associates or disassociates
  a meeting with `opportunityId` and required `expectedUpdatedAt`.

The workspace contract contains no transcript body, prompt/schema/provider or
model labels, job/artefact identifiers, worker/lease/retry fields or raw errors.
Cross-tenant identifiers use the established safe `404` behaviour.

## Web routes and user experience

- `/opportunities` — responsive enriched list, search, stage/status filters,
  deterministic pagination and clear loading/empty/error states;
- `/opportunities/new` — accessible metadata form;
- `/opportunities/{opportunityId}/edit` — metadata update with stale-write
  protection; and
- `/opportunities/{opportunityId}` — Opportunity Workspace.

The workspace presents the opportunity header, prominent **Latest Next Best
Action**, latest-meeting momentum and buying signals, objections and competitive
signals, latest-meeting stakeholders, risks, open questions, action items, key
decisions, latest Executive Summary, read-only Follow-up Email with Copy and
recent meetings. Existing product-safe content renderers are reused without
meeting generation controls. **Open latest meeting intelligence** takes the user
to the established Meeting experience when generation or retry is needed.

No-meeting, no-company, no-value, no-close-date, no-transcript, not-generated,
valid-empty and partial-capability states leave the metadata usable. Completed
valid sections remain visible when another section is unavailable. Layout is a
single column on mobile and uses restrained columns on larger screens; semantic
headings, labels, landmarks, links, status text and visible focus states remain
the primary interaction model.

## Tenant isolation, privacy and telemetry

Opportunity, meeting, company, membership, job and artefact repositories apply
explicit organisation predicates. PostgreSQL forces RLS on opportunities,
opportunity audit events and every existing tenant-owned source table. The
runtime role must not bypass RLS and migration credentials remain separate.

Metadata-only logs cover opportunity create/update, workspace view, selected
latest meeting, available-section count, partial and no-meeting states, plus
association changes. Audits cover opportunity writes and association changes.
Neither contains names, descriptions, stakeholder names, objections,
decisions, actions, risks, questions, email text, transcript text, prompts or
provider output. WO-007 adds no external transmission.

## Migration, validation and rollback

Migration `0017_opportunity_workspace` expands the opportunity stage set, adds
status and description, renames `value` to decimal-safe `estimated_value`, makes
company/value/currency nullable under new pair constraints, removes probability,
adds list indexes, adds the meeting association and index, and creates the
append-only opportunity audit table with forced PostgreSQL RLS.

Upgrade, downgrade and re-upgrade are covered. PostgreSQL validation checks
constraints, indexes, policies and drift; SQLite migration coverage exercises
portable structure. Downgrade is destructive: opportunity audit events and all
meeting associations are removed, company-less opportunities cannot be
represented and are deleted after dependent links are cleared, and the newer
stage/status/value shape is mapped back to the earlier Sprint 2 contract. A
downgrade therefore requires an explicit backup and data-loss decision.

Tests cover contracts and validation, tenant/company boundaries, CRUD and stale
writes, association/disassociation/audits, deterministic latest selection,
cancelled exclusion, product-safe aggregation, current transcript selection,
all ten stored capabilities, bounded query count, UI states and a deterministic
mock-only create–associate–refresh browser flow.

## Known limitations and future boundary

The workspace shows latest associated meeting intelligence only. It has no
cross-meeting reasoning, opportunity health, trend analysis, historical
stakeholder tracking, relationship graph, Revenue Brain, forecast, probability,
automatic matching, CRM integration, line items, quotes, contracts, generated
content editing, email sending, task/calendar integration or next-action
execution. These require separately approved work. Production customer data
remains prohibited while production identity, consent, retention, export and
erasure controls are incomplete.

Future Revenue Brain work may introduce evidence-backed longitudinal reasoning,
but it must use a separately reviewed source and provenance model. It must not
silently reinterpret this latest-meeting read model as historical intelligence.

## Related decisions

- [ADR 0002: tenant-owned business entities](../08-decisions/0002-tenant-business-entities.md)
- [ADR 0017: derived Meeting Intelligence workspace](../08-decisions/0017-derived-meeting-intelligence-workspace.md)
- [ADR 0022: opportunity ownership and latest-meeting read model](../08-decisions/0022-opportunity-ownership-latest-meeting-read-model.md)
