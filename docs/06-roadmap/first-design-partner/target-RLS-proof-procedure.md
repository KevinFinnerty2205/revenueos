# Target PostgreSQL RLS proof procedure

Status: **WAITING FOR TARGET**. Use synthetic tenants only. Run destructive integration tests in an isolated validation database on the actual target PostgreSQL service/region/version—not in a database that contains or may receive partner data.

## Preconditions

The validation database must use the exact release migration, PostgreSQL service class/settings and runtime-role grants intended for the partner. The guarded migration role may create the database schema and temporary test role; application/API/worker checks use the actual non-bypass runtime role. Record any unavoidable variance and treat it as a failure until the launch reviewer approves and the exact path is repeated.

## Record target facts

```sh
psql "$REVENUEOS_TARGET_RUNTIME_DATABASE_URL" -X -v ON_ERROR_STOP=1 <<'SQL'
SELECT clock_timestamp() AT TIME ZONE 'UTC' AS checked_at_utc;
SELECT version();
SELECT current_database(), current_user, rolsuper, rolbypassrls
FROM pg_roles WHERE rolname = current_user;
SELECT version_num AS alembic_head FROM alembic_version;
SELECT ssl, version AS tls_version, cipher, bits
FROM pg_stat_ssl WHERE pid = pg_backend_pid();
SQL
```

PASS requires head `0054_credits_variable_cost`, `rolsuper=false`,
`rolbypassrls=false`, TLS on and a recorded PostgreSQL version.

## All-table automated proof

With the validation database empty except for migration state:

```sh
DATABASE_URL="$REVENUEOS_TARGET_MIGRATION_DATABASE_URL" pnpm api:migrate
DATABASE_URL="$REVENUEOS_TARGET_MIGRATION_DATABASE_URL" \
  uv --directory apps/api run pytest -q \
  tests/test_rls.py::test_postgresql_rls_isolates_every_tenant_table
DATABASE_URL="$REVENUEOS_TARGET_MIGRATION_DATABASE_URL" \
  uv --directory apps/api run pytest -q tests/test_ai_worker_postgresql.py
```

Run from the immutable release. The first test deliberately creates and drops a restricted role and representative rows across every tenant table; the second exercises concurrent worker claim/recovery. The database must be disposable. PASS is zero skips and zero failures; record test output and duration without customer content.

## Operational runtime-role drill

1. Provision synthetic Tenants A and B with distinct admins through `revenueos-operations provision-organisation`.
2. Populate representative Accounts, Contacts, open Opportunities, Tasks, Interactions, Evidence, Actions, Pipeline/Targets/Forecast and—only when the approved profile enables it—Create metadata in both tenants.
3. Capture only the two organisation UUIDs and safe record UUIDs.
4. Connect as the actual runtime role. In separate transactions set `app.organisation_id` to Tenant A and prove Tenant B reads return zero/not found for representative tables and application routes.
5. Attempt a Tenant B insert/update/delete while Tenant A context is set. PASS requires an RLS/authorisation failure or zero affected rows and no mutation.
6. Begin with no tenant setting and prove tenant tables return zero rows and writes fail. Missing context must never default to a tenant.
7. On one pooled connection: verify context empty; set Tenant A transaction-locally and read A; commit; verify empty; set Tenant B and read B; commit; verify empty. Any residual value or A row in the B transaction fails.
8. Queue one permitted synthetic job for each tenant. Let one worker process/switch tenants. Verify each result is stored only under its claimed organisation, a wrong-tenant claim/read returns none and context is empty between claims.

Use this query before, during and after each transaction:

```sql
SELECT current_setting('app.organisation_id', true) AS tenant_context;
```

The canonical application-level reset check is also executed by:

```sh
revenueos-operations production-preflight > preflight.json
jq -e '.checks[] | select(.name == "database_tenant_context_reset") | .status == "pass"' preflight.json
```

## Required result record

```text
target/database:
PostgreSQL version:
runtime role:
superuser:
BYPASSRLS:
migration head:
TLS:
test started/completed UTC:
Tenant A cannot read B:
Tenant A cannot write B:
missing context fails:
pool reuse does not leak:
worker tenant switching does not leak:
all-table forced-RLS test:
overall result:
operator/reviewer:
```

Any failure is an immediate launch pause. Destroy both synthetic tenants and the isolated validation database after evidence review; retain content-safe results only.
