# Online Meeting Capture guide

**Status:** WO-018 current implementation.

Online meetings are first-class Interactions across Microsoft Teams, Zoom, Google
Meet and `other`. RevenueOS prepares the seller before the meeting, remains passive
while the user attends in the normal meeting platform, then offers only the capture
paths the server says are available.

## Lifecycle

### Before

The existing Pre-Interaction Brief supplies the linked opportunity, stakeholders,
objectives, commitments, risks, questions, desired outcome and recent Revenue Brain
change. A validated meeting reference produces an **Open Meeting** link. It is never
opened automatically or followed by the server.

### During

**Start meeting** records Interaction time and opens the responsive Companion. The
Companion can show elapsed time, controlled markers and Visual Evidence where
enabled. It remains passive: it does not join the call, run a bot, intercept system
audio or describe local microphone audio as complete meeting capture.

### After

**End meeting** opens **Capture this meeting**. Server capabilities determine
whether the user sees authorised recording import, transcript import, AI Debrief or
Voice Journal. **Finish for now** is always a valid outcome. Imported evidence uses
the established Recording/Transcript/Evidence pipeline and the same Meeting
Intelligence, Opportunity Workspace and Revenue Brain paths.

## Platform and capture labels

Platforms are normalised as `microsoft_teams`, `zoom`, `google_meet` or `other`.
Capture provenance is independent: `platform_recording`, `platform_transcript`,
`user_uploaded_recording`, `user_uploaded_transcript`, `native_integration`,
`meeting_bot`, `ai_debrief`, `voice_journal` or `manual_notes`. The bot value is
future-ready metadata only; no bot is implemented.

## Honest limits

- No desktop app, mobile app or browser extension is required.
- No system-audio capture, live transcription or live coaching is implemented.
- Platform artefacts depend on the customer's provider plan, policy and meeting
  settings.
- Import requires an authority attestation and external-processing acknowledgement.
- Speaker labels remain unverified labels; there is no biometric identification.
- Private-beta identity, consent, retention and external-provider launch gates still
  apply.
