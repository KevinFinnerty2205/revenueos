# Online Meeting transcript import

**Status:** WO-018 current implementation.

`POST /api/v1/interactions/{id}/online-meeting/transcript` accepts one deliberate
UTF-8 TXT, WebVTT or SubRip source as pasted text or base64-encoded file content.
The server enforces the 512 KiB default byte ceiling, strict UTF-8 decoding, bounded
line/segment parsing and an explicit authority and external-processing
acknowledgement. It rejects missing, ambiguous, malformed, oversized and unsupported
inputs without logging content.

WebVTT/SRT timestamps become ordered immutable `transcript_segments`; speaker
prefixes are retained in labels only. The importer never maps a label to a Contact,
infers identity from voice or marks content customer-confirmed. TXT remains valid
without timestamps. Provenance distinguishes platform-generated, user-uploaded,
externally-generated and manually-pasted material.

A tenant-scoped idempotency key handles safe retry. A content fingerprint prevents
the same immutable content becoming another transcript version under a different
request key. Import creates the existing Meeting transcript compatibility row,
immutable version, segments, Capture Session and Evidence record, then leaves
intelligence generation to the existing orchestration endpoint—there is no parallel
AI pipeline or duplicate job creation.

Export v9 includes normalised import metadata and authorised transcript content.
Organisation deletion and existing Meeting retention remove local imports,
transcript versions/segments and derived evidence. The source platform artefact is
outside this local deletion boundary.
