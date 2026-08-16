# Simplicity and discoverability principles

- **Status:** Mandatory design gate for future work orders
- **Goal:** RevenueOS absorbs complexity so the salesperson does not have to

## Product rules

- One page primarily answers one user question.
- One primary action is visually and semantically obvious.
- Put detail behind **Why?**, **View gaps** or section drill-down.
- Reuse Home, Find, Sell, Pipeline, Create and Insights before proposing navigation.
- Use salesperson language: **Analyse meeting**, **Prepare for call**, **Add customer
  information**, **Create next actions**, **Send email**, **Update opportunity** and
  **Find prospects**.
- Never expose job/provider/connector/internal-aggregate terminology as the primary
  label.
- An empty state teaches the first useful action.
- An error says what failed, what remains safe and what to do next.
- AI is explainable on demand and correctable where appropriate.

## Three disclosure levels

1. **Tell me what matters.** One headline, state or recommendation.
2. **Show me why.** Evidence classes, important inputs, freshness and conflict.
3. **Show me everything.** Source fragments, versions, detailed tables and audit,
   subject to permission.

Example methodology: `5 confirmed · 2 partial · 1 unknown` → **View gaps** → field
explanation → exact evidence.

## Consistent system patterns

- **Hierarchy:** page title, short context, primary action, exceptions, then detail.
- **Cards:** use only for separable actions/status; avoid nesting every paragraph.
- **Colour:** restrained and semantic; state always has text/icon.
- **Loading:** stable section skeletons; independent sections do not block the page.
- **Empty:** state why empty and one next action; never fabricate sample customer data.
- **Error:** preserve valid content and inputs; retry only the failed boundary.
- **Confirmation:** identify action, target, content/version and consequence.
- **Destructive:** explicit language, impact preview and safe recovery where possible.
- **AI review:** source, uncertainty, edit/reject and downstream effect are consistent.
- **Terminology:** one controlled glossary across pages and API-facing copy.

## Mandatory gate for every future engineering work order

The work order and acceptance criteria must answer:

1. Can a first-time user understand this page without documentation?
2. Is one primary action obvious?
3. Are advanced controls hidden until needed?
4. Are labels written in salesperson language?
5. Does the page say what to do next?
6. Can the workflow be completed without understanding RevenueOS architecture?
7. Does the feature really need a navigation item?
8. Can it live within an existing page?
9. Is mobile simpler than desktop?
10. Are empty states instructional?
11. Are errors actionable?
12. Are destructive actions obvious?
13. Is AI explainable on demand?
14. Can the user correct or undo AI where appropriate?
15. Does the design preserve one question per page?

The work order must also state where the capability lives, first action, first-time
state, power-user controls, mobile behaviour, unavailable-entitlement behaviour and
AI verification/correction path. A design that cannot answer these is not ready for
implementation.

## Review method

Run a 30-second comprehension test with a first-time seller, keyboard/screen-reader
review, narrow-screen review and empty/error/unavailable walkthrough. Measure task
discovery and completion, not preference alone. Any exception to this gate needs an
explicit product-design decision and user evidence.
