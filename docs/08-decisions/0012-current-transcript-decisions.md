# ADR 0012 — Current-transcript Decisions execution

- **Status:** Accepted
- **Date:** 2026-07-18

## Context

RevenueOS already executes Executive Summary against a pinned current
transcript through versioned prompts/schemas, a deterministic mock or OpenAI,
and a durable worker. WO-004C2 requires a structured Decisions capability
without retaining historical transcript bodies, mixing it with Action Items or
adding another execution stack.

The existing JSON artefact and trace columns can represent Decisions, but
database check constraints permit only infrastructure test and Executive
Summary types.

## Decision

- Add `decisions` as an independent job and artefact type.
- Pin the current usable transcript ID/version and include job type plus prompt
  and schema v1 in equivalence/idempotency.
- Register one immutable Decisions prompt/schema pair and reuse the common
  renderer, provider port, parser, bounded structured-output retries and worker.
- Accept an empty decisions list as a successful result; cap the list at 25 and
  reject unknown or later-capability fields.
- Treat transcript content as untrusted data and persist only validated
  decision, optional supported owner, normalised status, finite confidence and
  brief paraphrased evidence.
- Keep Executive Summary and Decisions jobs/artefacts independent.
- Add migration `0008_decisions` only to widen type checks; do not add columns.
- Expose only meeting-scoped POST/GET product contracts and poll from the
  mounted Intelligence panel; do not add generic AI APIs or WebSockets.

## Alternatives considered

- **Embed decisions inside Executive Summary:** rejected because it couples
  lifecycle, idempotency, schema evolution and retries for distinct user
  capabilities.
- **Store dedicated decision rows/columns:** rejected because the strict
  versioned JSON artefact already represents immutable output and the work
  order requires no downstream decision CRUD.
- **Retain transcript snapshots now:** rejected as a valuable but materially
  broader retention, privacy and erasure decision.
- **Generate synchronously in the API:** rejected because it bypasses durable
  timeout, retry, cancellation, telemetry and atomic completion rules.

## Consequences

Decisions can evolve and retry independently while preserving tenant isolation
and append-only trace. A narrow destructive downgrade is required because it
must remove Decisions rows before restoring earlier constraints. Results remain
limited to the evidence in the current transcript version; after correction,
the historical body cannot be reconstructed. Owners may be null, deterministic
mock quality is intentionally limited and production customer data remains
prohibited.
