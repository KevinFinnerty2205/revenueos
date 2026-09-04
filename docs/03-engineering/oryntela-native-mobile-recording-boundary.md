# Oryntela native mobile recording boundary

- **Status:** Future candidate; validate first; not built or authorised
- **Last reviewed:** 4 September 2026

## Decision

Do not build a native mobile application solely to claim mobile parity or background recording. Consider native recording only if partner evidence shows that deliberate, consented in-person capture is a critical workflow that a browser cannot perform safely and reliably.

## Why the boundary exists

Mobile browsers cannot be assumed to preserve capture across screen lock, backgrounding, operating-system suspension, interruptions or resource pressure. Workarounds that pretend otherwise risk silent data loss, unexpected recording and poor consent visibility. A native application introduces ongoing security, privacy, platform, release and support obligations.

## Entry criteria

- Repeated field evidence that in-person capture materially improves sales follow-through.
- A documented alternative assessment covering manual notes, deliberate transcript paste, foreground web capture and approved conferencing sources.
- Supported operating systems and device lifecycle agreed.
- A deliberate start/stop flow with persistent, unmistakable recording indication.
- Authority and consent evidence appropriate to the participants and jurisdiction.
- Recovery behaviour for calls, notifications, screen lock, battery loss, offline use and application termination.
- Security, privacy, retention, export and erasure controls approved.
- A finite partner pilot and support model approved.

## Safety and data boundaries

- Never listen or record implicitly.
- Never disguise recording state.
- Show the exact meeting or context to which capture will attach.
- Encrypt local buffers and uploaded content; minimise on-device retention.
- Define whether capture continues through interruptions rather than relying on platform defaults.
- Make upload progress, failure, recovery and final deletion visible.
- Do not write recordings, transcripts or participant content to application logs.
- Keep organisation scope on storage paths, metadata and derived records.
- Treat the current deliberately supplied plain-text transcript path as distinct from recording.

## Candidate product flow

Deliberately arm → confirm context and consent → visibly capture → stop → verify upload → review transcript or notes → approve follow-through → apply retention and deletion policy.

No step should silently advance into outreach, CRM mutation or model training.

## Build decision

Professionalism alone is not evidence that a native app is needed. If the validated mobile job is preparation, note review, action completion or progress update, improve the focused web experience. If reliable background capture is indispensable and the full gate passes, authorise a separately scoped native work order with platform-specific threat modelling and test evidence.

## Related sources

- [Oryntela simplicity principles](../02-design/oryntela-simplicity-principles.md)
- [Oryntela Daily future state](../02-design/oryntela-daily-future-state.md)
- [End-to-end security and privacy](end-to-end-sales-platform-security-privacy.md)
