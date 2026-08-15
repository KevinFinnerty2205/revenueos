# Pre-Interaction Brief engineering guide

## Implemented boundary

WO-012 implements the deterministic, interaction-scoped brief. WO-016 now presents
its bounded high-value fields in the **BEFORE** phase of the browser Companion and
links to the full brief. It supports all ten initial Interaction types and does not
require recording. The brief includes explicit company/opportunity/participant
labels and the current Next Best Action where available. It never reads recording
or transcript content.

`PreInteractionBriefService` owns access validation, source loading, normalisation,
composition, strict validation, versioning, persistence and product-safe responses.
Routes remain thin. Composition is bounded and synchronous because it performs no
external provider call and reads only structured database records.

## Provider-use decision

Version 1 is fully deterministic. It does not register a prompt, schema-registry
entry or AI job type, and it does not use the worker or provider abstraction. This
keeps the structured context authoritative and makes transcript/provider exclusion
structural. A later provider-backed wording pass would require a separate work
order, the existing durable worker, a strict registered schema and normalised
context only.

## Persistence and lifecycle

Migration `0022_pre_interaction_brief` adds `pre_interaction_briefs` with:

- organisation, Interaction and optional company/opportunity scope;
- a SHA-256 source-context fingerprint;
- positive brief and schema versions;
- strict normalised content and structured source references;
- creator, created time and one-time review metadata;
- tenant-safe logical-version and idempotency constraints; and
- forced PostgreSQL RLS plus database immutability guards.

Equivalent source context reuses the completed row without consuming another
generation. Changed relevant context creates the next immutable version. Review is
an idempotent metadata-only append and never mutates content. Approved retention,
Interaction deletion, organisation deletion and demo reset use the established
beta-maintenance path.

## API and UI

- `GET /api/v1/interactions/{interactionId}/companion/brief`
- `POST /api/v1/interactions/{interactionId}/companion/brief`
- `POST /api/v1/interactions/{interactionId}/companion/brief/review`

GET returns unavailable, not-generated, completed, failed or cancelled product
states. Queued/running remain in the public state union for future durable
composition, but deterministic v1 completes within the bounded request. Responses
exclude transcript, raw artefact, provider, prompt, schema-registry, lease and
worker fields. Product-safe source labels replace raw source IDs in the UI.

Interaction lists expose only readiness and generated time. Interaction Detail
contains the responsive preparation card, review action and all bounded sections.
Phone calls keep objectives, questions, stakeholder role and commitments near the
top. Presentation guidance explicitly treats seller-prepared material as context,
not evidence of customer intent.

## Operational controls

`API_FEATURE_AI_COMPANION_ENABLED` is server authoritative and defaults on in the
example private-beta configuration. Generation requires the current data-notice
acknowledgement and reserves one normal generation; idempotent reuse is free and no
provider-call counter is incremented. Logs contain IDs, state, interaction type and
section counts only—never brief text, names, questions, commitments or risks.

See [source grounding](pre-interaction-source-grounding.md), the
[security review](pre-interaction-security-review.md) and the
[Interaction API](interaction-api.md).
