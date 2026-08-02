# Revenue Brain longitudinal reasoning

## Current product boundary

WO-008B adds the first longitudinal Revenue Brain capability. It compares
immutable, validated Revenue Brain snapshots and persists an explainable account
or opportunity insight. It does not read a transcript, re-run Meeting
Intelligence, call an AI provider, predict an outcome, produce a deal score or
change another system.

Version 1 is deliberately deterministic. Application code is authoritative for
snapshot selection, conservative matching, change classification, evidence,
confidence and summary wording. A provider would add cost and a second
fact-introduction boundary without improving the reliable v1 contract, so no
prompt, schema registry entry, AI job type, worker flow or OpenAI allowlist was
added.

Reasoning is created on demand. Automatic creation was rejected for v1 because
it would add hidden work to snapshot completion and is unnecessary for bounded
deterministic comparison.

## Source boundary

The reasoning repository may select only:

- `RevenueBrainSnapshot`;
- each snapshot's nine referenced `AIArtifact` rows;
- company and opportunity identifiers required to resolve scope; and
- completed, non-deleted meeting metadata required for ordering and links.

It has no transcript dependency and never joins `transcripts`, selects
`raw_text`, calls a transcript repository, renders a prompt or reads a provider
payload. Referenced artefacts are loaded in one bounded query and must still
pass their code-deployed strict schema. Every artefact must match the trusted
organisation, snapshot meeting, expected type and expected schema version. All
nine references must share one artefact transcript ID/version trace, but no
transcript row or body is loaded.

Malformed snapshots, missing references, invalid artefacts, mixed transcript
traces, deleted meetings and non-completed meetings are ineligible.
Follow-up Email is never a reasoning source.

## Snapshot selection

Candidates are scanned with explicit organisation and scope predicates. At most
50 candidates are considered to find up to the latest 10 eligible snapshots.
The deterministic order is:

1. meeting date descending;
2. snapshot schema version descending;
3. snapshot creation time descending; and
4. snapshot UUID descending.

`latest_change` compares the latest eligible snapshot with the immediately
preceding eligible snapshot. `recent_history` creates or reuses each adjacent
comparison across the bounded latest-10 window.

Opportunity scope requires both snapshots and both meetings to carry the same
explicit opportunity ID. Account scope requires the same company and may
compare adjacent company snapshots from different or company-level opportunity
associations; the API explicitly identifies this as aggregated account history.
Account and opportunity insights use distinct idempotency scopes.

Fewer than two eligible snapshots returns `insufficient_history`. When two or
more eligible snapshots exist but their latest pair has not been compared, GET
returns `not_generated` while retaining older immutable insight history.

## Strict output and evidence

`RevenueBrainInsightContent` rejects unknown fields and contains:

- account or opportunity scope;
- required from/to snapshot and meeting IDs;
- required date-only comparison period in forward order;
- zero to 50 controlled change records;
- a concise deterministic summary; and
- finite comparison confidence from 0 to 1.

Each change has a controlled type, direction, importance, title, description,
confidence, one or more allowed source capabilities and one to eight structured
evidence references. Evidence identifies only a selected snapshot, one of its
referenced artefacts, an artefact type, a stable entity key, a field and a short
normalised value. Stakeholder and free-text entity keys contain a truncated
SHA-256 digest rather than a person's name or source sentence. Product APIs do
not expose evidence artefact IDs or entity keys in the rendered UI.

The service validates every `(snapshot, artefact, capability)` evidence tuple
against the selected bundles before persistence. Evidence cannot refer to a
future, unrelated, unreferenced or cross-tenant source.

Summary composition uses only the highest-importance validated change title and
the bounded change count. When the snapshots contain no material supported
change it uses exactly:

> No material supported changes were identified between the latest eligible
> meetings.

Confidence represents support for the comparison, not likelihood of winning.

## Deterministic matching and change rules

Buying Signals compare controlled signal types and explicit strength. Paired
states cover budget, timeline, decision-maker engagement, procurement, urgency,
next-step commitment, stakeholder alignment, technical fit and security/legal
progress. Commercial intent and procurement can strengthen only with explicit
later evidence.

Objections and risks match by identical category plus either identical
normalised text or conservative token overlap of at least two meaningful terms
and a Jaccard score of at least 0.55. Open questions, decisions and action items
use the same conservative text rule within their own capability. There are no
embeddings, vector search or cross-capability identity merges.

Stakeholders match only by the same punctuation-normalised explicit name or the
same anonymous label. Matching is case-insensitive but performs no fuzzy person
resolution. Role, influence and stance transitions can yield champion,
economic-buyer, technical-buyer, blocker and general stakeholder changes.
`champion_disappeared` requires matched later evidence with an explicit
departure phrase; absence is insufficient.

Named competitors match by exact normalised name. Position changes use the
controlled position states. Absence does not remove a competitor.

Risks emit introduced, severity change, persisted or explicitly resolved.
Resolution requires explicit later resolution language in the matched validated
risk. Questions missing later are not answered. Current Action Items can emit
new, owner-change and due-date-change records; their schema has only `open`
status, so absence never means completion and system time never creates overdue
evidence. Next Best Action compares the normalised overall recommendation and
priority and never treats a recommendation as executed.

### No negative inference from silence

Missing later content never means disappeared, weakened, resolved, answered,
completed, removed or negative. Later `not_discussed` is distinct from
`not_identified` and `unclear`. A negative or resolved transition requires an
explicit supported later state. This rule is regression-tested across
objections, competitors, stakeholders, risks, questions and action items.

## Persistence and idempotency

Migration `0019_revenue_brain_reasoning` adds `RevenueBrainInsight`.
Rows contain tenant and scope ownership, from/to snapshot references, reasoning
version `1`, completed status, validated content JSON and creation time. They
have no update time.

Composite tenant foreign keys protect the company, optional opportunity and
both snapshots. A non-null internal scope-target ID equals company ID for
account scope and opportunity ID for opportunity scope. The unique key covers
organisation, scope, target, from snapshot, to snapshot and reasoning version.
The table has account/opportunity history indexes, forced PostgreSQL RLS and
database triggers that reject every update and delete.

The service checks for an existing completed equivalent before comparison.
Creation runs inside a savepoint; a concurrent unique-key winner is re-read and
reused. A new snapshot creates a new pair while old insights remain immutable.
Comparison semantics will advance `reasoning_version` rather than changing the
meaning of stored version-1 history.

Downgrading to `0018_revenue_brain` drops all longitudinal insights permanently
but leaves snapshots intact. Back up the table before rollback if its history
must be retained.

## API

The same safe contract is available at:

- `POST /api/v1/opportunities/{opportunityId}/brain/reasoning`;
- `GET /api/v1/opportunities/{opportunityId}/brain/reasoning`;
- `POST /api/v1/accounts/{accountId}/brain/reasoning`; and
- `GET /api/v1/accounts/{accountId}/brain/reasoning`.

POST accepts `mode=latest_change` by default or
`mode=recent_history`. Deterministic comparison is bounded and synchronous;
there is no external provider latency or cost. POST returns whether any
equivalent insight was newly created. GET returns the latest insight only when
it matches the current latest eligible pair, plus up to 10 recent immutable
insights.

The public state enum includes `insufficient_history`, `not_generated`,
`queued`, `running`, `completed`, `failed` and `cancelled` for contract
stability. This synchronous v1 normally produces only the first, second and
completed states.

Responses contain no transcript, raw artefact body, provider/model/prompt/schema
registry data, worker/lease state or raw error.

## Product integration

The Opportunity Workspace aggregate response includes the current safe
reasoning state and latest matching completed insight without creating work.
The **Longitudinal Changes** section appears after the opportunity controls and
before current-meeting intelligence. It shows the period, summary, up to six
important changes, explicit direction/importance text, confidence, source
capability labels and meeting links. It includes generation, insufficient,
not-generated, no-material-change and safe unavailable states. It has no gauge,
forecast, probability, transcript excerpt or raw ID.

The account Revenue Brain page loads snapshots and reasoning together. Its
bounded latest-10 timeline shows meeting and opportunity links plus the concise
adjacent insight summary when present. It has no graph, score, infinite loading
or free-form chat.

Both surfaces use semantic headings and lists, keyboard links/buttons, visible
focus, responsive layouts and text labels that do not rely on colour.

## Telemetry and audit

Metadata-only logs cover requested, reused, insufficient-history, selected
snapshots, comparison start, counts by controlled change type/direction/
importance, no-material-change, completed and viewed events. Logs include
tenant/scope IDs and counts, never descriptions, summaries, evidence values,
stakeholder names, account/opportunity names, generated artefact content or
transcript content.

The existing append-only meeting audit stream records
`revenue_brain_reasoning_requested` and `revenue_brain_insight_created` in
metadata. It stores the scope, reasoning version, insight ID and change count
only. It does not copy source or generated content.

## Validation

Tests cover strict contracts, controlled taxonomy, deterministic ordering,
bounded recent history, conservative matching, no inference from silence,
evidence ownership, missing/invalid references, account/opportunity and tenant
isolation, idempotent reuse, new-snapshot history, audit minimisation, aggregate
API safety, UI states, refresh persistence, migration
upgrade/downgrade/re-upgrade, append-only enforcement and forced RLS.

One API regression records every SELECT during reasoning and asserts that
neither `transcripts` nor `raw_text` appears. Automated tests use stored
artefacts and make no OpenAI call.

## Known limitations and future v2 boundary

- Reasoning uses validated snapshots only and cannot recover facts absent from
  them.
- Matching is conservative and code-deployed.
- Named people match only by normalised explicit name; anonymous labels must be
  identical.
- Absence never establishes resolution or deterioration.
- Action completion and answered questions require future schemas with explicit
  states.
- There are no embeddings, semantic vectors, CRM context, opportunity health,
  close probability, forecast, scoring, chat, relationship graph, automatic
  action execution or cross-account benchmarking.
- Production customer data remains prohibited unless separately approved.
  WO-009 feature-gates Revenue Brain and its approved retention/deletion path
  removes dependent immutable insights/snapshots before source records.

Revenue Brain v2 may add separately approved explicit lifecycle states or an
optional provider summary composer. It must preserve deterministic changes as
authoritative and cannot broaden the transcript boundary implicitly.

WO-010 further defines Revenue Brain's target as customer-relationship intelligence
over validated meetings, presentations, workshops, site visits, debrief-supported
interactions, documents, emails and supported changes. The current version-1
deterministic comparison remains unchanged and never reads those future sources.
Cross-version reasoning requires an explicit normalised structured projection that
preserves origin, conflict and verification, never rewrites historical insights and
never treats absence as resolution. See the
[evidence and provenance model](evidence-and-provenance-model.md) and
[Interaction Intelligence migration strategy](interaction-intelligence-migration-strategy.md).

WO-011 does not add an Interaction reasoning source or change version-1 comparison.
Historical snapshots/insights keep their exact Meeting, transcript and artefact
references; retention removes the linked Interaction only in the same approved
dependency-ordered Meeting deletion path.
