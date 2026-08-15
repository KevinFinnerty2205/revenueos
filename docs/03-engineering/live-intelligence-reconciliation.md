# Live-to-final reconciliation guide

## Purpose

Reconciliation makes the difference between provisional and final interpretation
visible. It never makes live output authoritative and never writes a final claim.

The service loads the latest final `InteractionIntelligenceSnapshot` for the same
tenant and Interaction, normalises its structured items and compares each retained
live signal deterministically.

## Outcomes

- `confirmed`: final intelligence contains the same normalised type and statement;
- `revised`: the same signal type/subject is present with materially different final
  wording;
- `unsupported`: final intelligence exists but contains no compatible item; and
- `unresolved`: no final snapshot or insufficient final structure is available.

Confirmed or revised, non-dismissed live records become `promoted_candidate` only as
a live-history lifecycle label. The final snapshot is still the authority and the
live statement is not copied into it. Superseded/expired records are excluded from
classification; dismissed records retain their dismissal and can still carry a
comparison outcome.

## Product display

The completed Live Companion shows a small count summary and per-signal final-review
labels. The full final intelligence remains on its normal Interaction/Opportunity
surface. Refresh reads persisted outcomes.

## Gap-fill Debrief

The Debrief repository adds generic targeted prompts only for live gap types that
remain pending, unsupported or unresolved and were not dismissed. Confirmed/revised
signals are not asked again. The prompt never embeds the live statement, transcript
excerpt, participant name or provider rationale.

This keeps the question useful—such as clarifying procurement ownership—without
turning uncertain live text into a leading assertion.
