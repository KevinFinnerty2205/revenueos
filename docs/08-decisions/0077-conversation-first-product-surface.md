# 0077: Conversation-first product surface

- Status: Accepted
- Date: 2026-10-31

## Context

The repository contains a broad relationship-revenue platform with substantial
conversation, evidence, knowledge and framework foundations. The owner changed
the commercial focus to conversation intelligence. Leaving every broad module
in the default navigation would make the product's core job unclear, while
deleting those modules would destroy records and proven security work.

## Decision

The protected web shell presents four primary destinations: Home,
Conversations, Knowledge and Frameworks. Search / Ask Oryntela and Settings are
secondary. Conversation routes become the canonical links emitted by the daily
service, while legacy Interaction routes remain compatible.

The existing modular-monolith domains remain in place. Company knowledge adds a
small tenant-owned source table with explicit honest states. A website address
is stored without being fetched; manually supplied bounded text is ready for
administrator review and can be inspected or removed. The versioned Company &
Selling Profile remains the only approved organisation context.

Completed user-owned debriefs are recoverable in the conversation page so
phone calls receive the same visible review journey as meetings. Conversation
coverage is evaluated against the selected framework without being presented
as win probability. Cumulative qualification remains attached only to an
explicitly linked Opportunity so unrelated initiatives are not merged.

Digest and pre-meeting preferences use a deterministic browser-local preview
in this pass. It demonstrates current-state content, tenant-scoped links and a
stable duplicate key but intentionally does not activate a scheduler or email
transport.

Legacy CRM, prospecting, revenue, campaign and content-creation routes and
tables remain intact but are absent from default navigation and onboarding.

## Alternatives considered

- Deleting legacy modules was rejected because it would be destructive and
  discard tenant, authority and audit work.
- Moving every old module under a large “More” menu was rejected because it
  would preserve the same unfocused product surface.
- Building a separate conversation service was rejected because the existing
  Interaction and Meeting domains already provide the correct modular-monolith
  foundation.

## Consequences

- New owner reviews enter through a coherent conversation journey.
- Existing deep links and records continue to work.
- Some legacy pages remain reachable by direct links from supporting records;
  they are compatibility surfaces, not the product's primary experience.
- Native capture and live external providers remain separate future work.
