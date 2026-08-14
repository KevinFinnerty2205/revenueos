# Deployment guide

## Current status

RevenueOS has no selected production hosting platform and this repository does
not deploy automatically. WO-009 defines one supported private-beta topology
and operating boundary for the current web, API, worker and PostgreSQL
components; it is not production-data approval.

Do not use production customer data unless separately approved. Technical Clerk
verification, versioned notice, beta retention/export/deletion, bounded health,
usage and runbooks now exist. Target-environment Clerk governance, provider
privacy approval, secret/log/backup infrastructure, restore evidence and every
unchecked launch item remain gates.

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

WO-013 requires current head `0023_ai_debrief_voice_journal`. Apply it once before
the matching API/web release and verify forced RLS, candidate review guards and
immutable source-aware snapshots. Configure the existing AI provider plus the narrow
transcription provider only when the feature is enabled; mock remains the no-network
default.

## Rollback

Prefer application rollback while retaining `0023`. Downgrading `0023` removes all
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
