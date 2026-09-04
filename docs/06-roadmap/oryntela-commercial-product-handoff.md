# Oryntela commercial-product handoff

- **Status:** Owner decision brief
- **Prepared:** 4 September 2026
- **Scope:** Documentation consolidation; no launch or implementation authority

This consolidation incurred **AUD $0 new spend**, used only repository material,
public official competitor sources and synthetic evidence, and did not use customer
data, contact customers, change domains/email, activate providers or file a trade
mark. The separately recorded historical brand setup spend remains AUD $108.30.

## Executive decision

Use **Oryntela** as the selected public product brand and describe the product as **“The AI operating system for sales.”** Keep RevenueOS in technical repository identifiers until a separately approved rebrand work order exists.

The product strategy is to make the evidence-to-action loop difficult to live without: deliberate interaction evidence becomes explainable Sales Brain guidance, methodology-aligned action, trustworthy pipeline movement and transparent forecast context. Oryntela complements systems of record; it is not required to replace every CRM.

The single recommended next owner milestone is **professional Oryntela trade-mark clearance and filing advice**. This does not replace the current target-environment launch gate. Safe design-partner discovery may continue in parallel without production data, spend or claims of launch readiness.

## Commercial readiness

| Area          | Current position                                   | What prevents publication or operation                                                 |
| ------------- | -------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Brand         | Oryntela selected; business name and domains held  | Professional trade-mark clearance and approved brand implementation plan               |
| Positioning   | Internal line approved for consolidation           | Evidence-backed customer copy and legal review of material claims                      |
| Plans         | Core, Growth, Complete and Enterprise hypothesis   | Customer validation and entitlement design                                             |
| Price         | AUD 200/350/500 monthly anchors; Enterprise custom | Willingness-to-pay, unit economics, GST, billing-period and owner approval             |
| Trial         | 14 days, no card, broad Complete access hypothesis | Abuse controls, exclusions, data lifecycle, support model and technical implementation |
| Credits       | Prepaid variable-cost control hypothesis           | Provider economics, ledger, reconciliation, refund and exposure controls               |
| Billing       | Not implemented                                    | Approved provider, tax/terms design, tenant-safe implementation and tests              |
| First partner | Free 6–8 weeks, 3–5 users, Native CRM, supervised  | All launch-gate evidence and owner GO                                                  |

Nothing in this table is permission to advertise a price, accept payment, start a public trial or process real customer data.

## Product status

- **Repository baseline:** broad end-to-end foundation across CRM, meetings, actions, methodology, pipeline, targets, forecasts, manager intelligence, Create and Value Models.
- **Mocks and constrained paths:** Prospect is deliberately mock-backed; Engage is simulation-oriented; deterministic AI infrastructure does not equal a production intelligence service.
- **External providers:** focused integration architecture may exist, but no broad connector, live mailbox, SMS, research, voice or recording claim is authorised.
- **Launch:** the documented state is waiting for target-environment proof. WO-040 is not authorised by this consolidation.
- **Brand:** public Oryntela identity is selected; technical RevenueOS names remain intentional until separate approval.

## Decisions made

- Oryntela is the public brand direction; RevenueOS is not yet technically renamed.
- Plans and product modules remain different concepts.
- monday CRM is an overlapping competitor, not a dependency or feature checklist.
- The first design partner remains core-first, free and supervised.
- Every future work order must pass the simplicity gate.
- Variable-cost features require a measured safety and margin gate before implementation.
- SMS, native recording, AI voice, broad Files and generic autonomous SDR are not near-term commitments.

## Decisions still open

- Trade-mark availability, filing strategy and relevant classes.
- Public brand rollout and technical rebrand sequencing.
- Published positioning and proof points.
- Final plans, price, GST presentation, annual terms and discount authority.
- Trial eligibility, exclusions, abuse controls, data lifecycle and conversion path.
- Credits unit, allowance, expiry, refunds and ledger behaviour.
- Which provider-backed capability, if any, partner evidence justifies first.
- Target environment and final design-partner GO.

## monday CRM conclusion

monday CRM competes for overlapping small and mid-market CRM, workflow, automation and AI-assisted sales jobs. Its strengths are a mature configurable platform, broad integrations and a substantial feature surface. Oryntela should not pursue parity. Its defensible direction is a calmer, opinionated Evidence → Sales Brain → Methodology → Action → Pipeline/Forecast loop with visible evidence and less configuration. See the [competitive landscape](../04-commercial/oryntela-competitive-landscape.md) for dated official sources and pricing caveats.

## Simplicity conclusion

The three largest risks are navigation breadth, setup complexity around company context and confusing partial states from providers. Keep the current grouped navigation until testing demonstrates a better alternative. Develop Company Selling Profile first as a concise editable brief, not a parallel data platform. Keep Daily focused on the next useful action rather than adding every metric.

## First design-partner implication

Use the current approved model: 3–5 users, 6–8 weeks, no fee, Native CRM, supervised support and no dependency on an unproven external provider. The partner should validate the core operating loop, Daily comprehension, methodology fit, action follow-through, target/forecast trust, manager attention, Create and Value Models. Real data remains prohibited until every applicable gate is satisfied.

## Validation defect discovered

The documentation-only validation on 4 September 2026 exposed one pre-existing,
calendar-dependent test defect in
`apps/api/tests/test_sales_analytics.py::test_overview_funnel_activity_and_win_loss_reconcile_exactly`.
Its `call-immature` fixture is fixed at 5 August 2026 while production logic evaluates
the 30-day window against the actual current time. On 4 September it becomes mature,
so the expected cohort counts are no longer stable. The isolated rerun reproduced
the failure; 1,058 other API tests passed and four were skipped. No test or product
code was changed because this consolidation is documentation-only. A separately
authorised bug-fix should make the fixture clock explicit before a green full API/CI
gate can be claimed.

## Trade-mark adviser handoff

Facts approved for disclosure to a qualified adviser:

- Proposed mark: **ORYNTELA**.
- Applicant/legal entity: **Management Services Australia Pty. Ltd.**
- ABN: **15 113 119 556**.
- Australian business name ORYNTELA is registered.
- Domains `oryntela.com` and `oryntela.com.au` are held.
- Intended field: software and AI-assisted sales workflow, intelligence and operating-system services.
- No repository review identified a prior similarity concern, but repository review is not clearance.

Questions for professional advice:

- Is ORYNTELA available and sufficiently distinctive in Australia and priority future markets?
- Which goods/services descriptions and classes fit the intended software, SaaS and business services?
- Should word and device marks be sequenced separately?
- What searches, filing order, ownership evidence and watch services are appropriate?
- Does any existing mark create a pronunciation, appearance or conceptual-similarity risk?

Do not state that the name is legally clear, protected or registrable until qualified advice and official processes support that claim.

## Source set

- [Oryntela owner register](../00-company/oryntela-owner-register.md)
- [Oryntela master product blueprint](../01-product/oryntela-master-product-blueprint.md)
- [Oryntela executive product map](../01-product/oryntela-executive-product-map.md)
- [Pricing hypothesis](../04-commercial/oryntela-pricing-hypothesis.md)
- [Free-trial hypothesis](../04-commercial/oryntela-free-trial-hypothesis.md)
- [First design-partner commercial model](../04-commercial/oryntela-first-design-partner-commercial-model.md)
- [Owner-notes reconciliation](oryntela-owner-notes-reconciliation.md)
- [First design-partner launch gate](first-design-partner/first-design-partner-launch-gate.md)
