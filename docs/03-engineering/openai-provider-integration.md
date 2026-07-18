# OpenAI provider integration

## Current boundary

WO-004C1A adds the first external AI adapter behind the existing
provider-neutral boundary. The separately deployed worker can run the existing
Executive Summary, Decisions, Action Items and Risks & Blockers through either the deterministic `mock`
provider or the server-only `openai` provider. Selection is process
configuration; there is no
browser setting, tenant credential, model selector or fallback provider.

The default remains `mock`. Automated tests and ordinary local development need
no OpenAI credential and make no external call.

> **External data-flow warning:** setting `AI_PROVIDER=openai` sends the
> rendered Executive Summary, Decisions, Action Items or Risks & Blockers instructions and selected meeting transcript to
> OpenAI. Do not enable it with production customer content until production
> identity, consent, retention, deletion, provider privacy and operational
> controls are approved.

## Responses API and strict output

`OpenAIProvider` uses the official Python SDK's asynchronous Responses API. It
converts the provider-neutral ordered `system`/`user` messages to Responses API
input and requests a strict `json_schema` text format. The JSON Schema is
generated directly from the matching registered Pydantic Executive Summary,
Decisions, Action Items or Risks & Blockers schema v1; there is no second vendor-specific product schema.

The adapter disables response storage with `store=false`, requests no tools,
does not stream and does not grant the model write authority. A completed
response is normalised into the internal `ProviderResponse`. The existing
structured-output parser and Pydantic model remain authoritative and reject
malformed JSON, extra fields or invalid field values before an artefact can be
stored.

Refusals, incomplete responses and responses without a usable output body fail
with bounded safe provider errors. Raw SDK response objects and raw model output
never cross the adapter boundary.

## Configuration

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `AI_PROVIDER` | `mock` | Exact provider selection: `mock` or `openai` |
| `OPENAI_API_KEY` | empty | Server-only secret; required only for `openai` |
| `OPENAI_MODEL` | empty | Required provider model identifier; for example `gpt-5.6` where available to the account |
| `OPENAI_TIMEOUT_SECONDS` | `30` | Per-request timeout, greater than zero and at most 300 |
| `OPENAI_MAX_OUTPUT_TOKENS` | `4096` | Output ceiling from 256 to 32,768 |

The model is never silently changed. An inaccessible or unsupported configured
model fails non-retryably so an operator can correct configuration. Model
availability must be confirmed for the specific OpenAI project before use.

Only the API/worker environment may receive `OPENAI_API_KEY`. It must come from
an environment-specific secret manager in deployed environments. No
`NEXT_PUBLIC_*` equivalent exists, and the key is not returned by safe
configuration diagnostics, stored in PostgreSQL, included in audits or logged.
Empty, malformed or incomplete OpenAI configuration fails during settings
validation or provider construction.

## Request lifecycle

1. The API queues the tenant-owned Executive Summary, Decisions, Action Items or Risks & Blockers job.
2. The worker claims it and loads the exact pinned transcript in a short
   tenant-bound transaction.
3. The transaction closes and cancellation is checked before provider
   execution.
4. The executor resolves the immutable prompt/schema and selected provider.
5. With `openai`, the adapter performs one bounded Responses API request.
6. The adapter normalises status, request ID, latency and token usage.
7. Existing bounded structured-output validation/retry runs outside a database
   transaction.
8. The completion transaction rechecks tenant ownership, worker ownership and
   cancellation, then atomically stores the validated artefact and completes
   the job.

The SDK transport retry count is zero. The durable PostgreSQL worker owns
backoff, attempt limits, leases, recovery and idempotency, preventing a hidden
second retry system.

## Error mapping

Retryable classifications are timeout, rate limiting, connection/transient
network failure and server/service unavailability. Authentication, permission,
model not found, invalid request, invalid configuration, refusal, incomplete
response and malformed response are non-retryable.

Only stable internal codes and safe messages reach job state, audit metadata or
logs. Raw SDK exception text, response bodies and authorisation data are not
persisted or logged. A timeout becomes the existing retryable
`provider_timeout`; durable worker policy decides whether and when to retry.

## Usage, traceability and cost

Completed jobs and artefacts record the normalised provider and configured
model. Jobs additionally retain the OpenAI request identifier and available
input/output token counts. Total tokens are validated as input plus output.
Provider latency and finish status are emitted only as content-free structured
telemetry under the existing schema.

Estimated cost remains `0 AUD` because the repository has no approved,
versioned pricing source. Zero means **not calculated**, not that the OpenAI
request is free. Do not use this field for billing, budgets or pricing claims.

## Metadata-only telemetry

Allowed telemetry includes tenant/job IDs, provider/model, schema identity,
provider request ID, latency, token counts, finish status, safe error code and
retryability. It excludes API keys, headers, transcripts, participant data,
prompt templates, rendered messages, provider input/output, artefact content
and raw exceptions.

## Manual non-production smoke test

Do not automate this procedure and use only non-sensitive synthetic transcript
data:

1. Create a restricted OpenAI project API key and make the selected model
   available to that project.
2. Inject `OPENAI_API_KEY` through the local/deployment secret mechanism. Do
   not place its value in a command, screenshot or shell history.
3. Set `AI_PROVIDER=openai`, `OPENAI_MODEL=gpt-5.6` (or another available model)
   and the bounded timeout/output settings.
4. Start the API, worker and web processes.
5. Create a meeting with a synthetic transcript and generate its Executive
   Summary or Decisions.
6. Verify the completed UI, provider/model/request trace and token usage using
   content-safe operational tooling.
7. Return `AI_PROVIDER` to `mock` and revoke/remove the temporary key when the
   check is complete.

No real OpenAI smoke test is part of the automated gate or this delivery.

## Deployment and rollback

Deploy the API and worker from the same immutable release. Provide the OpenAI
secret only to server-side processes that require it, apply outbound network
controls, and alert on safe rate-limit/authentication/timeout metrics. Production
customer-content use is an explicit operational gate; this code alone does not
approve it.

Rollback does not require a database migration: set `AI_PROVIDER=mock`, restart
the worker, confirm new jobs record the mock provider, then remove/revoke the
OpenAI secret where it is no longer required. Existing completed artefacts
retain their original provider/model trace.

## Known limitations

- Only Executive Summary, Decisions, Action Items and Risks & Blockers use the real adapter;
  infrastructure test and unknown job types are rejected before SDK
  invocation.
- There is no pricing source, budget enforcement or accurate cost estimate.
- There is no runtime provider/model UI or tenant-managed credential.
- The current transcript body is not an immutable historical snapshot.
- Provider privacy, residency, retention and contractual settings are
  deployment responsibilities and not proven by configuration alone.
- Production Clerk verification, consent evidence, deletion/export and
  operational controls remain incomplete; production customer data is
  prohibited.
