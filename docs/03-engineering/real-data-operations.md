# Real-data production operations

This is the executable operator contract for WO-039C. It supplements the existing private-beta runbooks. It does not approve a target environment or partner by itself.

## Environment and identity boundary

Development/test may use clearly labelled mock auth and local storage. Production requires Clerk verification, PostgreSQL, explicit public HTTPS CORS origins, explicit allowed hosts, non-debug logging and `API_IDENTITY_JIT_PROVISIONING_ENABLED=false`. The API derives the organisation from the verified Clerk `org_id`; browser-supplied organisation identifiers never select tenant context. Missing organisations, users and memberships fail authentication. Disabled users/members fail access checks, and download/export grants re-check active membership.

Clerk bearer tokens are sent in the `Authorization` header rather than an application session cookie, so the API is not cookie-authenticated and does not add an unrelated CSRF token scheme. The web server's Clerk session cookie controls remain Clerk/deployment responsibilities: production evidence must verify Secure, HttpOnly, SameSite, expiry, logout and disabled-member behaviour. Callback/origin/host values are bounded by configuration. Public TLS remains an edge responsibility. After stable HTTPS is proven, the production-only `API_HSTS_ENABLED` and `ORYNTELA_HSTS_ENABLED` flags add a one-year HSTS header without `includeSubDomains`; the API and web also add CSP, frame, MIME, referrer, permissions and no-store headers.

## Production preflight

Run from the immutable API release with secrets injected by the platform:

```text
revenueos-operations production-preflight
```

The command exits non-zero unless typed configuration has already passed and it can
prove: current Alembic head `0061_manual_paid_credit_grant`; immutable 40-hex release identity; a runtime PostgreSQL role
that is neither superuser nor `BYPASSRLS`; transaction-local tenant context reset;
private object write/read/delete; tenant-scoped durable S3 export write/read/delete; real-data
flag; legal approval reference; and support address. Output contains safe feature
states and generic results only.

The migration role is separate. A production runtime-role sketch is:

```text
CREATE ROLE revenueos_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
GRANT CONNECT ON DATABASE revenueos TO revenueos_runtime;
GRANT USAGE ON SCHEMA public TO revenueos_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO revenueos_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO revenueos_runtime;
```

Apply equivalent default privileges with the migration owner. Verify them in the target platform; do not run migrations through the runtime role.

## Provisioning and member lifecycle

Provision only after owner approval. Keep idempotency/operator references non-secret and do not put a legal agreement, personal notes or credentials in them.

```text
revenueos-operations provision-organisation \
  --external-organisation-id <clerk-org-id> \
  --organisation-name <approved-name> \
  --timezone Australia/Sydney \
  --admin-external-user-id <clerk-user-id> \
  --admin-email <approved-business-email> \
  --admin-display-name <approved-name> \
  --idempotency-key <ticket-random-reference> \
  --operator-reference <operator-or-change-id> \
  --crm-mode native \
  --retention-days 90 \
  --confirm "PROVISION <clerk-org-id>"
```

The command creates a deterministic organisation/user identity, active first-admin
membership, Core commercial state plus any explicitly selected add-ons, Native CRM
configuration when requested, retention settings, onboarding state and content-free
immutable provisioning/commercial events. Native CRM itself is Core; select the CRM
add-on only for supported external CRM connector access. Repeating identical input
returns `already_applied`; reusing the key for different input blocks.

Add a verified Clerk user with `provision-member` and its printed exact confirmation. Role changes and disable/re-enable use the existing authenticated admin membership route so the decision remains visible to the tenant. Disable the Clerk membership/session first for emergency revocation, then disable Oryntela membership. Existing business history remains, active personal targets are archived and access/download grants fail on the next API request; already-issued JWTs remain valid only until Clerk revocation/expiry, so the target Clerk policy and measured maximum latency belong in partner evidence.

Run `tenant-preflight --organisation-id <uuid>` before access. It checks an active admin, Native CRM configuration and pipeline/import state without printing names or content.

Plan/trial changes are a separate support authority. Inspect first, then run
`commercial-start-trial`, `commercial-assign-plan` or `commercial-change-state` with
the returned lock version, exact confirmation, bounded operator reference and reason.
Organisation administrators have read-only commercial visibility and cannot use the
legacy module switches. See the exact commands and recovery rules in
[Commercial authority](commercial-authority.md).

## Exceptional cleared-funds Credit purchase

Normal customers continue to use card payment followed by verified automatic Credit
reconciliation. For an exceptional large negotiated purchase only, an authorised
deployment/support operator may use the WO-055 preview/execute CLI after independently
verifying exact cleared funds. **Never grant paid Credits against an unpaid invoice.**
There is no customer or tenant-administrator grant surface, and the operation does
not issue an invoice, establish credit terms, activate a provider or permit negative
Credits. Follow the exact [manual paid Credit grant runbook](manual-paid-credit-grant-runbook.md).

## Worker and support visibility

```text
revenueos-operations queue-status --organisation-id <uuid>
revenueos-operations support-bundle --organisation-id <uuid>
```

Queue status groups only state counts and expired-lease counts for AI, Prospect, Action execution, Campaign, Create template and Create presentation workers. The support bundle adds release-compatible migration/feature/tenant checks and declares `contentIncluded=false`. It excludes names, email, evidence, transcripts, prompts, values, recipient data, provider payloads, tokens and object keys.

Workers set transaction-local tenant context for every claim/execution path. On SIGTERM they stop claiming; in-flight work relies on lease/reconciliation rules. Never edit a job status or blindly retry `unknown_external_state`/`unknown_delivery_state`; use the existing reconciliation API after verifying provider state. Server flags are the kill switches. Stop/disable the affected worker and flag together when contracts may differ.

Public liveness is process-only. Readiness reports generic database, migration, auth, AI-provider and worker-configuration states. Deep role/storage checks belong to preflight so normal probes do not mutate storage. The worker exposes a private, content-free `/health` listener when `API_WORKER_HEALTH_PORT` is configured; it fails after the configured processing-loop staleness threshold so the platform can restart a wedged process. The database does not invent a global heartbeat when no job exists.

## Migration, backup and restore

Release sequence: approve change and encrypted checkpoint; stop new claims if needed; run `alembic upgrade head` once with the migration role; run drift check; start API; verify readiness/preflight; start matching workers; deploy web; run synthetic smoke. Prefer a forward fix/application rollback. A downgrade from `0050` deletes import/merge/provisioning metadata and removes `import_baseline` support; it requires explicit data-loss approval and a verified backup.

For production, back up PostgreSQL plus the configured private object namespace to the independent destination with:

```text
revenueos-backup create-remote
revenueos-backup verify-remote --backup-id <backup-id>
```

The tool uses `pg_dump --format=custom --no-owner --no-acl`, streams object payloads, records content-free SHA-256/count/release metadata, encrypts each payload with AES-256-GCM and authenticates the format-v2 manifest with a domain-separated HMAC-SHA256 key. The 32-byte key comes from `API_BACKUP_ENCRYPTION_KEY` and is exposed only to the dedicated job. Source/destination database and object credentials are passed through the job environment, never command arguments or manifest. Remote upload verifies size/SHA metadata, commits the manifest last, then downloads and cryptographically verifies the committed bundle before reporting success. Secret-manager configuration is backed up by its owner, not copied into this archive; maintain a separately controlled offline recovery copy of the encryption key.

Restore only to named isolated targets:

```text
revenueos-backup restore-remote \
  --backup-id <backup-id> \
  --confirm "RESTORE <backup-id> TO CONFIGURED NAMED TARGET"
```

Inject the target only as `API_BACKUP_RESTORE_TARGET_DATABASE_URL` from the operator's
secret manager so credentials do not appear in process arguments or shell history.
Source-database and source-storage fingerprints are blocked. Verification authenticates/decrypts archives, checks hashes/counts and rejects unsafe tar paths before restore. After restore: migrate to the intended release; run drift, runtime-role and RLS tests; reconcile object rows/checksums; verify app readiness and a synthetic tenant; then destroy the isolated targets. The application command supplements, not replaces, managed encrypted snapshots/PITR.

Internal beta objectives, pending deployment-owner approval, are a successful encrypted backup at least daily, a 14-day maximum retained backup window, RPO 24 hours and RTO four hours. These are internal goals, not contractual SLAs. A target-environment measured restore drill is mandatory before each partner and quarterly thereafter.

## Retention, export, deletion and offboarding

Use the existing `revenueos-beta-maintenance` commands. Always run tenant-scoped retention dry-run before execute and repeat bounded batches until zero. Preview-only CRM import metadata expires with the maintenance lifecycle; raw CRM CSV never exists in storage. Create, recording, visual and document rows coordinate private-object deletion according to their existing domain rules.

Organisation export contract v29 includes current customer-owned domains, content-free CRM import/merge/provision history and authorised Create object manifests. It excludes credentials, raw CSV, secrets, bearer grants, leases and provider payloads. In production, export archives stream through an ephemeral temporary file to a tenant-scoped private S3 object; download remains an authenticated API operation and grants expire after 24 hours. Binaries remain in the separately authorised private-file retrieval workflow. Generate/download before deletion when requested; verify schema/tenant, permission, expiry and cross-tenant denial.

Organisation offboarding is request → authority verification → optional export/file delivery → disable memberships → disconnect/revoke integrations → pause/cancel eligible work through supported lifecycle → exact-confirmation delete → verify rows, objects, grants, APIs/search/deep links and worker discovery → record metadata-only completion. Provider-revoke failure blocks a success claim and uses the existing retry/reconciliation state. Backups are inaccessible operational copies that expire under the approved window; deletion does not imply instantaneous removal from immutable snapshots.

## Secrets and providers

Secret inventory: Clerk server secret/JWKS configuration; runtime and migration database credentials; object-storage credentials/signing key; outreach suppression HMAC key; backup encryption key; connector credential master key; HubSpot client secret; OpenAI key when approved. All are server-side secret-manager values with named owner, expiry and tested rotate/revoke procedure. They are prohibited from source, frontend variables, logs, exports, support bundles and screenshots.

Connector ciphertext records carry a key version, but the current configuration exposes one master key. Therefore HubSpot remains disabled unless the target owner has an approved same-window reconnect/re-encryption and rollback procedure; no generic live rotation was added. OpenAI/customer-content paths remain disabled unless the approval flag, account/settings, data-flow disclosure, quota and partner feature decision are all recorded. No production provider call was introduced by WO-039C.

## Incident and privacy response

Authentication outage: disable access, verify Clerk/issuer/audience/clock and never enable mock. Database or migration outage: stop new writes/workers and do not bypass readiness. Storage outage: disable binary capabilities and preserve database reconciliation state. Backlog: use queue counts/leases, restart safely and do not edit states. Missing Create object: disable download/generation and use checksum reconciliation. Suspected tenant crossing is highest severity: stop affected traffic/writes, preserve safe logs, rotate relevant credentials, engage security/privacy/legal owners and assess notifications. Credential exposure: revoke first, identify by safe fingerprint, rotate, redeploy and scan.

Support uses request IDs, release SHA, opaque tenant/user/job IDs, state counts and safe error codes. Customer-content access is exceptional, explicitly authorised and recorded; raw dumps/CSV/transcripts/prompts never go into tickets. Legal counsel determines Privacy Act/NDB duties and timing for the actual incident—this runbook does not manufacture a statutory conclusion.
