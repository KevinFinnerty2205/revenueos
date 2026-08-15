# Companion state and lifecycle guide

## State authority

The Interaction lifecycle remains the source of truth. The Companion derives
`BEFORE`, `DURING` and `AFTER`; it does not persist a second phase field.

```text
planned --POST /start--> in_progress --POST /complete--> completed
   |                         |
   +------ cancel -----------+--------------------------> cancelled
```

`POST /api/v1/interactions/{id}/start` is tenant-scoped and idempotent for an
already-started Interaction. It stores the first `actualStartAt`. Existing
Interaction transition validation owns all other lifecycle rules.

## DURING substates

Capture choice is `undecided`, `recording` or `passive`. It is stored in
`sessionStorage` under the Interaction identifier and is not server evidence.
Phone calls and online meetings derive passive mode regardless of stored choice.

Recording state is owned by the WO-015 recording lifecycle. The Companion
receives a narrow activity projection from the recording component:

- active state;
- whether completion must be blocked;
- elapsed seconds; and
- current recording session.

The interaction cannot complete while recording is active, finalisation is in
progress or audio remains queued in the current tab. A backend rule separately
rejects a second active recording session for the same tenant Interaction.

## Marker state

Markers can be created and soft-deleted only while the Interaction is
`in_progress`. Creation is idempotent per organisation, Interaction, creator
and idempotency key. Metadata is immutable; only the first soft-delete
transition is permitted. Completed Interactions expose markers read-only.

## AFTER state

The latest recording, active visual count and active marker count form the
capture summary. The Opportunity Workspace uses a tenant-scoped bounded query
to expose the latest linked Interaction capture status, including processing,
review-required and completed states.

No phase transition automatically generates evidence or intelligence. Existing
recording transcription, Visual Evidence review and AI Debrief review rules
remain authoritative.

## Live Intelligence substate

The optional live aggregate has its own server lifecycle:
`active → processing → active → stopped → completed`, plus safe `failed`/`expired`
states. It is not a second Interaction phase. Polling never supplies the cursor and
cannot advance it without contiguous segments. Interaction completion locks and
freezes active processing state. Final reconciliation is available only after normal
final Interaction Intelligence exists (or reports unresolved when it does not).

See [incremental processing](live-intelligence-incremental-processing.md) and
[reconciliation](live-intelligence-reconciliation.md).
