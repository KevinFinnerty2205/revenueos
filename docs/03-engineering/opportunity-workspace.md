# Opportunity Workspace

## Purpose and current boundary

WO-007 adds the first opportunity-centred product read model. WO-008B extends
that surface with a separate longitudinal comparison. The workspace combines
manually managed opportunity metadata with stored, validated intelligence from
the latest associated meeting so a salesperson can understand the current
commercial context quickly.

Opening or refreshing the workspace does not create intelligence or reasoning.
It performs tenant-scoped database reads only: it does not read transcript
text, render a prompt, create an AI job or call a provider. All Meeting
Intelligence wording is explicitly scoped to the latest meeting. The separate
**Longitudinal Changes** section reads a current immutable WO-008B comparison
when present and offers one explicit deterministic generation action.

WO-016 adds a separate `latestInteractionCapture` metadata projection for the
most recent active linked Interaction. It reports lifecycle/capture state,
recording and debrief state, visual count and marker count, with direct
Companion navigation. It does not read transcript content or create
intelligence.

WO-017 phone calls use the same `reportedIntelligence` projection after complete
candidate review. Each item now also carries deterministic `conflictState`, which
the workspace renders without choosing between recording and Debrief sources. A
missed, voicemail or cancelled call creates no reported Interaction Intelligence.
The Interaction timeline remains the place for its call direction, Contact,
duration, outcome and capture readiness; there is no phone-only workspace.

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
bounded reads for opportunity metadata, recent meetings, readiness artefacts,
the latest meeting's existing jobs/artefacts and the safe current reasoning
state. Query count does not grow per
opportunity, meeting, participant or capability; there is no N+1 loop.

## Longitudinal reasoning

The aggregate's reasoning field is read-only. It selects only immutable
snapshots explicitly associated with the opportunity and their nine referenced
strict validated artefacts. The latest eligible pair must match the stored
insight before the workspace reports `completed`; otherwise it reports
`insufficient_history` or `not_generated` while older insights remain
immutable.

`POST /api/v1/opportunities/{opportunityId}/brain/reasoning` performs the
explicit bounded comparison. The default `latest_change` mode creates or reuses
one pair; `recent_history` handles adjacent pairs among the latest 10 eligible
snapshots. It does not load transcripts, call a provider or generate new
Meeting Intelligence. See
[Revenue Brain longitudinal reasoning](revenue-brain-reasoning.md).

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
  state, current safe Revenue Brain reasoning, latest linked Interaction
  capture status and a generated timestamp.
- `POST /api/v1/opportunities/{opportunityId}/brain/reasoning` creates or
  reuses deterministic `latest_change` or `recent_history` comparisons.
- `GET /api/v1/opportunities/{opportunityId}/brain/reasoning` reads the current
  latest comparison and bounded immutable history.
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

The workspace presents the opportunity header, latest field-Interaction capture
status, **Longitudinal Changes**,
prominent **Latest Next Best Action**, latest-meeting momentum and buying signals, objections and competitive
signals, latest-meeting stakeholders, risks, open questions, action items, key
decisions, latest Executive Summary, read-only Follow-up Email with Copy and
recent meetings. Existing product-safe content renderers are reused without
meeting generation controls. **Open latest meeting intelligence** takes the user
to the established Meeting experience when generation or retry is needed.

Longitudinal Changes appears before the current-meeting intelligence sections.
It shows comparison dates as meeting links, a concise summary, up to six
important changes, textual direction/importance, confidence and source
capability labels. It includes explicit generation, insufficient-history,
not-generated, no-material-change and safe unavailable states. No raw evidence
identifier, gauge, forecast or score is rendered.

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

WO-008B migration `0019_revenue_brain_reasoning` adds the separate immutable
reasoning table; it does not change Opportunity ownership or the WO-007
migration rollback.

Tests cover contracts and validation, tenant/company boundaries, CRUD and stale
writes, association/disassociation/audits, deterministic latest selection,
cancelled exclusion, product-safe aggregation, current transcript selection,
all ten stored capabilities, bounded query count, UI states and a deterministic
mock-only create–associate–refresh browser flow.

## Known limitations and future boundary

The workspace still shows current Meeting Intelligence for only the latest
associated meeting, while the separate deterministic section reports supported
adjacent-snapshot changes. It has no opportunity health score, relationship
graph, forecast, probability,
automatic matching, CRM integration, line items, quotes, contracts, generated
content editing, email sending, task/calendar integration or next-action
execution. These require separately approved work. Production customer data
remains prohibited unless separately approved. WO-009 now feature-gates the
workspace in both API and UI and retention/deletion remove its source meetings
and artefacts; this does not broaden the workspace's intelligence boundary.

Future Revenue Brain work may extend explicit schemas or explanation, but it
must preserve the separately reviewed snapshot/evidence boundary and must not
silently reinterpret this latest-meeting read model as historical intelligence.

## Target Interaction continuity

WO-011 deliberately does not change this current latest-meeting read model. It
adds presentations, workshops, site visits and other customer events through the
separate Interaction list/API, while Opportunity Workspace retains its stable
`latestMeeting` contract. WO-013 now implements AI Debrief and Voice Journal Capture
Session types beneath their Interaction, not customer events.

After the additive migration, the Workspace keeps its current `latestMeeting` and
ten Meeting Intelligence capability fields. A later `latestInteraction` or
source-neutral opportunity-intelligence contract must be additive and must not
reinterpret salesperson-reported evidence as transcript-grounded customer evidence.
The compatibility adapter and migration are defined in the
[Interaction Intelligence migration strategy](interaction-intelligence-migration-strategy.md).
The implemented adapter is documented in
[Interaction migration and compatibility](interaction-migration-and-compatibility.md).

## Related decisions

- [ADR 0002: tenant-owned business entities](../08-decisions/0002-tenant-business-entities.md)
- [ADR 0017: derived Meeting Intelligence workspace](../08-decisions/0017-derived-meeting-intelligence-workspace.md)
- [ADR 0022: opportunity ownership and latest-meeting read model](../08-decisions/0022-opportunity-ownership-latest-meeting-read-model.md)
- [ADR 0024: deterministic Revenue Brain longitudinal reasoning](../08-decisions/0024-deterministic-revenue-brain-longitudinal-reasoning.md)
- [ADR 0026: Interaction Intelligence platform](../08-decisions/0026-interaction-intelligence-platform.md)

## Post-interaction reported intelligence

WO-013 adds the optional `reportedIntelligence` field without changing
`latestMeeting` or any of the ten Meeting Intelligence capability fields. It selects
the newest validated post-interaction snapshot for the exact opportunity and renders
its accepted items in a separate “Reported by you” section. Each item retains category,
statement, Evidence identifier, `salesperson_reported` origin and verified validation
state. It is never presented as transcript-grounded or customer-confirmed evidence.

The workspace remains read-only and does not start a debrief, provider request or
Brain update. See [Source-aware Interaction Intelligence](source-aware-interaction-intelligence.md).

## Pre-interaction preparation consumer

## Reviewed visual evidence

The workspace can now expose the latest eligible schema-version-2 visual
Interaction Intelligence snapshot. Items include AI origin, source ownership,
support classification, validation and conflict state. The web surface labels
them AI-interpreted and user-reviewed and calls out observed site-photo evidence.
The repository verifies every source Evidence is still available and verified,
so visual deletion suppresses stale derived current content.

WO-012 reuses the same exact-opportunity latest eligible Meeting rule to build a
Pre-Interaction Brief for a future Interaction. It reads validated stored
artefacts directly in one backend service; it does not repeatedly call Workspace
endpoints and does not trigger Meeting Intelligence generation. An Interaction
without an opportunity may use company scope, but one with an opportunity never
mixes another opportunity at the same company. See
[Pre-Interaction source grounding](pre-interaction-source-grounding.md).
