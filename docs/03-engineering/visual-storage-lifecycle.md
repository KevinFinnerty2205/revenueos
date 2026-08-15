# Visual storage lifecycle

## States

Objects move through `pending`, `available`, `missing`, `deletion_pending`, `delete_failed` and `deleted`. Analysis state is separate: upload, processing, review, completed, failed or deletion states. Database state never reports a deletion complete until object deletion succeeds.

## Retention and organisation deletion

Retention selects eligible tenant interactions, calculates dry-run counts, deletes their visual objects, then removes visual candidates/assets before Evidence and Capture Sessions. Any object-storage failure aborts database deletion. Organisation deletion follows the same object-first rule and remains retryable.

## Export

Export version 7 includes visual metadata, source ownership, review decisions and extracted candidate text. Internal storage keys, provider request IDs and signed URLs are excluded. Image bytes are omitted by default. `API_PRIVATE_BETA_EXPORT_VISUAL_IMAGES_ENABLED=true` includes base64 bytes only inside an already confirmed admin export; this setting requires separate privacy approval.

## Reconciliation

Run a metadata-only report:

```text
pnpm --filter @revenueos/api exec revenueos-beta-maintenance visual-reconcile --organisation-id <uuid>
```

Add `--repair` to mark missing database objects failed/excluded and delete unreferenced objects under that tenant prefix. Repair is idempotent. Investigate unexpected counts before repair; never manipulate the bucket by filename or broad prefix.
