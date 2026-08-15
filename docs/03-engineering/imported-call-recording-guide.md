# Imported-call recording guide

**Status:** Current WO-017 extension of the WO-015 Recording Session domain.

## Flow

1. A completed `phone_call` exposes **Add Recording** only as an import action.
2. The user selects WebM, MP4 or M4A, sees file metadata, supplies duration and
   chooses a controlled recording source.
3. The user attests that the recording is an authorised business interaction and
   that required participant notice or consent exists.
4. The browser creates `imported_audio_recording`, uploads 8 MiB checksummed chunks
   to tenant-derived private object grants and explicitly finalises the manifest.
5. The existing durable recording worker creates immutable transcript evidence and
   segments. A gap-fill debrief can reconcile unresolved material before reviewed
   Interaction Intelligence is composed.

There is no alternate uploader, public media URL, autoplay, synchronous provider
call or phone-specific transcription queue.

## Provenance

`recording_source` is required for non-live recordings and accepts only:

- `customer_call_recording`;
- `business_phone_recording`;
- `user_uploaded_recording`; or
- `external_provider_recording`.

This describes how the audio reached RevenueOS. It does not prove legality,
speaker identity or truth. Recording-derived transcript Evidence remains distinct
from reviewed `salesperson_reported` Debrief Evidence.

## Limits and recovery

The inherited allowlist and limits remain authoritative: 512 MiB total, 8 MiB per
chunk, 4,096 chunks and three hours. Session creation, chunk allocation/completion
and finalisation are tenant-scoped and idempotent. A duplicate sequence with a
different checksum fails. Partial or failed uploads remain recoverable through the
WO-015 manifest; they are never reported as complete.

The server-enforced recording and transcription feature flags, byte/minute/request
quotas and private-beta restrictions apply unchanged. Tests use local private
storage and deterministic mock transcription; they make no external provider call.
