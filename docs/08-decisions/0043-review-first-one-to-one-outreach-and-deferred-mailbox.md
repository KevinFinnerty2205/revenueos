# ADR 0043: Review-first one-to-one outreach with deferred production mailbox

## Context

Engage needs to convert bounded Prospect research into a legitimate conversation
without creating a campaign/spam system or bypassing the existing Action/Execution
safety boundary. The recipient must be canonical, personalisation explainable,
suppression durable and exact content reviewable. Gmail and Microsoft Graph are both
viable future mailbox paths, but current design-partner/provider, OAuth, compliance
event and operational evidence does not justify choosing one.

## Decision

Implement Engage as a separately entitled one-to-one Contact workflow. Resolve the
recipient and sender server-side. Persist an outreach aggregate with immutable exact
versions and source references; every edit invalidates approval. Treat address trust
and permission as separate concepts. Use an organisation-scoped HMAC suppression
identity so opt-out state can survive Contact deletion/re-discovery.

Reuse the Action Layer for reviewed intent and the Execution Foundation for exact
preview, explicit confirmation, idempotency and worker revalidation. Permit only the
clearly labelled deterministic Mock Email adapter outside production. Defer Gmail and
Microsoft production adapters and fail closed in production.

## Alternatives

- **Select Gmail now:** rejected until customer ecosystem, OAuth verification,
  alias/reconciliation and event-operating requirements are approved.
- **Select Microsoft Graph now:** rejected until tenant consent, `202` reconciliation,
  alias/shared-mailbox and event-operating requirements are approved.
- **Use transactional email/SMTP:** rejected because it does not prove the user's
  authorised salesperson mailbox and expands spoofing/credential risk.
- **Store suppression only on Contact:** rejected because deletion/reimport could
  erase a recipient's do-not-contact decision.
- **Send directly after approval:** rejected because approval is not exact external
  confirmation and conditions may change.
- **Add campaigns/sequences now:** rejected as outside the smallest trustworthy
  one-to-one boundary.

## Consequences

Private beta can validate workflow, copy quality, provenance, policy and anti-abuse
without sending real email or activating a paid service. Production sending remains
unavailable and no delivery/bounce/reply claims are made. Schema/export/retention are
larger and suppression key rotation needs an explicit future migration strategy.

A future provider work order must choose one ecosystem, implement least-privilege
OAuth and encrypted tokens, verify sender/send-as identity, define provider receipt
and unknown-outcome reconciliation, add opt-out/bounce/complaint handling where
required and preserve the same exact-version/idempotency boundary.
