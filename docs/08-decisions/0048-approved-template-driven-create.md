# ADR 0048: Approved-template-driven Create

## Context

Customer-facing decks must preserve an organisation's authorised brand and legal
copy without turning RevenueOS into free-form design software or a document store.
Automatically treating every uploaded slide as safe would expose hidden, stale,
pricing or internal content.

## Decision

Require an administrator-attested PPTX upload, bounded processing, per-slide
classification and explicit immutable version approval. Generation may select only
approved slides and must preserve required/exact-text policy. Members can use approved
versions but cannot upload, classify or approve templates. Create stays separately
entitled and Account-bound.

## Alternatives

- **Prompt-to-design generation:** rejected because it cannot guarantee approved
  brand, claim or legal treatment.
- **Approve the whole file on upload:** rejected because hidden/internal/stale slides
  need individual exclusion and policy.
- **General content/DAM repository:** rejected as scope and governance expansion.

## Consequences

Initial administration is deliberate and desktop-first. In exchange, every reusable
slide and text block has an explicit policy, approved versions are reproducible and
ordinary sellers cannot weaken organisation controls.
