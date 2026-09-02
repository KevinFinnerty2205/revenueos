# Real-data production operations

This is the executable operator contract for WO-039C. It supplements the existing private-beta runbooks. It does not approve a target environment or partner by itself.

## Environment and identity boundary

Development/test may use clearly labelled mock auth and local storage. Production requires Clerk verification, PostgreSQL, explicit public HTTPS CORS origins, explicit allowed hosts, non-debug logging and `API_IDENTITY_JIT_PROVISIONING_ENABLED=false`. The API derives the organisation from the verified Clerk `org_id`; browser-supplied organisation identifiers never select tenant context. Missing organisations, users and memberships fail authentication. Disabled users/members fail access checks, and download/export grants re-check active membership.

Clerk bearer tokens are sent in the `Authorization` header rather than an application session cookie, so the API is not cookie-authenticated and does not add an unrelated CSRF token scheme. The web server's Clerk session cookie controls remain Clerk/deployment responsibilities: production evidence must verify Secure, HttpOnly, SameSite, expiry, logout and disabled-member behaviour. Callback/origin/host values are bounded by configuration. HSTS and public TLS remain edge responsibilities; the API and web add CSP, frame, MIME, referrer, permissions and no-store headers.

## Production preflight

Run from the immutable API release with secrets injected by the platform:

```text
revenueos-operations production-preflight
```

The command exits non-zero unless typed configuration has already passed and it can prove: current Alembic head `0050_real_data_operations`; a runtime PostgreSQL role that is neither superuser nor `BYPASSRLS`; transaction-local tenant context reset; private object write/read/delete; owner-only durable export directory; real-data flag; legal approval reference; and support address. Output contains safe feature states and generic results only.

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

The command creates a deterministic organisation/user identity, active first-admin membership, explicit CRM/add-on entitlements, retention settings, onboarding state and a content-free immutable provisioning event. Repeating identical input returns `already_applied`; reusing the key for different input blocks.

Add a verified Clerk user with `provision-member` and its printed exact confirmation. Role changes and disable/re-enable use the existing authenticated admin membership route so the decision remains visible to the tenant. Disable the Clerk membership/session first for emergency revocation, then disable RevenueOS membership. Existing business history remains, active personal targets are archived and access/download grants fail on the next API request; already-issued JWTs remain valid only until Clerk revocation/expiry, so the target Clerk policy and measured maximum latency belong in partner evidence.

Run `tenant-preflight --organisation-id <uuid>` before access. It checks an active admin, Native CRM configuration and pipeline/import state without printing names or content.

## Worker and support visibility

```text
revenueos-operations queue-status --organisation-id <uuid>
revenueos-operations support-bundle --organisation-id <uuid>
```

Queue status groups only state counts and expired-lease counts for AI, Prospect, Action execution, Campaign, Create template and Create presentation workers. The support bundle adds release-compatible migration/feature/tenant checks and declares `contentIncluded=false`. It excludes names, email, evidence, transcripts, prompts, values, recipient data, provider payloads, tokens and object keys.

Workers set transaction-local tenant context for every claim/execution path. On SIGTERM they stop claiming; in-flight work relies on lease/reconciliation rules. Never edit a job status or blindly retry `unknown_external_state`/`unknown_delivery_state`; use the existing reconciliation API after verifying provider state. Server flags are the kill switches. Stop/disable the affected worker and flag together when contracts may differ.

Public liveness is process-only. Readiness reports generic database, migration, auth, AI-provider and worker-configuration states. Deep role/storage checks belong to preflight so normal probes do not mutate storage. A supervisor/hosting heartbeat still must prove the worker process is alive; the database does not invent a global heartbeat when no job exists.

## Migration, backup and restore

Release sequence: approve change and encrypted checkpoint; stop new claims if needed; run `alembic upgrade head` once with the migration role; run drift check; start API; verify readiness/preflight; start matching workers; deploy web; run synthetic smoke. Prefer a forward fix/application rollback. A downgrade from `0050` deletes import/merge/provisioning metadata and removes `import_baseline` support; it requires explicit data-loss approval and a verified backup.

Back up PostgreSQL plus the configured private object namespace with:

```text
revenueos-backup create --destination <private-encrypted-backup-root>
revenueos-backup verify --source <backup-directory>
```

The tool uses `pg_dump --format=custom --no-owner --no-acl`, creates an object tar, records content-free SHA-256/count metadata, and streams each archive through AES-256-GCM. The 32-byte key comes from `API_PRIVATE_BETA_BACKUP_ENCRYPTION_KEY`; database credentials are passed through the child environment, never command arguments or manifest. The destination is owner-only. Secret-manager configuration is backed up by its owner, not copied into this archive.

Restore only to named isolated targets:

```text
revenueos-backup restore \
  --source <backup-directory> \
  --target-database-url <isolated-url-from-secret-manager> \
  --target-storage-directory <empty-isolated-private-directory> \
  --confirm "RESTORE <backup-id> INTO <target-database-name>"
```

Source-database and source-storage fingerprints are blocked. Verification authenticates/decrypts archives, checks hashes/counts and rejects unsafe tar paths before restore. After restore: migrate to the intended release; run drift, runtime-role and RLS tests; reconcile object rows/checksums; verify app readiness and a synthetic tenant; then destroy the isolated targets. The application command supplements, not replaces, managed encrypted snapshots/PITR.

Internal beta objectives, pending deployment-owner approval, are a successful encrypted backup at least daily, a 14-day maximum retained backup window, RPO 24 hours and RTO one business day. These are internal goals, not contractual SLAs. A target-environment measured restore drill is mandatory before each partner and quarterly thereafter.

## Retention, export, deletion and offboarding

Use the existing `revenueos-beta-maintenance` commands. Always run tenant-scoped retention dry-run before execute and repeat bounded batches until zero. Preview-only CRM import metadata expires with the maintenance lifecycle; raw CRM CSV never exists in storage. Create, recording, visual and document rows coordinate private-object deletion according to their existing domain rules.

Organisation export contract v29 includes current customer-owned domains, content-free CRM import/merge/provision history and authorised Create object manifests. It excludes credentials, raw CSV, secrets, bearer grants, leases and provider payloads. Binaries remain in the separately authorised private-file retrieval workflow. Generate/download before deletion when requested; verify schema/tenant, permission, expiry and cross-tenant denial.

Organisation offboarding is request → authority verification → optional export/file delivery → disable memberships → disconnect/revoke integrations → pause/cancel eligible work through supported lifecycle → exact-confirmation delete → verify rows, objects, grants, APIs/search/deep links and worker discovery → record metadata-only completion. Provider-revoke failure blocks a success claim and uses the existing retry/reconciliation state. Backups are inaccessible operational copies that expire under the approved window; deletion does not imply instantaneous removal from immutable snapshots.

## Secrets and providers

Secret inventory: Clerk server secret/JWKS configuration; runtime and migration database credentials; object-storage credentials/signing key; outreach suppression HMAC key; backup encryption key; connector credential master key; HubSpot client secret; OpenAI key when approved. All are server-side secret-manager values with named owner, expiry and tested rotate/revoke procedure. They are prohibited from source, frontend variables, logs, exports, support bundles and screenshots.

Connector ciphertext records carry a key version, but the current configuration exposes one master key. Therefore HubSpot remains disabled unless the target owner has an approved same-window reconnect/re-encryption and rollback procedure; no generic live rotation was added. OpenAI/customer-content paths remain disabled unless the approval flag, account/settings, data-flow disclosure, quota and partner feature decision are all recorded. No production provider call was introduced by WO-039C.

## Incident and privacy response

Authentication outage: disable access, verify Clerk/issuer/audience/clock and never enable mock. Database or migration outage: stop new writes/workers and do not bypass readiness. Storage outage: disable binary capabilities and preserve database reconciliation state. Backlog: use queue counts/leases, restart safely and do not edit states. Missing Create object: disable download/generation and use checksum reconciliation. Suspected tenant crossing is highest severity: stop affected traffic/writes, preserve safe logs, rotate relevant credentials, engage security/privacy/legal owners and assess notifications. Credential exposure: revoke first, identify by safe fingerprint, rotate, redeploy and scan.

Support uses request IDs, release SHA, opaque tenant/user/job IDs, state counts and safe error codes. Customer-content access is exceptional, explicitly authorised and recorded; raw dumps/CSV/transcripts/prompts never go into tickets. Legal counsel determines Privacy Act/NDB duties and timing for the actual incident—this runbook does not manufacture a statutory conclusion.
