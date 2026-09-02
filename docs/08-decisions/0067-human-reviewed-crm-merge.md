# ADR 0067 — Conservative human-reviewed Account and Contact merge

## Context

Duplicate cleanup otherwise requires unsafe database surgery, but automated merging could destroy identity, suppression and evidence provenance.

## Decision

Only tenant admins may preview and explicitly confirm one Account/Contact pair. Deterministic locks, record fingerprints and explicit field choices make the transaction stale-safe and idempotent. The source becomes an immutable tombstone. Incompatible external mappings or unrepresentable provenance/campaign collisions block. Suppression is most restrictive and historical statement/recipient provenance is not rewritten.

## Alternatives

Fuzzy/AI auto-merge, batch merge, hard delete and user undo were rejected. Opportunity merge remains out of scope.

## Consequences

Some complex duplicates require containment rather than merge. The audit/export retains IDs and choices without field values; full erasure occurs only through organisation lifecycle.
