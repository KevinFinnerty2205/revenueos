# Campaign sequence scheduling architecture

- **Status:** implemented; deterministic scheduler, no AI send-time optimisation

Campaign time is stored as timezone-aware UTC. A published version pins the sender's
IANA timezone, ISO weekdays and minute-based local send window. The scheduler converts
candidate times through `zoneinfo`, advances weekends/disallowed weekdays and stores
the resulting UTC timestamp. WO-030 defaults to weekdays 08:30–17:00
Australia/Sydney; DST therefore follows the pinned IANA timezone.

The first eligible recipient starts at launch-window time and recipients are spaced
five minutes apart. A later step is created only after the prior Action Execution is
confirmed `succeeded` or `simulated_success`, using that completion timestamp plus
the step's calendar delay. No future sequence backlog is pre-created. Pausing stops
claims; resume recalculates overdue work inside the next permitted window with the
same recipient spacing. Quota/cooldown deferral also computes a future permitted
window, so downtime cannot release a burst.

Drafts are prepared up to 24 hours before scheduled time, capped at 100 Campaign
drafts per organisation/day. Review mode ends preparation in `ready_for_review`.
Auto-send ends in `prepared`, then a separate due-send claim performs full preflight,
campaign-authorised approval, exact preview and provider confirmation.

The existing durable worker performs a bounded Campaign pass before and after Action
Execution work. PostgreSQL discovery uses a security-definer function returning only
eligible organisation IDs; every claim transaction sets trusted tenant context.
