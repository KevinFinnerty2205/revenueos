# Target-environment preflight checklist

Status: **WAITING FOR TARGET**. Run this from the immutable API release with platform-injected secrets. Use synthetic data only. Store the content-safe output in the restricted launch record, not in the repository.

## Evidence header

Record target name, hosting project/account, region, public web/API origins, release SHA/image IDs, PostgreSQL service/version, runtime role name, migration role name, object-storage service/region, backup service, log destination, approved feature-profile revision, CRM mode, AI profile, operator and UTC start/end times. Never record database URLs, keys, bearer tokens, signed URLs or customer content.

The shell examples use non-secret public-origin variables. Database URL variables must be injected by the platform secret manager, not typed into shell history.

```sh
export REVENUEOS_TARGET_WEB_ORIGIN='https://app.example.invalid'
export REVENUEOS_TARGET_API_ORIGIN='https://api.example.invalid'
export REVENUEOS_TARGET_API_HOST='api.example.invalid'
export REVENUEOS_TARGET_DB_HOST='db.example.invalid'
```

## Required proofs

| # | Gate | Executable check | PASS condition |
| --- | --- | --- | --- |
| 1 | Deployment exists | `curl --proto '=https' --tlsv1.2 --fail --silent --show-error "$REVENUEOS_TARGET_WEB_ORIGIN" >/dev/null` and `curl --proto '=https' --tlsv1.2 --fail --silent --show-error "$REVENUEOS_TARGET_API_ORIGIN/health/live"` | Web responds successfully; API returns product-safe live status for the intended release |
| 2 | HTTPS/public origin | `openssl s_client -connect "$REVENUEOS_TARGET_API_HOST:443" -servername "$REVENUEOS_TARGET_API_HOST" </dev/null 2>/dev/null | openssl x509 -noout -subject -issuer -dates` and repeat for the web host | Valid, unexpired certificate for each public host; no HTTP-only or localhost origin; HTTP redirects to HTTPS |
| 3 | Clerk production configuration | Run `revenueos-operations production-preflight`; then inspect the Clerk instance dashboard | Preflight starts only with Clerk mode, mock auth off and complete issuer/audience/JWKS; dashboard identifies the intended production instance and invite policy |
| 4 | Callback/origin configuration | Complete one synthetic sign-in and sign-out from the public origin; inspect Clerk allowed origins, redirect/callback URLs and web/API CORS values | Exact HTTPS origins only; no wildcard, localhost or unexpected callback; successful round trip |
| 5 | Runtime PostgreSQL role | `psql "$REVENUEOS_TARGET_RUNTIME_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user;"` | `rolsuper=false` and `rolbypassrls=false` |
| 6 | Separate migration role | Run the same query through `REVENUEOS_TARGET_MIGRATION_DATABASE_URL`, then `test "$(psql "$REVENUEOS_TARGET_RUNTIME_DATABASE_URL" -XAtc 'SELECT current_user')" != "$(psql "$REVENUEOS_TARGET_MIGRATION_DATABASE_URL" -XAtc 'SELECT current_user')"` | Roles differ; only the guarded migration job receives migration credentials; runtime cannot create/alter schema or roles |
| 7 | Database TLS | `psql "$REVENUEOS_TARGET_RUNTIME_DATABASE_URL" -X -v ON_ERROR_STOP=1 -c "SELECT ssl, version, cipher, bits FROM pg_stat_ssl WHERE pid=pg_backend_pid();"` | `ssl=true`; protocol/cipher comply with the hosting decision and current platform policy |
| 8 | Private durable file storage | `revenueos-operations production-preflight` | `private_object_storage=pass`; bucket/container blocks public access, uses tenant-prefixed private keys and durable storage—not local ephemeral disk |
| 9 | Storage backup | Inspect the storage provider backup/versioning schedule and run the named restore drill | Backup is enabled, access-restricted and retention-aligned; an object is actually restored and checksum-matched |
| 10 | Encryption keys | `revenueos-operations production-preflight` plus secret-manager inventory review | A 32-byte decoded backup key and deployment-specific storage signing key exist; storage/database/backup encryption is enabled; named owners and rotate/revoke procedures exist |
| 11 | Debug disabled | Start/preflight under the deployed configuration and inspect structured logs | `API_LOG_LEVEL` is not `DEBUG`; no stack trace or debug toolbar; product errors expose safe code/message/request ID only |
| 12 | Mock providers disabled | Compare preflight feature/provider output with the signed profile and run the disabled-path smoke tests | Mock auth/connectors are off; Prospect is off; no customer-content capability can surface deterministic mock output; enabled external AI paths use only the approved provider/model |
| 13 | Demo/JIT provisioning disabled | Inspect the deployed secret/config record and attempt login with an unprovisioned synthetic Clerk organisation | `API_IDENTITY_JIT_PROVISIONING_ENABLED=false`; unprovisioned organisation/user fails closed; demo seed is not scheduled or exposed |
| 14 | Allowed hosts/origins | `curl -fsS -H 'Host: unapproved.example.invalid' "$REVENUEOS_TARGET_API_ORIGIN/health/live" -o /dev/null -w '%{http_code}\n'` and inspect production configuration | Unapproved host is rejected; configured host/CORS lists equal the approved HTTPS origins with no wildcard/local value |
| 15 | Worker configured | Verify supervisor status; run `revenueos-operations queue-status --organisation-id <synthetic-tenant-uuid>`; process one permitted synthetic job if the profile has a worker-backed capability | API and worker use the same release/runtime role; supervisor restarts it; no stale lease; synthetic work completes once; SIGTERM stops new claims |
| 16 | Health/readiness | `curl --proto '=https' --tlsv1.2 --fail --silent --show-error "$REVENUEOS_TARGET_API_ORIGIN/health/ready"` | HTTP 200 and every product-safe component state is ready; no secret/content in response |
| 17 | Feature flags | `revenueos-operations production-preflight > preflight.json`; `jq -e '.status == "ready" and ([.checks[] | select(.status != "pass")] | length == 0)' preflight.json`; `jq -S '.featureFlags' preflight.json > actual-feature-flags.json`; `diff -u approved-feature-flags.json actual-feature-flags.json` | Preflight ready, all checks pass and exact flags equal the owner/partner-approved profile |
| 18 | Content-safe operational logs | Exercise synthetic canaries through login, CRUD, import, support, Create and one safe failure; export the time-bounded log slice; run `if rg -n 'CANARY_TRANSCRIPT_|CANARY_CSV_|CANARY_EMAIL_|CANARY_PROMPT_|Authorization:|Bearer |token=' target-logs.jsonl; then exit 1; fi` | No canary content, auth material, signed query, CSV cell, transcript, prompt, email body, document text or provider payload appears; request IDs remain searchable |

Also verify web/API security headers:

```sh
curl --proto '=https' --tlsv1.2 --silent --show-error --dump-header - \
  --output /dev/null "$REVENUEOS_TARGET_WEB_ORIGIN"
curl --proto '=https' --tlsv1.2 --silent --show-error --dump-header - \
  --output /dev/null "$REVENUEOS_TARGET_API_ORIGIN/health/live"
```

PASS requires the approved CSP plus clickjacking, MIME, referrer, permissions and no-store controls, and edge HSTS after HTTPS is confirmed. Record headers without cookies.

## Canonical production preflight

```sh
revenueos-operations production-preflight > preflight.json
jq -e '.status == "ready"' preflight.json
```

The command proves migration `0050_real_data_operations`, non-superuser/non-`BYPASSRLS` runtime role, transaction-local tenant reset, private object write/read/delete, owner-only durable export storage, real-data mode and configured approval/support references. It does not prove Clerk dashboard policy, managed backups, monitoring, legal approval or partner consent.

Any failed or unexecuted row blocks data entry. Attach the completed Clerk, RLS, backup/restore, monitoring and offboarding evidence before changing this checklist to `PASS`.
