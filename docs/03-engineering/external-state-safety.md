# External-state safety

RevenueOS remains the source of approved intent; a connected system may be the
source of current external state. Execution must never silently overwrite state
that changed after review.

WO-022 demonstrates this with Mock CRM. A preview shows one allowlisted field,
one target, expected current value and proposed value. At worker time the adapter
compares current simulated external state with the approved expected value. A
mismatch ends as `failed_permanent` with `stale_external_state`; the canonical
RevenueOS Opportunity or Contact is not mutated.

Calendar requires an exact ISO date/time with timezone and fixed validated
Contact attendees. Email requires a confirmed Contact/email pair and non-empty
approved subject/body. Task creation fixes the approved linked Opportunity,
nullable owner, due date and context. Execute requests cannot provide arbitrary
replacement payloads.

For a future live connector, expected-version or ETag support is preferred.
Otherwise the adapter must read immediately before mutation, compare a normalised
allowlisted state, and stop on uncertainty. Conflict resolution belongs in a new
review cycle, not in an automatic retry.
