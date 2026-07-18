# ADR 0014: current-transcript Risks & Blockers execution

- **Status:** Accepted
- **Date:** 2026-07-18

## Context

RevenueOS already executes Executive Summary, Decisions and Action Items as
independent transcript-pinned durable jobs through shared prompt, schema and
provider registries. Risks & Blockers needs the same traceability and tenant
isolation while preventing questions, actions and decisions from being
misrepresented as risk.

## Decision

Add `risks_blockers` as an independent job and artefact type. Pin the current
usable transcript version, use code-deployed prompt/schema v1, require strict
normalised risk/category/severity/nullable-owner/confidence/evidence output,
and persist only validated append-only content. Reuse the durable worker,
bounded structured-output retries, existing safe lifecycle API and one
non-overlapping UI poller. Allow the deterministic mock by default and OpenAI
only when explicitly configured.

Migration `0010_risks_blockers` widens the existing type checks only. Content
telemetry is limited to counts and safe trace metadata. Probability,
mitigation, editing, tasks, Open Questions and later intelligence remain
outside this decision.

## Alternatives considered

- Store risks inside Action Items or Decisions. Rejected because each has
  distinct extraction semantics, idempotency and lifecycle.
- Derive severity probability. Rejected because the transcript supports only
  qualitative impact and the product contract prohibits probability output.
- Execute synchronously in the API or add WebSockets. Rejected because the
  durable worker and bounded polling convention already provides recovery and
  safe terminal states.
- Add mitigation or task creation. Rejected as later product scope requiring
  separate authorisation and review.

## Consequences

The Intelligence tab gains a fourth independent panel and OpenAI may receive
the selected transcript when configured. Owners can be null and severity is
qualitative. Prompt/schema changes remain code deployments. Historical
transcript bodies are still unavailable. Production customer data remains
prohibited until the documented trust controls are complete.
