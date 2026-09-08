# Closed-Won Handover architecture

## Purpose and post-sale boundary

WO-044 adds an internal, reviewed transition artefact inside one Opportunity
Workspace. It lets the Opportunity owner or an organisation administrator prepare a
bounded draft from sales context already held by RevenueOS. It is not a contract,
customer portal, implementation project, task system or automatic workflow.

The handover has no public route or share token. It does not publish into the Deal
Room, send email, write to HubSpot or Salesforce, create tickets, trigger onboarding
or billing, or activate any provider. It uses the existing `create` entitlement,
including the Complete trial entitlement, consumes no Oryntela Credits and introduces
no external cost. A web-based internal document is the V1 export experience; no PDF,
file store or document provider was added.

## Data and lifecycle

Migration `0060_closed_won_handover` adds four tenant-owned tables:

- `closed_won_handovers` is the single aggregate for one Opportunity and carries the
  aggregate optimistic lock;
- `closed_won_handover_revisions` stores the versioned, schema-validated content,
  lifecycle metadata and source-pack fingerprint;
- `closed_won_handover_sources` stores exact bounded source snapshots, identifiers,
  versions, authority and fingerprints for one revision; and
- `closed_won_handover_audit_events` stores actor/action and safe counts or lifecycle
  metadata, never the handover body or source content.

The lifecycle is `not prepared → draft → in review → approved`. Preparing after an
approval creates a new numbered draft. Approval atomically changes the prior current
revision to `superseded`; a unique partial index permits at most one current
`approved` revision. An authorised owner or administrator can retire the current
approved revision without erasing history.

Draft preparation is explicit and idempotent: repeated preparation returns the one
editable draft. It is available only while the Opportunity is active and `open` or
`won`. Final approval requires the canonical Opportunity status to be `won` and the
Opportunity to remain unarchived. Canonical status is the authority regardless of
whether it originated in native CRM or passed through reviewed WO-042 external stage
mapping. Raw external stage labels are never read.

If an approved Opportunity is reopened, archived or corrected away from Won, the
current approved handover becomes `retired` and remains historical. Both the
application reopen path and a PostgreSQL Opportunity trigger enforce the boundary;
the trigger also covers provider/import corrections that legitimately update the
canonical record. A later legitimate close and handover requires a new reviewed
revision.

Approved, superseded and retired revision content and pinned sources are immutable.
PostgreSQL triggers enforce immutability and the Closed-Won approval prerequisite in
addition to service checks. Aggregate and revision expected versions reject stale
seller/reviewer writes. Ordered row locks plus the one-current index make competing
edits, approvals, retirement and Opportunity-status changes fail safely.
Lifecycle checks bind submitted/approved states to their human actor and timestamp,
constrain retirement reasons and reject actorless manual retirement. Source checks
require coherent positive version metadata for Evidence, Business Case, Deal Room and
Action sources, no version metadata for canonical unversioned sources, and no
duplicate unversioned source reference within a revision.

## Truth and authority model

Every section item carries one authority type and zero or more references from the
revision's server-owned source pack. The client cannot name a source table or attach
an arbitrary identifier. Manual changes are recorded as `SELLER_CONFIRMED` with the
authenticated actor and timestamp; they are never relabelled as Customer Evidence.

| Authority                  | Meaning                                                                                                     | Eligible in an approved handover                                                                      |
| -------------------------- | ----------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `CUSTOMER_EVIDENCE`        | A reviewed Evidence snapshot contains a customer-direct, adequately supported, non-conflicting statement.   | Yes. It must cite a pinned Evidence snapshot.                                                         |
| `SELLER_CONFIRMED`         | An authorised seller or administrator explicitly authored or confirmed the statement.                       | Yes, with actor and timestamp. It remains seller testimony, not Customer Evidence.                    |
| `COMMERCIAL_RECORD`        | A canonical Opportunity value/close fact or exact approved Business Case revision.                          | Yes. It must cite the canonical commercial source. It does not turn a Deal Room into a contract.      |
| `CUSTOMER_FACING_APPROVED` | Context copied from an immutable published Deal Room revision.                                              | Yes. It must cite that exact revision; publication is reviewed context, not legal-contract authority. |
| `SYSTEM_DERIVED`           | Deterministic formatting of bounded canonical data, such as a Contact label, Interaction reference or Task. | Yes outside high-risk claims when source-backed. It is not a customer statement.                      |
| `INFERENCE`                | A possible interpretation without approved factual authority.                                               | No. It must be removed or explicitly seller-confirmed before approval.                                |
| `UNKNOWN`                  | The fact is not established.                                                                                | No. It must remain visibly unresolved, be removed, or be explicitly seller-confirmed before approval. |

Commercial scope, commitments and implementation expectations accept only Customer
Evidence, seller confirmation, commercial records or approved customer-facing
context. Any inference or unknown in any section blocks approval. This rule prevents
phrases such as “we promised” or “the customer expects” from becoming authoritative
without a permitted source or a named human confirmation.

Empty sections are valid. RevenueOS prefers an explicit empty/unknown state to generic
success metrics, manufactured objectives or invented implementation requirements.
The UI exposes source and authority badges, approval blockers and a claim-confirmation
control rather than hiding provenance in a metadata wall.
Explicit confirmation preserves cited source references and records the previous
authority, authenticated actor, time, fixed reason and source count in metadata-only
history. It does not copy the claim text into the audit or elevate the claim beyond
Seller Confirmed.

## Source pack and deterministic drafting

The server builds the source pack; the browser cannot expand it. It can contain only:

- the canonical same-Opportunity record;
- the exact current published Deal Room revision, even if its external link is later
  paused or revoked;
- up to five exact approved Business Case revisions for that Opportunity;
- the latest reviewed Evidence snapshot for up to twenty same-Opportunity Evidence
  records;
- up to twenty active canonical Contacts for the associated Account, containing only
  professional name, job title, company and status;
- up to twenty explicitly linked Interactions with bounded lifecycle/timing metadata;
- up to twenty approved same-Opportunity Actions; and
- up to twenty open/in-progress same-Opportunity Tasks.

It excludes raw CRM payloads and provider stages, mailboxes, unrelated calendar
history, Prospect research, private profiling, billing/Credit/provider economics,
other Opportunities and all other tenants. Source text is untrusted data and is never
executed as instructions. The V1 does not call an AI provider: deterministic drafting
copies only specifically allowed fields and therefore costs AUD $0.

Deterministic drafting adds a source-backed internal summary label with the canonical
Account name, canonical value with an explicit “not a contract” caveat, canonical
close date, professional canonical Contact labels, published Deal Room
overview/commercial/stakeholders/milestones, narrowly eligible customer-direct
Evidence, and relevant approved Actions or open Tasks. Dense valid source packs are
deterministically clamped to the documented section and 120-item limits rather than
failing draft preparation. It deliberately does not infer
why the customer bought, invent objectives or success criteria, convert buying signals
to fact, or infer promises from tasks, coaching, forecasts, methodology or AI
summaries. Reviewers add missing truthful context as seller-confirmed statements.

Every source stores the exact source/version identifier, a bounded immutable snapshot
and SHA-256 fingerprint. Approval rebuilds the current bounded pack and detects
changed, replaced or deleted sources for non-seller-confirmed claims. The reviewer can
refresh sources, which returns the revision to draft and requires review again.
Approved handovers never follow a later Business Case, Evidence or Deal Room revision
silently. If the source later disappears under existing retention policy, the pinned
historical snapshot remains readable while the tenant exists; a pre-approval deletion
becomes a review blocker rather than a crash.

## Content schema

The version-1 document has twelve claim collections plus its separate expandable
source pack: Executive Summary, Customer Objectives, Why They Bought, Commercial
Scope, Key Stakeholders, Commitments, Success Criteria, Implementation Expectations,
Risks, Open Items, Timeline and Next Actions. Next Actions can include owner, due date
and status without creating another task system. Risks distinguish observed evidence,
seller concern and system inference.

Claims are bounded to 2,000 characters, eight sources each and 120 items across the
document. Section-specific maxima range from five to thirty items. Unknown fields,
duplicate claim/source identifiers, misplaced action/risk metadata, unversioned schema
and arbitrary source types are rejected by Pydantic and mirrored by database checks
where practical.

## Access, security and data lifecycle

All reads derive the organisation from verified authentication and every repository
query carries explicit organisation plus relevant Opportunity/aggregate predicates.
The Opportunity owner or an organisation administrator may prepare, edit, confirm,
submit and retire. Final approval is administrator-only. An administrator may approve
their own reviewed handover in V1; RevenueOS has no manager hierarchy and WO-044 does
not invent a two-person approval chain. Other authorised organisation members can
view only approved, superseded and retired revisions—not another seller's working
draft.

All four tables have forced PostgreSQL RLS. Composite foreign keys bind revisions and
sources to the same organisation and Opportunity. Partial indexes enforce one editable
and one current-approved revision per aggregate. Audit/error paths expose safe codes,
counts, revision numbers and source types/versions, never claim text, Evidence text,
source packs, prompts, credentials or provider payloads.

Organisation export version 37 includes handover aggregates, immutable revisions,
content, pinned source snapshots/fingerprints and safe audits. It contains no provider
credentials. Approved organisation deletion explicitly removes handover audits,
sources, revisions and aggregates before Opportunities. Existing retention policy
remains authoritative; WO-044 invents no statutory period.

## Verification

Deterministic API tests cover Create entitlement, explicit/idempotent preparation,
owner/admin policy, administrator approval, open/Won eligibility, seller confirmation,
unsupported high-risk claims, prompt-like source text, lifecycle, immutability,
supersession, retirement, reopen behaviour, export and cross-tenant denial.
PostgreSQL coverage uses a real `NOBYPASSRLS` runtime role and exercises forced RLS,
same-tenant source foreign keys, exact Deal Room version pinning and staleness,
Closed-Won database approval guards, immutable content/sources, concurrent approval,
one-current supersession and Won-to-Lost retirement. Component and Playwright tests
cover not-prepared, draft, in-review warning, approved, superseded and retired states,
source badges, administrator controls, keyboard focus and 390 px overflow.
