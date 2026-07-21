# AI provider abstraction

## Current boundary

The provider-neutral seam supports two implementations:

- `DeterministicMockAIProvider`, the default offline provider for local
  development, tests and demos; and
- `OpenAIProvider`, a server-only adapter using the official asynchronous Python
  SDK and Responses API.

Together they support the existing `infrastructure_test`, `executive_summary`,
`decisions`, `action_items`, `risks_blockers`, `open_questions`, `buying_signals`,
`objections_competitive_signals` and
`follow_up_email` contracts where explicitly allowed. Executive Summary,
Buying Signals, Objections & Competitive Signals, Decisions, Action Items,
Risks & Blockers, Open Questions and Follow-up Email
are the only customer-facing AI capabilities. There is no provider UI, tenant-
managed credential, additional vendor, tool use, streaming or automatic
provider fallback.

Selecting OpenAI sends the rendered Executive Summary, Buying Signals,
Objections & Competitive Signals, Decisions, Action Items,
Risks & Blockers or Open Questions prompt and bounded meeting transcript to
OpenAI. Follow-up Email sends only the validated Executive Summary, Decisions,
Action Items and Open Questions projection plus tone; its typed provider input
has no transcript field. The default mock makes no network call. See
[OpenAI provider integration](openai-provider-integration.md) for the external
data boundary and operating guide.

## Contracts and interface

`AIProvider` exposes one asynchronous structured execution operation plus a
provider name and model identifier. Vendor SDK types cannot cross this boundary.

`ProviderRequest` is a frozen Pydantic contract containing:

- request, organisation and job identifiers;
- job type and configured model identifier;
- a job-specific input with exactly one ordered `system` then `user` message;
- expected artefact schema version;
- the registry-derived strict JSON Schema and matching schema identity; and
- a validated positive timeout.

The output schema must be a closed top-level object with explicit required
properties. The schema version must match the expected application schema.

`ProviderResponse` normalises provider/model/request identifiers, output payload,
input/output/total tokens, non-negative integer cost and currency, latency and
finish status. Unknown fields are rejected and total tokens must equal input
plus output. Raw provider responses never leave an adapter or enter persistence.

## Registry and configuration

`AIProviderRegistry` is instance-owned and dependency-injection friendly. With
ordinary settings it creates only the selected provider. Mock selection never
constructs an SDK client and requires no OpenAI key. Unknown providers and
models fail closed; there is no model fallback.

| Environment variable | Default | Constraint |
| --- | --- | --- |
| `AI_PROVIDER` | `mock` | `mock` or `openai` |
| `API_AI_PROVIDER_MODEL_IDENTIFIER` | `mock-infrastructure-v1` | Mock model; 1–200 safe identifier characters |
| `API_AI_PROVIDER_TIMEOUT_SECONDS` | `10` | Mock timeout; greater than zero, at most 300 |
| `OPENAI_API_KEY` | empty | Server-only; required only for `openai` |
| `OPENAI_MODEL` | empty | Required for `openai`; 1–200 safe identifier characters |
| `OPENAI_TIMEOUT_SECONDS` | `30` | Greater than zero, at most 300 |
| `OPENAI_MAX_OUTPUT_TOKENS` | `4096` | 256–32,768 |

`Settings.safe_ai_configuration()` contains only provider/model/bounds and an
external-transmission flag. It never returns the key.

## Deterministic mock

The mock produces repeatable validated output with zero token usage, zero cost
and zero latency. For Executive Summary it derives a bounded excerpt and simple
keyword-based classifications. For Decisions it deterministically recognises
explicit agreement/rejection/deferral markers. For Action Items it recognises
explicit future commitments, applies the narrow meeting-date calendar and
returns nullable owner/date fields or a valid empty list. For Risks & Blockers
it recognises narrow transcript-grounded obstacles, normalises category and
qualitative severity, supports nullable owners and excludes question-,
decision- and action-only text. All exclude obvious instruction-like transcript
sentences and never perform a network request. This is test output, not a
quality claim or substitute for a genuine LLM evaluation.

For Open Questions the mock recognises narrow unresolved-question markers,
excludes answered-later, rhetorical, conversational, action-request, risk-only
and decision-only fixtures, normalises importance and supports nullable owners
or an empty list.

For Buying Signals the mock recognises a bounded set of explicit commercial
markers, returns paraphrased evidence and deterministic qualitative momentum,
and emits `insufficient_evidence` for unsupported or merely polite transcript
language. It makes no prediction or scoring claim.

For Objections & Competitive Signals the mock recognises bounded resistance and
competitor markers, distinguishes question/risk/politeness-only fixtures,
normalises handling state and competitive position, and returns empty lists
when unsupported. It makes no prediction, ranking or scoring claim.

For Follow-up Email the mock copies the validated customer-safe source fields
exactly, applies stable generic framing for each of the three tones and never
accepts transcript or Risks & Blockers input.

## OpenAI adapter

`OpenAIProvider` maps provider-neutral messages to `responses.create`, supplies
the registered schema through strict `json_schema` text format and sets
`store=false`. It uses no tools, streaming or reasoning configuration. The
adapter captures the public request ID, available usage counts, latency and a
safe completed status. The application parser validates the returned JSON again
against the registered Pydantic schema.

The model is configured by `OPENAI_MODEL`; documentation uses `gpt-5.6` only as
an example where the OpenAI project has access. The adapter never silently
selects another model.

## Timeout, retry and error model

Provider execution occurs after the claim transaction commits and before the
completion transaction opens. Cancellation is checked before each provider call
and again under the completion lock. The executor retains its bounded
structured-output retry for malformed/schema-invalid output.

The OpenAI SDK transport retry count is zero. Durable worker attempts own retry
and backoff:

- retryable: timeout, rate limit, connection/transient failure and
  server/service unavailability;
- non-retryable: authentication, permission, unavailable configured model,
  invalid request/configuration, refusal, incomplete or malformed response.

Only stable safe error codes/messages reach persistence or audit metadata. Raw
SDK exception text, provider bodies and credentials are neither logged nor
stored.

## Worker flow and persistence

1. Claim and commit a tenant-owned job.
2. Resolve the job prompt/schema and load the exact pinned transcript for an
   extractor or four validated artefacts for Follow-up Email in a short tenant
   transaction.
3. Build the validated provider request with the registry-derived schema.
4. Resolve exactly the configured provider/model.
5. Execute without an open database transaction.
6. Strictly parse and validate output.
7. Re-enter the claimed tenant context, lock the owned job and recheck
   cancellation.
8. Atomically persist the validated artefact, safe trace/audits and completed
   job state.

Existing job/artefact columns store provider, model, request ID, token counts,
integer cost/currency and prompt/schema trace. No WO-004C1A migration is needed.
Provider latency and finish status remain metadata-only telemetry.

Estimated OpenAI cost is stored as `0 AUD` under the existing convention because
there is no approved versioned pricing source. It means not calculated, not
free.

## Tenant isolation and telemetry

Provider requests copy tenant/job identifiers from the claimed job and cannot
query persistence. Every worker database transaction resets the trusted tenant
context and retains explicit organisation predicates, composite tenant keys and
forced RLS. Provider selection does not change these boundaries.

Logs may contain opaque organisation/job IDs, provider/model/schema labels,
provider request ID, latency, tokens, finish status and safe error
classification. They exclude API keys, headers, prompt/transcript/participant
content, rendered input, raw/validated output, artefact content and raw
exceptions.

## Tests and limitations

All automated provider tests use dependency-injected SDK-shaped fakes and make
no real OpenAI call. Coverage includes the explicit customer-capability
allowlist, rejection of infrastructure/unknown work before SDK invocation,
configuration, lazy registry selection, strict request mapping,
response/usage mapping, safe errors, durable worker
retry behaviour, trace persistence and content/secret redaction. Mock
regressions, tenant/API/RLS, migration, UI and browser gates remain unchanged.

Production customer data is prohibited. Production identity, consent,
retention/deletion, provider privacy/residency, cost controls and operational
readiness remain incomplete.
