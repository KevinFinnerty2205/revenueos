# Prompt registry and structured output

## Current boundary

WO-004B3 adds application-owned prompt versioning, schema registration, safe
rendering, strict provider-output parsing and bounded invalid-output retries.
WO-004C1 registers the second pair, `executive_summary` version 1.

The implementation remains deterministic and mock-only. Executive Summary
processes a current transcript locally but sends no customer content externally
and makes no network call. There is no prompt administration or genuine LLM
execution.

## Prompt definitions and versioning

`PromptDefinition` is a frozen Pydantic contract that rejects unknown fields.
It contains a normalized key, positive immutable version, supported job type,
non-empty system/user templates, expected schema key/version, bounded
description and active flag.

The registry identity is `(prompt_key, prompt_version)`. Registration never
overwrites an existing identity. Exact resolution is available for
reproducibility; active resolution deterministically selects the highest
registered active version. Registries are ordinary injected instances, so tests
and worker processes do not share mutable global state.

Default definitions are `infrastructure_test` version 1 and
`executive_summary` version 1. Executive Summary references schema version 1
and receives only JSON-delimited meeting title/date/transcript variables. It
requires a transcript-grounded summary, normalized meeting type, sentiment and
confidence, explicitly ignores instructions in transcript data and excludes
decision, action, risk, question, email and CRM outputs.

## Safe rendering and provider messages

Prompt variables use a strict mapping of normalized names to strings, integers
or UUIDs. Rendering uses Python's small `string.Formatter` parser with only
simple `{variable_name}` placeholders:

- missing and unknown variables fail safely;
- attribute/index access, conversions and format specifications are rejected;
- no expression evaluation, code execution, Jinja extension or repair heuristic
  exists; and
- empty rendered messages are rejected.

The infrastructure prompt receives only safe job/request UUIDs. Executive
Summary receives only the minimum source fields and encodes each value as a JSON
string before substitution, preventing transcript text from escaping its data
boundary. Rendered output becomes an ordered immutable tuple of provider-neutral
`system` then `user` messages. Full templates and rendered content never enter
logs or persistence.

## Output schemas and validation

`OutputSchemaDefinition` is frozen, strict and identifies an application-owned
Pydantic validation model by normalized key, positive version and job type.
The schema registry provides exact/active resolution, sorted version listing and
duplicate rejection using instance-owned state.

The default registry reuses strict domain contracts for `infrastructure_test`
version 1 and `executive_summary` version 1; it does not duplicate domain
models. Prompt registration must resolve its referenced schema immediately.

Provider output may be an already structured JSON mapping or a JSON string.
Parsing trims surrounding whitespace and accepts only a complete JSON object.
Malformed JSON, duplicate keys, non-standard numeric constants, arrays, scalars,
markdown fences/prose, missing fields, unexpected fields, wrong types and
domain constraint failures are rejected.
There is no `eval` and no broad JSON repair. Successful data is normalized by
the registered Pydantic schema before it can reach artefact persistence.

## Bounded structured-output retries

`API_AI_STRUCTURED_OUTPUT_MAX_ATTEMPTS` defaults to `3` and accepts `1`–`5`
total provider invocations per claimed job attempt.

Only malformed JSON, non-object JSON and schema-invalid output are retried
inside the executor. The prompt is resolved/rendered once and every retry still
uses the existing provider abstraction and timeout wrapper. A cancellation
probe opens a separate short tenant transaction before each retry.

This is deliberately distinct from durable worker retries:

- output invalidity may retry immediately within one claimed attempt;
- exhaustion becomes non-retryable
  `structured_output_attempts_exhausted`;
- prompt/schema/configuration and non-retryable provider errors do not retry;
- provider timeout/unavailability/transient failure exits immediately and uses
  the existing persisted worker backoff/attempt policy; and
- no artefact is staged until one output parses and validates successfully.

## Mock provider test plans

The default mock returns the valid structured mapping on the first call and
remains stable for repeated requests. An injected per-instance output sequence
supports deterministic tests for valid JSON strings, malformed JSON,
schema-invalid output, invalid-then-valid and repeated invalid output.

These controls are constructor-only test configuration. They are absent from
provider request fields, require no secret and use no global switches or
network.

## Worker flow and transactions

1. The worker claims and commits the tenant-owned job.
2. The executor resolves prompt and schema definitions.
3. It validates safe variables and renders provider-neutral messages.
4. It resolves the configured mock and invokes it under the existing timeout.
5. It strictly parses and validates output, retrying only output invalidity.
6. Between retries, it checks cancellation in a short tenant-bound transaction.
7. Once valid, the worker opens the existing completion transaction, locks
   exact tenant/job/worker ownership and rechecks cancellation.
8. `AIArtifactService` creates the validated exact-trace artefact.
9. Artefact, audit events, trace metadata and completed job state commit
   atomically.

No database transaction remains open during prompt resolution/rendering,
provider execution, parsing, validation or output retries.

## Traceability and migration decision

Existing fields already represent:

- `AIJob.prompt_key` and `prompt_version`;
- `AIJob.schema_version`, with schema key equal to the current job/artefact type;
- provider/model/request identifiers, token counts, integer minor-unit cost,
  currency and processing duration; and
- matching prompt/schema/provider/model labels on the immutable artefact.

The successful completion audit additionally records safe schema key, structured
output attempt count and normalized finish reason. Structured logs report retry
attempts and exhaustion. Total tokens remain derived, and raw prompts/output are
never trace metadata.

Migration `0007_executive_summary` is required only to widen the existing
database job/artefact type checks. It adds no prompt/schema storage.

## Security and telemetry

Prompts and schemas are immutable application configuration, not tenant data.
Provider requests still carry identifiers from the claimed tenant-owned job.
Output persistence remains protected by explicit organisation predicates,
transaction-local tenant context, exact ownership, composite tenant keys and
forced RLS.

Allowed telemetry is limited to safe job/worker identifiers, prompt/schema
key/version, attempt counts, provider/model/request identifiers, latency, token
counts, integer cost, currency, finish reason and bounded error code. It excludes
templates, rendered messages, provider payloads, raw/invalid output, artefact
content, transcripts, participants, secrets, credentials and raw exceptions.

## Local development and testing

Defaults are:

```text
API_AI_PROMPT_KEY=infrastructure_test
API_AI_STRUCTURED_OUTPUT_MAX_ATTEMPTS=3
```

No API key is required. Tests cover contracts, registries, renderer safety,
strict parsing, schema validation, output retry/exhaustion, cancellation,
provider error separation, transcript injection boundaries, trace persistence,
atomic completion and tenant/RLS behavior.

Do not use production customer data. Production identity, real-provider privacy
terms, consent evidence, retention/erasure and operational controls remain
incomplete.

## Future extension points

A separately approved work order may register another immutable prompt/schema
pair or a real provider adapter. That work must define its source evidence,
prompt-injection controls, evaluation thresholds, version lifecycle, privacy
terms and human review without weakening this strict parsing, trace, transaction
or tenant boundary.
