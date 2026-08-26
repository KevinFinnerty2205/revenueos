# Campaign enrolment and stop-condition model

Each eligible launch-audience row creates one enrolment pinned to Campaign/version,
sender, Contact/company reference and recipient name/email/trust/title snapshots.
Only one active campaign may contain a Contact. The snapshot supports audit/export;
the live Contact remains authoritative at execution.

## Stop and defer matrix

| Condition | Result |
| --- | --- |
| organisation suppression, opt-out, complaint or permanent bounce | stop enrolment; block unsent step |
| active Opportunity when campaign rule is enabled | stop enrolment before cold follow-up |
| seller reports replied, meeting booked or not interested | stop; provenance `seller_reported`; cancel future steps |
| seller removes recipient or stops Campaign | stop/cancel future steps |
| Contact deleted | cancel queued retryable execution, scrub live Contact references, retain snapshots |
| global daily quota or cooldown | defer into a future allowed window |
| recipient email/company/title changed | needs attention; do not silently retarget |
| policy, entitlement, sender mailbox or source changed | needs attention; require deliberate resolution |
| provider delivery state unknown | halt Campaign/enrolment; do not retry or schedule the next step |

Pause/resume is a campaign-level control. Pause changes active enrolments to paused;
resume recalculates overdue work with spacing. Completed, stopped and blocked
enrolments never resume implicitly.
