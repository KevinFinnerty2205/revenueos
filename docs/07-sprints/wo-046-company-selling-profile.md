# WO-046 — Company & Selling Profile

- **Branch:** `codex/wo-046-selling-profile`
- **Baseline:** `19314dedc3a537c679ee4a9de0f16f1b2be4cc2b`
- **Status:** implemented in PR #70
- **Migration:** `0051_selling_profile`
- **Provider/data boundary:** no external provider; synthetic test data only

## Outcome

WO-046 adds one tenant-owned Company & Selling Profile per organisation. An
administrator supplies a company description and one to eight simple offerings.
Every offering has a required name and concise description, with optional bounded
lists for who normally buys, problems solved, intended outcomes, differentiators,
approved competitors/alternatives, approved proof and approved claims.

This is organisation-supplied, company-approved selling context. It is not customer
Evidence, public Prospect research, a buyer-specific fact, CRM authority or
AI-generated truth. Profile text remains untrusted data even after approval.

## Domain and lifecycle

`selling_profiles` owns the stable organisation aggregate.
`selling_profile_revisions` owns the versioned content snapshot and lifecycle:

The durable boundary is recorded in
[ADR 0068](../08-decisions/0068-versioned-company-selling-profile.md).

```text
DRAFT ── approve ──> APPROVED/CURRENT ── retire ──> RETIRED
                           │
                           └── later approval ──> SUPERSEDED
```

Only one draft and one approved/current revision may exist for a profile. Draft
updates require an optimistic `lockVersion`. Approval supersedes the prior current
revision atomically. Approved, superseded and retired content is immutable at the
service and database-trigger layers. Historical revisions remain available to
administrators and in an organisation export.

## Projection and consumers

`GET /api/v1/selling-profile/context` is the single server-owned approved Selling
Context projection. It returns only the current approved revision, its exact revision
identity, `authority: organisation_approved` and `customerEvidence: false`. Members
with an active organisation membership may read it; only administrators may create,
edit, approve, supersede or retire profile revisions.

Connected now:

- the Settings administration experience for explicit authoring, approval,
  retirement and history review; and
- Ask RevenueOS for bounded organisation-context questions such as “What do we
  sell?”. Answers cite the exact approved revision, keep organisation provenance
  visible and explicitly say the result is not customer Evidence.

Deliberately left later:

- Sales/Revenue Brain, preparation, Prospect, Engage, Create, Business Cases,
  Methodology and Actions. Their durable outputs or distinct authority models need
  explicit revision pinning and consumer-specific composition. WO-046 does not
  silently blend this profile into customer evidence, public research, target-market,
  approved-template, value-model or methodology truth.

## Security, privacy and operations

- Tenant identity comes only from verified authentication context. Repository reads
  and writes carry explicit organisation predicates, and composite foreign keys deny
  cross-tenant profile/member references.
- Both new tenant tables use enabled and forced PostgreSQL RLS with transaction-local
  trusted organisation context.
- Mutation requires an active administrator membership; active members receive only
  the approved projection. Missing, disabled and cross-tenant membership paths fail
  closed.
- Structured validation bounds field lengths, list sizes, offering count and duplicate
  names/points. Instruction-like text is stored as inert profile data; Ask excludes it
  from its bounded response context.
- Audit events contain IDs, revision numbers, lifecycle action and counts only. Logs do
  not include profile bodies, claims, proof or fingerprints.
- Export schema v30 includes the profile and revisions. Approved organisation deletion
  removes revisions before the aggregate and membership rows.

## Administration experience

Settings shows empty, draft, approved/current, retired, error and loading states. The
minimum form asks only for a company description plus offering name/description.
Optional fields use progressive disclosure and one-item-per-line entry. Approval is a
separate explicit action; retiring current context does not erase history. Labels,
native fieldsets/details, focus behaviour, status/alert announcements, wrapping grids
and 390 px no-overflow checks cover the accessible responsive boundary.

Synthetic browser evidence:

- [desktop approved profile](assets/wo-046-selling-profile-desktop.png)
- [390 px approved profile](assets/wo-046-selling-profile-mobile.png)

## Scope boundary

No provider, dependency, billing, Credits, web crawl, product catalogue, second ICP,
content library, knowledge base, CMS, logo, rebrand, marketing site, deployment or
later work order is part of WO-046. Spend is AUD $0 and no customer data was used.
