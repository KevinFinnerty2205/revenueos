# AI provider abstraction

## Current boundary

WO-004B2 added a provider-neutral execution seam and WO-004C1 now uses it for
both `infrastructure_test` and `executive_summary`. The only registered
implementation is `DeterministicMockAIProvider`. It requires no credentials and
performs no network calls. Executive Summary supplies the current bounded
transcript to this in-process mock, so customer content is processed locally
but never leaves the application.

There is no OpenAI, Anthropic, Gemini or other external provider adapter. There
is no provider configuration UI. The only AI product surface is the
meeting-scoped Executive Summary POST/GET API and Intelligence panel; see
[Executive Summary intelligence](executive-summary-intelligence.md).

## Contracts and interface

`AIProvider` exposes one asynchronous structured execution operation plus a
provider name and model identifier. Vendor SDK types cannot cross this
boundary.

`ProviderRequest` is a frozen Pydantic contract with:

- request, organisation and job identifiers;
- job type and model identifier;
- a strict job-specific input with exactly one ordered `system` then `user`
  provider-neutral message;
- expected artefact schema version; and
- a validated positive timeout.

Unknown fields are rejected. Infrastructure messages contain only fixed
instructions and safe identifiers. Executive Summary messages contain only its
registered instructions and JSON-delimited meeting title/date/transcript. They
never contain unrelated customer records, secrets or vendor objects.

`ProviderResponse` is also frozen and rejects unknown fields. It normalises the
provider/model/request identifiers, a JSON mapping or JSON string output,
non-negative input/output/
total token counts, non-negative integer minor-unit cost, three-letter currency,
non-negative provider latency and finish reason. Total tokens must equal input
plus output. The raw provider response is never persisted.

## Registry and configuration

`AIProviderRegistry` resolves a configured name and validates the configured
model against the selected provider. It owns no global mutable state. Unknown
providers and models fail closed with bounded, non-retryable errors.

| Environment variable | Default | Constraint |
| --- | --- | --- |
| `API_AI_PROVIDER_NAME` | `mock` | 1–100 lowercase name characters |
| `API_AI_PROVIDER_MODEL_IDENTIFIER` | `mock-infrastructure-v1` | 1–200 safe identifier characters |
| `API_AI_PROVIDER_TIMEOUT_SECONDS` | `10` | Greater than zero, at most 300 |

No API-key or provider-secret setting exists. Prompt and output-attempt settings
are documented separately because they belong to the executor, not provider
selection.

## Deterministic mock

The mock validates the job type, model and schema version and returns:

```json
{
  "status": "ok",
  "message": "AI processing infrastructure is operational."
}
```

Usage and cost are zero, currency is `AUD`, latency is deterministically zero
and the provider request identifier is a UUIDv5 derived only from safe request
and job identifiers. Repeating the same valid request returns the same response.
For `executive_summary`, the mock extracts the delimited transcript, excludes
obvious instruction-like injection sentences from its deterministic excerpt,
classifies small keyword-based meeting-type/sentiment enums and returns a fixed
confidence rule. The result is repeatable test output, not a quality claim or
fake external-provider implementation. Transcript and output bodies are never
logged. Usage, cost and network latency remain zero.

## Timeout and error model

Provider execution is wrapped by `asyncio.wait_for`. A timeout cancels the
provider coroutine and becomes retryable `provider_timeout`. Provider execution
occurs after the claim transaction commits and before the completion transaction
opens, so no database transaction waits on a provider.

Normalised retryable failures are timeout, temporary unavailability, transient
execution failure and an unexpected internal provider exception. Normalised
non-retryable failures are invalid request, unsupported provider, unsupported
model, invalid configuration and malformed provider output. Only bounded codes
and safe messages reach worker persistence or audits. Raw exception text can be
chained in memory but is not logged, stored or audited.

## Worker flow and persistence

1. The worker claims a tenant-owned job and commits the short claim transaction.
2. The job-specific executor resolves and safely renders the selected
   prompt/schema pair; Executive Summary first loads its exact current tenant
   transcript through a short worker transaction.
3. It creates a validated provider request with ordered messages.
4. The registry resolves `mock` / `mock-infrastructure-v1`.
5. The timeout wrapper executes and validates the provider response.
6. The executor strictly parses and validates `output_payload`, retrying only
   bounded output invalidity within this execution.
7. The worker opens a new tenant-bound transaction, locks the owned running job
   and rechecks cancellation.
8. Existing `AIJob` fields receive prompt/schema/provider/model/request trace,
   zero
   token usage, zero cost and `AUD`.
9. `AIArtifactService` creates the exact-trace artefact and copies the prompt,
   schema, provider and model labels.
10. Artefact, audit events and completed job state commit atomically.

`processing_duration_ms` remains the existing total worker execution duration.
Provider latency and derived total tokens are emitted as safe structured
telemetry; no duplicate columns were needed. Migration
`0007_executive_summary` widens only database job/artefact type checks.

## Tenant isolation and telemetry

The request carries identifiers copied from the claimed job; it cannot query the
database. Persistence still uses the claimed organisation, explicit repository
predicates, transaction-local tenant context, forced RLS and composite tenant
keys. A mismatched organisation cannot lock the owned job or persist an
artefact.

Logs contain only safe identifiers, provider/model labels, request identifier,
latency, token counts, integer cost, currency, finish reason, bounded error code
and retryability. Logs never contain input/output payloads, artefact content,
transcripts, prompts, participants, secrets, credentials or raw exceptions.

## Local development and tests

The defaults run without paid services or credentials:

```bash
pnpm dev:worker
```

Provider tests cover strict contracts, deterministic/no-network behaviour,
registry selection, safe configuration, timeout cancellation and provider
retry classification. Prompt/output tests cover safe rendering, strict JSON
and schema validation, bounded output retry/exhaustion and cancellation. Worker
integration tests cover atomic
artefact completion, metadata persistence, retries, timeout, terminal provider
failure, cancellation, leases/recovery, tenant isolation and safe audits.
PostgreSQL RLS tests remain authoritative for the forced-RLS boundary.

Do not use production customer data. Production identity, provider privacy
terms, consent evidence, retention/erasure and operational controls are not
complete.

## Future extension points

A separately approved work order may register a real adapter that implements
`AIProvider`. That work must add provider-specific secret management, privacy/
retention review, network controls and deterministic contract tests without
leaking SDK types into executors. Additional schemas, model-specific JSON modes
and genuine external-model output remain separate decisions.
