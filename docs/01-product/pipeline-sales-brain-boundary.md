# Pipeline and Sales Brain boundary

**Current principle:** Pipeline is workflow state. Sales Brain is evidence-backed
intelligence.

An Opportunity may be in Proposal while its Economic Buyer remains Unknown and Revenue
Brain records a confirmed security requirement. That state is valid. Moving the stage
does not complete a Methodology field, create Evidence, confirm a commitment, change a
Revenue Brain customer fact, generate a buying signal or imply close likelihood.

## Responsibilities

| Surface | Owns | Does not own |
| --- | --- | --- |
| Pipeline | current workflow stage, current seller-entered amount and expected close date, stage history, closure state, seller-reported outcome | Evidence, Methodology truth, probability, forecast, customer commitment |
| Revenue Brain | source-grounded customer and relationship intelligence with provenance | sales-process stage or silent CRM mutation |
| Methodology | evidence state, gaps, conflicts and seller review | stage gates or automatic completion from movement |
| Actions/Daily | explicit next work and deterministic attention | a hidden deal score or autonomous stage mutation |

Pipeline can link back to the Opportunity and show the next open Action. It does not
copy the Methodology matrix or Revenue Brain into every card. No new AI provider,
prompt, model call or reviewed Action mutation was introduced by WO-035.

## Non-negotiable rules

- Stage movement is manual and server-authoritative.
- No Methodology requirement can block movement.
- No stage has a default probability or target duration.
- Won/Lost reasons are labelled `seller_reported`; they are not customer Evidence.
- Operational telemetry contains identifiers and event categories only, never Account
  names, Opportunity names, amounts or outcome notes.
- Analytics may later use canonical history, but it must retain the workflow-versus-
  evidence distinction.

WO-036 may calculate reproducible lifecycle metrics from history. WO-038 may build a
transparent, uncertainty-first forecast after sufficient history exists. Neither is
implemented here.
