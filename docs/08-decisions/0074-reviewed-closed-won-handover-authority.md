# ADR 0074: reviewed claim authority for Closed-Won Handovers

- **Status:** Accepted
- **Date:** 2026-09-08

## Context

Post-sale teams need a coherent transition document, but existing sales context mixes
customer Evidence, seller testimony, canonical commercial facts, published Deal Room
context, deterministic system formatting and inference. A generated narrative without
claim-level authority could turn an AI guess, seller task or methodology gap into a
false promise. A mutable document could also silently follow later source changes or
remain current after an incorrect Won status.

WO-044 must remain internal, tenant-isolated, deterministic in CI and cost AUD $0. It
must use canonical RevenueOS state, not raw provider payloads, and it must not create a
contract, customer communication, CRM write-back or implementation workflow.

## Decision

Store one handover aggregate per Opportunity with multiple schema-versioned revisions,
a bounded pinned source pack and claim-level source references. Use seven explicit
authority states: Customer Evidence, Seller Confirmed, Commercial Record,
Customer-Facing Approved, System-Derived, Inference and Unknown. Manual edits and
explicit confirmation become Seller Confirmed with actor and timestamp; they never
become Customer Evidence.

Allow explicit draft preparation while an active Opportunity is open or Won. Require
seller review and submission, then administrator approval while the canonical
Opportunity is Won. An administrator may self-approve in V1. Do not auto-approve on
close and do not invent a manager hierarchy or two-person chain.

Block every Inference and Unknown at approval. Also restrict commercial scope,
commitments and implementation expectations to Customer Evidence, Seller Confirmed,
Commercial Record or Customer-Facing Approved authority. Empty sections are valid.

Build the source pack only from allow-listed canonical/same-Opportunity sources. Pin
exact versions and fingerprints. Detect changes before approval; source refresh returns
the revision to draft. Approved revision content and sources never mutate. A new
approval atomically supersedes the prior current approval. Reopen, archive or
Won-to-Lost correction retires the current revision while preserving history.

Use forced PostgreSQL RLS and composite tenant/Opportunity foreign keys on every new
table. Keep audits metadata-only and export the document/provenance through the
existing organisation export/deletion framework.

Run the automatic Opportunity-correction retirement as a trigger-only
`SECURITY DEFINER` function with a locked search path, revoked public execution and
tenant/Opportunity predicates derived only from the trusted trigger row. This lets a
least-privilege runtime role update the canonical Opportunity without receiving
unrelated handover-table grants; callers cannot supply an organisation or handover
identifier to the function.

Use deterministic drafting for V1. Do not invoke the existing AI provider merely
because AI could draft: the conservative allow-list already creates useful context
without API spend, prompt construction or another authority-escalation path.

## Alternatives rejected

- **Auto-approve on Won:** closing a deal does not verify the transition narrative or
  its promises.
- **One mutable document:** destroys historical explainability and lets later sources
  silently change an approved handover.
- **Narrative-level sources only:** cannot show which high-risk claim has authority.
- **Treat seller confirmation as Evidence:** misrepresents who supplied the fact.
- **Infer missing objectives, success metrics or commitments:** fabricated
  completeness is less trustworthy than an explicit unknown.
- **Read raw CRM, mailbox, calendar or Prospect data:** bypasses canonical authority
  and violates minimisation.
- **Publish through the Deal Room or email automatically:** crosses the internal
  post-sale boundary and could create unintended obligations.
- **Add PDF/document/project providers:** unnecessary for a useful V1 and violates the
  zero-spend boundary.

## Consequences

Sellers may need to add or confirm facts and administrators must perform an explicit
approval. Some sections will remain empty when no trustworthy source exists. Source
changes require refresh and review, while approved history remains readable from its
pinned snapshots. Customer Success can trust that a current revision was approved
against a canonical Won Opportunity but must still interpret each authority badge;
the artefact is an internal handover, not a contract.
