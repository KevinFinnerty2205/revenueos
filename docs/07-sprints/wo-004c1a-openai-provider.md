# WO-004C1A — Production OpenAI Provider Integration

## Objective

Run the existing Executive Summary vertical slice through either the
deterministic mock or a server-side OpenAI Responses API adapter without
changing its API/UI contract or adding another intelligence capability.

## Delivered

- official OpenAI Python SDK dependency and lockfile update;
- server-only asynchronous Responses API adapter;
- registry-derived strict JSON Schema output with the application Pydantic
  validator remaining authoritative;
- `mock`/`openai` configuration selection with mock as the default;
- lazy OpenAI provider construction and dependency-injected transport seam;
- configurable model, timeout and maximum output tokens;
- normalised completion/request ID, usage, latency and finish metadata;
- safe retryable/non-retryable OpenAI error classification;
- pre-provider cancellation check plus existing completion-time cancellation
  recheck;
- deterministic SDK fakes and worker integration coverage with no network call;
- frontend secret-surface, log, audit, API-response and persistence checks; and
- architecture, provider, worker, development, deployment, security, roadmap
  and decision documentation.

## Database

No migration was required. Existing AI job and artefact fields represent
provider, model, request ID, token counts, integer cost/currency and exact
prompt/schema trace. Provider latency and finish status remain metadata-only
telemetry under the existing convention.

## Security and privacy

The key is server-only, secret-typed, required only when OpenAI is selected and
absent from frontend variables, safe configuration, API responses, database
rows, audits and logs. Prompt/transcript/model output bodies and raw SDK
exceptions are excluded from telemetry. Tenant predicates, forced RLS,
transcript-version pinning, durable queue ownership and atomic
artefact-before-completion behaviour are unchanged.

Enabling OpenAI changes the data-flow boundary and sends the selected transcript
to OpenAI. Production customer data remains prohibited until production
identity, consent, retention/deletion, provider privacy and operational controls
are approved.

## Usage and cost

Input/output token counts and provider request trace are stored when returned.
Estimated cost remains `0 AUD`, meaning not calculated, because no reliable
versioned pricing source is configured.

## Validation

Automated tests use SDK response fakes and dependency injection; no test calls
the real OpenAI API. The complete repository, PostgreSQL/RLS, migration, browser,
build, audit, secret and scope gates are required before hand-off.

## Explicitly out of scope

No additional intelligence type, provider settings UI, browser key, tenant
credential, model listing/selector, Anthropic, Gemini, Azure OpenAI, recording,
transcription, embedding, vector search, integration, billing, notification,
agent, streaming, WebSocket or alternate queue was added.

## Known limitations

- Real-provider quality and availability are not established by deterministic
  tests.
- No cost estimate, tenant budget or provider configuration UI exists.
- Model availability depends on the configured OpenAI project and never falls
  back silently.
- Production customer-content use is not approved.

See [OpenAI provider integration](../03-engineering/openai-provider-integration.md)
and [ADR 0011](../08-decisions/0011-server-side-openai-responses-provider.md).
