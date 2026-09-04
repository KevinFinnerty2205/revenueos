# Oryntela product navigation exploration

- **Status:** Exploration only; current navigation remains the approved implementation
- **Last reviewed:** 4 September 2026

## Decision

Retain the current grouped, goal-based navigation until partner evidence supports a smaller change. Do not reorganise the application into a product-to-feature tree merely because Oryntela has Prospect, Engage, Create, CRM and intelligence concepts.

## Current model

The implemented desktop navigation groups destinations around work:

- Home
- Prospect and Find when the mock prospect capability is enabled
- Sell: Accounts, People, Interactions, Campaigns and Events
- Pipeline and Insights
- Create and Studio
- Search and Settings

The mobile navigation emphasises Today, Interactions, Actions and Search, with other destinations available through More. This already follows several simplicity principles: human task language, stable objects and role-relevant emphasis.

## Alternative worth testing

A future prototype may explore a small number of outcome groups:

| Outcome group | Possible contents                                      | Risk to test                                     |
| ------------- | ------------------------------------------------------ | ------------------------------------------------ |
| Today         | priorities, interactions, commitments, recommendations | becoming a dashboard wall                        |
| Relationships | accounts, people, history and company context          | hiding pipeline work inside records              |
| Pipeline      | opportunities, methodology, forecast and targets       | overloading sellers with manager reporting       |
| Outreach      | prospect discovery, campaigns and approved messages    | implying live providers where only mocks exist   |
| Create        | presentations, business cases and reusable assets      | splitting creation from the relationship context |
| Insights      | manager attention, activity, funnel and outcomes       | duplicating Home and Pipeline                    |

This is a research artefact, not an implementation recommendation. “Core”, “Growth” and “Complete” are packaging language and must not become primary navigation.

## Product-to-feature inspiration boundary

Reference products may demonstrate useful ideas such as grouping, progressive disclosure or role-based navigation. Oryntela should not copy another product's labels, visual hierarchy or category structure without task evidence. The owner note referring to a CreditorWatch-style product hierarchy is therefore treated as a prompt to test comprehension, not as a design instruction.

## Prototype method

1. Record five representative tasks in the current navigation.
2. Create one low-fidelity alternative without changing production code.
3. Ask sellers and managers to locate the next step without coaching.
4. Compare success, time, backtracking and terminology confusion.
5. Keep the current model unless the alternative materially improves the important tasks.

## Guardrails

- Add capability contextually before adding a destination.
- Keep accounts, contacts, interactions, actions and opportunities as stable anchors.
- Do not expose mock or unavailable providers as normal product destinations.
- Preserve keyboard navigation, visible focus and semantic landmarks.
- Do not make mobile a smaller desktop menu.
- Any approved change needs a migration of terminology, routes, tests and documentation in the same work order.

## Related sources

- [Current RevenueOS information architecture](revenueos-information-architecture.md)
- [Oryntela simplicity principles](oryntela-simplicity-principles.md)
- [Oryntela Daily future state](oryntela-daily-future-state.md)
