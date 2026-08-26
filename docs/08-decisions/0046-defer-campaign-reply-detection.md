# ADR 0046: Defer Campaign reply detection

## Context

Reply is an important stop condition, but WO-030 has no production mailbox adapter,
inbound webhook/read scope, thread correlation or operational rules for auto-replies
and ambiguous messages. Pretending provider send status implies reply would be false.

## Decision

Defer automatic reply detection. Let authorised sellers report `replied`,
`meeting_booked` or `not_interested`; record provenance as `seller_reported` and stop
future steps. Do not create customer Evidence from the outcome or outbound content.

## Alternatives

- **Poll/read the full Inbox:** rejected as excessive scope and privacy risk.
- **Infer replies from activity or send status:** rejected as inaccurate/fabricated.
- **Ignore reply outcomes:** rejected because sellers still need a safe manual stop.

## Consequences

The Campaign UI and metrics must label outcomes honestly. Automatic reply handling
can be reconsidered only with the selected provider, minimum inbound permissions,
thread semantics, retention/deletion and reconciliation tests.
