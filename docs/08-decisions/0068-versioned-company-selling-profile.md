# ADR 0068 — Versioned organisation-approved Company & Selling Profile

## Context

Existing Target Market, Methodology, Create, Business Case and customer Evidence
domains each own a different kind of truth. Sellers still need one concise,
organisation-approved description of their company and offerings, but duplicating
those domains or treating seller-authored context as buyer evidence would weaken
authority and provenance.

## Decision

Store one tenant-owned `SellingProfile` aggregate per organisation and immutable
`SellingProfileRevision` content snapshots. Administrators may edit one draft,
approve it as current, supersede it with a later approval or retire it. Composite
tenant keys, forced RLS, optimistic draft locks, partial uniqueness constraints and
database history guards enforce the lifecycle. A server-owned projection exposes
only the exact current approved revision with `organisation_approved` authority and
`customerEvidence: false`. WO-046 connects that projection only to bounded Ask
organisation-context answers.

## Alternatives

A generic knowledge base, second ICP/content/methodology store, unversioned settings
blob, customer Evidence reuse and automatic website ingestion were rejected. Broad
automatic injection into every existing consumer was deferred until each consumer
has an explicit revision and authority boundary.

## Consequences

The profile is useful with minimal manual input and retains an auditable revision
history, but organisation approval does not verify a buyer-specific fact or legal
claim. Persistent future consumers must pin the exact revision and preserve their
own review/provenance rules. Expanding the schema or adding provider-assisted
ingestion requires a later authorised work order.
