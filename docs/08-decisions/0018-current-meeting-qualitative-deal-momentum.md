# ADR 0018: derive qualitative deal momentum from current-meeting evidence

## Status

Accepted for WO-006A.

## Context

Sales users need a concise explanation of whether one meeting contains evidence
of deal progress. A numeric close probability would imply predictive validity
that the current transcript, without CRM stage, account history or calibrated
outcomes, cannot support.

## Decision

Buying Signals uses the current transcript only. It persists normalised
evidence-paraphrased signals and one qualitative classification from strong
positive through insufficient evidence. Confidence measures support in the
available transcript, not likelihood to close. Deterministic consistency rules
reject contradictory polarity/strength/momentum combinations and unsupported
named signal areas in the summary. No hidden weighted score is introduced.

The capability is independently jobbed and persisted. It joins the aggregate as
the sixth extraction; Follow-up Email remains a seventh separate composition and
does not consume it.

## Alternatives considered

- A percentage or score was rejected because it would be uncalibrated and
  predictive in presentation.
- Reusing Risks & Blockers was rejected because risks describe obstacles, while
  Buying Signals explains sales momentum from supported deal evidence.
- Cross-meeting or CRM scoring was rejected because those sources and evaluation
  controls are outside this work order.

## Consequences

Users receive an explainable current-meeting view with explicit insufficient
evidence. The output cannot be treated as a forecast. Later cross-meeting or
predictive work requires a separate contract, evaluation evidence and decision
record rather than silently extending this schema.
