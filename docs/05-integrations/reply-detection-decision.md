# Reply-detection decision for Campaigns

- **Decision:** defer automatic reply detection in WO-030
- **Current behaviour:** seller-reported outcomes only

Reliable reply detection requires an approved mailbox ecosystem, least-privilege
inbound/read scopes, thread correlation, webhook/reconciliation handling, retention
and erasure controls, shared-mailbox authority, incident response and clear semantics
for auto-replies, forwards and out-of-office messages. WO-030 has none of those
production capabilities and must not fabricate them from outbound status.

Sellers may report replied, meeting booked or not interested. The event is stored as
`seller_reported`, stops future steps and does not become customer Evidence.
Provider-accepted send state is not delivered, opened or replied.

A later decision may implement reply detection only alongside the selected production
mailbox adapter, smallest justified read/webhook permissions, explicit tenant/sender
authority and contract tests for ambiguous thread state. Polling an unrestricted
Inbox and heuristic/fake reply inference are rejected.
