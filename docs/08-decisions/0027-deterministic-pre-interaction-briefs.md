# ADR 0027: Compose pre-interaction briefs deterministically from validated context

- **Status:** Accepted
- **Date:** 2026-08-14

## Context

WO-012 needs concise preparation across heterogeneous Interaction types while
guaranteeing that raw transcript text, stale artefacts and unsupported facts cannot
enter a brief. The existing provider/worker path is appropriate for unbounded
external execution, but a first version can be expressed reliably from the strict
structured intelligence already persisted.

## Decision

Build an authoritative tenant-scoped context, validate every selected artefact,
compose bounded text deterministically in application code and persist an immutable
Interaction-scoped brief keyed by a canonical source fingerprint. Do not add a
prompt, provider allowlist entry or job type for version 1.

## Alternatives

- **Provider composition through the durable worker:** more flexible wording, but
  adds latency, failure modes, processing disclosure and hallucination risk without
  being necessary for the current bounded output.
- **Frontend composition across existing endpoints:** duplicates policy, increases
  query/load complexity and cannot provide one authoritative fingerprint/version.
- **Reuse Meeting AI artefacts directly:** cannot cleanly own Interaction scope or
  review/version semantics.

## Consequences

No external request occurs and transcript exclusion is structural. Output wording is
less flexible and type policy lives in explicit application mappings. A future
provider wording pass must remain downstream of the same normalised context and use
the existing durable worker under a separate decision/work order.
