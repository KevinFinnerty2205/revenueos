# Prospect foundation readiness

- **Status:** Architecture readiness decision after WO-025C
- **Verdict:** No foundational rearchitecture is required before WO-026
- **Scope:** Defines constraints for a future WO-026; it does not implement or
  authorise routes, schema, providers, workers or UI
- **Decision authority:** [Checkpoint 1B](../06-roadmap/checkpoint-1b-core-readiness.md)

## Architecture conclusion

The existing modular monolith can support Prospect as an additional bounded domain.
Identity, organisation isolation, canonical Company/Contact records, Evidence and
provenance, provider abstraction, reviewed promotion, Revenue Brain projection and
Action execution are already the right seams.

WO-026 should extend those seams with tenant-owned research observations. It should
not replace canonical business entities, create a second evidence model, let an LLM
own retrieval policy, or introduce another service/datastore.

No migration is required before WO-026 begins. Schema needed by WO-026 belongs in its
own reviewed work order and Alembic revision after the exact lifecycle and access
patterns are approved.

## Baseline readiness

| Foundation                 | Current capability                                                                        | Prospect use                                                     | Readiness                                                 |
| -------------------------- | ----------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | --------------------------------------------------------- |
| Identity and organisations | Verified auth context, membership policy, fail-closed protected routes                    | Authorise every research run/read/promotion                      | Ready; target environment still needs launch evidence     |
| Tenant persistence         | Explicit organisation predicates plus transaction-local PostgreSQL RLS                    | Scope every research row, unique key and query                   | Ready                                                     |
| Canonical entities         | Tenant-isolated Company, Contact, Opportunity and Task repositories/services              | Duplicate-check and promote accepted records                     | Ready                                                     |
| Interaction/Evidence       | Typed sources, provenance, trust/freshness/conflict/correction concepts                   | Represent externally observed research without overstating truth | Ready                                                     |
| Revenue Brain              | Immutable, source-aware longitudinal projections                                          | Receive only reviewed/promoted context                           | Ready                                                     |
| Ask                        | Typed, permission-scoped retrieval with strict citations and no tools                     | Link to explicitly scoped Prospect evidence later                | Ready; do not turn it into the research executor          |
| AI boundary                | Versioned prompts, structured output validation, deterministic mock and optional provider | Bounded extraction/classification over permitted source material | Ready                                                     |
| Provider boundary          | Explicit adapters, feature flags, safe configuration failure                              | Add one selected research provider behind policy                 | Ready                                                     |
| Action boundary            | Proposal, review, approval, preview, confirmation, idempotency and reconciliation         | Govern any later outreach or external mutation                   | Ready for reuse; no WO-026 send                           |
| Quotas/operations          | Tenant/user limits, content-free audit patterns, health/readiness and safe errors         | Limit research cost and abuse                                    | Ready for extension                                       |
| Retention/export/deletion  | Existing private-beta maintenance contracts                                               | Include research data and provider identifiers                   | Pattern ready; WO-026 must add its data                   |
| Entitlements               | Core/add-on projection described in platform architecture                                 | Keep Core complete when Prospect is disabled                     | Ready as a boundary; exact WO-026 contract remains future |

The migration chain through `0034_crm_sync` is linear and upgrades cleanly in the
controlled review environment. This is repository evidence only; PostgreSQL/RLS and
target deployment checks remain mandatory in WO-026 and launch validation.

## Required WO-026 domain boundary

The future implementation should distinguish four states:

1. **Research request/run** — who requested it, authorised scope, purpose, provider,
   policy/version, bounded cost and lifecycle.
2. **Source observation** — source identifier/link where permitted, retrieval time,
   terms/visibility class, content fingerprint and deletion/expiry policy.
3. **Finding/candidate** — a normalised claim with subject, value, evidence reference,
   trust/verification state, freshness and contradiction state.
4. **Promotion decision** — explicit accept/reject/merge decision that creates or
   attaches to canonical Company/Contact data idempotently.

Research observations remain separate from accepted customer truth. A provider
payload is not a canonical Contact. An inferred email is not verified contact data. A
person result is not a buying-committee fact. Promotion is a policy/service decision,
not a route-level side effect.

The exact names and schema require the WO-026 contract; this checkpoint does not
pre-approve tables.

## Source and trust contract

Every material finding must retain enough metadata to answer:

- What is being claimed, about which subject?
- Which permitted source supports it?
- When was the source observed and when does it expire?
- Is the value observed, reported, inferred, conflicting, stale or verified?
- Which policy/provider/version produced the normalisation?
- Has a user reviewed, rejected, corrected, merged or promoted it?
- Can the source and derived finding be exported and deleted?

Unknown remains unknown. The API and UI must not collapse “likely”, “inferred” and
“verified” into a truthy field. Provider confidence may be retained as diagnostic
metadata but may not become an unexplained seller-facing score.

Source availability is not permission to ingest. Provider selection requires a
documented assessment of terms, lawful purpose, geographic coverage, personal-data
categories, prohibited sources/traits, retention, onward transfer, deletion,
correction, rate/cost limits and kill-switch behaviour.

## Promotion and duplicate safety

Promotion to Sell must be explicit and idempotent:

- resolve tenant scope from auth, never from an untrusted organisation identifier;
- search for tenant-local candidate duplicates using approved normalised identifiers;
- show the likely existing record and the fields that would be added or changed;
- distinguish create, attach, merge suggestion and reject;
- preserve the research source and decision without copying an unrestricted provider
  payload into canonical or audit data;
- prevent retry/concurrency from creating duplicate Company or Contact records;
- require separate review for any sensitive or lower-trust value; and
- project into Revenue Brain only after the canonical acceptance policy is satisfied.

Cross-organisation identity matches must never reveal that another tenant has the
same company or person.

## API and service constraints

The future routes should remain thin. Application services own provider policy,
normalisation, duplicate review, promotion and deletion. Repositories own explicit
tenant-filtered persistence. Pydantic/OpenAPI remains the contract source of truth,
with only necessary client-facing contracts copied to `packages/shared`.

Required endpoint behaviours include:

- fail closed for missing auth, organisation or membership;
- bounded pagination, filters and result sizes;
- explicit pending/ready/partial/failed/expired/cancelled states;
- safe codes, messages and request IDs without provider content;
- idempotency for run creation and promotion;
- stale-state/conflict protection on review;
- no arbitrary URL fetch supplied directly to a worker without SSRF policy; and
- no generic text-to-SQL, unrestricted tool use or provider-owned authorisation.

WO-026 may use the existing job/worker foundation if provider latency requires durable
work. Job claiming, retry and terminal states must follow the existing queue contract;
do not create a new queue, service or broker.

## Tenant isolation and RLS requirements

Every Prospect-owned row and relationship must contain organisation scope even where
it can be inferred through a parent. Repository queries require an explicit
organisation predicate. PostgreSQL RLS uses the trusted transaction-local tenant
setting as defence in depth; the runtime role cannot bypass it.

WO-026 tests must cover:

- cross-organisation reads by ID, filter, pagination and nested relationship;
- cross-organisation update/delete/review/promotion attempts;
- attachment of a finding/source/run to another tenant's Company or Contact;
- duplicate lookup without cross-tenant existence leakage;
- worker execution with missing or wrong trusted tenant context;
- export/deletion scoped to the requesting organisation; and
- admin/migration credentials remaining separate from runtime credentials.

SQLite may support isolated developer checks but cannot prove PostgreSQL RLS.

## Provider and privacy requirements

Normal development and CI use a clearly labelled deterministic mock. Live research is
off by default and unavailable unless configuration, organisation entitlement,
provider approval and target-environment policy all pass.

Do not log source bodies, personal profiles, email addresses, provider payloads,
queries containing customer content, tokens or headers. Content-free audit should
record IDs, lifecycle transition, policy/provider version, counts, actor, request ID
and outcome only.

Provider content must be treated as untrusted input. Sanitise display, validate
structured output, resist prompt injection, restrict URL schemes/hosts and prevent
provider text from issuing instructions or triggering Actions. Store the minimum
source material necessary for review and traceability.

Research must support purpose limitation, correction, expiry, export and deletion.
Deletion must cover canonical links, derived findings, jobs/artefacts, retained source
material and eligible provider identifiers without erasing immutable content-free
security audit beyond policy.

## Ask, Revenue Brain and Action separation

Prospect should integrate with the current platform through explicit transitions:

| From                    | To                | Allowed transition                                               |
| ----------------------- | ----------------- | ---------------------------------------------------------------- |
| Research result         | Prospect detail   | Display source-rich untrusted observation                        |
| Research finding        | Company/Contact   | Explicit duplicate review and promotion                          |
| Accepted canonical fact | Revenue Brain     | Existing source-aware projection policy                          |
| Prospect scope          | Ask               | Bounded authorised retrieval with citations, if separately added |
| Accepted person/account | Action proposal   | Future reviewed draft under WO-029                               |
| Action approval         | External provider | Future separate execution and confirmation policy                |

Ask must not browse the public web merely because Prospect has a provider. Revenue
Brain must not ingest rejected or unreviewed findings. WO-026 must not send outreach,
create campaigns or update an external CRM as a side effect of saving a candidate.

## Core compatibility requirements

With Prospect disabled or unavailable:

- Home/Daily, Sell, Interactions, Opportunity, Search/Ask and Settings remain complete;
- current routes and API contracts keep compatible behaviour;
- Core health/readiness does not depend on a research provider;
- provider outage does not hide or corrupt canonical customer records;
- no Prospect navigation dead end is shown; and
- Core data is not backfilled or migrated into research observations.

This is a package boundary and a resilience requirement, not only a feature flag.

## Validation gate for WO-026

Before WO-026 can be called complete, its work order should require:

- one documented provider/permitted-source decision and deterministic mock contract;
- PostgreSQL migration upgrade/downgrade review and RLS tests;
- cross-tenant, permission, quota, abuse and provider-failure tests;
- source attribution, freshness, conflict and verification-state tests;
- duplicate-safe idempotent promotion and concurrency tests;
- correction, retention, export and deletion tests;
- safe logging/audit and prompt-injection/SSRF tests where applicable;
- accessible loading, empty, partial, stale, error, forbidden and disabled UI states;
- mobile result/detail/promotion review; and
- measurements for source trust, useful match rate, duplicate burden, latency, cost
  and accepted-promotion rate.

Live-provider credentials must never be required for the normal suite.

## Later dependencies that do not block WO-026

- A selected Gmail or Outlook execution path gates live WO-029 outreach, not research.
- Salesforce expansion belongs to WO-042 unless customer evidence changes priority.
- Native CRM, analytics, targets, forecast, manager views, coaching and win/loss need
  later lifecycle/history and do not alter the research trust boundary.
- Provider-assisted Ask synthesis may be evaluated from observed questions; it is not
  required for research retrieval or promotion.

## Engineering decision

Authorise WO-026 planning against the existing modular-monolith architecture. Add the
smallest tenant-owned research/evidence/promotion model in that work order, reuse the
existing provider and worker foundations, and preserve reviewed promotion into
canonical truth. Do not add a microservice, datastore, generic agent runtime, broad
integration framework or pre-emptive Core migration.
