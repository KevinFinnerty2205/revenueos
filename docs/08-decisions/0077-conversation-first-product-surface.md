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

The existing modular-monolith domains remain in place. Company knowledge uses the
tenant-owned queued ingestion/review lifecycle. Approved bounded website/document
extractions and the versioned Company & Selling Profile are organisation context;
unapproved source content remains unavailable to preparation and guidance.

Completed user-owned debriefs are recoverable in the conversation page so
phone calls receive the same visible review journey as meetings. Conversation
coverage is evaluated against the selected framework without being presented as
win probability. Lightweight conversation threads replace Opportunity as the
mandatory longitudinal grouping key. Company and participant overlap may suggest a
thread, but only an explicit user confirmation creates or corrects the assignment;
there is no company-wide fallback.

Private live/enhanced notes, follow-up drafts and briefing preferences use
authenticated user-and-tenant server persistence with optimistic locking. Digest
and pre-meeting scheduling writes exact deterministic content to a local outbox with
timezone, duplicate, reschedule and cancellation handling; it intentionally does
not activate email delivery.

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
- Explicit supported-browser shared tab/display audio is a web capability under
  [ADR 0081](0081-explicit-conversation-threads-and-browser-shared-audio.md); native
  cross-app capture remains future work.
