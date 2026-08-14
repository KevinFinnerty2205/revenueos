# Candidate evidence and review

Structured extraction creates Candidate Evidence only. Each item is tenant/session/
Interaction scoped and points to one Evidence Fragment. The database forces
`origin_class=salesperson_reported`, `support_class=reported` and an initial
unreviewed/pending state.

The review screen shows category, statement, source label and an editable statement.
The user must submit exactly one accept/reject decision for every pending candidate.
An accepted edit preserves `original_statement`; a rejection never creates accepted
Evidence. Accepted items create new verified Evidence and retain the fragment/session
lineage. Candidate review state is guarded by database constraints and a transition
trigger.

Completion composes snapshots once. Repeated review submissions return the existing
result; tenant-scoped row locks and unique keys prevent concurrent submissions from
double-applying accepted Evidence or intelligence. Candidate/provider output is not
authoritative before this step.

Deletion follows Interaction/Capture Session ownership. Export includes reviewable
records and lineage but omits idempotency keys, provider request identifiers and
other internal processing metadata.
