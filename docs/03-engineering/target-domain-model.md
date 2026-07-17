# Target domain model

**Status:** Conceptual model through private beta. This document creates no SQLAlchemy models, database migrations or API contracts.

The current persisted model includes organisations, users, memberships, companies, contacts, opportunities, tasks, meetings, meeting participants, supplied plain-text transcripts and meeting audit events. The target keeps the existing modular-monolith, PostgreSQL, SQLAlchemy/Alembic and tenant-isolation decisions. Candidate entities are introduced only by their named implementation sprint after a schema/API decision and migration review.

## Modelling rules

- Every tenant-owned row has a non-null `organisation_id`.
- Same-tenant composite foreign keys protect cross-organisation relationships in addition to repository predicates and PostgreSQL RLS.
- UUIDs, timezone-aware UTC timestamps, explicit lifecycle states and immutable provenance are used at boundaries.
- External provider identifiers are scoped by organisation, provider, connection and external object type.
- Content, state transitions and audit metadata are separate where their retention or access differs.
- Alembic remains the sole owner of application schema changes.

## Current identity and business entities

| Entity | Purpose and key relationships | Tenant and source of truth | Lifecycle and retention | Current / expected sprint |
| --- | --- | --- | --- | --- |
| Organisation | Tenant and policy boundary; has memberships and all tenant data | Organisation-scoped root; Clerk is authoritative for authenticated organisation identity once connected | Active → suspended/deletion-pending → deleted; deletion policy governs descendants | **Current — Sprint 1** |
| User | Local identity projection referenced by memberships/ownership | Global identity projection; Clerk is future production identity source | Active projection while required; retain minimal audit linkage after removal | **Current — Sprint 1** |
| OrganisationMembership | Links user to organisation and role | Tenant-owned; verified Clerk membership plus application policy must agree | Invited/active/removed; access ends immediately, metadata retained per audit policy | **Current — Sprint 1** |
| Company | Relationship account; has contacts, opportunities, meetings, events and memory | Tenant-owned; manual now, CRM may become authoritative for mapped fields | Active/inactive; delete or archive according to relationship/source dependencies | **Current — Sprint 2** |
| Contact | Person linked to a company and meetings | Tenant-owned; manual now, CRM/provider identity may be authoritative by field | Active/merged/deleted; personal data follows deletion and source policy | **Current — Sprint 2** |
| Opportunity | Commercial context linked to company, tasks and meetings | Tenant-owned; manual now, supported CRM authoritative for mapped fields | Open stages → closed; retain according to customer and CRM policy | **Current — Sprint 2** |
| Task | Human-owned commitment linked to company/contact/opportunity and later source evidence | Tenant-owned; RevenueOS authoritative for native tasks, external task system if later mapped | Open/in progress → completed/cancelled; configurable operational retention | **Current — Sprint 2** |

## Meeting and ingestion entities

| Entity | Purpose and key relationships | Tenant and source of truth | Lifecycle and retention | Current / expected sprint |
| --- | --- | --- | --- | --- |
| Meeting | Conversation aggregate linking participants, optional company and supplied transcript | Tenant-owned; RevenueOS is authoritative for manually entered metadata | Scheduled/completed/cancelled; soft-deleted with active children and hidden from normal reads | **Current — Sprint 3** |
| MeetingParticipant | A meeting-specific attendee and optional confirmed contact link | Tenant-owned; user-entered identity or same-tenant contact reference | Invited/attended/absent/unknown; active or soft-deleted with meeting | **Current — Sprint 3** |
| Transcript | One versioned plain-text representation supplied for a meeting | Tenant-owned; pasted or browser-read `.txt`, with user correction authoritative | Created/restored → corrected by optimistic version → soft-deleted; no snapshot history yet | **Current — Sprint 3** |
| MeetingAuditEvent | Content-minimised activity metadata for meeting, participant and transcript mutations | Tenant-owned; RevenueOS service transaction is authoritative | Append-only metadata retained with meeting; retention/export policy is not implemented | **Current — Sprint 3** |
| TranscriptSegment | Timestamped/speaker-linked transcript evidence used for citations | Tenant-owned child of transcript | Immutable per transcript version; deleted with transcript/source | **Not current — Sprint 6** |
| IngestionJob | Durable, leased, idempotent processing state for an explicitly supplied source | Tenant-owned; RevenueOS job system authoritative | Queued/running/retry/complete/failed/cancelled; operational metadata retained, payload minimised | **Not current — Sprint 5** |

## Connection and external identity entities

| Entity | Purpose and key relationships | Tenant and source of truth | Lifecycle and retention | Current / expected sprint |
| --- | --- | --- | --- | --- |
| SourceConnection | Capability/scopes/health projection for a calendar, mail, meeting or CRM connection | Tenant-owned; provider is authoritative for grant/revocation, secret vault stores credentials | Pending/active/degraded/revoked/deleting; purge tokens immediately on revoke/delete | **Not current — Sprint 11** |
| ExternalIdentity | Maps a RevenueOS entity to a provider object under one connection | Tenant-owned; provider supplies external ID/version, user may confirm ambiguous match | Candidate/confirmed/conflicted/retired; retain minimal tombstone for idempotency where lawful | **Not current — Sprint 6 for matching; provider use Sprint 11+** |

## Relationship and intelligence entities

| Entity | Purpose and key relationships | Tenant and source of truth | Lifecycle and retention | Current / expected sprint |
| --- | --- | --- | --- | --- |
| RelationshipEvent | Chronological, source-linked change or interaction for company/contact/opportunity | Tenant-owned projection; linked source remains authoritative | Recorded → corrected/superseded/deleted; retention follows originating source and policy | **Not current — Sprint 8** |
| MemoryItem | Concise correctable claim used in future briefs/answers | Tenant-owned; user-confirmed correction outranks inferred versions | Candidate → active → stale/superseded/deleted; excluded immediately from retrieval on deletion request | **Not current — Sprint 9** |
| MemorySource | Links atomic memory claims to transcript segments/events/external records | Tenant-owned provenance edge; source object is authoritative evidence | Immutable link per memory version; cascades/invalidation follows source deletion | **Not current — Sprint 9** |
| AIArtifact | Versioned structured model output such as summary, next steps, draft or brief | Tenant-owned; AI is never authoritative fact, reviewed version may become a user-confirmed artefact | Generated → review/accepted/rejected/superseded/deleted; derived-data retention follows source | **Not current — Sprint 7** |

## Action, audit and notification entities

| Entity | Purpose and key relationships | Tenant and source of truth | Lifecycle and retention | Current / expected sprint |
| --- | --- | --- | --- | --- |
| SuggestedAction | Bounded proposal for a task, follow-up, CRM change or other reviewable work | Tenant-owned; RevenueOS proposal, never proof of execution | Proposed → edited/approved/rejected/expired/superseded; content retention follows source/policy | **Not current — Sprint 10** |
| Approval | Specific actor decision bound to action content/version, destination and expiry | Tenant-owned; RevenueOS approval record is authoritative | Pending → approved/rejected/expired/revoked; retention aligned to audit/legal policy | **Not current — Sprint 10** |
| SyncOperation | Idempotent execution/reconciliation record for an approved external action | Tenant-owned; provider is authoritative for external outcome | Queued/executing/acknowledged/confirmed/failed/unknown; receipts retained per audit policy | **Not current — Sprint 14** |
| AuditEvent | Content-minimised record of security, consent, AI review, approval, execution and deletion events | Tenant-owned with guarded operational access; append-only in intent | Written once; retention is policy/regulatory with cryptographic/integrity controls evaluated before production | **Not current — initial events Sprint 5; operational model Sprint 17** |
| Notification | User-directed exception or time-sensitive workflow signal linked to an entity/action | Tenant-owned and addressed to an authorised membership | Pending/delivered/read/deferred/resolved/expired; short retention after resolution | **Not current — Sprint 16** |

## Key relationship constraints

```text
Organisation
├── OrganisationMembership ── User
├── Company
│   ├── Contact
│   ├── Opportunity
│   ├── Meeting
│   │   ├── MeetingParticipant ── Contact?
│   │   ├── Transcript ── TranscriptSegment
│   │   ├── AIArtifact
│   │   └── SuggestedAction ── Approval ── SyncOperation?
│   ├── RelationshipEvent
│   └── MemoryItem ── MemorySource ── source entity
├── SourceConnection ── ExternalIdentity
├── IngestionJob
├── AuditEvent
└── Notification
```

- A task linked to multiple relationship records must resolve to one consistent company/organisation.
- A meeting participant can remain unlinked; an uncertain candidate is not a contact.
- Memory and AI artefacts may cite multiple sources, but every source must be accessible in the same tenant.
- An approval cannot be reused for a different action version, destination or organisation.
- A sync operation cannot exist without an approved eligible action.
- Deletion processing must traverse source-to-derived edges without requiring raw content in the audit event.

## Source-of-truth precedence

1. Security identity and active membership: verified Clerk assertion plus application membership/policy.
2. Connected object fields: designated provider, such as CRM or calendar, for mapped fields.
3. User-confirmed correction: authoritative within RevenueOS for transcript/memory interpretation.
4. Direct source evidence: immutable recording/transcript/external snapshot version.
5. Model-derived inference: candidate only until policy/user confirmation; never silently outranks the above.

Conflicts are represented, not overwritten. Field-level source ownership must be configured for integrations.

## Retention classes

- **Raw media:** configurable; 30-day default after successful transcription, earlier user deletion supported.
- **Transcript and derived content:** retained only while the relationship workflow and policy require it; delete with source on request unless a documented obligation applies.
- **Relationship memory:** active while useful and supported; correction, staleness, exclusion and deletion are explicit.
- **Connector secrets:** until revocation/deletion; never copied into domain/audit tables.
- **Operational jobs/logs:** content-minimised and short-lived.
- **Approval/sync/audit metadata:** retained according to customer, security and applicable regulatory policy, without unnecessary raw content.
- **Backups:** expire on a documented schedule; deletion responses distinguish active-store completion from backup expiry.

## Decisions deferred to implementation ADRs

- Exact enum/state machines, columns, indexes and API contracts.
- Event versioning versus append-only replacement mechanics.
- Search/vector technology and whether embeddings are necessary in the pilot.
- Audit integrity mechanism and retention duration by launch region.
- Transcript correction granularity and storage cost envelope.
- Role/permission matrix and source-level transcript visibility.

## Related documents

- [Current application architecture](architecture.md)
- [Core workflows](../02-design/core-workflows.md)
- [AI system blueprint](../04-ai/ai-system-blueprint.md)
- [Privacy, security and trust model](privacy-security-and-trust-model.md)
- [Product roadmap to beta](../06-roadmap/product-roadmap-to-beta.md)
