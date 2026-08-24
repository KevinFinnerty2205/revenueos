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

WO-025C applies that rule to HubSpot, whose object APIs do not provide the required
conditional update primitive for this path. Preview fetches the mapped allowlisted
field and provider update timestamp. The worker fetches it again, reconstructs the
preview fingerprint and stops with `stale_external_state` if it changed. Amounts use
exact decimal normalisation and require matching currency context; no conversion is
performed. Conflict resolution belongs in a fresh preview/review cycle, not an
automatic retry.
