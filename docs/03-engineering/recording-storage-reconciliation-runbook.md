# Recording storage reconciliation runbook

Use the worker CLI `recording-reconcile --organisation-id <uuid>` for one trusted
organisation. Run without repair first; add `--repair` only after reviewing counts.
Use `recording-retention --organisation-id <uuid>` for raw-audio expiry. Commands
emit metadata counts/opaque IDs only.

## Checks

- database chunk row whose object is missing;
- object under the tenant recording prefix without a matching row;
- expired unfinalised, cancelled or terminally failed session;
- expired pending chunk;
- object-first deletion retry.

## Procedure

1. Confirm release SHA, migration `0025_recording_transcription`, worker/API parity,
   trusted organisation ID and private storage connectivity.
2. Disable recording capture for the affected tenant/release if new writes could
   race repair.
3. Run report-only reconciliation and record counts, safe codes and opaque IDs.
4. For missing objects, preserve the database row/failure state; do not fabricate a
   receipt or mark transcription complete.
5. For orphans older than the safety threshold, run repair to delete only objects
   under the exact tenant prefix.
6. Retry `deletion_pending`/`delete_failed` objects. Do not remove relational rows
   until every object deletion succeeds.
7. Run report-only again. Expected missing/orphan/retry counts are zero; verify a
   synthetic tenant read cannot see another tenant.
8. Re-enable only after backlog age, storage errors and worker processing are stable.

Never inspect/download audio for diagnosis, print signed URLs/keys, broaden a prefix,
or mark a transcript successful manually. Escalate tenant mismatch, unknown object
prefix, repeated delete failure or suspected public access to the security owner.
