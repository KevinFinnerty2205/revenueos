# ADR 0021: Ground Next Best Action in validated intelligence only

- **Status:** Accepted
- **Date:** 2026-07-24

## Context

RevenueOS now has eight independent, current-meeting intelligence extractions.
WO-006D requires a recommendation layer that helps a professional decide what
to do next. Re-reading the transcript would duplicate extraction, broaden data
exposure and allow the composer to rely on facts outside the validated
intelligence boundary. Giving the composer operational authority would also
combine advice with consequential execution before approval, consent and
integration controls exist.

## Decision

- Add `next_best_action` as an independent job and append-only artefact using
  prompt/schema key and version `next_best_action`/`1`.
- Compose only from validated Executive Summary, Buying Signals, Objections &
  Competitive Signals, Stakeholder Intelligence, Decisions, Action Items, Open
  Questions and Risks & Blockers for one current transcript trace.
- Exclude Follow-up Email and transcript text. The request path, worker loader
  and typed provider input cannot query or carry transcript content.
- Return one overall recommendation and one to five ordered actions with
  bounded text, `high|medium|low` priority, finite confidence and explicit
  dependencies.
- Restrict dependencies to Buying Signals, Stakeholders, Risks, Open Questions
  and Action Items. Require every reasoning item and declared dependency to
  cite an exact value from its validated source before persistence.
- Reuse the durable queue, active-work idempotency, retry/cancellation,
  provider abstraction, strict structured output, atomic completion,
  tenant-scoped repositories, forced RLS and metadata-only audits.
- Add meeting-scoped POST/GET endpoints and include the capability in unified
  generation, aggregate progress and the existing polling chain.
- Present advice only. Do not add buttons or authority for CRM updates, emails,
  tasks, automation, integrations or any other external action.
- Add migration `0016_next_best_action` to widen only the job/artefact type
  constraints.

## Alternatives

- **Compose directly from the transcript:** rejected because it weakens the
  validated-fact boundary and expands provider data exposure.
- **Use Follow-up Email as input:** rejected because it is audience-shaped
  prose rather than an independent evidence artefact.
- **Let the provider infer dependencies:** rejected because unsupported
  reasoning could pass structural validation without deterministic evidence
  checks.
- **Execute the recommendation automatically:** rejected because advice does
  not confer authority to mutate a CRM, send communication or create work.
- **Add a workflow engine:** rejected because the existing small, idempotent
  dependency gate is sufficient.

## Consequences

Users receive traceable, current-meeting recommendations without retransmitting
the transcript or granting operational authority. Composition is unavailable
until all eight sources are current and valid, which favours evidence quality
over partial speculative advice. The exact-reference grounding rule constrains
provider phrasing but makes unsupported output fail closed. Future execution,
account memory, broader dependency types or schema changes require separately
approved work.
