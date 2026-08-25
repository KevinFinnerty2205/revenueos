# Integrations

WO-018 adds a meeting-provider adapter contract and deterministic fake only. These
are extension/test boundaries, not a Teams, Zoom or Google Meet connection.
WO-019 adds a document/email extraction provider boundary but accepts sources only
through first-party upload or paste. It is not a mailbox or drive connection; see
the [document and email provider boundary](document-email-provider-boundary.md).

WO-022 adds organisation-scoped **mock** email, calendar, CRM and task connections
for deterministic simulation. They make no external request and must not be
described as working provider integrations. WO-025C adds HubSpot as the sole
feature-gated live CRM provider; no other live CRM, ATS, email, calendar, meeting
or payment provider is represented as connected. Supabase remains a
planned production database/storage provider rather than proof of a configured deployment.

Future adapters require least-privilege credentials, explicit user authority, idempotency, receipts, reconciliation, audit and a real sandbox test before being called complete.

The [integration strategy](integration-strategy.md) defines provider value, data direction, source-of-truth, approval, authentication, recovery, deletion and phased rollout through beta.

WO-021 adds [the Action execution boundary](action-execution-boundary.md) and
[CRM-ready Action payloads](crm-ready-action-payloads.md). These documents describe
reviewable intent. WO-022 implements the simulation portion of that boundary plus a
[future webhook boundary](future-webhook-boundary.md). WO-025C implements the
focused outbound path documented in the [provider decision](crm-provider-selection.md),
[connection guide](hubspot-connection-guide.md) and
[admin setup](crm-admin-setup.md). It does not add broad inbound sync.

WO-026 adds a strict
[Prospect research provider boundary](prospect-research-provider-boundary.md) and a
deterministic synthetic adapter only. No real research/search/company-data provider,
page fetcher, OpenAI synthesis, LinkedIn scraper or paid plan is configured. The mock
makes no network request and fails closed in production; provider selection remains
a separately approved integration decision.
