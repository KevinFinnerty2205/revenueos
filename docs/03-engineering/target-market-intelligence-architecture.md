# Target Market Intelligence architecture

- **Status:** Current — WO-028
- **Migration:** `0037_territory_icp`

## Boundaries

The FastAPI modular monolith owns criteria validation, quota policy, matching,
relationship reconciliation and persistence. A provider-neutral
`CompanyDiscoveryProvider` supplies a bounded structured company set. The active
adapter is `DeterministicMockDiscoveryProvider`; it performs no network I/O and is
unavailable in production.

The web client calls only the API. It does not query a provider or database directly.

## Data model

| Table | Role |
| --- | --- |
| `prospect_target_markets` | Mutable name/status pointer to the current revision |
| `prospect_target_market_versions` | Immutable normalised criteria revision |
| `prospect_discovery_runs` | Durable request, provider/schema version, counts and lifecycle |
| `prospect_discovery_candidates` | Immutable point-in-time candidate and relationship context |
| `prospect_candidate_reasons` | Immutable criterion-level explanation, origin and trust |
| `prospect_target_feedback` | Per-user saved/excluded state for a Prospect Research Target |

Candidate identity reuses `prospect_research_targets` by exact normalised domain.
Every row and unique/FK boundary is organisation-scoped. Repository queries include
an explicit organisation predicate; PostgreSQL enables and forces RLS on all six new
tables. Composite foreign keys reject cross-tenant attachment.

## Lifecycle and idempotency

An edit appends a version and advances `current_version`. A discovery run references
that immutable version and moves `pending → running → completed|partial|failed`.
Fresh completed/partial results are reused. Explicit refresh creates a new run with
lineage. Organisation, Target Market and client idempotency keys prevent duplicate
same-request runs; candidate identity remains stable across refreshes.

The deterministic provider completes synchronously for the private-beta slice. The
durable lifecycle leaves a future worker boundary, but WO-028 does not add claiming,
locks, scheduled monitoring or external provider retries.

## Matching

Matching is deterministic and non-numeric:

- a known required mismatch is excluded;
- an unknown required value becomes `needs_more_information`;
- an explicit exclusion wins over positive criteria;
- preferred characteristics and bounded provider-supplied trigger context distinguish
  high from worth-researching candidates;
- exact-domain Company and open-Opportunity lookups add relationship context only.

Each reason persists product-safe text, criterion key, match state, trust state, data
origin, coarse observed-value class and an optional canonical public HTTPS source.
Raw provider responses and page content are never persisted or logged.

## Privacy, retention and operations

Organisation privacy export schema 18 includes definitions, revisions, runs,
candidates, reasons and feedback. The standard research-retention sweep does not
delete a Prospect Research Target referenced by discovery history. Archived Target
Markets and point-in-time runs persist until organisation deletion; organisation
deletion explicitly removes all six tables before shared Prospect identities.

Logs contain IDs, state, counts and safe failure codes only. Quotas are stored in the
existing tenant/user usage counter with `discovery_run_count`. No user-facing CSV or
bulk export endpoint exists.
