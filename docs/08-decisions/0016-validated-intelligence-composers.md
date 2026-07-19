# ADR 0016: Compose customer content from validated intelligence only

- **Status:** Accepted
- **Date:** 2026-07-19

## Context

Five independent Meeting Intelligence capabilities already turn a deliberately
supplied transcript into validated, versioned artefacts. WO-004C6 requires the
first customer-ready composer: a draft Follow-up Email. Re-reading the source
transcript would expand data exposure, duplicate extraction work and let the
composer infer facts outside the already reviewed intelligence boundary.

Risks & Blockers can contain internal concerns that are not appropriate for a
customer email. The composer must also preserve durable jobs, provider
neutrality, strict structured output, tenant isolation and traceability without
introducing send authority or an external integration.

## Decision

- Add `follow_up_email` as an independent job and artefact type using prompt and
  schema key/version `follow_up_email`/`1`.
- Compose only from validated Executive Summary, Decisions, Action Items and
  Open Questions artefacts for one current transcript version plus an explicit
  `professional`, `friendly` or `executive` tone.
- Use transcript audit metadata only to prove source currency. The request,
  worker and provider input must not query, contain or transmit transcript
  text.
- Exclude Risks & Blockers, source evidence/confidence fields and other internal
  details from the composer source projection.
- Require returned factual fields and tone to match that projection exactly in
  a post-provider grounding check, in addition to strict schema validation.
- Persist tone on the job, include it in active-work equivalence and make it
  immutable. Reuse equivalent pending/running work, but allow a user to create
  a new append-only job/artefact after completion.
- Reuse the provider port, durable worker, retry/cancellation path, atomic
  artefact completion and metadata-only audit events.
- Add meeting-scoped POST/GET routes and one terminating polling panel with
  plain-text copy and regeneration. Do not add send or integration authority.
- Add migration `0012_follow_up_email` for type constraints and the guarded
  nullable tone column; preserve existing tenant keys and forced RLS.

This establishes the architecture for future customer-ready composers: accept
the minimum validated artefacts, project only audience-safe fields, use a typed
provider input that cannot carry raw source material, validate structure and
grounding, and retain human-controlled external action.

## Alternatives

- **Compose directly from the transcript:** rejected because it duplicates
  extraction, broadens provider data exposure and weakens the validated-fact
  boundary.
- **Include Risks & Blockers:** rejected because internal concerns can be
  customer-inappropriate and are not required for the requested email.
- **Permit the provider to rewrite facts freely:** rejected because polished
  prose does not justify invented, removed or materially changed commitments.
- **Generate synchronously:** rejected because the durable lifecycle already
  supplies idempotency, retries, cancellation and traceability.
- **Send through Gmail, Outlook or a CRM:** rejected because this work order
  authorises draft composition and copy only; external action requires separate
  consent, integration and audit decisions.
- **Store rendered prompts or raw output:** rejected as unnecessary sensitive
  retention.

## Consequences

Users can create traceable customer-ready drafts without re-exposing transcript
content or internal risks to the composer provider. Empty source lists remain
valid and are omitted naturally in presentation. Completed regeneration
produces append-only history, while concurrent duplicate clicks reuse active
work.

Composition is unavailable until all four source artefacts are valid and
current. Generic greeting/closing text is required because recipient identity
is not an approved source. Exact fact preservation may reduce stylistic
flexibility. No editing, recipient selection, send, CRM activity or automation
is provided, and production customer data remains prohibited.
