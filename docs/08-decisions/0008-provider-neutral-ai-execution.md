# ADR 0008 — Provider-neutral AI execution

**Status:** Accepted

**Date:** 2026-07-18

## Context

WO-004B1 established durable tenant-safe job execution but deliberately
hard-coded the deterministic infrastructure-test result inside its executor.
WO-004B2 needs a stable seam for later provider adapters without adding a real
provider, prompt system, customer-content processing or a new queue.

## Decision

- Define one asynchronous `AIProvider.execute` protocol using internal frozen
  Pydantic request/response contracts.
- Keep vendor SDK types entirely inside future adapter implementations.
- Resolve providers through an instance-owned registry using validated
  environment configuration.
- Register only a deterministic, zero-network `mock` provider and exact
  `mock-infrastructure-v1` model.
- Wrap provider calls in a bounded timeout and normalise every failure into a
  retryable or non-retryable safe provider error.
- Perform provider execution after the claim transaction and before the
  completion transaction.
- Validate the normalised output again with the domain artefact schema.
- Reuse existing AI job/artefact provider, model, request, usage, cost, currency
  and processing-duration fields; add no migration.
- Log metadata only and keep all provider input/output content out of telemetry
  and audits.
- Preserve PostgreSQL queue ownership, cancellation recheck, forced RLS and
  artefact-before-completion atomicity.

## Alternatives considered

- **Call a vendor SDK from the executor:** rejected because domain execution
  would become vendor-coupled and difficult to test deterministically.
- **Add OpenAI/Anthropic placeholders now:** rejected because unused adapters,
  credentials and SDKs would imply unsupported production capability.
- **One provider method per future AI task:** rejected as speculative surface
  area; one structured operation is sufficient.
- **Persist raw provider responses:** rejected because they are unstable,
  vendor-specific and may contain sensitive content.
- **Hold the database transaction during provider execution:** rejected because
  network latency must not extend locks or tenant-bound transactions.
- **Add total-token and provider-latency columns:** rejected because total usage
  is derivable, provider latency is currently telemetry, and existing trace
  fields satisfy this work order.
- **Use a global mutable provider singleton:** rejected because explicit registry
  instances are safer to configure and replace in tests.

## Consequences

Positive:

- executors and worker lifecycle remain vendor-neutral;
- deterministic tests require no network or credentials;
- retry policy consumes a single normalised provider classification;
- no raw vendor objects enter persistence; and
- future adapters have a narrow extension point.

Trade-offs:

- the current interface has been proven only by the infrastructure mock;
- provider latency is logged rather than stored separately;
- model selection is process configuration, not tenant/user configuration; and
- real-provider privacy, secret, residency, rate-limit and cost policies remain
  unresolved.

## Follow-up triggers

Create or update an ADR before adding a real provider, provider credentials,
tenant/model routing, prompt registry/versioning, structured-output retries,
customer-content transmission, provider-specific retention settings or an
AI-facing API/UI.

## Related documents

- [AI provider abstraction](../03-engineering/ai-provider-abstraction.md)
- [ADR 0009: versioned prompts and strict structured output](0009-versioned-prompts-and-strict-output.md)
- [AI worker and durable job queue](../03-engineering/ai-worker-queue.md)
- [WO-004B2 sprint record](../07-sprints/wo-004b2-ai-provider-abstraction.md)
- [Security and privacy](../03-engineering/security-and-privacy.md)
