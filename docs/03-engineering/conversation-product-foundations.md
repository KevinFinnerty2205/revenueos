# Conversation product foundations

## Current implementation

Migration `0067_conversation_foundations` adds the durable foundations behind
the conversation-first interface. It does not activate live providers,
outbound delivery or native capture.

### Private user work

Enhanced notes and follow-up drafts are stored in
`conversation_user_workspaces`. Briefing preferences are stored in
`conversation_delivery_preferences`; exact generated previews are retained in
`conversation_briefing_outbox`. Every row carries both organisation and user
ownership. PostgreSQL RLS requires the transaction-local trusted organisation
and user settings, while repository queries repeat both predicates.

Updates use a positive lock version. A stale browser receives a conflict and
must reload; the server never silently replaces another session's version.
Original debrief answers and accepted evidence remain in their existing
records. A browser-local value can be explicitly imported only when its stored
owner ID matches the authenticated server workspace owner. Older unscoped keys
are detected but neither displayed nor imported because their owner cannot be
verified. Owner-tagged browser drafts require an explicit authenticated
ownership check before their contents are loaded. The browser-only view also
exposes a manual `.txt` export for currently visible content before linking,
without weakening the ownership boundary.
Regeneration presents an explicit replacement choice and leaves the current
private draft untouched until the user accepts the new generated version.

Private workspace and preference records are deleted by their membership,
interaction or organisation foreign-key lifecycle. A data export includes
private workspace, preference and local-outbox content only for the user who
requested that export; organisation-shared knowledge remains organisation
data. Knowledge exports include the retained original document as base64 as
well as its filename, media type, extracted text and review metadata.

### Knowledge ingestion

`company_knowledge_ingestion_jobs` is a bounded queue processed by the existing
worker. Fetching/extraction and deterministic synthesis are separate
interfaces. PDF, DOCX and plain text are parsed with file, archive, response and
text limits. Production document parsing runs in a child process with memory,
CPU and wall-clock bounds; the worker terminates the child at the deadline, so
a timed-out parser cannot continue consuming worker resources. Website fetches
require HTTPS, resolve only public addresses, pin
the validated address for the request, revalidate every redirect, limit
redirects and bytes, and reject unsupported content.

Website fetching is disabled by default. Local tests inject deterministic DNS
and HTTP fixtures; they do not contact customer sites. Extracted material is
untrusted source text, never an instruction. Only administrator-approved
sources are retrieved into preparation and debrief context. Refresh marks the
old approval stale until the new extraction is reviewed; retry and cancellation
retain explicit states and safe failure codes.

### Briefing outbox

Preferences are versioned and user-private. Morning and pre-meeting generation
uses the existing Daily and pre-interaction brief contracts. The local outbox
stores the exact subject, body, conversation link, intended time and source
fingerprint. Identical requests are deduplicated, a changed meeting time
supersedes the prior item, and a cancelled meeting cancels prepared items.
Interaction updates and linked provider-calendar sync reconcile already
prepared rows immediately; a second preview request is not required. When an
authorised colleague changes a shared interaction, the server derives the
briefing owner from the locked interaction row and temporarily applies that
trusted owner context only for the bounded reconciliation update.
For a linked Microsoft 365 or Google Workspace calendar projection owned by
the same user, its latest synchronised start and state are authoritative for
the preview. This reuses the existing bounded provider-calendar contract, so a
synthetic connector reschedule or cancellation is reflected without a second
scheduling model.

This is a local test transport and preview boundary. It does not send email or
perform an external connector action. Live email, live website fetching, live
AI/transcription and production connector execution remain disabled.

### Persistence acceptance

`pnpm test:e2e:full-stack` is the dedicated browser-to-API persistence gate. It
requires a migrated PostgreSQL database and a running local API on port 8000;
Playwright starts the web app, changes briefing preferences through the UI,
confirms the new row through the API, verifies it in an independent browser
context, and restores the original values. CI provisions an isolated
PostgreSQL service, migrates it and starts the API before running this gate.
