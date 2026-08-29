# Target domain model

## Current Target Market and discovery boundary

WO-028 persists one `ProspectTargetMarket` aggregate with immutable
`ProspectTargetMarketVersion` revisions. `ProspectDiscoveryRun`,
`ProspectDiscoveryCandidate` and `ProspectCandidateReason` retain point-in-time,
explainable results; `ProspectTargetFeedback` holds per-user save/exclude state.
Candidates reuse `ProspectResearchTarget` identity. Exact-domain Company and open
Opportunity links are contextual only and no discovery action mutates canonical
sales truth. See the [architecture guide](target-market-intelligence-architecture.md).

## Current Prospect Person and Contact boundary

WO-027 adds `ProspectPerson` as company-scoped public research beneath
`ProspectResearchTarget`. It is not the canonical `Contact`. Explicit promotion
creates or links one Contact only after duplicate review and stores trust per copied
field. Unknown email is valid for a promoted Contact; manual Contact creation still
requires an email through its current API contract. Prospect refresh/deletion does
not silently update/delete the Contact.

## Current Engage outreach and Campaign boundary

WO-031 adds `SalesEvent`, `EventAttendeeImport`, `EventAttendee`, per-user
`EventAttendeeUserState`, `EventEncounter` and `EventCampaignLink`. EventAttendee is
an Event-local authorised-list identity that may reference—but never substitutes
for—canonical Contact/Company/Prospect Person/Opportunity. EventEncounter is
seller-reported activity and optional Interaction linkage, not Evidence. Contact
promotion and Campaign audience remain explicit canonical boundaries.

WO-029 adds `OutreachPolicy`, `OutreachMessage`, immutable `OutreachVersion`,
immutable `OutreachPersonalizationSource` and `ContactSuppression`. Outreach belongs
to an organisation, canonical Contact (nullable only after deletion), authenticated
sender and versioned Action. It is not an Interaction, Evidence, campaign or Lead.
Suppression is keyed by organisation plus HMAC-normalised email so it can survive
Contact deletion/re-discovery. `action_proposals.opportunity_id` is nullable only to
support legitimate Contact-scoped Actions; tenant and target IDs remain explicit.

WO-030 adds organisation-owned `EngageCampaign` control state, immutable published
`EngageCampaignVersion`, ordered `EngageSequenceStep`, exact
`EngageCampaignAudience`, per-Contact `EngageCampaignEnrollment` and due
`EngageEnrollmentStep`. An enrolment points to a canonical Contact and Company while
retaining bounded recipient snapshots for history; live references may become null
after deletion. Each prepared step points to the existing exact `OutreachMessage`
and Action/Execution graph. Campaign outbound activity and seller-reported outcomes
are not customer Interaction/Evidence or Opportunity truth.

**Status:** Current entities through WO-011 plus conceptual model through the
Interaction Platform private beta. Target rows do not authorise implementation.

The current persisted model includes organisations, users, memberships,
companies, contacts, opportunities, tasks, meetings, meeting participants,
supplied plain-text transcripts, Interactions, Capture Session/Evidence metadata,
audit events, AI jobs/artefacts, immutable
Revenue Brain snapshots and immutable longitudinal insights. The target keeps
the existing modular-monolith, PostgreSQL, SQLAlchemy/Alembic and
tenant-isolation decisions. Candidate entities are introduced only by their
named implementation sprint after a schema/API decision and migration review.

WO-011 makes Interaction the current logical parent for customer events while
preserving Meeting as a compatible subtype. AI Debrief and Voice Journal are Capture
Sessions producing salesperson-reported Evidence; Visual Capture belongs to
Evidence. The detailed model and safe staged transition are in
[Interaction domain architecture](interaction-domain-architecture.md) and the
[Interaction Intelligence migration strategy](interaction-intelligence-migration-strategy.md).

WO-009 also persists the current private-beta operational surface:
`OrganisationBetaSettings`, `DataNoticeAcknowledgement`, `OnboardingProgress`,
`AIUsageCounter`, `BetaFeedback`, `BetaDataRequest` and `BetaSystemEvent`.
These are focused tenant-owned models with forced RLS rather than one generic
settings table.

## Modelling rules

- Every tenant-owned row has a non-null `organisation_id`.
- Same-tenant composite foreign keys protect cross-organisation relationships in addition to repository predicates and PostgreSQL RLS.
- UUIDs, timezone-aware UTC timestamps, explicit lifecycle states and immutable provenance are used at boundaries.
- External provider identifiers are scoped by organisation, provider, connection and external object type.
- Content, state transitions and audit metadata are separate where their retention or access differs.
- Alembic remains the sole owner of application schema changes.

## Target Interaction and evidence entities

WO-011 implements the first four metadata boundaries below. The remaining rows are
future concepts:

| Entity                         | Purpose and key relationships                                                                                      | Tenant and source of truth                                                   | Lifecycle and retention                                                       | Expected work order                       |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ----------------------------------------- |
| Interaction                    | Source-neutral customer event; logical parent of Meeting and owner of shared type/time/account/opportunity context | Tenant-owned; manual or Meeting-compatible creation in WO-011                | Planned → in progress → completed/cancelled; soft-deleted with linked Meeting | **Current — WO-011 foundation**           |
| Meeting compatibility relation | One-to-one same-tenant link preserving existing Meeting ID/API/artefacts                                           | RevenueOS additive migration/backfill                                        | Required, deterministic and removed only through approved rollback/deletion   | **Current — WO-011**                      |
| CaptureSession                 | Metadata-only supporting activity below an Interaction; no execution/content in WO-011                             | Tenant-owned; same-tenant starter and Interaction                            | Created/capturing/completed/abandoned/failed; execution remains future        | **Current metadata foundation — WO-011**  |
| Evidence                       | Source-neutral metadata envelope; no body/storage/version chain in WO-011                                          | Tenant-owned; origin never changes through verification                      | Received/available/excluded/superseded/deleted                                | **Current metadata foundation — WO-011**  |
| EvidenceFragment               | Citeable time/text/image/page/response/field region of one evidence version                                        | Tenant-owned and bound to its evidence source                                | Immutable locator version; invalidated with source/version                    | **Target — WO-011 and source work order** |
| InteractionIntelligence        | Source-aware versioned capability artefacts/claims for an Interaction and evidence-set fingerprint                 | RevenueOS derived; strict schema/provenance and review determine eligibility | Provisional/review-required/validated/disputed/superseded/deleted             | **Target — WO-013 onward**                |

Recording, Transcript, Visual Evidence, Document Evidence and User Observation are
controlled Evidence types rather than nullable fields on Interaction. WO-011 stores
their classification metadata only; typed bodies, versions, fragments, processing
and public APIs remain future implementation decisions.

## Current identity and business entities

| Entity                 | Purpose and key relationships                                                                                                                    | Tenant and source of truth                                                                          | Lifecycle and retention                                                                                | Current / expected sprint               |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | --------------------------------------- |
| Organisation           | Tenant and policy boundary; has memberships and all tenant data                                                                                  | Organisation-scoped root; verified Clerk organisation is authoritative in production                | Active → deletion-requested → deleted through reviewed maintenance                                     | **Current — Sprint 1, expanded WO-009** |
| User                   | Local identity projection referenced by memberships/ownership                                                                                    | Global projection of verified Clerk user identity                                                   | Active/disabled; retained while another authorised membership exists                                   | **Current — Sprint 1, expanded WO-009** |
| OrganisationMembership | Links user to organisation and `admin`/`member` role                                                                                             | Tenant-owned; verified Clerk membership plus application status must agree                          | Active/disabled; access ends on the next verified request                                              | **Current — Sprint 1, expanded WO-009** |
| Company                | Relationship account; has contacts, opportunities, meetings, events and memory                                                                   | Tenant-owned; manual now, CRM may become authoritative for mapped fields                            | Active/inactive; delete or archive according to relationship/source dependencies                       | **Current — Sprint 2**                  |
| OrganisationModuleEntitlement | Bounded organisation switch for the Prospect add-on; not a billing catalogue | Tenant-owned admin configuration plus server feature availability | Enabled/disabled; revocation fails closed without synchronously deleting retained research | **Current — WO-026 for Prospect only** |
| ProspectResearchTarget | Staged company identity and promotion link before canonical Account creation | Tenant-owned provider candidate/domain; never customer Evidence | Unpromoted/promoted; retention deletion does not cascade to promoted Company | **Current — WO-026** |
| ProspectResearchRun | Immutable execution/version for one Research Target with refresh lineage | Tenant-owned worker lifecycle; provider output is execution input only | Pending/fetching/synthesising → completed/partial/failed; bounded leases and attempts | **Current — WO-026** |
| ProspectResearchSource | Bounded public/provider source metadata for one run | Tenant-owned canonical URL/fingerprint and authority metadata | Immutable with run; no full page or raw provider payload | **Current — WO-026** |
| ProspectResearchObservation | Structured company finding with exact trust state and run-local citations | Tenant-owned validated provider result; never customer-direct truth | Immutable with run; refresh creates another version | **Current — WO-026** |
| ProspectTargetMarket | Named ICP/territory aggregate pointing to a current immutable definition revision | Tenant-owned; administrator-defined | Draft/active → archived; no hard-delete API | **Current — WO-028** |
| ProspectDiscoveryRun | Bounded provider execution pinned to one Target Market revision | Tenant-owned; RevenueOS owns lifecycle and explanation | Pending/running → completed/partial/failed; refresh appends | **Current — WO-028** |
| ProspectDiscoveryCandidate/Reason | Point-in-time company context plus criterion-level explanations | Provider-supplied facts plus exact tenant relationship context | Immutable with run; no canonical truth mutation | **Current — WO-028** |
| ProspectTargetFeedback | User-specific saved/excluded state for a staged company identity | Tenant/user-owned feedback | Saved/excluded or restored by deletion | **Current — WO-028** |
| Contact                | Person linked to a company and meetings                                                                                                          | Tenant-owned; manual now, CRM/provider identity may be authoritative by field                       | Active/merged/deleted; personal data follows deletion and source policy                                | **Current — Sprint 2**                  |
| Opportunity            | Commercial context with optional company, manual value/date, owner, tasks and associated meetings; its workspace derives the latest meeting view | Tenant-owned; manual now, supported CRM may later become authoritative for explicitly mapped fields | `open`, `won`, `lost` or `on_hold`; stage remains independently user-managed                           | **Current — Sprint 2, expanded WO-007** |
| Task                   | Human-owned commitment linked to company/contact/opportunity and later source evidence                                                           | Tenant-owned; RevenueOS authoritative for native tasks, external task system if later mapped        | Open/in progress → completed/cancelled; configurable operational retention                             | **Current — Sprint 2**                  |
| OpportunityAuditEvent  | Metadata-only opportunity create/update/delete and meeting-association activity                                                                  | Tenant-owned; RevenueOS service transaction is authoritative                                        | Append-only metadata; deliberately has no content payload or opportunity FK so delete audit can remain | **Current — WO-007**                    |

## Current AI and Revenue Brain entities

| Entity               | Purpose and key relationships                                                                                      | Tenant and source of truth                                                                   | Lifecycle and retention                                                           | Current / expected sprint                        |
| -------------------- | ------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------ |
| AIJob                | Durable tenant-scoped work state pinned to meeting/transcript/prompt/schema/provider trace                         | RevenueOS orchestration is authoritative for lifecycle; provider is execution-only           | Pending/running/retry/completed/failed/cancelled with bounded leases and attempts | **Current — WO-004A1/B1 and later capabilities** |
| AIArtifact           | Append-only strict structured capability output linked to its exact completed job and transcript trace             | Tenant-owned generated content; never silently authoritative over direct evidence            | Immutable logical versions with one-way supersession                              | **Current — WO-004A1 and later capabilities**    |
| RevenueBrainSnapshot | Content-free composition of nine exact validated artefact references for one completed meeting transcript revision | Tenant-owned reference projection; source artefacts remain authoritative                     | Append-only; later transcript revisions create new rows                           | **Current — WO-008A**                            |
| RevenueBrainInsight  | Controlled evidence-backed change set for one account/opportunity snapshot pair and reasoning version              | Tenant-owned deterministic derivation; selected snapshots and artefacts remain authoritative | Append-only and idempotent by scope/target/pair/version                           | **Current — WO-008B**                            |

## Meeting and ingestion entities

| Entity             | Purpose and key relationships                                                                                           | Tenant and source of truth                                                                                  | Lifecycle and retention                                                                          | Current / expected sprint               |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | --------------------------------------- |
| Meeting            | Conversation aggregate linking participants, optional company, optional same-tenant opportunity and supplied transcript | Tenant-owned; RevenueOS is authoritative for manually entered metadata and explicit opportunity association | Scheduled/completed/cancelled; soft-deleted with active children and hidden from normal reads    | **Current — Sprint 3, expanded WO-007** |
| MeetingParticipant | A meeting-specific attendee and optional confirmed contact link                                                         | Tenant-owned; user-entered identity or same-tenant contact reference                                        | Invited/attended/absent/unknown; active or soft-deleted with meeting                             | **Current — Sprint 3**                  |
| Transcript         | One versioned plain-text representation supplied for a meeting                                                          | Tenant-owned; pasted or browser-read `.txt`, with user correction authoritative                             | Created/restored → corrected by optimistic version → soft-deleted; no snapshot history yet       | **Current — Sprint 3**                  |
| MeetingAuditEvent  | Content-minimised activity metadata for meeting, participant and transcript mutations                                   | Tenant-owned; RevenueOS service transaction is authoritative                                                | Append-only normally; removed with its meeting only by approved tenant retention/deletion        | **Current — Sprint 3, expanded WO-009** |
| TranscriptSegment  | Timestamped/speaker-linked transcript evidence used for citations                                                       | Tenant-owned child of transcript                                                                            | Immutable per transcript version; deleted with transcript/source                                 | **Target — WO-015**                     |
| IngestionJob       | Durable, leased, idempotent processing state for an explicitly supplied source                                          | Tenant-owned; RevenueOS job system authoritative                                                            | Queued/running/retry/complete/failed/cancelled; operational metadata retained, payload minimised | **Target — WO-014/015 source stages**   |

## Connection and external identity entities

| Entity           | Purpose and key relationships                                                       | Tenant and source of truth                                                                    | Lifecycle and retention                                                                       | Current / expected sprint                        |
| ---------------- | ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| SourceConnection | Capability/scopes/health projection for a calendar, mail, meeting or CRM connection | Tenant-owned; provider is authoritative for grant/revocation, secret vault stores credentials | Pending/active/degraded/revoked/deleting; purge tokens immediately on revoke/delete           | **Target — WO-017/019 and later CRM work**       |
| ExternalIdentity | Maps a RevenueOS entity to a provider object under one connection                   | Tenant-owned; provider supplies external ID/version, user may confirm ambiguous match         | Candidate/confirmed/conflicted/retired; retain minimal tombstone for idempotency where lawful | **Target — WO-017/019 and later connector work** |

## Relationship and intelligence entities

| Entity               | Purpose and key relationships                                                                                  | Tenant and source of truth                                              | Lifecycle and retention                                                                                | Current / expected sprint                                      |
| -------------------- | -------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------- |
| RelationshipEvent    | Chronological projection of a material source-linked change beneath or beside the primary Interaction Timeline | Tenant-owned projection; linked source remains authoritative            | Recorded → corrected/superseded/deleted; retention follows originating source and policy               | **Target — WO-011/013 timeline; does not replace Interaction** |
| MemoryItem           | Concise correctable claim used in future briefs/answers                                                        | Tenant-owned; user-confirmed correction outranks inferred versions      | Candidate → active → stale/superseded/deleted; excluded immediately from retrieval on deletion request | **Target — WO-012/013 and WO-020 hardening**                   |
| MemorySource         | Links atomic memory claims to evidence fragments/events/external records                                       | Tenant-owned provenance edge; source object is authoritative evidence   | Immutable link per memory version; cascades/invalidation follows source deletion                       | **Target — WO-011/013 and later source work**                  |
| ReviewedIntelligence | Future user-reviewed version of generated intelligence with acceptance/correction state                        | Tenant-owned; a user-confirmed correction may outrank generated content | Generated → reviewed/accepted/rejected/superseded/deleted; derived-data retention follows source       | **Target — WO-013**                                            |

## Action, audit and notification entities

| Entity          | Purpose and key relationships                                                                     | Tenant and source of truth                                          | Lifecycle and retention                                                                                        | Current / expected sprint                                              |
| --------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| SuggestedAction | Bounded proposal for a task, follow-up, CRM change or other reviewable work                       | Tenant-owned; RevenueOS proposal, never proof of execution          | Proposed → edited/approved/rejected/expired/superseded; content retention follows source/policy                | **Not current — Sprint 10**                                            |
| Approval        | Specific actor decision bound to action content/version, destination and expiry                   | Tenant-owned; RevenueOS approval record is authoritative            | Pending → approved/rejected/expired/revoked; retention aligned to audit/legal policy                           | **Not current — Sprint 10**                                            |
| SyncOperation   | Idempotent execution/reconciliation record for an approved external action                        | Tenant-owned; provider is authoritative for external outcome        | Queued/executing/acknowledged/confirmed/failed/unknown; receipts retained per audit policy                     | **Not current — Sprint 14**                                            |
| AuditEvent      | Content-minimised record of security, consent, AI review, approval, execution and deletion events | Tenant-owned with guarded operational access; append-only in intent | Written once; retention is policy/regulatory with cryptographic/integrity controls evaluated before production | **Not current — initial events Sprint 5; operational model Sprint 17** |
| Notification    | User-directed exception or time-sensitive workflow signal linked to an entity/action              | Tenant-owned and addressed to an authorised membership              | Pending/delivered/read/deferred/resolved/expired; short retention after resolution                             | **Not current — Sprint 16**                                            |

## Key relationship constraints

```text
Organisation
├── OrganisationMembership ── User
├── Company
│   ├── Contact
│   ├── Opportunity
│   ├── Meeting ── Opportunity?
│   │   ├── MeetingParticipant ── Contact?
│   │   ├── Transcript ── TranscriptSegment
│   │   ├── AIArtifact
│   │   ├── RevenueBrainSnapshot ── RevenueBrainInsight
│   │   └── SuggestedAction ── Approval ── SyncOperation?
│   ├── RelationshipEvent
│   └── MemoryItem ── MemorySource ── source entity
├── EngageCampaign ── CampaignVersion
│   ├── SequenceStep
│   ├── AudienceSnapshot ── Contact?
│   └── Enrollment ── EnrollmentStep ── OutreachMessage/Action?
├── SourceConnection ── ExternalIdentity
├── IngestionJob
├── AuditEvent
└── Notification
```

- A task linked to multiple relationship records must resolve to one consistent company/organisation.
- A meeting may reference at most one opportunity; its composite foreign key and service validation keep organisation and, when both exist, company consistent. Opportunity Workspace latest order is meeting date then UUID, both descending, excluding cancelled and deleted meetings.
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
- **Prospect research:** organisation policy over targets, runs, concise observations
  and source metadata; no fetched page body is retained and deleting research never
  silently deletes a promoted Company.
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

## WO-023 future Sales OS extensions

The end-to-end blueprint introduces planning concepts for methodology definitions
and projections, research subjects/findings, ICP/territory, Leads, campaigns and
sequences, template/content/ROI assets, stage history, typed custom fields, metrics,
targets, forecasts and entitlements. These are not implemented entities and do not
authorise schema changes.

Future work must reuse the canonical Organisation, User/membership, Company, Contact,
Opportunity, Interaction, Evidence, Revenue Brain, Action and Workspace identities.
A Prospect is staged research; a Lead is pursuit state; a Contact and Company remain
the accepted canonical person and account. Detailed boundaries are in
[ADR 0035](../08-decisions/0035-end-to-end-sales-os-architecture.md) and the
[WO-023 architecture set](../07-sprints/wo-023-end-to-end-sales-platform-blueprint.md).

## Related documents

- [Current application architecture](architecture.md)
- [Core workflows](../02-design/core-workflows.md)
- [AI system blueprint](../04-ai/ai-system-blueprint.md)
- [Privacy, security and trust model](privacy-security-and-trust-model.md)
- [Product roadmap to beta](../06-roadmap/product-roadmap-to-beta.md)
- [End-to-End Sales Platform roadmap](../06-roadmap/end-to-end-sales-platform-roadmap.md)

## WO-033 domain addition

`CreateValueModel` owns organisation-visible administration state and immutable
`CreateValueModelVersion` definitions. `CreateBusinessCase` belongs to one Account,
optionally one of that Account's Opportunities, and pins an approved model version.
Each calculation appends an immutable `CreateBusinessCaseVersion` containing currency,
explicit inputs with provenance, scenario outputs, optional one-variable sensitivity,
formula-engine/model fingerprints and lineage. A Create presentation may reference
one exact approved case version and scenario; it never copies that output into a CRM,
Methodology or Revenue Brain field.
