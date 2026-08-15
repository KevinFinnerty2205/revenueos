# WO-015 — Recording & Transcription Foundation

## Outcome

WO-015 implements the shared optional browser-first recording foundation on
`feature/epic-8-wo-015-recording-transcription-foundation`. It adds explicit
recording consent, resumable private chunk upload, deterministic finalisation,
durable batch transcription, immutable transcript versions/segments and existing
Meeting Intelligence compatibility without a native app, broker, bot or telephony.

## Delivered

- migration `0025_recording_transcription` after single head
  `0024_visual_evidence`, including backfill, forced RLS and immutable history;
- Recording Session, Consent, Chunk, usage, Transcript Version and Segment models;
- WebM/Opus and MP4/M4A validation with three-hour/512 MiB/8 MiB/4,096 defaults;
- private tenant-scoped signed storage grants using the established binary adapter;
- server-authoritative flags, quotas, lifecycle and metadata-only observability;
- focused deterministic mock/optional OpenAI batch-transcription provider;
- existing worker integration with safe retry classes and duplicate-version guard;
- current Meeting transcript compatibility and optional flag-controlled intelligence
  handoff;
- object-first retention/deletion, export v6 and storage reconciliation;
- minimal accessible mobile-width browser UI with consent, permission,
  start/pause/resume/stop/cancel, retry, status, transcript and Debrief fallback;
- deterministic API, migration, tenant/RLS, privacy, component and Playwright tests.

## Deliberately out of scope

Native/background recording guarantees, screen-lock survival, meeting bots, Zoom,
Teams or Meet connectors, telephony/call interception, streaming/live transcription,
live coaching, biometric identification, billing and new infrastructure services.
Diarisation labels are optional and never mapped to a person automatically.

## Operational posture

All recording flags default off. Tests use deterministic local storage and mock
transcription; no real transcription/AI request is required. Production enablement
requires approved private S3-compatible storage, provider/privacy terms,
jurisdictional consent policy and browser-device validation. Raw audio retention is
seven days after verified transcription by default; export excludes raw audio and
internal object/provider trace.
