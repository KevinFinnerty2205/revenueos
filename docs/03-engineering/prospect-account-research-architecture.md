# Prospect Account Research architecture

**Status:** Current WO-026 implementation

WO-026 stays inside the existing FastAPI/Next.js modular monolith and PostgreSQL
worker process. It adds no service, datastore, message broker or general web agent.

## Domain and persistence

Migration `0035_prospect_research` adds:

- `organisation_module_entitlements` for the tenant Prospect switch;
- `prospect_usage_counters` for atomic user/organisation daily quota use;
- `prospect_research_targets` for unpromoted company identity;
- `prospect_research_runs` for immutable, versioned execution history;
- `prospect_research_sources` for bounded source metadata;
- `prospect_research_observations` for structured findings; and
- `prospect_research_observation_sources` for validated many-to-many citations.

It also adds `companies.normalized_domain` and a tenant/domain lookup index. The
Company index is intentionally not unique because historical Core data permits
duplicates. Promotion locks the unique organisation/domain Research Target and
chooses the oldest exact-domain Company deterministically; concurrent promotion
therefore cannot create another Company through this path.

Every new tenant table carries `organisation_id`, composite tenant foreign keys,
explicit organisation predicates and forced PostgreSQL RLS. The runtime role does
not bypass RLS. Promotion relationships cannot cross tenant boundaries.

## Services and worker

Thin `/api/v1/prospect` routes call `ProspectService`, which owns entitlement,
quota, idempotency, lifecycle and promotion policy. `ProspectRepository` owns
tenant-filtered persistence. `ProspectResearchProvider` is a strict provider-neutral
protocol; provider-specific payloads do not enter the API contract.

Initial research has a deterministic fingerprint idempotency key, and a caller key
can deduplicate retries. A target row lock prevents simultaneous active runs. Fresh
initial results are reused for the configured freshness window. Explicit Refresh
always creates a new run unless one is already active and references the prior
usable run.

The existing worker discovers eligible organisations through a narrow
security-definer function, establishes transaction-local tenant context and claims
one run using `FOR UPDATE SKIP LOCKED`. Bounded leases permit stale-run recovery.
States are `pending`, `fetching`, `synthesizing`, `completed`, `partial` and
`failed`; the customer contract maps these to pending, researching, ready, partial
or failed. Revoked entitlement or production mock configuration fails closed at
both enqueue/access and worker execution boundaries.

Sources and observations are written only after strict provider-result validation.
The most recent completed/partial run remains the current brief if a newer refresh
fails. Change comparison uses stable observation keys to report new, changed and no
longer supported findings without mutating earlier runs.

## API surface

- `GET /prospect/availability`
- `PATCH /prospect/admin/entitlement`
- `GET /prospect/companies/search?q=…`
- `GET|POST /prospect/research`
- `GET /prospect/research/{target_id}`
- `POST /prospect/research/{target_id}/refresh`
- `POST /prospect/research/{target_id}/promote`
- `DELETE /prospect/research/{target_id}`
- `GET /prospect/accounts/{company_id}/research-link`

All routes require authenticated, active tenant membership. OpenAPI/Pydantic remains
the source of truth and `packages/shared` mirrors only client-facing contracts.
