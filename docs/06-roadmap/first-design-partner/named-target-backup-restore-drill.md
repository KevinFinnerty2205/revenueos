# Named-target backup and restore drill

Status: **WAITING FOR TARGET AND PARTNER**. This drill is mandatory before real data, quarterly during the supervised beta and after a material database/storage/hosting change. Use synthetic data only.

## Fixed drill identity

Record the exact deployment environment, named design partner, release SHA/images, feature profile, Native CRM mode, PostgreSQL service/version/region, source and isolated restore targets, object-storage service/buckets/regions, AI provider/model state, backup key version, operators and UTC start/end. The design partner name is context only; do not use their data.

Create must be exercised even if the partner will not receive the Create entitlement. Use a synthetic operator drill tenant on the same release and storage topology. If Create is disabled globally in the final profile, enable it only in an access-restricted synthetic drill window, complete generation/download/restore proof, disable it again, rerun production preflight and record the controlled variance. Do not mark the exact-profile gate passed until the launch reviewer accepts that record.

## Preconditions

- Owner-approved backup retention, RPO and RTO objectives are recorded. Repository starting objectives are daily backup, maximum 14-day backup retention, RPO 24 hours and RTO one business day; they are not contractual SLAs.
- Source and restore database/storage are access-restricted and demonstrably different.
- Backup encryption key is injected by the secret manager and not shared with ordinary runtime credentials.
- The isolated restore target has no route to partner/customer data and will be destroyed after review.
- One approved synthetic Create template is available; the repository's synthetic `simple-corporate-source.pptx` fixture is suitable if the release accepts it.

## Drill

### 1. Provision and populate

1. Provision one synthetic tenant and admin with `revenueos-operations provision-organisation`, Native CRM and an idempotency key.
2. Add representative Core data: at least 5 Accounts, 10 Contacts, 5 open Opportunities, Tasks/Actions, Interactions with deliberately synthetic text, reviewed synthetic Evidence, Pipeline stages, Targets and Forecast judgments.
3. Run `revenueos-operations tenant-preflight --organisation-id <uuid>` and require `status=ready`.
4. Upload, validate and approve the synthetic PPTX template through the ordinary Create admin workflow.
5. Generate one approved synthetic presentation attached to a synthetic Account/Opportunity. Record opaque template/presentation/version/object IDs only.
6. Request an authenticated one-time download, download the PPTX and verify it opens. Record its byte count and checksum:

   ```sh
   shasum -a 256 synthetic-create-generated.pptx
   ```

### 2. Back up and verify

Start the RPO clock at the last confirmed canonical/object write. Create the backup in an access-restricted encrypted destination:

```sh
revenueos-backup create --destination "$REVENUEOS_TARGET_BACKUP_ROOT" > backup-create.json
revenueos-backup verify --source "$REVENUEOS_TARGET_BACKUP_DIRECTORY" > backup-verify.json
jq -e '.status == "complete"' backup-create.json
jq -e '.status == "verified"' backup-verify.json
shasum -a 256 "$REVENUEOS_TARGET_BACKUP_DIRECTORY"/*
```

Record backup ID, UTC time, database archive checksum, object archive checksum, manifest checksum and object count. Confirm the manifest contains no names, content, keys, URLs or credentials. Also record the managed database snapshot/PITR and object-backup identifiers; the portable tool supplements rather than replaces provider backups.

### 3. Restore into an isolated target

Start the RTO timer immediately before restore. The portable command restores the database and authenticated object archive to an empty isolated directory:

```sh
revenueos-backup restore \
  --source "$REVENUEOS_TARGET_BACKUP_DIRECTORY" \
  --target-database-url "$REVENUEOS_RESTORE_DATABASE_URL" \
  --target-storage-directory "$REVENUEOS_RESTORE_STORAGE_DIRECTORY" \
  --confirm "RESTORE <backup-id> INTO <restore-database-name>" > restore.json
jq -e '.status == "complete"' restore.json
```

For an S3-compatible production topology, copy the verified restored object tree into an empty, private isolated validation bucket using the selected provider's checksum-preserving CLI, then configure the isolated API/worker to that bucket. Record the exact provider command in the launch evidence. Public access must remain blocked; do not reuse the source bucket.

Deploy the same API/worker/web release to the isolated target. Apply only compatible
migration `0054_credits_variable_cost` with the restore migration role, then run
migration drift and production preflight with the restore runtime role.

### 4. Reconcile and authorise

1. Compare selected canonical table counts and opaque IDs between source manifest and restore: organisations/memberships, Accounts, Contacts, Opportunities, stage events, Interactions, Evidence, Actions, Targets, Forecast, Create templates/presentations/versions/grants and import/merge metadata.
2. Reconcile every restored private object against recorded SHA-256 and size. Require zero missing, corrupt and unexpected objects.
3. Confirm the restored generated Create object checksum equals the pre-backup checksum.
4. Sign in as the restored synthetic admin through the isolated public route; request a new download grant; download the restored presentation; require a matching checksum and successful open.
5. Prove another synthetic tenant and a disabled member cannot obtain or consume that download grant. Confirm old/used/expired grants fail.
6. Run the complete [target RLS proof](target-RLS-proof-procedure.md) on the restored database and require forced RLS/non-bypass role after restore.
7. Run `/health/ready`, `tenant-preflight`, `queue-status` and a content-safe log scan.
8. Stop the RTO clock only when canonical data, objects, authorisation, RLS and readiness all pass.

### 5. Record objectives and clean up

```text
last recoverable write UTC:
backup captured UTC:
observed RPO:
restore start UTC:
service/data verification complete UTC:
observed RTO:
approved RPO/RTO objectives:
Create checksum before/after:
canonical count reconciliation:
object reconciliation:
RLS result:
secure restored download result:
overall result:
```

Disable/destroy the isolated web/API/worker, restore database, restored bucket/directory and synthetic tenant data after evidence approval. Delete temporary decrypted material immediately; retain only encrypted backup material under the approved retention schedule and content-safe evidence. Record deletion identifiers and the date immutable backup copies will expire.

PASS requires all 14 requested steps, including actual generated Create bytes, authenticated post-restore download, forced RLS and measured objectives. A checksum mismatch, unavailable Create download, unproved storage restore, failed RLS or missed RPO/RTO is an immediate launch pause.
