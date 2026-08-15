# Action Layer

## Current outcome

WO-021 turns final validated intelligence into reviewable, opportunity-scoped
Action proposals. It closes the loop from Capture to Intelligence to Action while
keeping the human in control.

An Action can be proposed, edited as a new immutable revision, approved, rejected,
superseded, or marked complete manually where that is safe. Approval means only
that a user accepted the proposal. It does not mean RevenueOS sent an email,
created a task, updated a record, scheduled a meeting, or called another system.

## Grounding and action types

Generation reads only current final sources: completed current Meeting Intelligence,
validated Interaction Intelligence, accepted document/email/visual/debrief evidence,
and completed Revenue Brain insights. Live provisional signals, raw transcript text,
unreviewed candidates, stale artefacts and unsupported inference are excluded.

The bounded schema supports follow-up drafts and materials, internal tasks and
reminders, stakeholder follow-up, interaction preparation, proposed opportunity or
contact changes, decisions, commitments, risks, timeline/procurement/security notes,
open-question resolution and conflict review. Each proposal carries priority,
audience, risk class, typed payload and source references.

## User experience

The Opportunity Workspace shows pending, approved and rejected views. Customer-facing
proposals are visibly higher risk. Users can inspect why an Action was recommended,
edit safe fields, approve without execution, reject with a controlled reason, and
manually complete an approved internal Action. Approved customer-facing Actions remain
labelled **Approved — not yet executed**.

Current reviewed Actions can contribute to future Pre-Interaction Brief commitments.
Rejected, superseded and completed Actions do not.

## Explicit limitations

- no email sending, mailbox connection or recipient delivery confirmation;
- no CRM, calendar, task-system or collaboration-tool connector;
- no autonomous agent loop, background executor, retries or execution queue;
- no automatic Opportunity, Contact, Stakeholder or Task mutation;
- no use of provisional Live Intelligence;
- no predictive scoring or guarantee that a recommendation is correct.

The Action Layer is a review and intent-capture surface, not an execution engine.
