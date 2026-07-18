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
> Executive Summary or Decisions instructions to OpenAI. Production customer-content use is
> blocked operationally until the privacy and production-readiness gates are
> approved.

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

WO-004C1A requires no schema migration; WO-004C2 requires only
`0008_decisions`, which widens existing AI type checks. The current trace fields
already hold provider/model/request/token metadata.

## Rollback

Roll back API, worker and web to the same previously validated release. For an
OpenAI-specific operational issue, select `AI_PROVIDER=mock`, restart the
worker, verify new work uses the mock, and revoke/remove the unused OpenAI key.
Do not rewrite completed artefact trace. Database downgrade is unnecessary for
an OpenAI rollback. Downgrading `0008_decisions` is destructive to Decisions
jobs/artefacts and requires an explicit data/rollback decision.
