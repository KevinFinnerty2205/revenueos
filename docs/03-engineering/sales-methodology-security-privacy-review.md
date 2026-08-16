# Sales Methodology security and privacy review

**Review result:** Suitable for the existing private-beta boundary with the feature
flag and limitations below.

## Controls

- Organisation scope comes only from verified `TenantContext`; repository reads and
  writes include explicit organisation predicates.
- All five tables introduced by `0033_sales_methodology` have forced PostgreSQL RLS,
  tenant uniqueness and composite tenant relationships.
- Active members may read/generate/review authorised Opportunity views. Only active
  administrators may choose a default or manage custom definitions. Role/disabled
  membership changes are enforced by existing authentication on every request.
- Definitions are strict bounded data. Allowlists and length/order/uniqueness checks
  reject executable rules, extra fields, scripts, SQL-like content, template syntax
  and prompt-instruction text.
- Projection context contains structured validated conclusions and IDs, not raw
  transcripts, recordings, document/email bodies or visual bytes. No provider is
  called, so custom text cannot reach a model in v1.
- Seller-originated information remains labelled/contextual. Review never upgrades
  provenance. Clarification adds immutable salesperson-reported Evidence.
- Source currency is rechecked. Deletion/change hides unsupported current claims and
  requires regeneration. Provisional live signals never persist methodology state.
- Logs/audits contain IDs, versions, event types and counts only. Conclusions,
  questions, Evidence content, customer/stakeholder names and provider payloads are
  prohibited.

## Lifecycle

Export version 14 contains authorised definitions/versions, selection, projections,
source IDs/types and review metadata, but no provider internals or duplicated raw
Evidence. Retention deletes expired reviews before projections and deletes linked
clarification Evidence. Opportunity and organisation deletion explicitly remove
reviews/projections before their parents; organisation deletion also removes settings
and definitions. Forced RLS and cross-tenant tests cover all tables.

## Residual limitations

Deterministic keyword/category mapping can be incomplete or wrong, conflict detection
is deliberately conservative, and stale policy cannot understand every commercial
change. Reviewable lineage and fail-safe refresh are the mitigations. Methodology
does not replace seller judgement. Private-beta identity, consent, retention and
production-data restrictions continue to apply.

There is no arbitrary score, close probability, stage enforcement, rep ranking,
manager surveillance, autonomous action or new integration/provider boundary.
