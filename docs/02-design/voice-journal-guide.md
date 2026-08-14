# Voice Journal guide

Voice Journal is the fastest post-interaction capture path when the salesperson wants
to speak naturally instead of answering several prompts.

## User journey

1. Complete the Interaction and open its detail page.
2. Confirm that you are safely stopped. RevenueOS must never encourage capture while
   driving or operating equipment.
3. Choose Voice Journal. If microphone capture is supported, separately acknowledge
   that the short voice segment will be processed.
4. Start recording deliberately. The UI shows recording/paused state and elapsed
   time; pause, resume, stop and cancel remain explicit.
5. Review the transcription as a debrief answer. When microphone support, permission
   or transcription fails, use the visible typed fallback.
6. Finish, then edit, accept or reject every “Reported by you” candidate before the
   Interaction is updated.

## Product promises

- Recording never begins implicitly.
- Capture is foreground-only and the page must stay open.
- A segment stops at 120 seconds and is rejected above 8 MB.
- Cancelled or completed audio is discarded from browser memory; the API never
  stores raw audio.
- The visible source label is “Reported by you”. Voice does not make recollection
  customer-confirmed.
- Refresh restores the durable session, turns and review state, not an unfinished
  local audio buffer.

This is a short debrief aid, not resilient meeting recording. Background/locked-screen
capture, phone interception, customer recording, speaker diarisation and live
transcription are not supported.
