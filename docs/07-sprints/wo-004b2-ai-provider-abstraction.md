# WO-004B2 — AI Provider Abstraction and Deterministic Mock Provider

## Objective

Add a vendor-neutral, typed provider boundary to the merged durable worker and
route the existing `infrastructure_test` execution through a deterministic
no-network provider.

## Delivered

- frozen, strict provider request and response contracts;
- a small asynchronous `AIProvider` protocol with no vendor SDK types;
- deterministic `mock` / `mock-infrastructure-v1` execution;
- explicit provider registry and environment-backed selection;
- validated bounded timeouts with coroutine cancellation;
- normalised retryable and non-retryable provider errors;
- metadata-only provider selection, latency, usage, cost and finish telemetry;
- provider/model/request/usage/cost persistence through existing AI job fields;
- existing strict infrastructure-test artefact validation and atomic completion;
- provider contract, deterministic, timeout, error, worker and tenant tests; and
- architecture, security, development, roadmap and ADR updates.

## Database and migration

No migration was required. `AIJob` already provides `provider_key`,
`model_name`, `provider_request_id`, input/output token counts, integer estimated
cost, currency and total processing duration. `AIArtifact` already provides
provider/model labels, copied by `AIArtifactService`.

Total tokens are derived from the two persisted token counts. Provider latency
is structured telemetry while `processing_duration_ms` remains end-to-end worker
duration. Adding duplicate columns would not improve essential traceability.

## Security and tenancy

The mock receives only safe claim identifiers and the literal infrastructure
operation. It does not receive transcript/customer content, use the network or
require a secret. Provider work occurs outside database transactions.
Completion re-enters the claimed organisation context, uses an explicit tenant
predicate and forced RLS, rechecks lease ownership/cancellation and commits the
validated artefact before marking the job complete.

Safe errors contain bounded codes/messages; raw exceptions, provider payloads,
transcripts, artefact content, prompts, participant data and credentials are not
logged, persisted or audited.

## Validation

The repository gate covers Ruff, formatting, mypy, Pytest, PostgreSQL 16
migrations/RLS/worker behaviour, Alembic drift, web lint/type/unit/browser tests,
production builds and the repository secret/scope audit. CI is authoritative
for the clean checkout and PostgreSQL service.

## Explicitly out of scope

No OpenAI, Anthropic, Gemini or other real provider; real credential; secret
storage; prompt registry/template/version; model-specific JSON mode;
structured-output retry loop; AI API/UI/polling; summary; decision; action;
risk; question; email; CRM/integration; recording; transcription; embedding;
vector search; memory; notification; billing; autonomous agent; Redis; Celery;
Kafka or RabbitMQ was added.

## Known limitations

- The mock proves infrastructure contracts, not model quality or genuine AI.
- There is no user/operator provider selection or lifecycle surface.
- Only `infrastructure_test` is routed through the provider boundary.
- No external provider privacy, residency, retention, rate-limit or billing
  behaviour has been evaluated.
- Production customer data remains prohibited until production identity and
  operational privacy controls are complete.

See [provider architecture](../03-engineering/ai-provider-abstraction.md) and
[ADR 0008](../08-decisions/0008-provider-neutral-ai-execution.md).
