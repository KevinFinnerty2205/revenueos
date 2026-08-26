# ADR 0045: Explicit immutable Campaign audience snapshot

## Context

Dynamic segments and arbitrary recipient uploads obscure who will be contacted and
can expand after approval. Campaign safety requires an exact pre-launch decision for
every person while current Contact data still governs execution.

## Decision

WO-030 accepts one to 50 unique canonical Contact IDs only. Before launch, persist an
audience row with Contact/company reference, bounded recipient snapshot, trust,
eligibility code and human-readable reason. Publish freezes the audience and
sequence. Only eligible rows become enrolments. A Contact privacy deletion may null
the live reference while preserving the historical snapshot until retention.

## Alternatives

- **Saved/dynamic Target Market enrolment:** deferred because it can self-expand.
- **CSV/email input:** rejected because it bypasses canonical trust/provenance.
- **Store only eligible recipients:** rejected because the seller could not audit
  blocked decisions made at launch.

## Consequences

Launch is understandable and auditable, collision/RLS checks are straightforward and
blocked reasons remain visible. Audience changes require a new draft/version rather
than mutating a live campaign.
