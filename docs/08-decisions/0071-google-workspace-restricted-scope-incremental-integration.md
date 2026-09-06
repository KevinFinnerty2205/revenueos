# ADR 0071: use seller-delegated Google Workspace OAuth and bounded incremental reconciliation

- **Status:** Accepted for WO-041; awaiting engineering review
- **Date:** 2026-09-06

## Context

Google Workspace launch support needs reviewed seller-bound Gmail sending, reply
reconciliation and useful Calendar context without becoming a full-mailbox ingestion
or a generic Workspace integration. Gmail's narrow send scope is sensitive, while
fetching strongly correlated reply bodies requires the broader restricted
`gmail.readonly` scope. Google push/watch would add Pub/Sub or public channel lifecycle
before production infrastructure exists.

## Decision

Use confidential web-server OAuth with PKCE and signed OIDC validation, managed
Workspace accounts only, one Microsoft-or-Google primary mailbox per Oryntela seller,
`gmail.send`, `gmail.readonly` and `calendar.events.readonly`, and the existing
encrypted credential/provider-neutral receipt/reply/event/sync tables.

Bound actual Gmail processing below the technical permission: 30-day metadata-only
Inbox/Sent initial scans, Gmail History thereafter, and a full body fetch only after
one strong operation correlation. Use a 14-day-past/90-day-future primary Calendar
window with sync tokens. Poll through the durable worker every five minutes rather
than adding push infrastructure. Private event detail, inbound attachments and raw
payloads are discarded. Ambiguous sends stay unknown and are not blindly retried.

## Alternatives rejected

- `gmail.metadata` plus `gmail.send`: cannot provide the matched reply body, and adding
  it alongside `gmail.readonly` would not reduce the broader grant.
- Gmail modify/full-mailbox scope: unnecessary authority.
- Calendar write: no authorised creation/update workflow in WO-041.
- Consumer Gmail: widens account/privacy/support posture without launch need.
- Alias/delegated sending: provider configuration strings do not by themselves prove
  sender authority and settings access adds restricted scope burden.
- Push first: Pub/Sub/webhook/channel verification, renewal and recovery complexity is
  not justified before a production environment exists.

## Consequences

The restricted Gmail scope requires explicit customer explanation, Google verification
and likely an approved security assessment before external production use unless
Google confirms an exception. Polling introduces bounded latency. In return, Microsoft
and Google share commercial and security invariants while keeping provider-specific
cursor/thread semantics in adapters. Production remains disabled until owner-managed
Google project, domain, verification, legal/privacy, monitoring and smoke-test gates
are complete.
