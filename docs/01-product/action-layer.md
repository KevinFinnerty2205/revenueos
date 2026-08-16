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
manually complete an approved internal Action. Approved Actions are labelled
**Approved — execution requires confirmation**; the separate execution endpoints
still fail closed unless the complete WO-022 simulation flag set is enabled.
Users must review an exact server preview and make a separate final confirmation.

Current reviewed Actions can contribute to future Pre-Interaction Brief commitments.
Rejected, superseded and completed Actions do not.

## WO-022 simulation boundary

WO-022 adds deterministic mock email, calendar, CRM and task execution after
approval. It does not change the review lifecycle: approval never queues work and
the execute request cannot replace approved content. The simulation lifecycle and
history are separate from the Action's review status.

## Explicit limitations

- no real email sending, mailbox connection or recipient delivery confirmation;
- no real CRM, calendar, task-system or collaboration-tool connector;
- no autonomous agent loop or live external execution;
- no automatic Opportunity, Contact, Stakeholder or Task mutation;
- no use of provisional Live Intelligence;
- no predictive scoring or guarantee that a recommendation is correct.

The Action Layer remains the review/intent source. WO-022's separate execution
engine performs simulations only.

## WO-023 future Sales OS use

Engage outreach, Create delivery, CRM updates and closed-won handover must reuse the
Action Layer for reviewable consequential intent. Research, methodology, forecast or
manager recommendations cannot approve themselves. Live providers, policy-based
batches and any lower-risk automation require separately authorised work and must
preserve exact-input versioning, revocation and user-visible state. See the
[End-to-End Sales Platform roadmap](../06-roadmap/end-to-end-sales-platform-roadmap.md).

## WO-024 methodology source

Current final methodology gaps can produce review-only Prepare Next Interaction or
Review Conflict candidates through the existing Action generation service. Proposals
cite the immutable methodology projection. Approval rechecks that the projection is
still current. Provisional Live Intelligence and unsupported methodology conclusions
cannot create or execute Actions.
