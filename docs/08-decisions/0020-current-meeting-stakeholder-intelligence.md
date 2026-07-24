# ADR 0020: model stakeholders as cautious current-meeting evidence

## Status

Accepted for WO-006C.

## Context

Sales users need a clear view of who participated in a buying conversation and
which buying roles are covered. One transcript cannot establish durable
relationships, CRM identity, account history or predictive influence. A graph or
numeric stakeholder score would overstate what the source can support, while a
single generic participant label would hide useful evidence-bound distinctions.

## Decision

Stakeholder Intelligence uses only the current usable transcript. It persists a
bounded list with one primary role per named or explicitly supported anonymous
stakeholder, qualitative influence, stance, meeting engagement, evidence and
confidence. Six fixed coverage fields distinguish identified, not identified,
unclear and not discussed roles. Deterministic rules reject contradictions and
unsupported names, roles or relationship claims. Confidence describes source
support and no hidden weighted score is introduced.

The capability is independently jobbed and persisted as the eighth extraction.
Follow-up Email remains a ninth, separate composition and neither requires nor
consumes Stakeholder Intelligence.

## Alternatives considered

- A relationship graph or historical stakeholder map was rejected because the
  work order has one meeting source and no identity-resolution/history controls.
- A numeric influence, health or deal score was rejected because it would imply
  calibration and outcome prediction that the source cannot support.
- Inferring roles from titles or seniority was rejected because authority and
  advocacy require explicit meeting evidence.
- MEDDICC/BANT coverage was rejected because those methodologies and their
  broader data needs are outside the approved contract.
- Reusing Meeting Participants was rejected because attendance metadata does not
  establish a buying role, stance or influence.

## Consequences

Users receive an explainable, current-meeting stakeholder view with explicit
uncertainty and a successful insufficient-evidence outcome. Anonymous labels are
allowed when the transcript supports a role but no name. The output cannot be
treated as durable account truth or used as a forecast. Historical, graph,
identity-resolution, scoring or action-oriented work requires a new source,
privacy model, evaluation evidence and decision record.
