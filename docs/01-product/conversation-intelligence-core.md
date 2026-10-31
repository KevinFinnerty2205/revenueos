# Oryntela conversation intelligence core

## Current product direction

Oryntela's primary product is meeting and phone-call intelligence for GTM teams
and startups. The default web journey is:

1. add and approve company knowledge;
2. prepare for an upcoming conversation;
3. use the permissioned conversation workspace;
4. preserve personal notes and review enhanced notes;
5. review evidence-backed framework coverage and a follow-up draft;
6. search relationship history before the next conversation.

The primary navigation is Home, Conversations, Knowledge and Frameworks.
Search / Ask Oryntela is a secondary workspace destination that remains easy to
reach.

## Working local behaviour

- Conversations persist through the tenant-isolated Interaction and Meeting
  domains. Meetings, phone calls, general conversations and event/in-person
  notes do not require an Opportunity.
- Preparation reuses deterministic, source-aware pre-interaction briefs.
- Personal debrief answers are stored independently of enhanced intelligence
  and the latest user-owned debrief is recoverable after reload. A processing
  failure cannot erase the original answers.
- Completed meetings and phone calls expose personal notes, editable local
  enhanced notes, decisions, objections, action items, open questions,
  conversation-level framework coverage and a review-only follow-up draft.
  Browser-local edits never overwrite the accepted evidence record.
- Company knowledge sources persist with an explicit processing state. A saved
  website address is `saved_unprocessed`; the product does not claim the site
  was fetched. Bounded manually supplied text and `.txt` content is
  `ready_for_review` and remains administrator-only input to the versioned
  company profile. Administrators can inspect and delete source content before
  correcting and approving the separate profile.
- Framework definitions include BANT, SPICED, MEDDIC, MEDDICC and MEDDPICC,
  plus organisation-defined frameworks and notes-only operation.
- Existing deterministic calendar, research, brief, debrief, transcription,
  source evidence and intelligence adapters remain the local demonstration
  path. No live provider is activated by this refocus.
- Settings includes browser-local morning-digest and pre-meeting preferences
  plus a deterministic email preview/test transport. It reads current meeting
  state, emits tenant-scoped conversation links and demonstrates a stable
  duplicate-prevention key without scheduling or sending anything.
- Conversation search matches titles, linked company/person names, current
  transcript text and accepted reported evidence within the active tenant.

## Trust boundaries

- The browser never claims universal call detection or cross-application audio
  access. Browser microphone capture requires an explicit user action and
  permission; transcript import and typed notes remain alternatives.
- Website content is not fetched in this implementation. Future fetching must
  use a bounded, tenant-aware adapter with SSRF protection, content limits and
  untrusted-content handling.
- Framework coverage describes supported, missing, stale or conflicting
  evidence. `Not discussed` is unknown, not a negative buyer answer, and
  coverage is not a win probability.
- Follow-up output remains a draft until the user takes a separate action. This
  change adds no outbound automation. Meeting drafts can be edited, saved in
  the current browser, marked reviewed, copied or exported; regeneration does
  not replace a saved local edit.
- Personal debrief sessions remain readable only by the member who created
  them. Organisation-level reviewed intelligence continues to use its existing
  evidence and authority controls.

## Legacy disposition

The previous CRM, prospecting, campaigns, pipeline, targets, forecasting,
analytics, presentation creation, business cases, Deal Rooms and Handover
surfaces are no longer in the default navigation or onboarding. Their routes,
tables, records, audit history and tenant controls are preserved for
compatibility and possible supporting use. No legacy table or customer record
is dropped by this change, and the modules are not collected into a large
replacement menu.

Billing and Credits remain disabled. The refocus changes neither pricing nor
trial terms.

## Explicitly deferred

- live website ingestion and external research;
- live AI, transcription, email and connector execution;
- server-persisted digest/pre-meeting preferences, scheduled delivery and real
  email transport (the local preview/test transport is implemented);
- cumulative framework projections for conversations that are not explicitly
  linked to an Opportunity; these are deliberately not merged by company name;
- server persistence for user-edited enhanced notes and follow-up drafts (the
  accepted evidence and original personal notes are server-persisted; first-pass
  edits are explicitly browser-local);
- native macOS and Windows capture, call detection, overlays and installers.

Native clients should reuse the current conversation, capture and intelligence
service boundaries when separately authorised.
