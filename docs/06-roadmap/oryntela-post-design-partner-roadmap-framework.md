# Oryntela post-design-partner roadmap framework

- **Status:** Decision framework; no dates or implementation authority
- **Last reviewed:** 4 September 2026

## Decision

Sequence future work by evidence and dependency, not by the length of the idea list. The immediate product objective remains a safe, core-first design-partner experience. Post-partner work should strengthen the end-to-end operating loop before expanding channels or building provider-dependent breadth.

## Horizons

| Horizon                        | Purpose                                                      | Candidate work                                                                                                                                      | Entry evidence                                                     |
| ------------------------------ | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| A — Built baseline             | Preserve the coherent repository foundation                  | CRM, meetings, deliberate transcripts, actions, methodology, pipeline, targets, forecast, manager insights, Create, Value Models and labelled mocks | Existing tests and documentation                                   |
| B — Before partner             | Prove the approved target environment and close launch gates | Deploy, auth/tenant proof, RLS, migrations, safe errors, observability, rollback and owner approvals defined by the launch gate                     | All applicable evidence rows PASS; owner GO                        |
| C — Partner validation         | Learn from supervised core use                               | Daily hierarchy, methodology fit, action follow-through, target/forecast comprehension, manager attention, Create and Value Models                  | Observed tasks, interviews and issue log                           |
| D — High-value post-partner    | Deepen the operating loop                                    | Company Selling Profile, What Changed, customer commitments, meeting-to-progression and calls-to-meetings semantics                                 | Repeated need, clear owner object and measurable benefit           |
| E — Provider-backed candidates | Add bounded external capability                              | Focused HubSpot proof, one mailbox provider, approved research source, supervised personalised outreach                                             | Partner need, provider review, variable-cost gate and target proof |
| F — Later options              | Explore only with exceptional evidence                       | SMS, general file attachments, AI voice and native recording                                                                                        | Full security, privacy, legal, cost and operational gates          |
| G — Do not build               | Protect the product thesis                                   | Generic autonomous SDR, full CRM parity, general file repository, copied navigation, speculative provider matrix                                    | New owner decision and evidence would be required to reconsider    |

Horizons are dependency order, not calendar commitments.

## Product dependency map

```text
Trusted identity and organisation
  -> Accounts, People and Opportunities
  -> Interactions and deliberate meeting Evidence
  -> Sales Brain and Methodology interpretation
  -> Editable Actions and customer commitments
  -> Pipeline movement and transparent Forecast
  -> Daily priorities and manager attention

Accounts + validated Company Selling Profile
  -> better Sales Brain, Prospect, Engage and Create context
  -> reviewed Actions

Approved provider + variable-cost gate
  -> provider-backed Prospect or Engage capability

Identity + core records + deliberate Evidence + target-environment proof
  -> safe design-partner use
```

The diagram shows why more channels are not the first dependency. Identity, tenant isolation, core records, deliberate evidence and safe target proof precede partner use. Company context may later improve multiple workflows, but only after validation.

## WO-040 and later disposition

The existing beta roadmap identifiers remain historical planning references, not automatic authorisation:

- **WO-040:** defer or reorder until target-environment launch evidence and partner learning identify the next material gap.
- **WO-041:** if mailbox evidence warrants it, evaluate a narrow Gmail path before broad provider parity; Microsoft is not assumed.
- **WO-042:** defer a broad connector programme. Complete the already-defined focused HubSpot proof first if the partner actually needs it.
- **WO-043:** defer Deal Rooms until a customer collaboration job is observed.
- **WO-044:** defer broad handover until a real sales-to-customer-success transition is in scope.
- **WO-045:** treat release readiness as a gate across approved work, not a feature sprint that can compensate for missing evidence.

## Scoring future proposals

Score each proposal from 0–3 on:

- frequency and severity of observed customer need;
- contribution to the operating loop;
- reuse of trusted existing foundations;
- simplicity and learnability;
- evidence quality and measurability;
- safety, privacy and legal readiness;
- unit-economics confidence;
- operational supportability.

Any zero in safety, privacy, legal or tenant isolation blocks approval regardless of total score. Provider selection follows product evidence; it does not create it.

## Explicit non-decisions

This framework does not approve a technical rebrand, public launch, price, trial, Credits system, provider, integration, native app, recording capability or new work order. It also does not replace the current first-design-partner launch gate.

## Related sources

- [Product roadmap to beta](product-roadmap-to-beta.md)
- [First design-partner launch gate](first-design-partner/first-design-partner-launch-gate.md)
- [Oryntela owner-notes reconciliation](oryntela-owner-notes-reconciliation.md)
- [Oryntela variable-cost safety gate](../03-engineering/oryntela-variable-cost-safety-gate.md)
