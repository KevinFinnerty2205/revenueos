# Oryntela future SMS boundary

- **Status:** Future candidate; validate first; not built or authorised
- **Last reviewed:** 4 September 2026

## Decision

SMS may become a useful, supervised contact action, but it is not an approved dependency or current capability. If validated, it must extend the existing contact, interaction and action model through a provider-neutral adapter. Oryntela must not become a bulk-texting or consent-circumvention product.

## Candidate customer flow

1. A user opens a contact with an intentionally supplied business phone number.
2. Oryntela shows the source, contactability status and relevant suppression state.
3. The user drafts a message or requests a clearly labelled AI-assisted draft.
4. The user edits and reviews the exact recipient, content, identity, timing and estimated Credits use.
5. The user explicitly sends or schedules within approved policy.
6. Delivery, failure, reply and STOP or equivalent suppression events are attached to the contact timeline.
7. Follow-through can become an action or opportunity update with visible provenance.

## Required boundaries

- No silent, ambient or inferred consent.
- No sends to a number without source and contactability evidence.
- No bypass of STOP, suppression, quiet-hours or frequency controls.
- No automatic bulk generation and send in one unreviewed step.
- No purchased-list blasting, number rotation or deliverability evasion.
- No provider-specific fields in the core domain model.
- No message body, credentials or full provider payloads in application or audit logs.
- Every organisation-owned row, usage record and provider reference remains tenant scoped.
- AI assistance remains editable and distinguishable from a sent human-approved message.

## Australian review gate

Before any partner use, obtain qualified Australian legal review of applicable Spam Act, consent, identification, unsubscribe, record-keeping, privacy and telecommunications obligations. This document is a product boundary, not legal advice, and does not conclude that any proposed message is lawful.

## Commercial and operational gate

SMS pricing, included allowances and Credits conversion remain unknown. Provider pricing, segments, international routing, carrier fees, failed-message charging, reply costs and retry behaviour must pass the [variable-cost safety gate](oryntela-variable-cost-safety-gate.md). A Credits balance does not authorise contact or override safety controls.

## Entry criteria for a build work order

- Repeated partner evidence that SMS is important to a specific workflow.
- Approved contactability and suppression policy.
- Provider evaluation without committing the core model to one vendor.
- Unit economics and exposure controls approved.
- Exact user review, preview and failure-state designs.
- Security, privacy, legal and subprocessor reviews complete.
- Tenant-isolation, idempotency, opt-out and safe-retry test plan.

Until those criteria are satisfied, store deliberate business-phone data only through the existing contact boundary and do not imply that Oryntela can send SMS.
