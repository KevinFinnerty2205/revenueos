# Chunk and resumable-upload guide

## Protocol

1. Create/reuse a consented Recording Session.
2. For each emitted blob, calculate SHA-256 and request a chunk using sequence,
   byte size, checksum and idempotency key.
3. Upload bytes to the returned exact-object grant.
4. Complete the chunk with the same checksum.
5. List chunks after interruption and retry only missing/unverified sequences.
6. Stop and finalise with the declared last sequence, duration and final MIME.

Out-of-order receipt is accepted. `(organisation_id, recording_session_id,
sequence_number)` is unique. Repeating the same sequence/checksum is safe; changing
size/checksum conflicts. Completion verifies stored bytes. Finalisation locks the
session, rejects gaps, unverified objects, count/size mismatches, expiry and
unsupported MIME, then freezes the manifest for batch processing.

## Bounds

Defaults are 8 MiB per chunk, 4,096 chunks, 512 MiB total and three hours. WebM/Opus
and MP4/M4A are accepted. File extension is not authoritative; the worker verifies
the first header and every chunk checksum during streaming assembly. The API never
loads a multi-hour recording into memory.

## Grants and keys

Keys are opaque, random and server-derived under tenant/session scope. Local
development uses HMAC-signed relative URLs; production uses the existing private
S3-compatible adapter. Grants expire after five minutes by default, authorise one
object/direction and reveal no permanent credential. Logs exclude URLs and keys.

## Recovery limits

Verified chunks remain resumable until session expiry (24 hours by default).
Closing a tab, device lock or background suspension can interrupt browser capture;
RevenueOS does not promise background upload or local recovery after termination.
The maintenance command handles expired sessions, missing objects and orphans.
