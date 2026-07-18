# ADR 0011 — Server-side OpenAI Responses provider

**Status:** Accepted

**Date:** 2026-07-18

## Context

WO-004C1 proved the Executive Summary lifecycle using a deterministic mock.
WO-004C1A requires the same durable job to support a real external provider
without leaking vendor SDK types into domain code, exposing credentials to the
browser or changing the product surface.

## Decision

- Add one `openai` adapter behind the existing `AIProvider` port using the
  official asynchronous Python SDK and Responses API.
- Keep `mock` as the default and construct OpenAI only when explicitly selected.
- Configure provider, key, model, timeout and maximum output tokens in the
  server environment; do not add tenant/database/browser configuration.
- Generate the strict provider JSON Schema directly from the registered
  Pydantic schema and keep application validation authoritative.
- Disable provider response storage, tools, streaming and SDK retries.
- Normalise SDK responses/errors before they reach the executor, worker or
  persistence layer.
- Let the durable PostgreSQL worker remain the only retry/lease/idempotency
  authority.
- Record available provider/model/request/token trace in existing fields; keep
  latency/finish in content-free telemetry and record cost as zero/not
  calculated until an approved pricing source exists.
- Preserve content-redacted logs, forced RLS, short transactions, cancellation
  checks and atomic artefact-before-completion.
- Require an explicit production privacy/identity/consent/retention operations
  gate before sending customer content externally.

## Consequences

The existing API and UI can use genuine model output when server configuration
selects OpenAI, while local development and all tests remain deterministic and
offline. Model access is operator-controlled and fails instead of silently
falling back. Enabling OpenAI deliberately moves the selected transcript across
an external data boundary.

No migration is required. Cost remains unavailable in practical terms even
though the existing non-null convention stores zero. Provider-specific
residency, retention, contractual configuration, budget controls and model
quality evaluation remain deployment/product gates.

## Alternatives considered

- **Call OpenAI from the executor:** rejected because SDK types and error
  semantics would leak into domain orchestration.
- **Browser-side call/key:** rejected because it exposes a service credential
  and bypasses worker/tenant controls.
- **SDK automatic retries:** rejected because it would create a second retry
  authority outside durable job attempts.
- **Maintain a separate OpenAI schema:** rejected because it could drift from
  the application contract.
- **Hard-code a model or automatic fallback:** rejected because project model
  access varies and fallback obscures behaviour.
- **Hard-code current pricing:** rejected because it becomes stale and is not
  an approved billing source.

## Follow-up triggers

Revisit before tenant-managed providers, another vendor, model selection UI,
reasoning controls, pricing/budgets, streaming, tools, another intelligence
schema or production customer-content enablement.

## Related documents

- [OpenAI provider integration](../03-engineering/openai-provider-integration.md)
- [AI provider abstraction](../03-engineering/ai-provider-abstraction.md)
- [Executive Summary intelligence](../03-engineering/executive-summary-intelligence.md)
- [WO-004C1A sprint record](../07-sprints/wo-004c1a-openai-provider.md)
- [Security and privacy](../03-engineering/security-and-privacy.md)
