# Interaction migration and compatibility notes

## Revision and ordering

`0021_interaction_domain_foundation` directly revises
`0020_private_beta_readiness` and is the sole head. Alembic remains the only schema
owner. The upgrade is additive until the historical backfill has completed.

## Upgrade sequence

1. Create `interactions`, `capture_sessions`, `evidence` and
   `interaction_audit_events` with controlled checks, indexes and composite
   tenant foreign keys.
2. Add nullable `meetings.interaction_id`.
3. Select unlinked Meetings in stable organisation/UUID order, at most 500 per
   batch.
4. Derive each Interaction UUID with UUIDv5 namespace
   `cf709ef5-e59d-4ce2-9c93-547a4a5e5990` and name
   `{organisation_id}:{meeting_id}`.
5. Copy only generic metadata: tenant, company, opportunity, title, Meeting date,
   mapped type/status, creator, timestamps and soft-deletion time. No description,
   participant, transcript, audit content, AI artefact or Revenue Brain row is copied.
6. Make the Meeting link non-null, tenant-unique and protected by a composite
   organisation/Interaction foreign key.
7. Enable and force RLS with one tenant policy per new table on PostgreSQL.

The deterministic UUID and `interaction_id IS NULL` selection make interrupted or
repeated application safe to reconcile; ordinary Alembic versioning still ensures
the revision runs once. Migration tests seed multiple tenants, verify exact UUIDs
and mappings, downgrade to 0020, and re-upgrade without duplicate Meetings.

## Historical mapping

| Meeting | Interaction |
| --- | --- |
| `remote` | `online_meeting` |
| `phone` | `phone_call` |
| `in_person` | `face_to_face_meeting` |
| `other` | `manual_interaction` |
| `scheduled` | `planned` |
| `completed` | `completed` |
| `cancelled` | `cancelled` |

Completed historical Meetings use the Meeting date for both actual start and actual
end because no more precise authoritative value exists. Other rows leave actual
times unset. The source is labelled `meeting_compatibility`.

## Old-client and data compatibility

- Existing Meeting route paths, request bodies, IDs and URLs are unchanged.
- Meeting responses add `interactionId`; clients that ignore additive fields remain
  compatible.
- New Meeting creation always creates the Interaction first in the same transaction.
- Reads and writes can continue entirely through Meeting APIs.
- Meeting Intelligence continues to reference the same Meeting/transcript/job/
  artefact rows.
- Opportunity Workspace remains a latest-Meeting projection.
- Existing Revenue Brain snapshots and insights are neither updated nor backfilled.

## Constraints and indexes

The migration adds tenant-scoped unique keys to all four new tables and to the
Meeting/Interaction pair. Composite foreign keys protect Interaction company,
opportunity and creator; Meeting/Interaction; Capture Session/Interaction and
starter; Evidence/Interaction, optional Capture Session and capturer; and audit
Interaction/actor links. Checks enforce controlled types/states and valid time
ranges.

Interaction list indexes cover tenant plus schedule, status, type, company,
opportunity and deletion. Capture Session indexes cover Interaction and status;
Evidence covers Interaction, Capture Session, status and type; audit lookup covers
tenant, Interaction and creation time.

## Downgrade and rollback

Downgrade removes the Meeting link and all four new tables. Meetings, participants,
transcripts, Meeting Intelligence, Opportunity Workspace data and Revenue Brain
history remain intact. Interaction-only records, Evidence, Capture Session metadata
and Interaction audits are permanently lost. Back up, stop writes and obtain an
explicit data-loss decision before downgrade. A later re-upgrade deterministically
reconstructs Meeting-backed Interaction identities, but cannot reconstruct deleted
standalone Interaction metadata.
