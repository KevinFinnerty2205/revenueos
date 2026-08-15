# Browser Companion security and privacy review

## Scope reviewed

This review covers the WO-016 browser Companion orchestration, marker storage,
recording UI hardening, capture summary and Opportunity Workspace projection. It
inherits the WO-013 debrief, WO-014 visual and WO-015 recording controls.

## Controls

- Authentication derives organisation and membership server-side; no Companion
  request accepts a free organisation identifier.
- Every marker read/write contains an explicit organisation predicate and forced
  PostgreSQL RLS provides defence in depth.
- Marker types are allowlisted, have no free text, are immutable and are not
  logged as content or promoted to intelligence.
- Recording permission is requested only after capture choice, consent
  attestation and an explicit start action.
- A second active recording session for the same tenant Interaction is rejected
  with a safe conflict.
- Phone calls and online meetings cannot enter the Companion recording path.
- Stable chunk idempotency keys prevent retry duplication. Page-leave warning
  covers active and queued capture.
- Transcript bodies are not shown in the live Companion. Debrief gap-fill
  receives bounded semantic coverage categories, not raw transcript text.
- Markers are included in export version 7 and organisation deletion; soft
  deletion remains visible to metadata audit without exposing content.
- Opportunity capture status is a bounded metadata projection with no transcript,
  prompt, provider or storage identifiers.

## Residual risks and mitigations

| Risk                                  | Mitigation / accepted boundary                                                                       |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Device/browser suspends the tab       | Foreground-only copy, best-effort wake lock, page-leave warning, server chunk recovery               |
| Unsent memory chunk lost on reload    | Explicit limitation; no claim of durable offline capture                                             |
| Shared-device shoulder surfing        | Minimal DURING UI and no transcript body; device security remains the user’s responsibility          |
| User records without lawful authority | Explicit attestation and notice version; RevenueOS does not make jurisdictional legal conclusions    |
| Marker is mistaken for evidence       | Metadata-only schema, product labels, no automatic intelligence mutation                             |
| Duplicate tab starts another session  | Tenant-scoped active-session conflict in recording service                                           |
| Visual contains sensitive data        | Existing authorisation, private storage, metadata stripping, review, retention and deletion controls |

No covert capture, background recording, system-audio interception, call control,
native wake guarantee or automatic live intelligence is introduced.
