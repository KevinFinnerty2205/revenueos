# Oryntela simplicity principles

- **Status:** Approved product-design constraint for future work
- **Last reviewed:** 4 September 2026
- **Applies to:** seller, manager and administrator experiences

## Decision

Oryntela must make the next useful sales action easier to see and complete. Product breadth is not permission to expose every capability at once. Every future work order must demonstrate that it preserves or improves this simplicity before implementation is authorised.

This document governs future design. It does not authorise a navigation rewrite or any production change.

## The simplicity test

A seller should be able to answer these questions without interpreting an internal module model:

1. What matters now?
2. Why does it matter?
3. What should I do next?
4. What evidence supports that recommendation?
5. What changed after I acted?

A manager should additionally be able to see where attention is needed, what evidence supports the forecast and whether coaching changed behaviour. An administrator should be able to configure trusted foundations without turning ordinary seller work into system administration.

## Information hierarchy

Use the sequence **what matters → why → supporting detail**.

- Put one primary recommendation or decision at the top of a view.
- Reveal evidence, history and alternatives progressively.
- Keep creation close to the object or outcome it affects.
- Use human sales language in navigation; keep internal module and plan names out of the primary task flow.
- Prefer a small number of stable destinations over a growing list of feature links.
- Preserve context when moving between an interaction, an action and a deal.

## Role mental models

| Role          | Primary mental model                                             | What should stay secondary                            |
| ------------- | ---------------------------------------------------------------- | ----------------------------------------------------- |
| Seller        | today, relationship, next action, deal progress                  | configuration, reporting taxonomy, provider mechanics |
| Manager       | attention, evidence, coaching, target and forecast confidence    | low-level record administration                       |
| Administrator | identity, organisation, policy, access and trusted configuration | seller execution workflow                             |

Role-aware emphasis must not produce three unrelated products. The underlying account, contact, interaction, action, opportunity and evidence model remains shared.

## Mandatory gate for every future work order

Before a work order is approved, its specification must answer:

- Who has the problem, and what observable job are they trying to complete?
- What existing destination or object owns the capability?
- What is removed, combined or kept out of the primary path?
- What is the single primary action?
- What evidence and confidence state are visible?
- What are the loading, empty, error, partial and unavailable states?
- What does the keyboard and screen-reader path look like?
- What is deliberately unavailable on mobile?
- Which existing term does this introduce, replace or retire?
- Can a design partner complete the task without training or module knowledge?

A proposal that only adds another page, card, tab or navigation item has not passed the gate.

## Anti-patterns

- A dashboard wall in which every metric competes for attention.
- Product-plan names such as Core or Complete used as navigation.
- Separate feature islands that duplicate accounts, people or interactions.
- AI output presented without evidence, uncertainty or an editable human checkpoint.
- Configuration required before a user can understand the value.
- Empty destinations added in anticipation of a future integration.
- Mobile parity treated as a goal independent of the mobile job.
- Provider failures exposed as unexplained internal terminology.

## Three current simplicity risks

### 1. Breadth and navigation

The repository now contains a wide platform surface. The current grouped navigation is coherent, but adding each future capability as a peer destination would make the product harder to scan. New capability should normally deepen an existing account, interaction, action or opportunity workflow.

### 2. Company context and onboarding

Research, ideal-customer context, methodology and messaging can become a long setup process. The proposed Company Selling Profile must begin as a concise, editable brief and prove that it improves outputs before gaining more configuration.

### 3. Provider and partial-state complexity

Mailbox, calendar, SMS, research and AI providers create disconnected, delayed or partially available states. Oryntela should use provider-neutral user language, clearly label availability and fail safely without blocking unrelated core work.

## Mobile principle

Mobile is for focused, time-sensitive work: reviewing the next action, preparing for or capturing an interaction, updating progress and seeing essential context. Desktop remains appropriate for configuration, dense reporting and complex creation. Native recording is a separate future decision with explicit safety and consent gates; it is not implied by a mobile-friendly web experience.

## Evidence required before material simplification changes

- Current-state task walkthroughs with the design partner.
- Time-to-understand and time-to-complete observations.
- Mis-clicks, abandoned paths and terms users cannot explain.
- Comparison of the existing grouped navigation with one low-fidelity alternative.
- Accessibility and small-screen checks.

The result may be to keep the current information architecture. Validation is intended to identify the smallest warranted change, not manufacture a redesign.

## Related sources

- [Oryntela master product blueprint](../01-product/oryntela-master-product-blueprint.md)
- [Oryntela Daily future state](oryntela-daily-future-state.md)
- [Oryntela product navigation exploration](oryntela-product-navigation-exploration.md)
- [Current RevenueOS information architecture](revenueos-information-architecture.md)
