# End-to-end Sales Platform security and privacy

- **Status:** WO-023 threat and control direction; future capabilities are not implemented
- **Authority:** Extends the canonical security, privacy and trust requirements; it
  does not weaken current fail-closed controls

This document is product/engineering guidance, not legal advice. Every provider,
source, jurisdiction, outreach purpose and commercial launch requires qualified legal
and security review.

## Non-negotiable controls

1. Verified authentication and membership derive the active organisation; client
   organisation IDs are never trusted.
2. Every tenant-owned row, key, query, cache key and object path is organisation-scoped;
   PostgreSQL RLS remains defence in depth and the runtime role cannot bypass it.
3. Least privilege applies to personal, manager, admin, integration and support scope.
4. Evidence provenance, human review and reversibility govern AI-supported changes.
5. Credentials, customer content, prompts, research, contact details, documents,
   transcripts and provider payloads never enter logs or metadata-only audits.
6. Retention, export, correction, suppression and erasure include derived artefacts,
   indexes, files, provider state and backups through explicit policy.
7. External effects use review, exact approval, idempotency, stop/revoke where
   possible, reconciliation and safe receipts.

## Capability risk and required gate

| Area                      | Primary risks                                                        | Required controls before implementation/release                                                                               |
| ------------------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Prospect/person research  | Unlawful collection, sensitive inference, stale or fabricated claims | Approved sources/contracts, purpose limitation, provenance/trust state, prohibited-attribute filter, retention and correction |
| Business contacts         | Guessed address treated as fact or permission                        | Verification state/method/expiry; suppression overrides; permission assessed separately                                       |
| ICP/territory             | Discriminatory proxy criteria or unauthorised visibility             | Typed business criteria, sensitive/proxy review, territory access and explainable inclusion                                   |
| Outreach/campaigns        | Spam, deceptive personalisation, reputation harm                     | Lawful-basis/jurisdiction review, exact approval, opt-out, suppression, frequency/quiet-hour and sender controls              |
| Events                    | Attendee list used beyond authority                                  | Authority record, purpose/retention limits, explicit save/enrolment, no blanket-consent assumption                            |
| Interaction capture       | Covert recording or invalid consent                                  | Deliberately armed capture, persistent visible state, participant/authority evidence, pause/stop and jurisdiction policy      |
| Files/templates/Create    | Malware, active content, cross-tenant object leak, invented claims   | Signature/size scanning, isolated bounded parsing, private storage, citation manifest, render review and short-lived access   |
| Pricing/ROI/proposals     | False numbers or unauthorised commitments                            | Authorised sources, deterministic formula/version, labelled assumptions, commercial/legal approval                            |
| Native CRM/import/sync    | Bulk leak, duplicate/corrupt records, wrong source authority         | Dry run, field mapping, tenant-safe dedupe, typed authority/conflict policy, idempotency and reconciliation                   |
| Pipeline/targets          | Excess access, wrong aggregation or currency/time                    | Team permission, reproducible definition, timezone/currency policy and history                                                |
| Forecasting               | False certainty, bias, override concealment                          | Range, assumptions, version/calibration, sample sufficiency, human override history and unavailable state                     |
| Manager/coaching          | Employee surveillance or unfair evaluation                           | Revenue-execution inputs only, no keystrokes/presence/rep score, access policy and explainable association                    |
| Custom methodology/fields | Code injection, covert sensitive data or domain corruption           | Typed bounded definitions, no code/formulas, sensitivity and lifecycle limits                                                 |
| Entitlements              | Client bypass or cross-org cache leak                                | Server enforcement, scoped cache, version invalidation and auditable manual grants                                            |
| Integrations/execution    | Credential theft, duplicate/wrong-account action                     | Secret manager, verified OAuth state/scopes, exact preview, idempotency, receipts, revoke/reconcile                           |
| Handover                  | Excess customer data shared with CS                                  | Purpose-bound package, recipient access, minimisation, approval and retained provenance                                       |

## Responsible research

Research is limited to relevant public or contractually licensed professional/business
information. RevenueOS must not scrape prohibited sources, infer protected/sensitive
traits, reveal private-life knowledge, profile vulnerability, generate deceptive
rapport or label guessed contact points as verified. Findings are atomic, sourced,
dated and assigned `verified`, `provider_supplied`, `inferred` or `unknown` state.

People can be corrected, suppressed or erased under applicable policy. Bulk export,
provider caching and search access are separately controlled. Provider terms and data
residency must be known before enablement.

## Responsible outreach

A data source or verified contact point does not itself establish permission. Before
sending, evaluate purpose, relationship/consent or other lawful basis, jurisdiction,
sender identity, suppression, unsubscribe, frequency, quiet hours, complaint/bounce
history and provider policy. A recipient/content change invalidates approval.

No unbounded autonomous sending, purchased-list blasting, opt-out evasion or
autonomous cold calling. Emergency pause/stop and organisation-wide suppression must
be reliable under concurrency and queued-work races.

## AI trust and prompt/data boundaries

AI consumes the minimum authorised context through an explicit provider adapter.
Customer data is not used for provider training unless an approved contract and
clear customer choice permit it. Prompt/model/policy versions and Evidence references
support reproducibility; prompt text and customer content stay out of logs.

Model output is untrusted structured input: validate schema, tenant/entity references,
citations, claims and limits. It cannot grant access, approve its own action, create
source Evidence, override suppression or invent commercial facts. Users can inspect,
correct, reject and undo where the underlying external action is reversible.

## Files and storage

Use private organisation-scoped object paths, server-authorised access and short-lived
signed URLs. Verify file signature/size, scan before parse, bound CPU/memory/archive
expansion, reject active content and isolate transformations. Derived previews,
embeddings, extracted text and generated assets inherit source classification,
retention and erasure requirements. Do not send customer files to a provider without
an approved data-flow record.

## Residency, retention, export and erasure

Future enterprise residency is a deployment/data-placement policy, not a label. A
data inventory must map primary data, object storage, indexes, telemetry, subprocessors,
support access, backups and disaster recovery. Retention is category- and purpose-
specific. Legal holds are explicit and access-controlled.

Exports are authorised, rate-limited, auditable and complete enough to be meaningful
without exposing other tenants or secrets. Erasure follows dependency-aware jobs,
uses tombstones only where necessary, propagates to derived outputs/providers and
reports exceptions rather than claiming instant deletion.

## Closed-Won handover

The handover package may include objectives, success criteria, stakeholders,
executive sponsor, implementation needs, risks, promises, commercial commitments,
expected outcomes and open actions. A human reviews recipients and contents. The
package cites authorised Evidence, excludes irrelevant raw transcripts/research and
records who shared which version for which purpose.

```mermaid
flowchart LR
    B["Sales Brain"] --> P["Purpose-limited handover proposal"]
    P --> R["Seller review and redaction"]
    R --> A["Authorised recipient and exact approval"]
    A --> H["Customer Success handover package"]
    H --> C["Customer Brain in a future product"]
```

Customer Success Brain remains a separate future product; WO-023 does not implement
it or broaden Sales users' access.

## Assurance and incident readiness

Threat modelling, privacy impact assessment, provider review, abuse-case tests and
cross-tenant/RLS tests are release gates for affected work orders. Test deletion,
export, suppression, stop races, uncertain provider outcomes and support access.
Operational readiness requires safe auditability, alert ownership, kill switches,
runbooks, recovery objectives and customer communication paths.

## Explicit prohibitions

No employee surveillance, covert recording, sensitive-trait profiling, generic data
broker, uncontrolled outreach, hidden autonomous execution, credential logging,
production customer-data testing, security theatre or claims that mocks/stubs are
working integrations.
