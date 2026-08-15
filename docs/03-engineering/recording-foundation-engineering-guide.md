# Recording foundation engineering guide

**Status:** Current WO-015 implementation. Browser-first batch capture only.

WO-017 adds an `imported_audio_recording` browser client for completed phone
Interactions and a required controlled `recording_source`. It reuses every lifecycle,
storage, quota, consent and transcription boundary in this guide.

## Boundary

Recording is an optional Interaction Capture Session. AI Debrief, Voice Journal,
Visual Evidence and manual transcript capture continue to work when recording is
disabled, refused, unsuitable or unsupported. WO-015 adds no native application,
background guarantee, meeting bot, telephony, online-meeting connector, live
transcription, live coaching or biometric speaker identification.

## Architecture

1. The authenticated browser creates an explicitly consented Recording Session.
2. `MediaRecorder` emits bounded chunks using feature-detected WebM/Opus or MP4.
3. The API creates exact-object short-lived upload grants. The browser receives no
   storage credential or freely chosen key.
4. Chunk completion verifies size and SHA-256. Out-of-order verified chunks are
   resumable; finalisation requires a contiguous manifest.
5. Finalisation moves the durable Recording Session to `uploaded`.
6. The existing worker assembles the ordered source on bounded temporary disk,
   verifies every object, calls the focused `TranscriptionProvider`, persists one
   immutable transcript version and ordered segments, then removes the temporary
   file.
7. The Meeting current-transcript compatibility row points existing Meeting
   Intelligence at the final version. Automatic generation is separately flagged.

No raw audio blob is stored in PostgreSQL. The storage port is the existing hardened
private binary-object implementation shared with Visual Evidence.

## Models

- `recording_sessions`: lifecycle, consent state, safe provider trace, limits,
  retention/deletion state and transcript-version pointer; never transcript text.
- `recording_consents`: notice version, method, authority attestation, actor and
  acknowledgement time; never free-form legal text.
- `recording_chunks`: tenant/session/sequence, size, checksum, opaque key and upload
  state.
- `recording_usage_counters`: tenant/day byte and transcription use.
- `transcript_versions`: immutable transcript history, source and recording trace.
- `transcript_segments`: immutable ordered time ranges, optional neutral speaker
  labels and text.

All six new tables carry organisation scope, tenant-composite relationships,
indexes, forced RLS and lifecycle/shape constraints. Migration
`0025_recording_transcription` backfills existing current transcripts into version
history and supplies a safe downgrade/re-upgrade path.

## Limits and flags

Defaults are five active recordings per organisation, three hours, 512 MiB total,
8 MiB per chunk, 4,096 chunks, 1 GiB upload bytes/day, 600 transcription minutes/day,
25 requests/day, two simultaneous transcriptions and three attempts. Sessions
expire after 24 hours. The optional OpenAI adapter also applies its 25 MB
single-request ceiling before external processing; mock/local ingestion remains
bounded by the 512 MiB platform limit. Flags default off:

- `API_FEATURE_RECORDING_CAPTURE_ENABLED`
- `API_FEATURE_TRANSCRIPTION_ENABLED`
- `API_FEATURE_AUTO_GENERATE_INTELLIGENCE_AFTER_TRANSCRIPTION`

The server is authoritative; the browser cannot override flags or quotas.

## Idempotency

Session creation, lifecycle actions, chunk creation/completion and finalisation take
idempotency keys. Unique tenant/session/sequence and checksum constraints make
duplicate upload safe. The worker locks a session, records attempts and checks for
an existing recording transcript version before persisting; retries therefore do
not append duplicate transcript versions.

## Observability

Events contain opaque IDs, lifecycle, byte/duration/segment counts, attempt and safe
error code only. Audio, transcript text, signed URLs, object keys, customer names,
filenames and raw provider payloads are prohibited from logs and audit metadata.

## Related guides

- [Lifecycle](recording-lifecycle-guide.md)
- [Resumable upload](chunk-resumable-upload-guide.md)
- [Transcription provider](transcription-provider-guide.md)
- [Consent](recording-consent-guide.md)
- [Retention and deletion](audio-retention-deletion-guide.md)
- [Security review](recording-security-review.md)
- [Reconciliation runbook](recording-storage-reconciliation-runbook.md)
