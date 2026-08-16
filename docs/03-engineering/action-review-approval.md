# Action review and approval

Review is deliberate and server-authoritative. A reviewer sees the proposal type,
priority, audience/risk labels, editable content, proposed due date, typed payload,
provenance summary and human-readable source labels.

Editing preserves the original version and creates a new one. Approval validates the
expected version, state, payload relationships and source currency inside the tenant.
For a follow-up draft, any selected recipient must match a stored Contact and email;
approval still does not send. Proposed record changes validate allowed fields and
values but do not mutate the record.

Rejection uses one of: already done, incorrect, not relevant, unsupported, duplicate,
not now or other. Manual completion is available only for internal approved Actions;
it records user-reported completion and is not evidence that an external system ran.

The UI must never label approval as execution or imply delivery confirmation.
WO-022 may expose a consequentially labelled capability button only after a second,
read-only server preview inside a prominent simulation panel. That button confirms
the exact preview; it does not accept editable content and never contacts a live
provider.
