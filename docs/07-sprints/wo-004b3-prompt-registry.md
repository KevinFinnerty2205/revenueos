# WO-004B3 — Prompt Registry and Structured Output Validation

## Objective

Add versioned application prompt/schema configuration and strict, bounded output
validation to the merged deterministic provider worker without introducing a
real provider or genuine Meeting Intelligence.

## Delivered

- strict frozen prompt definitions and exact/active version registry;
- duplicate prevention and prompt-to-schema registration validation;
- scalar-only safe prompt variables and deterministic no-evaluation rendering;
- ordered immutable provider-neutral system/user messages;
- strict frozen output-schema definitions and exact/active schema registry;
- reuse of the existing infrastructure-test Pydantic artefact model;
- JSON object parsing with no markdown extraction or broad repair;
- normalized schema validation and bounded safe errors;
- configurable within-attempt invalid-output retries;
- short tenant-bound cancellation checks between output retries;
- deterministic per-instance mock output sequences for failure tests;
- existing-field prompt/schema/provider traceability plus metadata-only audit
  attempt trace;
- expanded content-safe structured telemetry;
- a workspace-level PostCSS 8.5.19 transitive override after the validation
  audit identified a moderate advisory in Next.js's pinned dependency;
- prompt, schema, parser, retry, worker, tenant and regression tests; and
- architecture, AI, worker, provider, security, development, roadmap and ADR
  documentation.

## Database and migration

No migration was required. Existing job and artefact prompt key/version and
schema-version fields represent the logical configuration. The current schema
key is the `infrastructure_test` job/artefact type. Existing provider, model,
request, usage, cost, currency and duration fields remain authoritative.
Successful completion audit metadata records the structured-output attempt
count, schema key and finish reason without content.

## Retry behavior

Malformed JSON, non-object JSON and schema-invalid output retry up to
`API_AI_STRUCTURED_OUTPUT_MAX_ATTEMPTS` within one claimed job attempt. Output
exhaustion is a safe non-retryable job failure. Prompt/schema/configuration and
non-retryable provider errors are not retried. Provider timeout/unavailability/
transient errors continue through the existing durable worker retry path.

## Security and tenancy

Prompts/schemas are application configuration. The mock receives only rendered
constant instructions plus safe job/request identifiers; it receives no
transcript/customer content and makes no network call. Rendering and provider/
parse/retry work happens outside database transactions. Completion preserves
the claimed organisation, explicit predicates, exact ownership, forced RLS,
composite tenant keys, cancellation recheck and artefact-before-completion
atomicity.

Templates, rendered prompts, provider payloads, raw/invalid output, artefact
content, transcripts, participant data, secrets and raw exceptions are excluded
from logs, audits and failure metadata.

## Validation

The full repository gate covers Ruff, formatting, mypy, Pytest, PostgreSQL 16
migrations/RLS/worker behavior, Alembic drift, web lint/type/unit/browser tests,
production builds and the repository secret/scope audit. CI remains
authoritative for PostgreSQL-only tests.

## Explicitly out of scope

No OpenAI, Anthropic, Gemini or other real provider; external network call;
credential/secret management; prompt database/editor/experiment/A-B UI; AI API/
UI/polling; summary; decision; action; risk; question; email; CRM/integration;
recording; transcription; embedding; vector search; memory; relationship graph;
notification; billing; autonomous agent; Redis; Celery; Kafka or RabbitMQ was
added.

## Known limitations

- Only `infrastructure_test` prompt/schema version `1` exists.
- Active version resolution is application configuration, not tenant/user
  administration.
- The mock tests execution contracts, not AI quality.
- No real-provider privacy, residency, retention, rate-limit or billing behavior
  has been evaluated.
- Production customer data remains prohibited.

See [prompt and structured-output architecture](../03-engineering/prompt-registry-and-structured-output.md)
and [ADR 0009](../08-decisions/0009-versioned-prompts-and-strict-output.md).
