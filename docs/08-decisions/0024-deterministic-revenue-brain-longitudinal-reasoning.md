# ADR 0024: Derive Revenue Brain changes deterministically from snapshots

- **Status:** Accepted
- **Date:** 2026-07-25

## Context

WO-008A introduced immutable Revenue Brain snapshots that reference nine
validated Meeting Intelligence artefacts. WO-008B needs explainable
cross-meeting change detection without reopening the deliberately supplied
transcript, repeating extraction, introducing predictive scoring or allowing a
model to invent facts.

The existing provider and worker can execute long-running AI work, but this
comparison is small, bounded and fully expressible with controlled state
transitions. Sending source artefact content to a provider would add latency,
cost and a second fact-introduction boundary without improving v1 reliability.

## Decision

- Compare only immutable snapshots, their nine exact referenced validated
  artefacts and completed, non-deleted meeting metadata.
- Never load transcript rows or raw text and never call an extraction,
  provider, prompt registry, worker or job flow.
- Use code-deployed deterministic matching, state transitions, confidence and
  summary wording for reasoning version `1`.
- Treat the latest eligible pair as the default. Bound recent history to the
  latest 10 eligible snapshots after scanning at most 50 candidates.
- Match entities conservatively and never infer negative changes from missing
  later content. Resolution, departure, completion or deterioration requires
  explicit supported evidence.
- Validate every evidence tuple against the two selected snapshots and their
  referenced artefacts before persistence.
- Persist one immutable `RevenueBrainInsight` per organisation, scope, scope
  target, snapshot pair and reasoning version. Account and opportunity scopes
  are distinct.
- Generate synchronously and explicitly on demand. GET operations remain
  read-only and report when the current pair has not been generated.
- Expose controlled change records and a concise summary in the Opportunity
  Workspace and account timeline without gauges, probability, forecast or raw
  evidence identifiers.

## Alternatives

- **Provider-generated reasoning:** rejected for v1 because deterministic
  transitions already cover the approved contract and a provider could
  introduce unsupported claims.
- **Transcript comparison:** rejected because snapshots and referenced
  artefacts are the authorised source boundary.
- **Automatic creation in the snapshot completion transaction:** rejected
  because on-demand comparison is cheap, explicit and avoids hidden work.
- **Mutable latest-state rows:** rejected because updates would erase the
  evidence and semantics used for an earlier comparison.
- **Fuzzy names, embeddings or vectors:** rejected because identity merging
  would become probabilistic and broaden the approved infrastructure.
- **Absence means resolved:** rejected because silence is not evidence.

## Consequences

The product gains a bounded, refresh-stable history of explainable changes with
no new external content transfer. A later snapshot creates a new immutable
comparison and preserves older pairs. Repeated or concurrent requests reuse the
same record.

Version 1 intentionally misses changes that cannot be established
conservatively from the existing schemas. Explicit answered-question and
completed-action states require a separately approved schema change. Any future
provider-written narrative must remain subordinate to the deterministic change
set, use a new reasoning version and preserve the transcript-free boundary.
