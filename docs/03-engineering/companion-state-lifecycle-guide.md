# Companion state and lifecycle guide

## State authority

The Interaction lifecycle remains the source of truth. The Companion derives
`BEFORE`, `DURING` and `AFTER`; it does not persist a second phase field.

Foreground Companion state is keyed to the canonical Interaction identifier,
verified organisation, verified user and external identity key. When any part of
that identity changes, the previous lifecycle, brief, markers, recording and
capture state, private local notes and notices are synchronously hidden and the
session is unmounted during the layout commit. Delayed actions and outward
callbacks from the previous session cannot affect the new one. The browser-only
capture choice uses the same organisation/user scope rather than an Interaction
identifier alone.

```text
planned --POST /start--> in_progress --POST /complete--> completed
   |                         |
   +------ cancel -----------+--------------------------> cancelled
```

`POST /api/v1/interactions/{id}/start` is tenant-scoped and idempotent for an
already-started Interaction. It stores the first `actualStartAt`. Existing
Interaction transition validation owns all other lifecycle rules.

## Lifecycle response boundary

The browser treats exact Interaction loads and successful start/complete payloads
as untrusted until a complete runtime decoder verifies the requested Interaction,
the authenticated organisation and the stable relationship, type, origin and
creator anchors. Start must return `in_progress`; complete must return `completed`.

An invalid response cannot update Companion state, invoke an outward callback,
show lifecycle success copy or trigger a post-completion refresh. The last verified
lifecycle, active conversation section, capture choice and private local edits stay
mounted behind a generic accessible warning. A later valid response can recover in
place. These browser checks are defence in depth; tenant-scoped API authorisation
and transition validation remain authoritative.

## DURING substates

Capture choice is `undecided`, `recording` or `passive`. It is stored in
`sessionStorage` under the verified organisation, user and Interaction identity
and is not server evidence.
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

The browser verifies the complete marker list before displaying it. A create
response must confirm the verified user, requested marker type and recording
offset. A delete response must confirm the requested marker ID. If the result is
uncertain, **Refresh markers** reads the authoritative list before enabling
further marker changes. Existing markers and unsaved private notes stay visible
while the list is checked.

## AFTER state

The latest recording, active visual count and active marker count form the
capture summary. The Opportunity Workspace uses a tenant-scoped bounded query
to expose the latest linked Interaction capture status, including processing,
review-required and completed states.

The Companion validates marker, recording and photo lists independently. Each
list must contain only complete entries for the active Interaction, with unique
record identities. If a list cannot be verified, the summary retains the prior
verified values for that list. A verified empty list clears the corresponding
summary. The photo panel uses the same list check and confirms the exact photo
ID in a deletion acknowledgement. The Companion verifies recording metadata in
activity and finalisation callbacks while keeping the recorder's local
completion guard active.

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
