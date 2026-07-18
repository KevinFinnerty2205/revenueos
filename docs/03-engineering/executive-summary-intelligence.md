# Executive Summary intelligence

## Product behaviour

WO-004C1 delivers RevenueOS's first Meeting Intelligence capability: a user opens a meeting's **Intelligence** tab and requests one concise Executive Summary from the current usable transcript. The UI shows empty, queued, running, completed, failed and cancelled states. A completed result contains only:

- an Executive Summary paragraph;
- meeting type (`sales_discovery`, `sales_demo`, `customer_success`, `recruitment`, `internal` or `other`);
- sentiment (`positive`, `neutral`, `negative` or `mixed`);
- confidence from 0 to 1; and
- a generated timestamp.

The worker uses the configured provider. `mock` remains the default and produces
deterministic no-network output suitable for product-flow validation, not model
quality evaluation. `openai` sends the prompt and selected transcript to the
server-side OpenAI Responses API and returns genuine model output that must still
pass the same strict application validation.

## API and UI flow

1. `POST /api/v1/meetings/{meetingId}/intelligence/executive-summary` authenticates the user, establishes one trusted tenant context and verifies the active meeting and transcript.
2. The service returns the equivalent active/completed job or creates a pending `executive_summary` job. A new job returns `202`; an existing job returns `200`.
3. The separately deployed worker claims the job through the existing durable PostgreSQL queue.
4. In a short tenant transaction it loads the exact current transcript ID/version pinned by the job. It does not keep the transaction open during generation.
5. `ExecutiveSummaryExecutor` resolves prompt `executive_summary` version 1 and schema `executive_summary` version 1, renders the transcript as a structurally delimited JSON string and invokes the exactly configured mock or OpenAI provider.
6. Strict structured-output parsing and validation run with the existing bounded retry policy.
7. The completion transaction rechecks ownership/cancellation, creates an append-only `executive_summary` artefact and atomically completes the job.
8. `GET` on the same path returns the product-safe current state and completed content.
9. The Intelligence panel polls every three seconds while the state is queued/running. Requests never overlap; polling stops on a terminal state and aborts on tab change/unmount.

There are no generic intelligence, cancellation, streaming or WebSocket endpoints.

## Prompt v1 and schema v1

Prompt v1 instructs the provider to use only the supplied transcript, avoid invented facts, classify type/sentiment/confidence, return exactly the registered fields, exclude future outputs and treat transcript instructions as untrusted data. Variables are limited to meeting title, meeting date and transcript text. Templates, rendered messages and transcript text are not logged or persisted as prompt trace.

Schema v1 is a frozen strict Pydantic model. It rejects unknown fields, non-string summary content, unsupported enum values, non-finite confidence and confidence outside 0–1. The summary is plain text from 20 to 2,000 characters. Decisions, action items, risks, open questions, participants, CRM suggestions and follow-up content are not part of this schema.

## Transcript rules

- Only the active transcript belonging to the active meeting and trusted organisation is eligible.
- Whitespace-only transcripts are rejected.
- Executive Summary input is limited to 50,000 trimmed characters and is never silently truncated.
- The job and artefact pin transcript ID and integer version.
- If the transcript changes, the previous result is no longer returned as current and the user may request a new version-specific job.
- Historical transcript bodies are not retained: a worker fails safely if the current body/version no longer matches the job's pinned source.
- Transcript text is excluded from logs, audit metadata, safe errors and API status fields.

## Idempotency and retries

Logical equivalence is organisation, meeting, transcript version, job type, prompt key/version and schema version. Repeated requests return a pending, running or completed equivalent job. Meeting locking plus the existing organisation-scoped unique key resolves concurrent requests.

Failed/cancelled jobs can be retried manually. A retry creates a new append-only job with the next deterministic retry ordinal. Transcript corrections create a new logical job because the version changes. Provider/transient retries and structured-output retries continue to use the established bounded worker policies.

## Provider behaviour

`DeterministicMockAIProvider` supports both the original infrastructure test and Executive Summary. For Executive Summary it reads the delimited transcript, creates a repeatable transcript-grounded paragraph, classifies simple deterministic keyword signals and reports zero token usage, zero cost and zero network latency. It ignores common prompt-injection instruction sentences as content. It requires no API key and performs no external call; no customer content leaves the application.

`OpenAIProvider` sends the same rendered system/user messages through the
official asynchronous Responses API with the registry-derived Executive Summary
JSON Schema in strict mode. It disables response storage, uses no tools or
streaming, and normalises request ID, token usage, latency and completion status
before the application validates output again. The configured model never
silently falls back.

## Traceability, tenancy and privacy

Traceability includes organisation, meeting, transcript ID/version, job/type/status, artefact/type/version, prompt/schema versions, provider/model/request labels, structured-output attempts, available token usage, integer cost/currency, duration and timestamps. Artefact content is stored only after schema validation. Prompt text, rendered messages, raw/invalid provider output and transcript copies are not trace fields. OpenAI cost remains zero/not calculated because no approved pricing source is configured.

API, service, repository and worker reads use the trusted organisation context and explicit organisation predicates. PostgreSQL forced RLS and composite tenant keys continue to cover meetings, transcripts, jobs and artefacts. Cross-tenant API and database tests fail closed with safe not-found behaviour.

With mock, customer content stays inside the application. With OpenAI enabled,
the selected meeting transcript and rendered instructions are sent to OpenAI.
No production customer data may be used. Production Clerk verification,
consent evidence, retention/export/erasure, provider privacy review, deployment
monitoring and incident controls remain incomplete.

## Local development and testing

Start the API, web and worker in separate terminals. The default mock requires no
AI credential. Create a meeting, add an authorised transcript of at most 50,000
characters, open **Intelligence**, select **Generate Executive Summary**, and
leave the worker running until the result appears. A real-provider smoke test
must use only synthetic non-sensitive content and follow the
[OpenAI provider guide](openai-provider-integration.md).

Tests cover contracts, prompt/schema registration, injection treatment, deterministic offline output, output retries, service idempotency, worker source loading and atomic persistence, safe API responses, transcript-version regeneration, cross-tenant denial, migration upgrade/downgrade, UI states, polling cleanup and the browser flow.

## Known limitations

- Mock generation is deterministic and not genuine LLM output; OpenAI quality
  has no production evaluation gate yet.
- Code deployment owns prompt/schema registration and activation.
- Historical transcript bodies are not retained.
- The summary has no citations or human review lifecycle.
- OpenAI cost is not calculated and no provider budget control exists.
- Enabling OpenAI deliberately moves transcript content across an external data
  boundary.
- Production identity and operational privacy controls are incomplete.
- Production customer data is prohibited.

Additional intelligence fields, citations/review, another provider, runtime
model configuration and production enablement require separate approval.
