# ADR 0009 — Versioned prompts and strict structured output

**Status:** Accepted

**Date:** 2026-07-18

## Context

WO-004B2 introduced a vendor-neutral provider response but the executor still
constructed no versioned prompt and directly validated a structured mapping.
WO-004B3 requires reproducible logical configuration and bounded handling of
malformed model output without adding a real provider, prompt database or AI
product surface.

## Decision

- Model prompt and output-schema definitions as frozen strict Pydantic
  application configuration.
- Identify definitions by immutable `(key, version)` pairs and reject duplicate
  registration.
- Resolve exact versions for reproduction and the highest active version for
  current execution.
- Require prompt registration to resolve its referenced schema.
- Render only simple named placeholders from validated scalar variables using
  `string.Formatter`; reject attribute/index access, conversions and format
  specifications.
- Represent rendered provider input as ordered immutable internal
  `system`/`user` messages.
- Accept only a structured mapping or complete JSON object string, with no
  markdown extraction, `eval` or broad repair.
- Normalize successful output through the registered Pydantic schema.
- Retry only malformed/non-object/schema-invalid output within a small bounded
  count in one claimed job attempt.
- Keep provider timeout/transient failures on the durable worker retry path.
- Probe cancellation in a separate short tenant transaction before each output
  retry and recheck again in the completion transaction.
- Reuse existing prompt/schema/provider trace columns and add attempt/schema-key
  trace only to content-free audit/log metadata; add no migration.
- Use per-instance deterministic mock output plans for tests, never global or
  request-controlled failure switches.

## Alternatives considered

- **Database-backed prompt administration:** rejected because no runtime
  administration, tenant customization or UI is authorized.
- **Jinja or an expression language:** rejected because simple scalar
  substitution is sufficient and a larger execution surface adds risk.
- **Provider-specific message objects:** rejected because SDK types must remain
  behind future adapters.
- **Accept markdown fences and repair JSON:** rejected because ambiguous repair
  can validate unintended content and hides provider quality failures.
- **Use durable job retries for every invalid output:** rejected because bounded
  correction attempts belong to one execution, while infrastructure failures
  require persisted backoff/recovery.
- **Retry every provider/configuration error inline:** rejected because
  configuration and permanent provider failures cannot become valid by
  repeating the same call.
- **Add prompt/schema/attempt columns:** rejected because current columns plus
  safe audit metadata provide essential traceability without duplicate schema.
- **Global mock failure flags:** rejected because they contaminate concurrent
  tests and can leak test controls into production behavior.

## Consequences

Positive:

- prompt/schema identity is reproducible and cannot be silently overwritten;
- provider output is never trusted before strict application validation;
- transient malformed output can recover without consuming a durable job
  attempt;
- retry and cancellation behavior remain bounded and observable; and
- prompt/output content remains outside logs and trace metadata.

Trade-offs:

- definitions are code-deployed rather than runtime-managed;
- active resolution uses the highest active version and has no activation UI;
- only one prompt/schema pair proves the abstractions today; and
- structured-output attempt count is audit/log trace, not a dedicated column.

## Follow-up triggers

Create or update an ADR before adding a real provider, customer/transcript
content to prompts, prompt activation workflows, database prompt storage,
experimentation/A-B testing, model-specific JSON modes, semantic repair,
additional intelligence schemas or an AI-facing API/UI.

## Related documents

- [Prompt registry and structured output](../03-engineering/prompt-registry-and-structured-output.md)
- [AI provider abstraction](../03-engineering/ai-provider-abstraction.md)
- [AI worker and durable job queue](../03-engineering/ai-worker-queue.md)
- [WO-004B3 sprint record](../07-sprints/wo-004b3-prompt-registry.md)
- [Security and privacy](../03-engineering/security-and-privacy.md)
