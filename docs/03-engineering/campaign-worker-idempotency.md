# Campaign worker, leases and idempotency

Campaign scheduling runs inside the existing durable worker process. It introduces no
microservice, queue or message broker. Organisation discovery is bounded; claims use
`FOR UPDATE SKIP LOCKED`, a worker ID, lease expiry and attempt counter. Recovery maps
an abandoned step back to pending/prepared/review/queued based on durable Outreach
and Action Execution state.

Preparation is idempotent because each enrolment/sequence-step pair and each
Campaign-step/Outreach relationship are unique. Send execution reuses WO-022's unique
Action version/connection/capability and SHA-256 idempotency key. Scheduler recovery
never creates a second provider request when an Action Execution exists.

Reconciliation treats queued/executing/retryable as queued. Confirmed success marks
the step sent and creates exactly one next step relative to actual completion.
Permanent failure blocks the enrolment. `unknown_external_state` changes the step to
`unknown_delivery_state`, clears future schedule and places Campaign/enrolment in
needs attention; automatic retry is forbidden.

Unexpected exceptions are caught at the claim boundary, transaction state is rolled
back and the exact claim fails closed with a safe code. Logs contain tenant,
Campaign/enrolment/step IDs, state, mode and safe codes—not recipient identity,
message content, research text or provider payloads.
