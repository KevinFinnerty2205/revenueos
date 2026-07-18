# ADR 0013 — Current-transcript Action Items execution

- **Status:** Accepted
- **Date:** 2026-07-18

## Context

RevenueOS already executes Executive Summary and Decisions against a pinned
current transcript through versioned prompts/schemas, a deterministic mock or
OpenAI, and a durable worker. WO-004C3 requires committed Action Items with
owners, due dates and priority without combining their lifecycle with
Decisions, retaining historical transcript bodies or creating downstream
tasks.

Existing JSON artefact and trace columns can represent Action Items, but
database type checks permit only infrastructure test, Executive Summary and
Decisions types. Relative due dates also need one deterministic, conservative
calendar convention.

## Decision

- Add `action_items` as an independent job and artefact type.
- Pin the current usable transcript ID/version and include capability plus
  prompt/schema v1 in equivalence and idempotency.
- Register one immutable Action Items prompt/schema pair and reuse the common
  renderer, provider port, parser, bounded structured-output retries and
  worker.
- Accept an empty list as success; cap it at 25 and reject unknown or
  later-capability fields.
- Persist only concrete task, optional supported owner/date, transcript-grounded
  priority, fixed `open` status, finite confidence and brief paraphrased
  evidence.
- Default an otherwise grounded normal committed follow-up to `medium`;
  reserve `high` for explicit urgency/blocking/time-critical work and `low` for
  explicit non-urgency.
- Interpret supported relative dates from the stored meeting calendar date,
  using ISO weeks and a Friday business-week end; use no system date or broad
  natural-language library and return null for ambiguous wording.
- Keep Executive Summary, Decisions and Action Items independent.
- Add migration `0009_action_items` only to widen type checks.
- Expose meeting-scoped POST/GET contracts and poll from the mounted
  Intelligence panel without generic AI APIs or WebSockets.

## Alternatives considered

- **Embed actions in Decisions:** rejected because the capabilities have
  distinct meaning, fields, retries, empty states and future review paths.
- **Create RevenueOS task rows:** rejected because extraction is not user
  approval and task CRUD/integration is outside this work order.
- **Use a general natural-language date library:** rejected because broad
  interpretation is difficult to explain, can vary over time and would create
  unsafe precision from ambiguous transcript language.
- **Make priority nullable:** rejected in favour of a documented `medium`
  default for an otherwise real normal commitment, while requiring evidence
  for `high` and `low`.
- **Generate synchronously:** rejected because it bypasses durable timeout,
  retry, cancellation, telemetry and atomic persistence.

## Consequences

Action Items evolves and retries independently with tenant isolation and an
append-only trace. A narrow destructive downgrade removes its rows before
restoring earlier checks. Results remain limited to the current transcript;
owner/date may be null and ambiguous dates deliberately stay null. The mock is
not production intelligence. There is no completion tracking, task editing or
task-system integration, and production customer data remains prohibited.
