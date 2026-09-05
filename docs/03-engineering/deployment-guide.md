# Deployment guide

## Current status

RevenueOS has no selected production hosting platform and this repository does
not deploy automatically. WO-009 defines one supported private-beta topology
and operating boundary for the current web, API, worker and PostgreSQL
components; it is not production-data approval.

WO-039C adds a conditional supervised real-data path through current Alembic head
`0053_billing_subscriptions`; it is not blanket approval. Before any named partner,
run the [real-data production preflight and lifecycle runbook](real-data-operations.md)
and satisfy its Clerk, runtime-role/RLS, encrypted backup/restore, support, legal,
provider and feature-profile gates. Unsupervised and commercial beta remain blocked.
WO-048 billing must remain disabled in production; its Stripe adapter is test-mode
only and does not authorise a provider account, live key, webhook or payment.

## Process topology

- Deploy the Next.js web application without database or OpenAI service
  credentials. It uses Clerk middleware and may receive only the server-side
  Clerk secret plus public publishable/template names.
- Deploy FastAPI as a long-running ASGI process.
- Deploy `revenueos-ai-worker` as an independently supervised long-running
  process from the same immutable release as the API.
- Use PostgreSQL with a non-RLS-bypass runtime role. Keep migration credentials
  separate and apply Alembic before starting the API or worker.

## Configuration and secrets

Use the deployment platform's environment-specific secret manager. Never copy
real values into repository files, build arguments, frontend variables,
screenshots or logs.

The default AI provider is `mock`. Enabling `openai` requires server-only
`OPENAI_API_KEY` and `OPENAI_MODEL` values plus bounded timeout/output settings.
Only the worker performs the provider call, but configuration validation must
remain consistent across server processes built from the release.

> Enabling OpenAI transmits the selected meeting transcript and rendered
> extractor instructions to OpenAI, including for Buying Signals and
> Objections & Competitive Signals and Stakeholder Intelligence. Next Best
> Action sends only the eight validated extraction artefacts. Follow-up
> Email transmits only its validated
> customer-safe artefact projection and never transcript text. Production
> customer-content use is blocked operationally until the privacy and
> production-readiness gates are approved.

See [OpenAI provider integration](openai-provider-integration.md) for the exact
variables, data flow, smoke test and rollback.

WO-026 adds `FEATURE_PROSPECT_ENABLED`, `PROSPECT_RESEARCH_PROVIDER_NAME`,
`PRIVATE_BETA_MAX_PROSPECT_RESEARCH_PER_USER_PER_DAY`,
`PRIVATE_BETA_MAX_PROSPECT_RESEARCH_PER_ORGANISATION_PER_DAY`,
`PRIVATE_BETA_MAX_CONCURRENT_PROSPECT_RESEARCH` and
`PRIVATE_BETA_PROSPECT_FRESH_DAYS`. The only current provider value is `mock`.
It is safe for local/CI synthetic data but deliberately unavailable in production;
no provider credential exists. Keep production Prospect disabled until an approved
adapter and its terms/security review are implemented.

WO-030 adds `API_FEATURE_ENGAGE_CAMPAIGNS_ENABLED` as a separate staged-rollout
gate under the existing Engage entitlement and `API_FEATURE_ENGAGE_ENABLED` flag.
Production Campaign execution also requires the existing Action Execution,
Integrations and an approved non-mock user mailbox path. No such mailbox path is
implemented: production rejects Mock Email and therefore Campaign sending must remain
disabled/fail closed. Disabling Engage or Campaign availability halts unsent work;
history remains available under retention policy.

WO-031 adds `API_FEATURE_ENGAGE_EVENTS_ENABLED`. Keep it disabled in production until
the target `0040_event_intelligence` migration, all six forced-RLS policies, import
authority/privacy review, retention/export and 5 MB/500-row/five-import/50-Event caps
are verified. No Event provider credential is required or supported.

## Release order

1. Build and scan one immutable release.
2. Back up and verify recovery expectations for PostgreSQL.
3. Apply Alembic with the guarded migration role.
4. Confirm migration drift checks are clean.
5. Start/update the API and verify `/health/live` and `/health/ready`.
6. Start/update the worker and verify content-free worker/provider telemetry.
7. Start/update the web application and exercise a synthetic smoke journey.
8. Monitor safe failure, lease, retry, rate-limit and latency signals.

WO-004C1A requires no schema migration; WO-004C2 through WO-004C5 require
`0008_decisions` through `0011_open_questions`, which widen existing AI type
checks. WO-004C6 requires `0012_follow_up_email`, which also adds the guarded
nullable job tone column. The current trace fields already hold provider/model/
request/token metadata. WO-005 requires no migration. WO-006A requires
`0013_buying_signals`; WO-006B requires `0014_objections`; WO-006C requires
`0015_stakeholders`; and WO-006D requires `0016_next_best_action`. All four
widen only the existing job/artefact type checks without adding a table or
column. WO-007 requires migration `0017_opportunity_workspace`, which
changes Opportunity metadata, adds the Meeting association and creates the
forced-RLS Opportunity audit table. WO-008A requires the preceding migration
`0018_revenue_brain`, which adds the immutable, forced-RLS Revenue Brain
composition table and append-only guards. WO-008B requires the head migration
`0019_revenue_brain_reasoning`, which adds immutable, forced-RLS account and
opportunity insights with append-only guards. Its deterministic comparison does
not require provider configuration or worker capacity. Deploy API, worker and web
from the same immutable release so aggregate prompt/schema selection and worker
source validation agree.

WO-009 requires head `0020_private_beta_readiness`. It adds deterministic Clerk
organisation mapping/status, admin/member membership status and seven focused
forced-RLS beta tables. It also permits Revenue Brain deletion only under the
trusted tenant plus approved maintenance context. Run migration exactly once,
then start the matching API/worker. Schedule tenant retention and expired-export
purge commands. The complete process, backup/restore drill and launch evidence
are in [private-beta deployment and recovery](private-beta-deployment-and-recovery.md).

WO-011 requires current head `0021_interaction_foundation`. Apply it once
before starting the matching API/web release, then verify deterministic Meeting
links and forced RLS. No worker or provider configuration changes are required.

WO-013 introduced `0023_ai_debrief_voice_journal`. Apply it once before
the matching API/web release and verify forced RLS, candidate review guards and
immutable source-aware snapshots. Configure the existing AI provider plus the narrow
transcription provider only when the feature is enabled; mock remains the no-network
default.

WO-014 requires current head `0024_visual_evidence`. Apply it once before the
matching API/web release and verify forced RLS, visual review guards and the
tenant-scoped storage lifecycle. Production visual capture additionally
requires private S3-compatible storage, a deployment-specific signing secret
and explicit `visualEvidence`/`presentationMode` flag review.

WO-016 requires current head `0026_face_to_face_companion`. Apply it once before
the matching API/web/worker release and verify six new forced-RLS tables, transcript
history backfill, the worker organisation-discovery function and object storage.
Keep recording/transcription/automatic-intelligence flags false initially. Production
binary capture requires private S3-compatible storage and a deployment-specific
signing secret. Run report-only recording reconciliation, a synthetic mock capture,
object-first deletion and raw-retention drill before tenant enablement. OpenAI
transcription additionally requires approved provider terms, server-only key/model
and the OpenAI flag; mock remains the no-network default.

WO-017 requires current head `0027_phone_call_intelligence`. Apply it before the
matching API/web release and verify phone metadata/source backfills, composite
Contact tenancy, constraints, downgrade/re-upgrade and a single Alembic head. The
work order adds no provider credential. Keep recording/transcription flags off until
the existing storage, consent, region and operational gates are approved.

WO-018 requires current head `0028_online_meeting_capture`. Verify both new tables,
source constraint changes, deterministic backfill, forced RLS, downgrade/re-upgrade
and a single head. `API_FEATURE_ONLINE_MEETING_NATIVE_INTEGRATION_ENABLED` and
`API_FEATURE_ONLINE_MEETING_AUTO_INGEST_ENABLED` remain false. No meeting-provider
credential is required; deliberate import reuses existing transcript/recording
storage, consent, quota, export and deletion gates.

WO-022 requires current head `0032_integration_execution`. Deploy API, worker and
web together; verify the six new tables, forced RLS, immutable triggers, worker
discovery function, downgrade/re-upgrade and single head. Keep Integrations, Action
Execution and Mock Connectors disabled in production. No provider credential is
required or accepted for these mock adapters. In a non-production environment,
enable the complete flag set and run one synthetic email simulation before rollout.

WO-025C advances the single head to `0034_crm_sync`. Deploy API, worker and web
together; verify the five new forced-RLS tables, updated connector/capability/status
checks, downgrade/re-upgrade and Alembic drift. HubSpot remains off unless all core
execution flags plus `API_FEATURE_HUBSPOT_CRM_ENABLED` are true and client ID, secret,
exact HTTPS callback and a base64url 32-byte credential master key validate. Register
only the documented scopes. Complete a separately gated developer-test-account
connect, test, deal link, preview, write, reconciliation and disconnect proof before
customer rollout. No real provider smoke test belongs in standard CI.

WO-026 advances the single head to `0035_prospect_research`. Deploy API, worker and
web together; verify Company domain backfill, the six forced-RLS Prospect tables,
module entitlement/usage tables, worker discovery function, downgrade/re-upgrade and
drift. Local development seeds the Prospect entitlement for the fixed development
organisation. Production with the mock provider fails closed and must not be
described as working public research.

WO-030 advances the single head to `0039_campaign_sequences`. Deploy API, worker and
web together; verify the six forced-RLS Campaign tables, published-version and
audience immutability guards, tenant worker-discovery function, downgrade/re-upgrade,
identifier length and drift. Keep the Campaign flag disabled in production until a
mailbox provider, sender authority, compliance and operational rollout are separately
approved. Rollback first disables Engage Campaigns and drains/cancels unsent work;
prefer retaining the forward schema because downgrading to
`0038_personalized_outreach` permanently removes Campaign definitions and history.

WO-031 advances the single head to `0040_event_intelligence`. Deploy API and web
together; verify Event constraints, all six forced-RLS tables, Interaction nullable
link, downgrade/re-upgrade, SQLite immutability-trigger restoration and no drift.
Rollback first disables Events; prefer the forward schema because downgrade deletes
Event-local history after normalising Event source values. Canonical Contacts,
Interactions and Campaigns are outside that cascade.

Rollback first disables HubSpot and Action Execution. Existing external updates
cannot be undone by RevenueOS. Disconnect/revoke tenant connections before retiring
the app/client secret or downgrading. Prefer application rollback with the forward
schema; downgrading `0034` permanently removes OAuth state, encrypted credentials
and CRM mapping configuration and restores the WO-022 simulation-only checks.

Disable Prospect before rolling back `0035`. Prefer application rollback with the
forward schema. Downgrade permanently removes Research Targets, runs, source
metadata, observations, citations, Prospect entitlement/usage and Company normalised
domain; it does not delete canonical Companies.

## Rollback

Disable Action Execution and Integrations before rolling back WO-022. Prefer an
application rollback with the forward schema. Downgrading `0032` permanently
removes connection metadata, previews, execution/attempt/audit history and mock
state; it has no provider-side action to undo because WO-022 is simulation-only.

Prefer application rollback while retaining `0025`. Disable recording,
transcription and automatic intelligence first. Downgrading `0025` permanently
removes recording manifests/consents/usage, transcript history and segments; delete
or export private objects separately before an approved downgrade. Then disable
`visualEvidence` and `presentationMode` if rolling farther back. Downgrading `0024` removes visual metadata and
cannot restore deleted image objects. Downgrading `0023` removes all
debrief sessions, turns, fragments, candidates and source-aware snapshot rows.
Downgrading `0022` removes
all brief versions, traces and review metadata. Downgrading `0021` removes all
standalone Interaction, Capture Session, Evidence and Interaction audit metadata;
Meeting and Revenue Brain rows survive but the compatibility link is removed.
Back up and approve that data loss before downgrade.

Downgrading `0020_private_beta_readiness` deletes all beta consent, settings,
onboarding, usage, feedback, request and safe-event metadata and cannot restore
historical `manager` roles. Prefer application rollback with the forward
schema; downgrade only with backup and explicit data-loss approval.

Roll back API, worker and web to the same previously validated release. For an
OpenAI-specific operational issue, select `AI_PROVIDER=mock`, restart the
worker, verify new work uses the mock, and revoke/remove the unused OpenAI key.
Do not rewrite completed artefact trace. Database downgrade is unnecessary for
an OpenAI rollback. Downgrade `0019_revenue_brain_reasoning` before
`0018_revenue_brain`; this permanently removes only longitudinal insight
history. Then downgrade `0018_revenue_brain` before
`0017_opportunity_workspace`; it removes only immutable snapshot compositions.
Downgrading `0017_opportunity_workspace` removes all
Opportunity audit events and Meeting associations, maps the expanded metadata
back to the earlier contract and may delete company-less opportunities after
dependent links are cleared. Back up and obtain an explicit data-loss decision
first. Downgrading `0016_next_best_action` is destructive to Next
Best Action jobs/artefacts; downgrading `0015_stakeholders` is destructive to Stakeholder
Intelligence jobs/artefacts; downgrading `0014_objections` is destructive to Objections &
Competitive Signals jobs/artefacts; downgrading `0013_buying_signals` is destructive to Buying
Signals jobs/artefacts; downgrading `0012_follow_up_email` is destructive to Follow-
up Email jobs/artefacts and drops their tone column; downgrading
`0011_open_questions` is destructive to Open
Questions jobs/artefacts; downgrading `0010_risks_blockers` is destructive to
Risks & Blockers jobs/artefacts; downgrading `0009_action_items` is destructive to Action
Items jobs/artefacts; downgrading `0008_decisions` is destructive to Decisions
jobs/artefacts. Any downgrade requires an explicit data/rollback decision.
