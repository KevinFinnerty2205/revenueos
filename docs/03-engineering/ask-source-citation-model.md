# Ask RevenueOS source and citation model

## Invariant

A factual Ask conclusion cannot exist without at least one source returned by the
authorised retrieval pass. The response contract rejects duplicate source IDs, point
citations outside the retrieved source set, suggested Actions referencing an unknown
source, and any `supported`, `partially_supported` or `conflicting` answer with no
sources. `supported` additionally requires a cited supporting point.

The composer creates source objects from database records; it does not accept source
IDs from question text or from an external model. This makes a fabricated provider
citation impossible in the current deterministic path and preserves the verifier for
any future composer.

## Source contract

The strict answer envelope declares `schemaVersion: 1`. Each source contains a UUID, bounded source type, human label, optional occurrence
time, short excerpt, provenance class and an internal relative link. Supported source
types are interaction intelligence, accepted Evidence, Methodology, Revenue Brain,
Action, Daily and Opportunity metadata.

## Provenance

The UI and answer text preserve:

- `customer_direct` — verified customer-provided/sent evidence;
- `salesperson_reported` — a seller's report or outbound statement;
- `seller_prepared` — seller-authored proposal/context;
- `imported_external` — imported context whose origin remains explicit;
- `validated_intelligence` — current validated RevenueOS derivation;
- `system_metadata` — current RevenueOS record fields.

Seller-side material is never rewritten as “the customer said”. Questions that
explicitly ask what the customer said filter to customer-direct evidence. Seller-side
sources make the answer partial and add an uncertainty notice.

## Conflicts, freshness and deletion

Methodology `conflicting` state and accepted-evidence conflict metadata produce an
explicit `conflicting` answer. Both relevant sources remain available; ranking never
silently selects a winner. Unknown, partial and stale Methodology states remain
incomplete. Latest valid Revenue Brain insights/bundles are selected by completed
meeting time. Deleted/unavailable Evidence, unverified accepted Evidence,
superseded artefacts and provisional live signals cannot enter the retrieved set.

Source links return to the Opportunity/Account, meeting, Methodology, customer
Evidence, Action or Daily record where the seller can inspect or correct the
underlying work. Ask itself does not mutate evidence.
