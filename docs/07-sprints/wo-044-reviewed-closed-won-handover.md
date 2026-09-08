# WO-044 — Reviewed Closed-Won Handover

- **Branch:** `codex/wo-044-reviewed-closed-won-handover`
- **Baseline:** `bd9fda9bf76418ea2e8730cee76a49e9b7d29a44`
- **Status:** implemented; awaiting engineering review
- **Migration:** `0060_closed_won_handover`
- **Data/spend:** deterministic synthetic fixtures only; no customer data, external
  provider, new storage or spend (AUD $0)

## Outcome

WO-044 adds a source-aware internal handover to the Opportunity Workspace. An
Opportunity owner or organisation administrator deliberately prepares a bounded draft
while the Opportunity is open or Won, edits or confirms facts, and submits it for
review. Only an organisation administrator can approve, and only while the canonical
Opportunity remains active and Closed Won. Approval creates an immutable current
revision; a later approval supersedes it atomically and retirement preserves history.

The document covers Executive Summary, Customer Objectives, Why They Bought,
Commercial Scope, Key Stakeholders, Commitments, Success Criteria, Implementation
Expectations, Risks, Open Items, Timeline and Next Actions. The expandable source pack
is the thirteenth review concern. Empty sections remain honest rather than being filled
with generic or inferred content.

## Trust and safety outcome

Each claim is labelled Customer Evidence, Seller Confirmed, Commercial Record,
Customer-Facing Approved, System-Derived, Inference or Unknown. Customer Evidence and
seller confirmation remain distinct. Commercial records do not invent terms, and a
published Deal Room revision is useful reviewed context but is not a contract.
Inference and Unknown cannot be approved. Commercial scope, commitments and
implementation expectations accept only the four strongest approved/human authority
classes.

The source pack is built server-side from the same canonical Opportunity plus bounded
same-Opportunity Evidence, published Deal Room, approved Business Case, Contacts,
linked Interactions, approved Actions and open Tasks. Exact source/version identifiers,
bounded snapshots and fingerprints are pinned. Changed/deleted sources block approval
until refreshed and reviewed. Raw CRM payloads, unrelated mail/calendar, unpromoted
Prospect research, provider economics, billing and Credits are excluded.

The V1 deliberately uses deterministic extraction and no AI/provider call. Prompt-like
source text remains inert data. It does not email a customer, publish externally,
write to CRM, create tickets, trigger billing/onboarding or make a downstream promise.

## Lifecycle and data

Migration `0060_closed_won_handover` creates one handover aggregate per Opportunity,
immutable numbered revisions, pinned sources and metadata-only audits. Forced RLS and
tenant/Opportunity composite foreign keys cover all four tables. Partial unique
indexes permit at most one editable revision and one current approved revision.
PostgreSQL independently blocks approval for a non-Won Opportunity and mutation of
approved content/sources.

Reopening, archiving or correcting the canonical Opportunity away from Won retires
the current approved handover without deleting it. A new legitimate close requires a
new reviewed revision. Organisation export version 37 contains the handover and
provenance; approved tenant deletion removes all four table families under the current
retention framework.

The feature uses the existing Create entitlement, including Complete trial access,
and no Credits. It adds no price, provider, public route, file product or new customer
user type.

## Verification

API, migration and real PostgreSQL tests exercise eligibility, idempotent preparation,
approval policy, unsupported promises, source tenancy/version staleness, RLS,
immutability, concurrent approval, supersession, retirement and Opportunity
correction. React and Playwright cover all six visible states, source warnings,
approved/history reading, keyboard interaction and desktop/390 px layout. Full gate,
visual evidence and CI results are recorded in the draft pull request and final owner
handoff.

See [Closed-Won Handover architecture](../03-engineering/closed-won-handover.md) and
[ADR 0074](../08-decisions/0074-reviewed-closed-won-handover-authority.md).
