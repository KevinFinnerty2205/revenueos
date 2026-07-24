# ADR 0019: derive qualitative objection pressure from current-meeting evidence

## Status

Accepted for WO-006B.

## Context

Sales users need an explainable view of resistance and competitive context from
one meeting. A numeric deal-loss probability or score would imply predictive
validity that a single transcript without calibrated outcomes, CRM stage or
account history cannot support. Reusing Risks & Blockers or Buying Signals would
also erase important product distinctions.

## Decision

Objections & Competitive Signals uses the current usable transcript only. It
persists normalised, evidence-paraphrased objections and competitor mentions,
plus one qualitative pressure classification from none through severe or
insufficient evidence. Confidence describes transcript support, never the
likelihood of a commercial outcome. Deterministic rules reject contradictory
status/strength/pressure combinations and summary references unsupported by the
validated items. No hidden weighted score is introduced.

The capability is independently jobbed and persisted. At WO-006B adoption it
joined the aggregate as the seventh extraction beside an eighth Follow-up Email
composition. WO-006C later adds Stakeholder Intelligence without making either
objections or stakeholders a Follow-up Email prerequisite/input.

## Alternatives considered

- A percentage, ranking or deal score was rejected because it would be
  uncalibrated and predictive in presentation.
- Reusing Risks & Blockers was rejected because a risk is an operational threat
  while an objection is expressed resistance; genuine overlap remains possible.
- Reusing Buying Signals was rejected because buying signals describe
  commercial progress or its absence rather than the handling of resistance.
- Cross-meeting or CRM analysis was rejected because those sources and controls
  are outside this work order.

## Consequences

Users receive an explainable current-meeting view with explicit empty and
insufficient-evidence outcomes. The output cannot be treated as a forecast.
Future predictive, cross-meeting or action-oriented work requires a separate
contract, evaluation evidence and decision record rather than silently
extending schema v1.
