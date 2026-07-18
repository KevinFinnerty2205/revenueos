# ADR 0010 — Current-transcript Executive Summary execution

**Status:** Accepted

**Date:** 2026-07-18

## Context

The AI foundation can durably execute strictly validated mock work but had no customer-facing capability. WO-004C1 requires one Executive Summary from the current transcript without introducing a real provider, historical transcript snapshots or future intelligence outputs.

## Decision

- Reuse `AIJob`, `AIArtifact`, the durable worker, provider port and prompt/schema registries.
- Add only `executive_summary` to existing database type constraints.
- Pin jobs and artefacts to the current transcript ID/version and reject execution if that current source no longer matches.
- Limit input to 50,000 trimmed characters with no silent truncation.
- Treat transcript/title as JSON-delimited untrusted prompt data and prohibit transcript/rendered-prompt logging.
- Define immutable prompt v1 and strict schema v1 with only summary, meeting type, sentiment and confidence.
- Keep the provider deterministic, mock-only, zero-network and zero-cost.
- Define idempotency over tenant, meeting, transcript version, job type, prompt version and schema version; allow a new ordinal job only after failure/cancellation or transcript change.
- Expose one meeting-scoped POST/GET resource and poll at a non-overlapping three-second interval while active.
- Return only product-safe lifecycle timestamps/errors and completed schema content.

## Consequences

The complete UI/API/worker/persistence flow can be evaluated without external data transfer or credentials. Existing transaction, retry, cancellation, audit and tenant controls remain authoritative. A minimal migration is required because database checks previously accepted only the infrastructure test.

The result is not evidence of real-model quality. The current mutable transcript row means historical source bodies cannot be reconstructed; a changed source requires new generation and can make an unprocessed old job fail safely. Prompt/schema activation remains code-deployed.

## Alternatives considered

- **Generate synchronously in FastAPI:** rejected because AI work belongs on the durable worker.
- **Store a transcript copy on each job:** rejected because source snapshot storage is outside WO-004C1.
- **Silently truncate long transcripts:** rejected because it obscures source coverage.
- **Return generic job/artefact contracts:** rejected because the UI needs only one bounded product-safe capability.
- **Add all future intelligence fields/cards:** rejected as Sprint 4C2+ scope.
- **WebSockets or streaming:** rejected because short polling is sufficient for this capability.

## Follow-up triggers

Revisit this decision before retaining transcript snapshots, adding a real provider, changing the input limit, introducing citations/review, enabling runtime prompt administration, or adding another intelligence schema.

## Related documents

- [Executive Summary intelligence](../03-engineering/executive-summary-intelligence.md)
- [WO-004C1 sprint record](../07-sprints/wo-004c1-executive-summary.md)
- [Prompt registry and structured output](../03-engineering/prompt-registry-and-structured-output.md)
- [Security and privacy](../03-engineering/security-and-privacy.md)
