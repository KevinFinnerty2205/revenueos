# Private beta readiness guide

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
meeting date and transcript update time are older than the cutoff. It removes,
in dependency order, Revenue Brain insights/snapshots, AI artefacts/jobs,
content-minimised meeting audit rows, transcript, participants and meeting.
Feedback references are detached; no content is copied into the maintenance
event. Deleted records therefore disappear from Opportunity Workspace and
Revenue Brain.

Run a tenant-scoped dry run first:

```text
uv --directory apps/api run revenueos-beta-maintenance retention --organisation-id <UUID> --batch-size 100 --dry-run
```

Review the counts, then omit `--dry-run` to execute one bounded batch. Repeat
until `eligible_meetings` is zero. The command is idempotent and each batch is a
separate transaction. Schedule it at least daily per beta organisation. The
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

The export has deterministic sections/order and a safe UUID filename. It may
contain authorised transcripts and validated intelligence, so store it only in
the restricted directory configured by `API_PRIVATE_BETA_EXPORT_DIRECTORY`.
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
  jobs. Idempotent reuse does not increment it. Mock and OpenAI are both
  bounded for abuse.
- `API_PRIVATE_BETA_MAX_OPENAI_REQUESTS_PER_DAY` counts each actual OpenAI
  request, including strict-output retries. Mock requests do not count here.
- `API_PRIVATE_BETA_MAX_TRANSCRIPT_CHARACTERS` rejects oversized transcript
  writes before processing.
- Existing `API_AI_STRUCTURED_OUTPUT_MAX_ATTEMPTS` and
  `API_WORKER_DEFAULT_MAX_ATTEMPTS` bound validation attempts and durable
  retries.

Counters use the UTC calendar date and reset by selecting the next date row;
they are not mutated at midnight. Admin Settings shows counts and limits. Cost
is reported as unavailable; RevenueOS makes no hard-coded pricing claim.

## Feature flags

The following environment flags are server-authoritative and have safe
defaults:

| Flag | Default |
| --- | --- |
| `API_FEATURE_OPENAI_PROVIDER_ENABLED` | `false` |
| `API_FEATURE_REVENUE_BRAIN_ENABLED` | `true` |
| `API_FEATURE_OPPORTUNITY_WORKSPACE_ENABLED` | `true` |
| `API_FEATURE_DATA_EXPORT_ENABLED` | `true` |
| `API_FEATURE_ORGANISATION_DELETION_ENABLED` | `false` |

OpenAI selection is invalid unless its flag is enabled. Disabled API routes
fail closed with a product-safe `404`; browser feature gates do not render the
disabled workspace. Unknown flags are never returned and are treated as off.
There is deliberately no feature-flag administration UI.

## Health and safe monitoring

- `GET /health/live` proves the process can serve a request.
- `GET /health/ready` performs fast, bounded checks for database connectivity,
  Alembic head `0020_private_beta_readiness`, identity configuration, selected
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
opportunity and two recent completed meetings with synthetic transcripts, so
the default retention policy does not immediately expire the walkthrough. Its
IDs and content are deterministic, it is tenant-scoped and idempotent, and it
makes zero provider calls:

```text
uv --directory apps/api run revenueos-demo-data seed --organisation-id <UUID> --user-id <UUID>
```

With `AI_PROVIDER=mock`, use the existing Generate Meeting Intelligence action
for both meetings and run the worker. This deterministic existing path creates
Buying Signals, Objections, Stakeholders, Next Best Action and the remaining
validated artefacts, which produce two Revenue Brain snapshots and support
deterministic reasoning. No new AI path exists for demo data.

Reset only that organisation's fixed demo IDs:

```text
uv --directory apps/api run revenueos-demo-data reset --organisation-id <UUID>
```

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
