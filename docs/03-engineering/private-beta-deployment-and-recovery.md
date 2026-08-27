# Private beta deployment, backup, restore and rollback

## Supported architecture

Deploy one immutable release as five components:

1. Next.js web service exposed over TLS. It receives only public web
   configuration and the server-side Clerk secret; it has no database or
   OpenAI credential.
2. FastAPI service exposed over TLS. It verifies Clerk tokens and uses a
   least-privilege PostgreSQL application role that cannot bypass RLS.
3. Independently supervised `revenueos-ai-worker` process using the same image,
   API configuration and application database role.
4. Private S3-compatible object storage with tenant-prefixed keys, encryption,
   blocked public access and least-privilege API credentials.
5. Managed PostgreSQL with encryption at rest/in transit, a separate guarded
   migration role and encrypted automated backups.

Use the platform secret manager. Do not put secrets in build arguments,
frontend/public variables, deployment logs, screenshots, shell history or the
repository. Restrict web/API origins explicitly. SQLite and mock identity are
not production options.

## Release procedure

1. Confirm the immutable commit and dependency/secret scans passed.
2. Confirm production customer data prohibition and approved design-partner
   list with the incident owner.
3. Confirm an encrypted backup exists and the latest restore drill passed.
4. Stop new worker claims or scale the worker to zero when the migration plan
   requires it; allow active bounded jobs to finish or recover by lease.
5. Run `alembic upgrade head` exactly once with the migration role.
6. Verify the database reports Alembic head `0026_face_to_face_companion` and
   drift check passes.
7. Deploy API, then confirm `/health/live` and `/health/ready` are green.
8. Start the worker only after readiness confirms migration/config compatibility.
9. Deploy the web service, confirm Clerk sign-in/organisation selection and run
   the synthetic Playwright journey.
10. Verify safe structured logs, tenant isolation, retention configuration,
    quotas, visual reconciliation and feature flags. Keep OpenAI off unless explicitly approved.

Do not perform a migration from every replica. One controlled release job owns
it. API and worker must use the same release because prompt/schema registries,
job contracts and persisted artefacts must agree.

## Production configuration review

Use the package `.env.example` files only as variable inventories. Required
production decisions include:

- `API_ENVIRONMENT=production`, `API_AUTH_MODE=clerk`,
  `API_MOCK_AUTH_ENABLED=false`;
- PostgreSQL URL for the non-bypass runtime role and a separate migration URL;
- exact Clerk JWKS URL, issuer and API audience; restricted sign-up,
  organisation creation and invitations;
- explicit TLS web/API URLs and CORS origins;
- data-notice version, default retention, transcript/generation/provider/visual limits,
  retry/timeout limits and restricted export directory;
- feature flags, with OpenAI, Engage Events and organisation deletion off initially;
- server-only OpenAI key/model only after approval;
- private S3-compatible visual endpoint/bucket/region/credentials, a
  deployment-specific signing secret and short signed-URL lifetime; and
- central JSON log sink, alert routes and named incident contacts.

Never expose `CLERK_SECRET_KEY`, database credentials or `OPENAI_API_KEY` as
`NEXT_PUBLIC_*`.

## Retention schedule

Invoke the tenant-scoped retention command daily for each approved
organisation. Always run/report dry-run counts before the destructive command
during initial rollout or after policy/config changes. Repeat bounded batches
until empty. Run expired-export purge at least hourly or immediately after a
support download completes. Alert on non-zero exit, repeated eligible counts,
unexpected record totals or missing organisation context.

## Backup policy

Recommended private-beta baseline:

- encrypted PostgreSQL snapshots at least daily with point-in-time recovery
  when the provider supports it;
- 14-day backup retention, reviewed against the selected product retention
  policy so backups do not become an undocumented indefinite archive;
- tightly restricted backup/migration principals separate from runtime;
- provider-side audit logging and tested restore access; and
- no copying production backups to a laptop or general developer environment.

Apply the same retention classification to private visual objects. Verify that
object-versioning or provider backups cannot silently outlive the declared
retention period, and exercise tenant-scoped object/row reconciliation during
restore drills.

Provider-agnostic logical backup shape (supply secrets through the platform,
not the command line):

```text
pg_dump --format=custom --no-owner --no-acl --file=<encrypted-restricted-path> <migration-database-url-from-secret-manager>
```

Prefer managed snapshots/PITR for normal recovery; use logical backup for a
portable validation artefact when approved. Encrypt the destination and delete
it according to the backup retention schedule.

## Restore drill

Restore only into an isolated, access-restricted non-production validation
database. Production content must never enter a local developer environment.

1. Record backup ID, source release, operator and authorisation without customer
   content.
2. Create an empty isolated PostgreSQL database and non-bypass validation role.
3. Restore using the managed provider workflow or:

   ```text
   pg_restore --clean --if-exists --no-owner --no-acl --dbname=<validation-url-from-secret-manager> <encrypted-backup-path>
   ```

4. Verify `alembic current`, then apply only the target release's compatible
   migration if the drill explicitly includes forward migration.
5. Run migration drift, forced-RLS and tenant-isolation tests against the
   restored database.
6. Verify append-only triggers, current notice/settings, counts and
   `/health/ready` without enabling OpenAI. Reconcile visual rows and private
   object keys without printing filenames, labels or signed URLs.
7. Record recovery time/objective result and discrepancies using metadata only.
8. Securely destroy the validation database and temporary backup copy.

Run the drill before launch and at least quarterly during the beta, and after a
material database/hosting change.

## Rollback

Prefer application rollback over database downgrade:

1. Contain the cause: turn the affected feature flag off; for provider issues,
   set `AI_PROVIDER=mock` and disable the OpenAI feature flag.
2. Stop worker claims if persisted contract compatibility is in doubt.
3. Re-deploy the last validated API, worker and web release together.
4. Verify its supported migration range before starting processes.
5. Check liveness/readiness, one synthetic tenant journey and safe logs.

Migration `0020_private_beta_readiness` adds identity mapping/status and the
seven forced-RLS beta tables, converts any historical `manager` membership to
`member`, and changes Revenue Brain append-only functions to permit only the
approved tenant-scoped maintenance deletion context. Its downgrade deletes all
beta notice, onboarding, settings, usage, feedback, request and safe-event
metadata, discards user/membership disabled state and organisation external-auth
mapping, and cannot reconstruct historical `manager` roles. Do not downgrade
without a backup, explicit data-loss approval and a release that understands
the prior schema.

Migration `0021_interaction_foundation` then adds the four forced-RLS
Interaction metadata tables and deterministic one-to-one Meeting link. Its
downgrade preserves Meeting, Meeting Intelligence and Revenue Brain records but
deletes standalone Interactions, Evidence, Capture Sessions and Interaction audits.
Prefer application rollback on the forward schema; obtain explicit data-loss
approval before schema downgrade.

Migration `0024_visual_evidence` adds forced-RLS visual metadata and candidates,
review guards, source-lineage constraints and visual snapshot support. Its
downgrade deletes visual rows and cannot recover already-deleted private image
objects. Prefer application rollback with `visualEvidence` and
`presentationMode` disabled; require a backup and explicit data-loss approval
before downgrade.

Migration `0025_recording_transcription` adds six forced-RLS recording/transcript
tables, transcript-history backfill and worker discovery. Its downgrade deletes
recording consent/manifests, transcript history and segments but cannot remove
external objects. Prefer application rollback with all recording flags disabled;
reconcile/export/delete objects and require backup plus explicit data-loss approval
before downgrade.

If a forward migration partially fails, keep API/worker stopped, preserve the
database, inspect the exact Alembic state with the migration role and follow the
migration-failure runbook. Never edit the version table manually to make
readiness green.

Migration `0032_integration_execution` adds six forced-RLS simulation tables,
immutable execution/audit guards and worker discovery. Roll back the application
with the three WO-022 flags disabled where possible. Its downgrade permanently
deletes connection/execution/mock metadata; no provider-side rollback exists or is
needed because the work order performs no external action.
