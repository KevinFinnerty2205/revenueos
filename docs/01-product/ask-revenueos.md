# Ask RevenueOS

**Status:** current WO-025B Core capability

Ask RevenueOS is an evidence-backed question-and-answer surface for the sales work a
signed-in user is already authorised to see. It makes Methodology, Revenue Brain,
accepted Evidence, current Actions, Next Best Action and RevenueOS Daily easier to
use; it is not a generic chatbot, a research agent or a database query tool.

## User promise

A seller can ask about one Opportunity, one Account, or a bounded set of their own
open Opportunities. RevenueOS returns one of four explicit states:

- `supported` — current retrieved sources support the answer;
- `partially_supported` — some relevant evidence exists, but a material gap remains;
- `conflicting` — current authorised sources disagree and both sides remain visible;
- `unknown` — RevenueOS lacks reliable evidence and does not guess.

Every substantive answer contains concise cited points. Source cards expose the
source label, provenance class, a short excerpt and a link back to the underlying
RevenueOS work. Customer-direct, seller-reported, seller-prepared and imported
evidence remain distinct.

## Entry points

- **Search → Ask RevenueOS** is the global/workspace entry. Normal Search remains the
  default deterministic record finder.
- **Ask about this deal** opens Opportunity scope.
- **Ask about this account** opens Account scope.

There is no additional top-level navigation destination. Scope is visible before and
after answering. Follow-ups are independent questions in the same explicit scope;
WO-025B does not retain conversation history.

## Supported question taxonomy

The deterministic classifier recognises deal summary, blockers/risks, stakeholders,
Methodology, timeline, commitments, next action, buying signals, objections,
competitors, decisions, customer requests, security/legal, procurement,
pricing/commercial, recent change, evidence lookup, bounded Opportunity filters and
Daily focus. Ambiguous general sales coaching and public-web questions return
`unknown` rather than silently widening retrieval.

Representative questions include:

- “What is holding this deal back?”
- “Who is the economic buyer?”
- “What changed recently?”
- “What should I do next?”
- “What opportunities are active?”
- “Which of my deals don’t have an economic buyer?”
- “What do I need to do today?”

## Current implementation

WO-025B uses a deterministic classifier, bounded structured retrieval and a
deterministic composer. It makes no external AI-provider call. Structured current
records and accepted/validated intelligence are preferred to text-like evidence.
The server—not the browser—resolves scope, applies tenant and membership predicates,
validates citations, enforces source/context/result bounds, reserves quota and emits
metadata-only audit/telemetry events.

Feature flag: `FEATURE_ASK_REVENUEOS_ENABLED`. Private-beta limits default to 75
answers per user/day and 500 per organisation/day, with at most 12 retrieved sources,
16,000 context characters and 10 workspace results.

## Known limitations

Ask only answers from authorised RevenueOS data. There is no public-web or Prospect
research, generic internet search, arbitrary SQL/text-to-SQL, vector database,
predictive forecast, autonomous Action, CRM mutation, email sending, calendar action,
biometric inference or sensitive-trait inference. Answers depend on available
evidence; unknown and conflicting outcomes are normal private-beta behaviour.

See the [retrieval architecture](../03-engineering/ask-retrieval-architecture.md),
[source/citation model](../03-engineering/ask-source-citation-model.md),
[scope/permissions guide](../03-engineering/ask-scope-permissions.md) and
[simplicity review](../02-design/ask-revenueos-simplicity-review.md).
