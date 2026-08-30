# Opportunity stage and closure guide

## Move an open Opportunity

Choose an active open stage from the board or Opportunity workflow panel. The request
includes the target stage, the stage the user observed and an idempotency key. The
server rejects a stale view, a stage from another organisation, an archived/final
target, a closed Opportunity or an external-authoritative stage.

A successful move transactionally updates the canonical Opportunity, resets
`stage_entered_at`, appends an immutable stage event and records CRM stage/status field
history. It does not update Evidence, Methodology or Revenue Brain.

## Mark Won

`Mark Won` requires an actual close date and permits an optional controlled win reason,
optional seller note and optional final amount. The date cannot be in the future. The
server resolves the pipeline's single Won stage and sets canonical status to `won`.

Win reasons are `solution_fit`, `commercial`, `relationship`, `implementation`,
`existing_customer`, `other` or `unknown`. They remain seller reported.

## Mark Lost

`Mark Lost` requires an actual close date and a controlled reason. Reasons are `price`,
`competitor`, `no_decision`, `budget`, `timing`, `requirements_fit`, `procurement`,
`relationship`, `other` or `unknown`. A short optional internal note is capped at 500
characters. The server resolves the pipeline's single Lost stage and sets canonical
status to `lost`.

The expected close date is not overwritten by the actual close date. The closure event
retains its reason/note/provenance snapshot and CRM field history records later
corrections or reopening.

## Reopen

`Reopen opportunity` requires an explicit active open target stage. It clears the
current closure fields, returns canonical status to `open` and appends a new stage
event. Earlier Won/Lost events, including their seller-reported outcome, remain in
history.

## Stage timing

New records have a reliable `stage_entered_at`; time in stage is derived from it.
Migrated records receive a clearly marked baseline, a tracking-start timestamp and no
fabricated entry time. Their UI says tracking began or timing is unavailable until the
next real transition. Stage history shows snapshot names so a later rename does not
rewrite what users saw at the time.
