# ADR 0033: versioned review-only Action Layer

## Status

Accepted — WO-021.

## Context

RevenueOS already produces final structured intelligence and recommendations, but a
recommendation is not a durable review decision. Direct external execution would add
credential, targeting, consent, retry and rollback risks before connector foundations
exist. Editing a proposal in place would also erase what the user actually reviewed.

## Decision

Store Action lifecycle separately from immutable content versions and immutable
metadata-only audit events. Generate deterministically from current final validated
sources, identify retries by canonical source fingerprint, and supersede changed
semantic recommendations. Approval records intent only and always remains
`not_executed`. External execution is excluded.

Use the existing FastAPI/PostgreSQL modular monolith with organisation predicates,
composite tenant keys and forced RLS. Revalidate source currency and target
relationships at approval. Permit manual completion only for internal Actions.

## Alternatives considered

- **Execute immediately after generation:** rejected because it removes meaningful
  human review and introduces unapproved external side effects.
- **Treat Next Best Action as executable state:** rejected because it is intelligence,
  not a versioned review record.
- **Mutable proposal rows:** rejected because edits would destroy review provenance.
- **New worker or microservice:** rejected because no execution workload exists.

## Consequences

RevenueOS gains durable, exportable intent and safer future connector payloads. It
also carries more lifecycle/schema complexity and must validate polymorphic source
references in application code. A future execution work order must introduce separate
execution states and controls rather than redefining `approved`.
