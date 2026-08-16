# Sales Methodology Engine implementation guide

**Status:** Implemented by WO-024 as a RevenueOS Core capability.

## Boundary

The engine is a deterministic, versioned projection over existing tenant-owned
Evidence, final Interaction Intelligence, Revenue Brain artefacts and Opportunity
metadata. It is not a separate brain, CRM qualification form, forecast, score or
workflow engine. Standard definitions are immutable code-deployed configuration;
custom definitions are bounded tenant configuration.

The service flow is:

`validated source context → canonical fact candidates → field policy → immutable projection → review`.

`SalesMethodologyProjectionService` resolves the organisation default, validates
Opportunity access, loads a bounded current source set, evaluates each field,
attaches source references and persists the result. No provider is used in v1.

## Persistence and versioning

Migration `0033_sales_methodology` creates:

- `methodology_definitions` and immutable `methodology_definition_versions` for
  custom definitions;
- `organisation_methodology_settings` for one organisation default or `none`;
- immutable `methodology_projections` containing bounded structured field results
  and source IDs, never duplicated raw Evidence content; and
- immutable `methodology_reviews`, including the ID of any additive
  salesperson-reported clarification Evidence.

Every table is organisation-scoped, uses composite tenant foreign keys where it
references tenant data and has forced PostgreSQL RLS. Projection uniqueness covers
Opportunity, definition key/version and the deterministic source fingerprint.
Equivalent inputs reuse the existing projection. Changes create a new projection;
history is never overwritten.

## Source boundary

Eligible input is limited to current final AI artefacts, accepted document/email
findings, final validated Interaction snapshots, safe Opportunity state and
methodology review clarifications. Live provisional signals, transcript bodies,
recordings, document bodies and email bodies are not read by the projection engine.
Source currency is rechecked when the current view is read. If an underlying source
changes or is deleted, the old conclusion is hidden and the view becomes
`needs_refresh`; the old projection remains explainable in history.

Customer-direct or accepted customer Evidence can confirm a field. Seller reports,
seller documents and outbound email remain partial/context support. Unknown speaker
identity cannot confirm authority. Conflicting admissible sources remain visible as
conflicts rather than being silently resolved.

## Product integration

- Opportunity Workspace includes the current summary under Deal and loads history
  only on request.
- Pre-Interaction Brief receives at most three relevant gap questions; a phone call
  receives at most one. Interaction type changes prioritisation.
- AI Debrief inherits those bounded brief questions, so it can ask whether an
  important gap was resolved without adding a checklist engine.
- the existing source-aware action generation receives final methodology gaps and
  may propose review-only `prepare_next_interaction` or `review_conflict` Actions.
- Next Best Action can consume the same typed final gap context in future; no second
  recommendation engine or provider path was added.

## Operations

`API_FEATURE_SALES_METHODOLOGY_ENABLED` uses the existing feature-flag surface and
defaults on for this Core private-beta slice. It is not an add-on entitlement.
Telemetry contains event type, methodology kind/version and state counts only. It
must never contain conclusions, evidence text, customer/stakeholder names or custom
questions.

Organisation export schema version 14 includes definitions, versions, selection,
projections and reviews. Retention removes expired projections/reviews and their
methodology clarification Evidence. Opportunity and organisation deletion use
explicit safe ordering. Demo data creates deterministic historical BANT and current
MEDDPICC projections from synthetic final sources, with zero provider calls.

## Deliberate limits

There is no Opportunity override, team assignment, automatic queue, provider
normalisation, arbitrary expression, stage gate, completeness percentage,
qualification score, close probability, manager dashboard, rep ranking or employee
surveillance. RevenueOS may be wrong; every conclusion remains inspectable and
reviewable.
