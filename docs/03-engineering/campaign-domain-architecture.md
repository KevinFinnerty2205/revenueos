# Campaign domain architecture

- **Status:** implemented by WO-030
- **Migration:** `0039_campaign_sequences`

## Ownership and model

The Engage module remains inside the FastAPI modular monolith. It owns Campaign
policy, audience, scheduling and enrolment state while reusing canonical Contacts,
the WO-029 Outreach Message/Version/Personalisation models and the WO-022
Action/Execution provider boundary.

| Table | Responsibility |
| --- | --- |
| `engage_campaigns` | owner and mutable lifecycle control plane |
| `engage_campaign_versions` | launch definition, policy/approval snapshot and fingerprints |
| `engage_sequence_steps` | one to four immutable ordered step definitions |
| `engage_campaign_audience` | exact selected Contact snapshot and eligibility decision |
| `engage_campaign_enrollments` | per-recipient progress, snapshots, outcome and terminal reason |
| `engage_enrollment_steps` | due/prepared/review/queued/sent/terminal scheduler instances |

All tables contain `organisation_id`, composite tenant foreign keys where records
cross domain boundaries, explicit tenant predicates and forced PostgreSQL RLS. The
application role remains non-bypass. Canonical Contact IDs are nullable only so
privacy deletion can scrub the live reference while retaining bounded historical
snapshots.

## Immutability and lifecycle

Draft updates replace the draft steps/audience under a campaign version. Launch
changes the version to `published`, records the policy version, approver,
approval-mode confirmation and deterministic policy/launch fingerprints, then
creates eligible enrolments. Database triggers reject ordinary updates to published
versions, sequence steps and audience entries. The sole audience exception is
privacy-driven `contact_id → NULL`; approved retention/organisation deletion remains
possible.

Campaign lifecycle is `draft/ready → active ↔ paused → completed/stopped`, with
`needs_attention` as a fail-closed halt. Enrolments distinguish active, paused,
stopped, completed, blocked and needs attention. Step state distinguishes pending,
processing, ready for review, prepared, queued, sent, deferred, blocked, cancelled
and unknown delivery.

## Service/API boundary

Routes live under `/api/v1/engage`. Sender ownership is required to edit/launch;
organisation administrators may view/manage/pause/stop. Cross-tenant access returns
not found. Server contracts forbid extra fields and accept Contact IDs rather than
email addresses. The web client mirrors only the public Pydantic response surface.
