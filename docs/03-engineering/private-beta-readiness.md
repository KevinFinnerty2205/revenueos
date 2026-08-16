# Private beta readiness guide

WO-018 adds a 512 KiB online transcript-import ceiling and server-authoritative
`ONLINE_MEETING_CAPTURE`, `ONLINE_MEETING_IMPORT`,
`ONLINE_MEETING_NATIVE_INTEGRATION` and `ONLINE_MEETING_AUTO_INGEST` flags. Capture
and deliberate import default on locally; native and auto-ingestion default off.
Recording bytes, transcription minutes/requests and AI generation limits are
reused—there is no billing or native-fetch quota.

## Status and boundary

WO-009 prepares RevenueOS for a controlled private beta with approximately
5–10 trusted design partners. It hardens the existing product; it adds no AI
capability, prompt, schema, job type or provider. Production customer data
remains prohibited unless a separate approval explicitly changes that rule.

The supported beta topology is the Next.js web service, FastAPI API, durable
worker and PostgreSQL. Clerk is the only production identity provider. Mock
authentication and SQLite remain development/test-only.

## Identity, organisations and roles

- Production configuration requires `API_AUTH_MODE=clerk`,
  `API_MOCK_AUTH_ENABLED=false`, PostgreSQL and complete Clerk issuer, audience
  and JWKS configuration. Startup fails closed otherwise.
- Next.js uses Clerk middleware and server-side session checks. A signed-in user
  without an active organisation is sent to organisation selection.
- Browser API requests carry a Clerk token. The API verifies RS256 signature,
  issuer, audience, expiry, issued-at time and required `sub`/`org_id` claims.
  JWKS retrieval is cached and time-bounded.
- Local IDs are deterministic from the verified external user and organisation
  IDs. The client cannot supply an organisation context.
- Roles are only `admin` and `member`. Unknown provider roles map to `member`.
- A disabled user or membership is rejected on the next authenticated request.
  An admin cannot disable their own membership through the beta API.
- Clerk invitations, sign-up restrictions and organisation creation policy are
  configured in Clerk. Deleting the external Clerk identity remains an
  operator step after RevenueOS deletion completes.

For a custom Clerk JWT template, set `NEXT_PUBLIC_CLERK_JWT_TEMPLATE` in the
web service. The template audience must equal `API_CLERK_AUDIENCE` and it must
preserve the active organisation claims. No Clerk secret or token may use a
`NEXT_PUBLIC_` variable.

## Onboarding

The skippable `/onboarding` journey persists one state per user and
organisation. It introduces the product, requires the data notice, then points
to company, opportunity, meeting, transcript, Meeting Intelligence,
Opportunity Workspace and Revenue Brain steps. It does not seed production
organisations or imply unavailable features.

Recommended operator onboarding:

1. Approve the design partner and their permitted organisation in Clerk.
2. Invite the first admin; disable unrestricted sign-up/organisation creation
   unless it is part of the approved Clerk policy.
3. Confirm the admin selected the expected organisation and can open Settings.
4. Set retention explicitly, even when accepting the 90-day default.
5. Confirm the current notice version and acknowledgement count.
6. Use synthetic demo data for the first walkthrough.
7. Keep OpenAI disabled initially. Enable it only after the separate data-use
   approval and provider review are recorded.

## Consent and privacy notice

Before a user can create/update a transcript or request any intelligence, the
API requires acknowledgement of the current code-deployed notice version. The
notice explains authority to process content, external OpenAI processing only
when explicitly enabled, internal mock processing and the need to review
generated intelligence.

Only organisation ID, user ID, positive notice version and timestamp are
stored. The client cannot choose the version and no free-form consent text is
accepted. Incrementing `API_PRIVATE_BETA_DATA_NOTICE_VERSION` requires every
user to acknowledge the new version. Do not change it without an approved
notice and release note.

## Retention and deletion policy

An admin chooses 30, 90 or 180 days, or explicitly chooses manual retention.
The safe default is 90 days. Retention selects old meetings only when both the
meeting date and transcript update time are older than the cutoff, plus old
standalone completed/cancelled Interactions using actual end, scheduled start or
updated time in that order. It removes, in dependency order, Revenue Brain
insights/snapshots, AI artefacts/jobs, content-minimised Meeting/Interaction audit
rows, transcript, Evidence, Capture Sessions, participants, Meeting and Interaction.
Completed Pre-Interaction Briefs are counted in dry runs and removed before their
Interaction; no brief content enters the maintenance event.
Feedback references are detached; no content is copied into the maintenance
event. Deleted records therefore disappear from Opportunity Workspace and
Revenue Brain.

Run a tenant-scoped dry run first:

```text
uv --directory apps/api run revenueos-beta-maintenance retention --organisation-id <UUID> --batch-size 100 --dry-run
```

Review the counts, then omit `--dry-run` to execute one bounded batch. Repeat
until both `eligible_meetings` and `eligible_interactions` are zero. The command is
idempotent and each batch is a separate transaction. Schedule it at least daily
per beta organisation. The
PostgreSQL append-only guards allow deletion only when this command sets both
the trusted tenant and explicit approved-maintenance context.

Disabling a member does not delete shared organisation records. An admin can
queue full organisation deletion only when the server flag is enabled and the
exact `DELETE <organisation-slug>` phrase matches. An operator executes:

```text
uv --directory apps/api run revenueos-beta-maintenance delete-organisation --organisation-id <UUID> --request-id <UUID>
```

The request moves to processing before the atomic deletion transaction. A
failed/interrupted run can be safely retried with the same IDs. On success the
organisation and its request are gone. Temporary export files are path-checked
and removed before their database records; an unsafe/unremovable path fails the
request visibly without deleting the organisation, and retry is supported after
operator correction. Verify absence, then manually remove the external Clerk
organisation/users only when they have no other authorised membership. There
is no legal hold or regulated erasure certification.

## Data export

Admins queue a versioned JSON export in Settings. An operator runs:

```text
uv --directory apps/api run revenueos-beta-maintenance export --organisation-id <UUID> --request-id <UUID>
```

Export version 9 has deterministic sections/order and a safe UUID filename. It may
contain authorised transcripts and validated intelligence, so store it only in
the restricted directory configured by `API_PRIVATE_BETA_EXPORT_DIRECTORY`.
It includes Interaction, Capture Session, Evidence, Interaction audit metadata and
Pre-Interaction Brief content plus safe typed source references.
It excludes credentials, provider request IDs, worker leases, retry errors and
other internal execution fields. API responses never expose the filesystem
path. Downloads expire after 24 hours and validate both the configured root and
exact filename.

After expiry, remove files and clear their paths in bounded tenant batches:

```text
uv --directory apps/api run revenueos-beta-maintenance purge-exports --organisation-id <UUID> --batch-size 100
```

Do not log, email or attach export content to an incident ticket.

## Usage guardrails

Daily PostgreSQL counters are tenant scoped and updated atomically:

- `API_PRIVATE_BETA_MAX_GENERATIONS_PER_DAY` counts newly created generation
  jobs or deterministic Pre-Interaction Brief versions. Idempotent reuse does not
  increment it. Mock, OpenAI and provider-free generation are bounded for abuse.
- `API_PRIVATE_BETA_MAX_OPENAI_REQUESTS_PER_DAY` counts each actual OpenAI
  request, including strict-output retries. Mock requests do not count here.
- `API_PRIVATE_BETA_MAX_TRANSCRIPT_CHARACTERS` rejects oversized transcript
  writes before processing.
- `API_PRIVATE_BETA_MAX_DEBRIEF_SESSIONS_PER_DAY` defaults to 25. The question
  cap defaults to six (allowed 1–10); voice segments default to at most 120 seconds
  and 8 MB. Debrief finish consumes the generation counter and configured OpenAI
  question/extraction/transcription calls consume the external-provider counter.
- Existing `API_AI_STRUCTURED_OUTPUT_MAX_ATTEMPTS` and
  `API_WORKER_DEFAULT_MAX_ATTEMPTS` bound validation attempts and durable
  retries.
- Recording guardrails separately bound active sessions, three-hour/512 MiB
  recordings, 8 MiB chunks, 4,096 chunks, bytes/day, transcription minutes and
  requests/day, simultaneous transcriptions and three durable attempts. Recording
  usage has its own tenant/day counter.

Counters use the UTC calendar date and reset by selecting the next date row;
they are not mutated at midnight. Admin Settings shows counts and limits. Cost
is reported as unavailable; RevenueOS makes no hard-coded pricing claim.

## Feature flags

The following environment flags are server-authoritative and have safe
defaults:

| Flag                                                         | Default |
| ------------------------------------------------------------ | ------- |
| `API_FEATURE_OPENAI_PROVIDER_ENABLED`                        | `false` |
| `API_FEATURE_REVENUE_BRAIN_ENABLED`                          | `true`  |
| `API_FEATURE_OPPORTUNITY_WORKSPACE_ENABLED`                  | `true`  |
| `API_FEATURE_AI_COMPANION_ENABLED`                           | `true`  |
| `API_FEATURE_AI_DEBRIEF_ENABLED`                             | `true`  |
| `API_FEATURE_VOICE_JOURNAL_ENABLED`                          | `true`  |
| `API_FEATURE_VISUAL_EVIDENCE_ENABLED`                        | `true`  |
| `API_FEATURE_PRESENTATION_MODE_ENABLED`                      | `true`  |
| `API_FEATURE_RECORDING_CAPTURE_ENABLED`                      | `false` |
| `API_FEATURE_TRANSCRIPTION_ENABLED`                          | `false` |
| `API_FEATURE_AUTO_GENERATE_INTELLIGENCE_AFTER_TRANSCRIPTION` | `false` |
| `API_FEATURE_ONLINE_MEETING_CAPTURE_ENABLED`                 | `true`  |
| `API_FEATURE_ONLINE_MEETING_IMPORT_ENABLED`                  | `true`  |
| `API_FEATURE_ONLINE_MEETING_NATIVE_INTEGRATION_ENABLED`      | `false` |
| `API_FEATURE_ONLINE_MEETING_AUTO_INGEST_ENABLED`             | `false` |
| `API_FEATURE_LIVE_INTERACTION_INTELLIGENCE_ENABLED`          | `false` |
| `API_FEATURE_LIVE_INTERACTION_EXTERNAL_AI_ENABLED`           | `false` |
| `API_FEATURE_DATA_EXPORT_ENABLED`                            | `true`  |
| `API_FEATURE_ORGANISATION_DELETION_ENABLED`                  | `false` |

OpenAI selection is invalid unless its flag is enabled. Disabled API routes
fail closed with a product-safe `404`; browser feature gates do not render the
disabled workspace. Unknown flags are never returned and are treated as off.
There is deliberately no feature-flag administration UI.

## Health and safe monitoring

- `GET /health/live` proves the process can serve a request.
- `GET /health/ready` performs fast, bounded checks for database connectivity,
  Alembic head `0032_integration_execution`, identity configuration, selected
  provider configuration and worker timing configuration. It never calls
  OpenAI.
- Legacy `/health` and `/ready` aliases remain available.

Responses contain only product-safe status. Structured server logs include
request/correlation ID and may include opaque organisation/user UUIDs after
authentication. They exclude transcripts, prompts, generated content,
provider output, customer descriptions, emails, stakeholder names and secrets.
Collect JSON logs centrally and alert on readiness failure, safe error codes,
worker retry exhaustion, stuck leases and quota responses.

## Synthetic demo data

The explicit seed creates one clearly labelled synthetic company, one
opportunity, two recent completed meetings with linked Interactions, three upcoming
participant-linked Interactions and completed synthetic phone, presentation, site,
executive and trade-show variants. Each upcoming Interaction has an immutable
deterministic brief. A reviewed phone AI Debrief supplies “Reported by you”
Interaction/Revenue Brain state. The upcoming and completed phone calls link the
same synthetic Contact with outbound direction; a trade-show Voice Journal remains resumable.
The online-meeting set adds deterministic Teams platform-transcript, Zoom
platform-recording and Google Meet AI-Debrief fallback paths.
Document/email evidence adds a customer RFP, seller proposal, verified inbound
customer email and outbound seller email with reviewed, provenance-labelled source
snapshots.
The completed presentation includes a synthetic, reviewed customer-whiteboard
visual in private storage and a provenance-labelled schema-v2 Interaction and
Revenue Brain projection. The completed executive lunch includes two
metadata-only Companion markers for the AFTER summary. It makes no provider call. The completed
Meetings retain synthetic transcripts, so
the default retention policy does not immediately expire the walkthrough. Its
IDs and content are deterministic, it is tenant-scoped and idempotent, and it
makes zero external provider calls:

```text
uv --directory apps/api run revenueos-demo-data seed --organisation-id <UUID> --user-id <UUID>
```

With `AI_PROVIDER=mock`, use the existing Generate Meeting Intelligence action
for both meetings and run the worker. This deterministic existing path creates
Buying Signals, Objections, Stakeholders, Next Best Action and the remaining
validated artefacts, which produce two Revenue Brain snapshots and support
deterministic reasoning. Seeded debrief state is deterministic persistence and does
not invoke a provider.

Reset only that organisation's fixed demo IDs:

```text
uv --directory apps/api run revenueos-demo-data reset --organisation-id <UUID>
```

Reset removes every fixed demo Interaction, its three briefs, phone Contact,
debrief/evidence state, Companion markers, visual and document objects, email
content and all established Meeting/Brain rows.
Never run the seed automatically or use it to overwrite a real record.

## Feedback handling

The Feedback navigation item accepts a fixed category, optional 1–5 rating,
message up to 2,000 characters, current route and optional same-tenant meeting
or opportunity IDs. RevenueOS never attaches transcripts, generated content or
screenshots. Submissions are user/tenant scoped and daily rate limited.
Admins can retrieve their organisation's bounded newest-first list from
`GET /api/v1/beta/admin/feedback`. Treat messages as potentially sensitive;
copy only the minimum necessary paraphrase into external support systems.

## Beta administration

`/settings` and `/api/v1/beta/admin*` are admin-only. The view exposes only
organisation metadata, member roles/status, retention, notice counts, safe
feature flags, daily counters, data-request status and metadata-only events.
It contains no transcript preview, generated content, prompt, provider error or
global cross-tenant console. Membership disablement takes effect at the next
verified API request.

## Known limitations

## WO-014 visual-data controls

Visual evidence has separate per-image, per-interaction storage, daily analysis
and retry limits. `visualEvidence` and `presentationMode` are independently
visible feature flags. Production validation rejects local storage or the
default signing secret when visual capture is enabled.

Retention and organisation deletion remove visual objects before database
lineage. Export version 8 includes visual metadata and review content; image
bytes remain disabled unless `API_PRIVATE_BETA_EXPORT_VISUAL_IMAGES_ENABLED`
has received separate approval. Telemetry records counts, type, ownership,
attempt and safe error codes only—not bytes, OCR, context labels, statements,
signed URLs or provider payloads.

## WO-015 recording-data controls

Recording uses distinct consent, active-session, size/duration/chunk, daily bytes,
transcription minutes/request, concurrency, retry, expiry and seven-day raw-audio
limits. Recording, transcription and automatic intelligence are independently
server-authoritative and default off. Production validation requires private
S3-compatible storage and a deployment signing secret when recording is enabled.

Retention and organisation/Interaction deletion remove recording objects before
database lineage. Export version 9 includes recording/consent metadata, a content-free
chunk manifest, transcript versions and segments; raw audio, storage keys, signed
URLs and provider request IDs are excluded. Reconciliation is tenant-scoped and
metadata-only.

## WO-016 Companion controls

The browser Companion is governed by `aiCompanion`; its reused recording,
visual and debrief capabilities keep their independent server flags and quotas.
Quick markers have no content or provider cost and therefore add no separate
usage quota. They are bounded by controlled type, lifecycle, tenant scope and
Interaction retention. Export version 8 adds active marker metadata without the
idempotency key. Organisation deletion removes markers before Interactions.

## WO-017 phone-call controls

Phone Call Intelligence adds no independent feature flag or quota. The ordinary
Interaction path is metadata-only; `aiCompanion`, `aiDebrief`, `voiceJournal`,
`recordingCapture` and `transcription` remain separately server-authoritative. Call
recording imports consume the existing recording byte, duration, request and
transcription-minute limits. Export version 8 adds Contact/direction/outcome,
recording-source and reconciliation-state metadata. Synthetic demo data includes an
outbound Contact-linked call and reviewed reported intelligence; it contains no real
number, customer content or provider call.

## WO-018 online-meeting controls

The import service reuses recording, transcription and AI generation quotas and
adds only `API_PRIVATE_BETA_MAX_ONLINE_MEETING_TRANSCRIPT_BYTES` (512 KiB by
default). Native and auto-ingestion flags default off. Export version 9 includes
normalised metadata and authorised transcript import lineage. Organisation deletion
removes local metadata/imports/objects and derived evidence but does not delete a
provider's upstream artefact. Demo data has one Teams transcript, one Zoom recording
and one Google Meet Debrief fallback; no external call or credential is used.

## WO-019 document and email controls

- `API_FEATURE_DOCUMENT_EVIDENCE_ENABLED` and
  `API_FEATURE_EMAIL_EVIDENCE_ENABLED` are
  independent kill switches. Capability responses continue to state that provider
  import is unavailable.
- Documents are limited by bytes, pages, extracted characters, uploads per day and
  total organisation storage. Emails are limited per organisation/day and by the
  plain-text contract. Processing retries are bounded separately.
- `API_EVIDENCE_EXTRACTION_PROVIDER_NAME=mock` is deterministic and makes no network call. Optional
  OpenAI mode requires explicit server configuration and shares the production
  customer-data approval boundary.
- Export format v10 contains authorised raw document/email source data plus
  fragments, candidates and source snapshots. Retention and organisation deletion
  delete document objects before database lineage and clear email content.
- Synthetic demo version 10 adds a customer RFP, seller proposal, verified inbound
  customer email and outbound seller email. All content is visibly synthetic and
  provider calls remain zero.

## WO-020 Live Intelligence controls

- Both live flags are independent server-side kill switches and default off. The
  external-live flag requires the base flag, acknowledgement and a separately
  configured adapter; no such adapter is implemented in WO-020.
- Default cadence/limits are 15 seconds, two new segments or 160 characters, 12
  segments/8,000 characters per window, four requests/minute, 120
  requests/Interaction, 200,000 processed characters/Interaction, three concurrent
  live Interactions/organisation and 200 external provider calls/day.
- Live data expires after 30 days by default. Export v11 includes bounded signal,
  source-range, progress and reconciliation metadata but excludes processing
  windows/fingerprints, raw transcript and provider internals.
- Meeting, recording-source, Interaction and organisation deletion remove live
  dependants before referenced source parents. Synthetic demo version 11 includes
  one completed/reconciled live Interaction and an online no-source fallback.
- The deterministic detector makes no network request and usage reservation reaches
  the existing provider counter only for an adapter declaring external processing.

- Private beta only; production customer data is prohibited unless separately
  approved.
- No enterprise SSO, SCIM, advanced RBAC, legal hold, billing, CRM or email
  integration, email sending, automatic recording, transcription, mobile app,
  free-form Revenue Brain chat or predictive forecasting.
- External OpenAI processing occurs only when explicitly enabled and approved.
- Retention, export and deletion are beta-grade operational controls, not a
  regulated-industry certification.
- Clerk invitation/deletion and all maintenance/runbook steps require a human
  operator.

See [private-beta deployment and recovery](private-beta-deployment-and-recovery.md),
[operational runbooks](private-beta-runbooks.md), the
[security review](private-beta-security-review.md) and
[launch checklist](private-beta-launch-checklist.md).

## Action Layer controls

`API_FEATURE_ACTION_LAYER_ENABLED` gates all Action routes and defaults on for the
WO-021 baseline. `API_FEATURE_ACTION_MANUAL_COMPLETION_ENABLED` separately gates
internal manual completion. `API_PRIVATE_BETA_MAX_ACTION_GENERATIONS_PER_DAY`
defaults to 100 per organisation; each request is capped at eight new proposals and
each opportunity at 50 active proposals. Export schema v12 contains proposals,
versions and safe audit metadata.

## WO-022 integration and execution controls

`API_FEATURE_INTEGRATIONS_ENABLED`, `API_FEATURE_ACTION_EXECUTION_ENABLED` and
`API_FEATURE_MOCK_CONNECTORS_ENABLED` are separate server-authoritative switches.
All must be on with the Action Layer outside production; safe defaults are off and
production rejects Mock Connectors. Capability limits default to 50 email, 25
calendar, 100 CRM and 100 task simulations per organisation/day, with five active
executions per organisation and a ten-minute preview TTL.

Export schema v13 includes connection, execution, attempt and integration-audit
metadata but omits credential references, idempotency keys, preview fingerprints,
leases and mock external objects. Retention of an Action or organisation cascades
its execution metadata. Revocation invalidates open previews and cancels queued
work. There is no live credential or external provider deletion in WO-022.

WO-024 advances export schema to v14 with methodology definitions/versions,
selection, projections and reviews. Retention and deletion cover those rows plus
linked salesperson-reported clarification Evidence. Synthetic demo data now includes
historical BANT and current MEDDPICC projections from final synthetic sources; it
makes zero provider calls. The Core methodology flag uses the existing feature-flag
endpoint and can fail closed without disabling other RevenueOS workflows.
