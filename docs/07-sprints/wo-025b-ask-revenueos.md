# WO-025B — Ask RevenueOS

- **Status:** implemented; draft-PR validation scope
- **Branch:** `feature/epic-11-wo-025b-ask-revenueos`
- **Migration:** none; `0033_sales_methodology` remains the single head
- **Persistence:** independent ephemeral questions; metadata-only beta events

## Delivered

- Search/Ask modes with deterministic Search unchanged and no new top-level nav.
- Opportunity, Account and user-owned workspace scopes with visible scope labels.
- Fixed question taxonomy, structured bounded retrieval and deterministic composition.
- Strict supported/partial/conflicting/unknown schema and validated clickable sources.
- Provenance separation, explicit uncertainty/conflict and safe unknown/public-web paths.
- Reuse of Methodology, Revenue Brain, accepted Evidence, Daily, Next Best Action and
  current Actions without new intelligence or execution authority.
- Active-membership/tenant checks, daily user/organisation quotas, feature flag and
  metadata-only answer/source/follow-up events.
- Contextual Opportunity and Account entry points, responsive progressive disclosure,
  retry and keyboard-focus behaviour.
- Backend, component and flagship Playwright regression coverage with no external
  provider calls.

## Bounds

Default ceilings are 1,000 question characters, 12 sources, 16,000 retrieved context
characters and 10 cross-Opportunity results. Workspace scope starts with open
Opportunities owned by the active user. Accepted Evidence must remain verified and
available. Provisional live signals, rejected/deleted sources and incomplete/superseded
intelligence are excluded.

## Screenshot evidence

- [Search page with Ask mode](assets/wo-025b-ask-mode-desktop.png)
- [Opportunity Ask desktop](assets/wo-025b-ask-opportunity-desktop.png)
- [Supported Opportunity answer](assets/wo-025b-ask-opportunity-supported-desktop.png)
- [Conflicting answer](assets/wo-025b-ask-conflict-desktop.png)
- [Unknown/public-web boundary](assets/wo-025b-ask-unknown-desktop.png)
- [Account conflict mobile](assets/wo-025b-ask-account-conflict-mobile.png)

The final images were inspected for visible scope, concise answer hierarchy,
uncertainty/conflict language, provenance, progressive source disclosure and mobile
overflow. See the [simplicity review](../02-design/ask-revenueos-simplicity-review.md).

## Scope confirmation and limitations

No Prospect/public-web research, generic internet search, provider call, vector
database, arbitrary SQL/text-to-SQL, autonomous agent, Action execution, CRM mutation,
email/calendar action, forecasting engine, manager analytics, new queue or native app
was introduced. Ask depends on existing authorised RevenueOS evidence and intentionally
returns unknown/conflicting answers. Conversation history is not retained.

See the [product guide](../01-product/ask-revenueos.md), [retrieval architecture](../03-engineering/ask-retrieval-architecture.md),
[citation model](../03-engineering/ask-source-citation-model.md), [permission guide](../03-engineering/ask-scope-permissions.md),
[injection review](../03-engineering/ask-prompt-injection-security.md),
[retention decision](../03-engineering/ask-retention-export-deletion.md) and
[ADR 0036](../08-decisions/0036-ephemeral-deterministic-ask-revenueos.md).
