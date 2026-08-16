# Integrations

WO-018 adds a meeting-provider adapter contract and deterministic fake only. These
are extension/test boundaries, not a Teams, Zoom or Google Meet connection.
WO-019 adds a document/email extraction provider boundary but accepts sources only
through first-party upload or paste. It is not a mailbox or drive connection; see
the [document and email provider boundary](document-email-provider-boundary.md).

WO-022 adds organisation-scoped **mock** email, calendar, CRM and task connections
for deterministic simulation. They make no external request and must not be
described as working provider integrations. No live CRM, ATS, email, calendar,
meeting or payment provider is represented as connected; Supabase remains a
planned production database/storage provider rather than proof of a configured deployment.

Future adapters require least-privilege credentials, explicit user authority, idempotency, receipts, reconciliation, audit and a real sandbox test before being called complete.

The [integration strategy](integration-strategy.md) defines provider value, data direction, source-of-truth, approval, authentication, recovery, deletion and phased rollout through beta.

WO-021 adds [the Action execution boundary](action-execution-boundary.md) and
[CRM-ready Action payloads](crm-ready-action-payloads.md). These documents describe
reviewable intent. WO-022 implements the simulation portion of that boundary plus a
[future webhook boundary](future-webhook-boundary.md); no outbound live connector
is implemented.
