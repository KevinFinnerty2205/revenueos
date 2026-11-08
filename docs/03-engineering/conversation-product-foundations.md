# Conversation product foundations

## Current implementation

Migrations `0067_conversation_foundations` through
`0078_private_note_draft_sources` add the durable foundations behind the
conversation-first interface. They do not activate live providers, outbound
delivery or native capture.

### Conversation initiatives and memory

`conversation_threads` are lightweight, tenant-owned buying-initiative groups;
they do not require an Opportunity or pipeline stage. Company and participant
overlap can produce ranked suggestions, but it never assigns a conversation.
Only an authenticated user confirmation creates or corrects the one-to-one
thread assignment. Assignments, corrections and thread metadata changes use
optimistic locks and append metadata-only audit events. Company compatibility is
derived from the direct Interaction company plus linked Opportunity and Person;
conflicting relationships fail closed instead of choosing a precedence. Clearing
an assignment retains a thread-free state row and increments its lock version, so
remove/recreate cycles cannot reset the logical resource and admit an ABA stale
write.

The memory projection keeps current-conversation framework coverage separate
from cumulative confirmed-thread coverage. Cumulative reads include validated
Interaction Intelligence snapshots only from completed, non-deleted
conversations in the confirmed thread. An eligible snapshot also requires its
Capture Session to remain completed and non-deleted and every referenced
Evidence row to remain verified, available, non-deleted and bound to that same
Interaction and session. A stale or deleted source therefore disappears from
both current and cumulative coverage. Eligible records retain source titles and
dates and reuse the existing conflict and staleness rules. There is deliberately
no company-wide fallback: separate initiatives at one company remain separate,
and private user workspaces are never projected into shared thread memory.

### Private user work

Live notes, enhanced notes and follow-up drafts are stored in
`conversation_user_workspaces`. Briefing preferences are stored in
`conversation_delivery_preferences`; exact generated previews and scheduled
deliveries are retained in `conversation_briefing_outbox` with an explicit
`preview` or `scheduled` intent. Preview rows are excluded from discovery and
claim queries and fail closed again before transport submission, so enabling a
provider cannot turn a local preview into an email. Every row carries both
organisation and user ownership. PostgreSQL RLS requires the transaction-local
trusted organisation and user settings, while repository queries repeat both
predicates.

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
Live notes require an explicit save and survive media-capture failures in the
web interface. They remain separate from generated enhanced notes. Regeneration
presents an explicit replacement choice and leaves the current private draft
untouched until the user accepts the new generated version.

For automatic post-conversation generation, one nonblank snapshot of up to
20,000 characters from the current owner's live notes is pinned under the
trusted organisation-and-user context for that generation. The existing
100,000-character workspace save boundary remains unchanged; a longer saved note
is preserved and the automatic generation is transcript-only. The snapshot is
untrusted personal content and remains inside the owner-private generation
boundary. It is composed with the pinned transcript
result only to produce private enhanced notes; it is not copied into tenant-wide
AI jobs or artefacts, follow-up source material, conversation memory or shared
intelligence. The original live notes remain unchanged. Optimistic locking and
explicit generated-version application continue to preserve user edits. A later
live-note save neither mutates the pinned snapshot nor claims to create a new
note-only generation.

Automatic post-conversation generation writes its private draft generation ID
atomically into a nullable internal AI-job column only when it creates a job.
Database triggers make that origin immutable, and the non-public creation audit
must independently agree with the durable origin, requester and transcript
trace. A missing, cleared, malformed, duplicated or mismatched audit therefore
fails closed rather than making automatic work look manual. The private
orchestrator reads only jobs and artefacts tagged with its exact generation;
manual and organisation-shared reads accept only untagged work. Its deliberately
neutral capability set is executive summary, decisions, action items, open
questions and follow-up draft—never the sales-only extraction set or Next Best
Action. Those structured jobs and the follow-up composer remain transcript-only.
After the transcript-derived prerequisites complete, the owner-private local
composer may use the pinned personal-note snapshot for enhanced notes only. The
composer fails with safe metadata instead of truncating either the verbatim note
or transcript-derived evidence if the rendered enhanced notes would exceed the
workspace save boundary. Raw personal notes, rendered prompts and note-derived
private content stay out of AI
job metadata, shared artefacts, logs and audits. Creation audits are revalidated
before a completed prerequisite is consumed or materialised. Before an automatic
job enters an executor, and again immediately before each provider request, the
worker re-establishes the linked owner's private RLS context and rechecks the
feature gate, completed/non-deleted Interaction, active membership, current data
notice and immutable source recording/evidence authority. Transcript corrections
inherit that source owner and consent lineage rather than falling back to the
Interaction creator. A missing, mismatched or revoked source cancels only jobs
carrying that durable automatic origin and its private generation, without
cancelling unrelated manual AI work. Only the deterministic local note-composition
path is verified; no live provider is activated. Migration downgrade refuses to
discard the origin column while any tagged AI job remains.

Private workspace, draft-generation and preference records are deleted by their
membership, interaction or organisation foreign-key lifecycle. A data export
includes the pinned personal-note snapshot, private workspace, generated draft,
preference and local-outbox content only for the user who requested that export;
organisation-shared knowledge remains organisation data. Knowledge exports
include the retained original document as base64 as well as its filename, media
type, extracted text and review metadata.

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
stores the exact subject, body, conversation link, intended time, source
fingerprint and delivery intent. Identical requests are deduplicated, a changed
meeting time supersedes the prior item, and a cancelled meeting cancels prepared
items. Exact-content preview rows are permanently non-deliverable and use a
separate deduplication namespace from scheduled rows.
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

The existing worker can now discover active owners with explicit saved
preferences, materialise one date-scoped timezone-aware morning row plus bounded
upcoming pre-meeting rows, discover due scheduled rows, claim them with a lease,
and persist `queued`, `sending`, `sent`, `failed` or `cancelled` outcomes. Here,
`sent` means the configured transport or provider accepted the submission; it
does not prove inbox delivery or exactly-once receipt. New
calendar items are picked up by the same polling worker; no parallel scheduler
or queue was added. A first run after the configured morning time materialises
that local date's deterministic row for same-day catch-up; its date-scoped key
and any existing sent row prevent replay. It rechecks the membership, user,
delivery preference,
current meeting time/state, mailbox capability and allowlisted relative link
while holding the row lock. Email content expands that path only against a
configured trusted application origin; production provider mode requires the
exact approved HTTPS Oryntela origin. Preference changes reschedule or cancel
queued scheduled work. Retryable failures reuse one stable operation key; an
uncertain provider response or an expired `sending` lease becomes terminal
`failed` work and is never resubmitted automatically. This work order does not
ship a manual ambiguity-resolution operation; that tooling is explicitly
deferred, so operators must not clear or replay an ambiguous row by editing the
database. Once a
provider submission starts, its logical morning or interaction source remains a
durable fence: a changed fingerprint waits for the receipt, and an ambiguous
outcome blocks replacement delivery. This gives one automatic submission
attempt under ambiguity, not exactly-once delivery.

The feature and production launch profiles remain disabled by default. Local
mode is rejected outside development/test and maps mock, Google Workspace and
Microsoft 365 mailbox authority to the same deterministic no-network transport,
so each connector-specific permission path is exercised without sending mail.
Provider mode is an explicit configuration boundary that selects the existing
bounded Google/Microsoft mail clients only when their integration flags,
credentials and production approvals already pass. No live activation was
performed. Cross-tenant scheduler discovery remains a revoked-by-default
`SECURITY DEFINER` function; activation must grant only that exact function to
the approved worker role. Logs retain identifiers and safe status codes only,
never briefing bodies or addresses.

### Persistence acceptance

`pnpm test:e2e:full-stack` is the dedicated browser-to-API persistence gate. It
requires a migrated PostgreSQL database and a running local API on port 8000;
Playwright starts the web app, changes briefing preferences through the UI,
confirms the new row through the API, verifies it in an independent browser
context, and restores the original values. CI provisions an isolated
PostgreSQL service, migrates it and starts the API before running this gate.
