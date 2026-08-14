# ADR 0028: bounded foreground debrief reasoning and ephemeral browser voice

**Status:** Accepted
**Date:** 2026-08-14

## Context

Interactive debrief answers need the next question in the same user flow. The existing
durable worker is designed for meeting/transcript-bound jobs, while browser audio is
binary, short-lived data that must not be forced through the text provider contract.

## Decision

- Reuse the versioned prompt, strict schema, provider request, mock/OpenAI allowlist,
  timeout and metadata-only telemetry architecture for two bounded foreground request
  types: `ai_debrief_question` and `ai_debrief_evidence`.
- Commit captured input before provider execution and reopen trusted tenant context to
  persist only validated output. Do not hold a transaction during the call.
- Persist the resulting question/candidates as the idempotent provider result. Do not
  add debrief types to the meeting/transcript AI job table or claim infrastructure-test
  support for them.
- Keep transcription behind a separate narrow provider contract. Capture at most 120
  seconds/8 MB in the foreground and never persist raw audio.

## Alternatives

- Extending meeting AI jobs was rejected because their non-null meeting/transcript
  trace is the wrong aggregate and interactive polling would add avoidable latency and
  schema distortion.
- Holding a transaction during provider work was rejected because it increases lock
  duration and weakens recovery.
- Persisting audio/object-storage references was rejected because short post-call
  debriefs do not justify a recording subsystem or its consent/deletion burden.

## Consequences

The interaction remains responsive and follows the same strict structured-output
policy, but foreground failure terminates the small session safely instead of using
the durable worker retry lifecycle. Long-running, streaming or resilient background
capture still requires a separate work order. External processing remains feature-
gated and quota-limited.
