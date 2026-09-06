# ADR 0070: Seller-delegated Microsoft Graph with bounded delta reconciliation

- **Status:** Accepted for WO-040
- **Date:** 2026-09-06

## Context

Engage already has immutable review, server scheduling, suppression, tenant-safe
execution and provider-neutral integration boundaries, but no production-capable
mailbox. Microsoft `sendMail` returns `202 Accepted` without an idempotency key or
message ID. Reply/calendar value must not turn Oryntela into a mailbox or calendar
archive. Production infrastructure has no public Microsoft webhook endpoint and no
owner-authorised Entra application.

## Decision

Use a multi-tenant confidential Microsoft identity application restricted to delegated
work/school accounts. Bind one `/me` mailbox/calendar connection to each Oryntela user,
request only `openid offline_access User.Read Mail.Send Mail.Read
Calendars.ReadBasic`, and keep tokens in the encrypted credential store.

Persist provider-neutral outbound operation, relevant reply, bounded calendar event
and delta sync state. Write the stable Oryntela operation ID into an outbound header,
persist `submitting` before Graph, and never retry an ambiguous write. Reconcile
positive sender/recipient evidence from Sent Items. Poll folder/calendar delta in the
existing worker with fixed origin, page, response-size and time-window bounds.
Webhooks may later wake this reconciliation loop but are not its authority.

## Alternatives

- Application permissions and tenant-wide mailbox access were rejected as excessive
  for seller-owned workflows.
- `Mail.ReadWrite` was rejected because Oryntela does not mutate mailbox content.
- `Mail.ReadBasic` was rejected because it cannot supply relevant reply body content.
- Webhook-first delivery was rejected for WO-040 because it adds public callback,
  validation/client-state secrets, subscription renewal and missed-event operations.
- Blind retry or an exactly-once claim was rejected because Graph does not prove it.
- Shared/alias sending was deferred because mailbox strings do not prove Exchange
  Send As authority.

## Consequences

Ambiguous sends can remain visibly unknown until reconciled or resolved, prioritising
recipient safety over automatic completion. Delta sync is operationally simpler and
privacy-bounded but has polling latency. `Mail.Read` consent needs clear customer
explanation even though Oryntela retains only strongly linked mail. Production remains
disabled until owner-managed registration, legal/privacy/provider approval, monitoring
and an authorised smoke test are complete.
