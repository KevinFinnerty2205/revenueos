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
- Completed meetings and phone calls expose personal notes, editable enhanced
  notes, decisions, objections, action items, open questions,
  conversation-level framework coverage and a review-only follow-up draft.
  Enhanced notes and follow-up drafts persist in an organisation-and-user
  private server workspace with optimistic concurrency. Original notes and
  accepted evidence remain separate. Saving, failure and conflict states are
  visible. Owner-tagged browser drafts require an explicit import; older
  unscoped keys are blocked because authenticated ownership cannot be proved.
- Company knowledge sources use queued, fetching, extracting,
  ready-for-review, approved, stale and failed states. Bounded background jobs
  extract authorised PDF, DOCX, TXT, supporting text and fixture-backed website
  content. Fetching is separated from deterministic synthesis; website requests
  reject private/reserved destinations across redirects and enforce DNS,
  response-size, redirect and text limits. No source is retrieved into
  preparation or debrief context until an administrator approves it.
- Framework definitions include BANT, SPICED, MEDDIC, MEDDICC and MEDDPICC,
  plus organisation-defined frameworks and notes-only operation.
- Existing deterministic calendar, research, brief, debrief, transcription,
  source evidence and intelligence adapters remain the local demonstration
  path. No live provider is activated by this refocus.
- Settings stores timezone, morning-digest and pre-meeting preferences in the
  authenticated user's private server scope. The exact generated content is
  written to a local test outbox for preview only. Stable source fingerprints
  suppress duplicates, rescheduling supersedes the old item and cancellation
  cancels the prepared item. Linked provider-calendar projections supply the
  latest reschedule/cancellation state for their owning user. No email is sent.
- Conversation search matches titles, linked company/person names, current
  transcript text and accepted reported evidence within the active tenant.
  User-owned debrief evidence remains restricted to its creator in search,
  preparation and debrief context.

## Trust boundaries

- The browser never claims universal call detection or cross-application audio
  access. Browser microphone capture requires an explicit user action and
  permission; transcript import and typed notes remain alternatives.
- Website extraction is implemented behind a disabled live-fetch feature flag.
  Local tests exercise the same fetch/extract boundary with deterministic HTTP
  fixtures. Extracted website and document text is always untrusted data: it
  cannot alter prompts, policy or authority and is not available to downstream
  reasoning before review and approval.
- Framework coverage describes supported, missing, stale or conflicting
  evidence. `Not discussed` is unknown, not a negative buyer answer, and
  coverage is not a win probability.
- Follow-up output remains a private draft until the user takes a separate
  action. This change adds no outbound automation. Drafts can be edited,
  server-saved, marked reviewed, copied or exported; optimistic concurrency
  prevents regeneration or another session from silently replacing an edit.
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

- activation of live customer-website fetching and external research (the
  bounded ingestion pipeline is implemented and locally fixture-verified);
- live AI, transcription, email and connector execution;
- real email transport or automatic external delivery (the private preferences,
  exact-content local outbox and schedule metadata are implemented);
- cumulative framework projections for conversations that are not explicitly
  linked to an Opportunity; these are deliberately not merged by company name;
- native macOS and Windows capture, call detection, overlays and installers.

Native clients should reuse the current conversation, capture and intelligence
service boundaries when separately authorised.
