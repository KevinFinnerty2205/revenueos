# Deployment guide

## Current status

RevenueOS has no selected production hosting platform and this repository does
not deploy automatically. This guide records the minimum process boundary and
configuration expectations for the current web, API and worker components; it
is not production approval.

Do not use production customer data. Clerk verification, consent evidence,
retention/export/erasure, provider privacy review, monitoring, backup/restore
and incident controls remain production gates.

## Process topology

- Deploy the Next.js web application without database or OpenAI service
  credentials.
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
5. Start/update the API and verify `/health` and `/ready`.
6. Start/update the worker and verify content-free worker/provider telemetry.
7. Start/update the web application and exercise a synthetic smoke journey.
8. Monitor safe failure, lease, retry, rate-limit and latency signals.

WO-004C1A requires no schema migration; WO-004C2 through WO-004C5 require
`0008_decisions` through `0011_open_questions`, which widen existing AI type
checks. WO-004C6 requires `0012_follow_up_email`, which also adds the guarded
nullable job tone column. The current trace fields already hold provider/model/
request/token metadata. WO-005 requires no migration. WO-006A requires
`0013_buying_signals`; WO-006B requires `0014_objections`; WO-006C requires
`0015_stakeholders`; and WO-006D requires the head migration
`0016_next_best_action`. All four widen only the existing job/artefact type checks without adding a table or
column. Deploy API, worker and web
from the same immutable release so aggregate prompt/schema selection and worker
source validation agree.

## Rollback

Roll back API, worker and web to the same previously validated release. For an
OpenAI-specific operational issue, select `AI_PROVIDER=mock`, restart the
worker, verify new work uses the mock, and revoke/remove the unused OpenAI key.
Do not rewrite completed artefact trace. Database downgrade is unnecessary for
an OpenAI rollback. Downgrading `0016_next_best_action` is destructive to Next
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
