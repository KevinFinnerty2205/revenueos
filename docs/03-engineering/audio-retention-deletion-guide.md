# Audio retention, export and deletion guide

Raw audio has a shorter policy than validated transcript evidence. The default raw
retention window is seven days after successful transcription plus the safety
window; it is never deleted before a completed transcript version exists. Recording
sessions, including cancelled and terminally failed sessions, expire after 24
hours when unfinished. Organisation policy still governs
transcripts, segments and derived evidence.

## Retention

`recording-retention` selects eligible completed recordings in bounded batches,
deletes every private chunk object first, marks chunk/object state, then retains the
metadata/transcript lineage required by policy. Failed object deletion leaves a
retryable state and never reports complete deletion. Abandoned sessions are cleaned
through reconciliation.

## Export

Export version 8 includes recording metadata and controlled phone-call source,
consents, a content-free chunk
manifest, transcript versions and ordered segments. Raw audio is excluded from the
synchronous archive and declared `excluded_manifest_only`; no signed URL, storage
key or provider request ID is exported. Version 8 also includes metadata-only
Companion markers without their internal idempotency keys. An authorised operator needing raw audio
must use a separately approved short-lived object workflow.

## Deletion

Interaction/organisation deletion first deletes recording objects. Database removal
then covers chunks, consents, Recording Sessions, transcript segments/versions,
current transcript/evidence links and usage rows in foreign-key-safe order. A
storage failure preserves retry state and blocks a false success. Backups and
external-provider expiry remain subject to the documented deployment/provider
policy; no instantaneous-erasure claim is made.
