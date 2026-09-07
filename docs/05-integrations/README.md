# Integrations

WO-018 adds a meeting-provider adapter contract and deterministic fake only. These
are extension/test boundaries, not a Teams, Zoom or Google Meet connection.
WO-019 adds a document/email extraction provider boundary but accepts sources only
through first-party upload or paste. It is not a mailbox or drive connection; see
the [document and email provider boundary](document-email-provider-boundary.md).

WO-022 adds organisation-scoped **mock** email, calendar, CRM and task connections
for deterministic simulation. They make no external request and must not be
described as working provider integrations. WO-025C added the first feature-gated
HubSpot path. WO-042 now adds production-capable but inactive HubSpot and Salesforce
account/contact/opportunity adapters behind explicit admin, entitlement and activation
gates. No provider app, key, account, spend, customer-data smoke test or production
activation was performed. No ATS, meeting or payment provider is represented as
connected. Supabase remains a planned production database/storage provider rather
than proof of a configured deployment.

Future adapters require least-privilege credentials, explicit user authority, idempotency, receipts, reconciliation, audit and a real sandbox test before being called complete.

The [integration strategy](integration-strategy.md) defines provider value, data direction, source-of-truth, approval, authentication, recovery, deletion and phased rollout through beta.

WO-021 adds [the Action execution boundary](action-execution-boundary.md) and
[CRM-ready Action payloads](crm-ready-action-payloads.md). These documents describe
reviewable intent. WO-022 implements the simulation portion of that boundary plus a
[future webhook boundary](future-webhook-boundary.md). WO-025C implements the
focused outbound path documented in the [provider decision](crm-provider-selection.md),
[connection guide](hubspot-connection-guide.md) and
[admin setup](crm-admin-setup.md). It does not add broad inbound sync.

WO-042 adds the bounded provider-neutral lifecycle described in the
[production CRM connector architecture](../03-engineering/production-crm-connectors.md),
[field authority matrix](../03-engineering/crm-authority-matrix.md) and dated
[provider research](crm-provider-research-2026-09-06.md). V1 deliberately uses
polling, allow-listed fields and per-record reviewed writeback. Dynamics 365,
webhooks/CDC, arbitrary objects/custom fields, files, notes, broad activity sync and
autonomous writes remain deferred.

WO-026 adds a strict
[Prospect research provider boundary](prospect-research-provider-boundary.md) and a
deterministic synthetic adapter only. No real research/search/company-data provider,
page fetcher, OpenAI synthesis, LinkedIn scraper or paid plan is configured. The mock
makes no network request and fails closed in production; provider selection remains
a separately approved integration decision.

WO-027 extends that synthetic boundary to company-scoped person discovery,
professional research and expiring business contact fields. The
[provider evaluation](person-contact-provider-evaluation.md) and
[licensing/storage decision](person-provider-licensing-storage-decision.md) document
why no live provider, trial or paid service was activated. No scraping fallback was
added and standard tests make no real external provider request.

WO-028 adds a provider-neutral company-discovery boundary for Target Markets. Apollo,
People Data Labs and Crunchbase were reviewed, but no live account-data provider was
approved or activated. The [company discovery provider evaluation](company-discovery-provider-evaluation.md)
records the decision. The shipped adapter returns deterministic synthetic fixtures,
makes no network request and fails closed in production.

WO-029 reuses the user-bound Mock Email simulation for reviewed one-to-one Engage
outreach. [Gmail and Microsoft Graph were evaluated](mailbox-provider-evaluation.md),
but customer ecosystem, OAuth, sender identity, reconciliation and compliance-event
readiness did not support a production choice. No mailbox OAuth or paid email service
was activated. Production email fails closed; Mock Email remains visibly simulation-
only outside production.

WO-030 re-evaluates that decision for bounded Campaigns and reaches the same
fail-closed result. Campaign orchestration uses the existing user-bound Mock Email
simulation, exact execution preview, idempotent receipt and reconciliation contract;
it does not introduce generic SMTP, shared senders or a live mailbox connector.
Automatic reply detection is also deferred because it would require a separately
approved inbound-mail privacy and scope expansion. Sellers may report a reply,
meeting or not-interested outcome, clearly labelled seller-reported. See the
[reply-detection decision](reply-detection-decision.md).
