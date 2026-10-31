# Conversation experience capability status

**Reviewed:** 31 October 2026
**Scope:** PR #109 local implementation. No live provider, connector, email or
customer-data execution was performed.

The labels in this document are deliberately strict:

- **A — Implementation locally verified.** The implemented path ran against
  local services, deterministic transports or the stated real browser fixture.
- **B — Production adapter implemented; live activation/verification pending.**
  Adapter code exists, but credentials, provider calls and production approval
  remain outside this change.
- **C — Implementation missing.** A contract, deterministic double or UI copy
  does not count as the production execution path.
- **D — Native desktop work deliberately deferred.**

## Capability matrix

| Area                                                                  | Class | Evidence and exact boundary                                                                                                                                                                                                                                                                                 |
| --------------------------------------------------------------------- | ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Explicit conversation initiatives without an Opportunity              | A     | Tenant/RLS-scoped threads, explicit user assignment/correction, company/participant suggestions that never auto-assign, optimistic locks and audit events.                                                                                                                                                  |
| Current-conversation versus cumulative framework coverage             | A     | Only validated Interaction Intelligence snapshots from completed, non-deleted interactions in the confirmed thread are projected. Source conversation titles and dates remain visible; conflicting and stale states reuse the framework projection rules.                                                   |
| Preparation from approved knowledge and authorised history            | A     | Approved organisation knowledge plus the latest completed, non-deleted conversation in the confirmed thread; no company-wide fallback. First outbound calls and later confirmed-thread meetings receive different objectives/questions.                                                                     |
| Private live notes                                                    | A     | User-and-tenant private server workspace, explicit save, optimistic conflict protection, separate from enhanced notes; capture errors do not unmount or clear the field.                                                                                                                                    |
| Microphone-only browser recording                                     | A     | Explicit permission, one verified live audio track, chunk upload/finalisation and failure cleanup. Automated media tests use mocked tracks.                                                                                                                                                                 |
| Shared tab/display audio plus microphone                              | A     | Explicit `getDisplayMedia` then `getUserMedia`, audio-track presence check, Web Audio mixing, duplicate microphone suppression, audio-only recorder stream, track/device interruption handling. Actually verified only on Chrome 156.0.8078.74 on macOS 15.6 with a synthetic tab tone and fake microphone. |
| Authorised recording/transcript import                                | A     | Existing bounded upload/import, provenance and immutable transcript version paths remain available as alternatives.                                                                                                                                                                                         |
| Batch audio transcription orchestration                               | A     | Durable worker, bounded manifest assembly, idempotent final transcript/segments and deterministic provider fixtures.                                                                                                                                                                                        |
| OpenAI batch transcription adapter                                    | B     | Server-only adapter and safe error mapping exist; live key/model/region/cost/retention verification remains disabled.                                                                                                                                                                                       |
| Provider-neutral progressive transcription orchestration              | A     | Ordered and deduplicated audio segments, partial/final revisions, bounded buffering, cancellation, reconnect/resume and retry exhaustion are fixture-tested. It is an internal boundary, not a provider adapter or public route.                                                                            |
| Production progressive transcription adapter                          | C     | No paid/provider streaming transport has been selected or implemented. The narrow owner decision is whether to approve an evaluated realtime transcription provider and its privacy, region, cost and reliability boundary.                                                                                 |
| Deterministic contextual Live Intelligence                            | A     | Bounded progressive-text windows, ordered cursor, deduplication, approved brief objective/question context, conservative speaker attribution, repetitive-signal suppression and recoverable failure tests.                                                                                                  |
| OpenAI live-signal adapter                                            | B     | Strict non-retained Responses request (`store=false`, no tools), schema/source validation, durable per-session provider/acknowledgement binding and safe retry/failure mapping are implemented with fake transport tests. Live activation is off.                                                           |
| Final transcript to structured Interaction Intelligence               | A     | Final transcript persistence can request the existing ten source-aware intelligence jobs through the local deterministic worker path.                                                                                                                                                                       |
| User-started debrief to enhanced notes and follow-up                  | A     | Original personal answers remain private and separate; accepted reviewed items generate editable private enhanced notes and a review-only follow-up draft.                                                                                                                                                  |
| Automatic final transcript to a private debrief/enhanced-note draft   | C     | Not implemented. Automatically treating customer transcript content as the user's reported notes would cross the current provenance/review boundary.                                                                                                                                                        |
| Local briefing scheduling/outbox                                      | A     | IANA timezone scheduling, fingerprints, duplicate suppression, reschedule supersession, cancellation and exact-content preview are fixture-tested.                                                                                                                                                          |
| Google Workspace and Microsoft 365 calendar/email adapters            | B     | Production-capable OAuth/read/send/reconciliation adapters and durable sync workers exist. Live OAuth, calendar access and email execution remain off.                                                                                                                                                      |
| Due briefing-email delivery worker                                    | C     | The conversation briefing outbox is preview-only; no worker claims due rows or connects them to the provider email adapters.                                                                                                                                                                                |
| Native macOS/Windows capture, call detection, overlays and installers | D     | Deliberately deferred; the web product does not claim these capabilities.                                                                                                                                                                                                                                   |

## Browser verification record

The release fixture in
`apps/web/e2e/actual-browser-media/browser-audio.spec.ts` launched the installed
Google Chrome 156.0.8078.74 on macOS 15.6. Chrome auto-selected a controlled
local browser tab playing a low-volume Web Audio oscillator and supplied its
fake microphone device. The test verified one shared audio track, one microphone
track, non-zero energy from both, one mixed audio-only recorder track, no video
track in the recorder stream and a non-empty recorded blob.

Vitest media doubles separately cover permission denial, a display share with no
audio, unsupported APIs, duplicate microphone identity, source mute/end,
`devicechange`, stop and idempotent cleanup. Playwright product acceptance uses
mocked media for deterministic capture state and upload behaviour. Edge, Safari,
Windows, screen/system-audio sharing, mobile browsers and physical microphone
hardware were not actually verified in this change.

## Activation boundaries

The B items are not C merely because activation is off: their production adapter
code exists. They still require the existing owner, security/privacy, variable-cost,
credential, regional-processing and target-environment approvals before any live
call. No activation was performed here.
