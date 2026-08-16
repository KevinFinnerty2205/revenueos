# Revenue Brain foundation

WO-018 does not add a Revenue Brain path. Once imported online-meeting evidence is
reviewed and processed by existing Interaction Intelligence, the established
Meeting-linked snapshot composition, provenance and idempotency rules apply. An
import retry cannot itself create a second snapshot.

WO-020 likewise adds no provisional Revenue Brain path. Live signals and brief
progress are never snapshot inputs. Only separately finalised and validated normal
Interaction Intelligence may create the existing immutable Brain composition;
live-to-final reconciliation updates only the live history.

## Product behaviour

WO-008A adds an append-only account timeline of immutable meeting-intelligence
compositions. A snapshot is attempted by the existing worker after any required
capability completes. It is created only when the meeting is completed, has an
account, the selected transcript revision is still current and all nine required
artefacts are complete and valid.

The required references are:

- Executive Summary;
- Buying Signals;
- Objections & Competitive Signals;
- Stakeholder Intelligence;
- Decisions;
- Action Items;
- Risks & Blockers;
- Open Questions; and
- Next Best Action.

Follow-up Email is not part of a Revenue Brain snapshot. A snapshot contains no
transcript or artefact content. It does not summarise, compare, reason, predict,
forecast or detect a trend. WO-008B builds a separate immutable comparison over
these references; it does not change snapshot composition.

## Persistence and idempotency

`RevenueBrainSnapshot` stores the organisation, company, optional opportunity,
meeting, stable transcript-revision identity, creation time, nine artefact IDs
and snapshot schema version. Snapshot schema version is currently `1`.

The existing transcript table identifies revisions with one transcript UUID and
a positive integer version. WO-008A derives `transcript_version_id`
deterministically from both values without copying transcript text or introducing
a second transcript store. A transcript correction therefore receives a distinct
revision identity while a retry of the same revision resolves to the same
identity.

The unique key `(organisation_id, meeting_id, transcript_version_id)` enforces
one composition for one meeting revision. The worker completion transaction
locks the meeting before its readiness check. Concurrent capability completions
therefore serialize at the meeting boundary, so the final completion observes
the preceding committed artefacts and creates at most one snapshot.

Every artefact candidate must:

- belong to the trusted organisation, meeting, transcript and transcript
  version;
- be the latest non-superseded artefact of its required type;
- belong to a completed matching job;
- use the code-deployed schema version; and
- pass its existing strict Pydantic artefact model again.

The composition stores only IDs. Composite tenant foreign keys prevent
cross-organisation account, opportunity, meeting or artefact references.
PostgreSQL RLS is enabled and forced. Database triggers reject every snapshot
update and delete, making the table append-only rather than relying on the
service surface alone.

Meetings link to companies and may carry one explicit, audited opportunity
association. A snapshot preserves that `opportunity_id` when present and keeps
it null otherwise; no opportunity is inferred from account data.

## API and web surface

`GET /api/v1/accounts/{accountId}/brain` returns a JSON array ordered by meeting
date descending, then snapshot creation and ID descending. Each item contains
the immutable composition fields and `meetingDate` for presentation. It returns
no artefact content, transcript, prompt, model, provider, job or worker state.

The company account page at `/companies/{accountId}` shows **Revenue Brain**,
the bounded snapshot timeline and any separately generated adjacent WO-008B
comparison summaries. Snapshot API items remain reference-only. See
[Revenue Brain longitudinal reasoning](revenue-brain-reasoning.md).

WO-009 places this surface behind the server-authoritative
`API_FEATURE_REVENUE_BRAIN_ENABLED` capability. Disabled API routes fail
closed and the web surface stays hidden; client input cannot enable it. The
deterministic demo-data command supplies two synthetic meeting transcripts.
Running the existing unified mock generation for both meetings is the supported
demo path for composing snapshots and the adjacent reasoning result—no new AI
capability or real provider request is involved.

## Failure and exclusion behaviour

No snapshot is created for a scheduled, cancelled, deleted or unlinked meeting;
an absent, failed, cancelled, superseded, wrong-version, wrong-schema or invalid
required artefact; or a stale/deleted transcript revision. Completion remains
idempotent and a later eligible transcript revision appends a new snapshot
without changing earlier rows.

Ordinary application code still cannot update or delete snapshots. The WO-009
retention and organisation-deletion maintenance services use the narrow,
tenant-scoped approved database deletion path added in migration 0020 so policy
expiry cannot leave stale Revenue Brain references visible.

## Out of scope

WO-008A itself includes no reasoning. The separately implemented WO-008B
comparison still excludes opportunity health, CRM behaviour, automation,
forecasting, predictive trend scoring, relationship graphs, embeddings, vector
search, new prompts, provider calls and transcript analysis.

## Target Interaction evolution

## WO-014 visual timeline

`GET /api/v1/accounts/{account_id}/brain/visual-evidence` reads tenant-scoped
schema-version-2 Interaction snapshots whose source Evidence is still verified
and available. The account UI shows source label, support classification and a
link to the Interaction; it never embeds raw image bytes in Revenue Brain.

`GET /api/v1/accounts/{account_id}/brain/reported-interactions` exposes the latest
validated post-interaction snapshots, including phone calls. Each item retains the
`Reported by you` label and its recording comparison state; revoked or deleted source
Evidence fails closed and is omitted. The account page renders this as a separate
reviewed Interaction timeline, so it cannot be mistaken for customer-direct Meeting
Intelligence.
Business cards and seller-context-only material do not create these snapshots.

WO-013 adds `RevenueBrainInteractionSnapshot` as an immutable additive subtype for
accepted post-interaction salesperson-reported Evidence. It references the source
Interaction Intelligence composition and accepted Evidence IDs and keeps the visible
source label “Reported by you”. It does not update, delete or reinterpret any existing
Meeting snapshot, and the existing WO-008B comparison continues to reason only over
its documented Meeting snapshot inputs. See
[Source-aware Interaction Intelligence](source-aware-interaction-intelligence.md).

WO-011 leaves every current snapshot immutable and Meeting-based. The new
Meeting/Interaction compatibility relation supplies timeline identity without
updating a snapshot or artefact reference. Future
Interaction snapshots use a new schema version and reference validated structured
Interaction Intelligence plus provenance, not copied raw recordings, transcripts,
documents or journals. Historical Meeting snapshots appear in the Interaction
Timeline through the compatibility relation; they are not rewritten or assigned new
semantics.

Cross-version composition and deletion impact require separately approved work. See
the [Interaction Intelligence migration strategy](interaction-intelligence-migration-strategy.md)
and [ADR 0026](../08-decisions/0026-interaction-intelligence-platform.md).

## WO-017 phone-call continuity

A connected phone call with accepted debrief candidates creates the same immutable
`RevenueBrainInteractionSnapshot` used by other reviewed post-interaction reports.
The content preserves the **Reported by you** origin and reconciliation state; it
does not copy a recording or transcript. Retry reuses the completed debrief and does
not append duplicate snapshots. No-answer, voicemail and cancelled calls append no
customer-intelligence snapshot and are not interpreted as relationship decline.

## WO-019 source timeline

The account Revenue Brain now reads immutable `RevenueBrainSourceSnapshot` rows in
addition to Interaction snapshots. Each row is created only after complete human
review and contains structured accepted statements, Evidence IDs, source label,
type, ownership, occurred-at time, provenance and exact source location. It does
not contain raw documents or email bodies.

Source rows are reference-only and are never recomputed in the read path. Deleting
the source removes its candidates, accepted Evidence and source snapshots, so it
cannot continue influencing the timeline. This slice does not score, forecast,
perform longitudinal inference across source types or mutate opportunity fields.

## Action Layer consumer

Completed Revenue Brain insights can ground bounded Action proposals when their
source snapshots remain current. The Action Layer stores only references and a
bounded provenance summary; it does not modify Revenue Brain snapshots or insights.
Approval is refused if the referenced insight is no longer current.

## Sales Methodology consumer

WO-024 reads bounded final Revenue Brain artefacts/snapshots and their validated
references as projection input. The methodology service does not create another
brain, edit snapshots or treat its own projection as new customer Evidence. Definition,
source or review changes produce a new immutable projection fingerprint/version.
