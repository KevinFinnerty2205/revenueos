# Browser face-to-face Companion guide

## Current boundary

WO-016 adds a mobile-first browser Companion at
`/interactions/{interactionId}/companion`. It is a focused field surface over
the existing Interaction, Pre-Interaction Brief, recording, Visual Evidence,
AI Debrief and Revenue Brain foundations. It is not a native mobile app, meeting
bot, call recorder or live coaching system.

The surface follows the Interaction lifecycle:

| Phase  | Lifecycle     | Primary job                                                                            |
| ------ | ------------- | -------------------------------------------------------------------------------------- |
| BEFORE | `planned`     | Scan a 30-second brief and deliberately start                                          |
| DURING | `in_progress` | Choose recording or passive capture, then use only essential controls                  |
| AFTER  | `completed`   | Review capture status and fill evidence gaps through existing debrief and visual flows |

## BEFORE

The concise brief shows the interaction type and time, linked company and
opportunity names, participants when known, a headline, up to three objectives,
up to three questions, the highest current risk, next best action, most recent
change and first success criterion. `Open full brief` returns to the complete
source-aware preparation view.

`Start interaction` records the first actual start time and moves the
Interaction to `in_progress`. It does not request microphone permission, start
recording, take a photo or generate intelligence.

## DURING

For supported in-person types the user must choose `Record interaction` or
`Continue without recording`. The choice is retained only for the browser tab.
Recording remains consent-gated after the user selects it. Passive Companion is
recommended for executive lunches and is the only Companion mode offered for
phone calls and online meetings.

The passive state says `No recording or listening`. Its large controls are:

- Add photo;
- Add marker; and
- End interaction.

Recording adds pause/resume only when the browser supplies those operations,
elapsed time, microphone/connection state, upload state and safe stop/retry
controls. `End interaction` stays disabled while recording or an unsent audio
chunk can still affect finalisation.

Quick markers contain only a controlled type, creator, timestamp and optional
recording offset. They do not contain free text and never become intelligence
without a later reviewed evidence workflow.

## AFTER

The summary shows recording duration and transcription state, photo count and
marker count. The user can start the existing AI Debrief or Voice Journal, add
visual evidence, open the Opportunity Workspace or Revenue Brain, or finish.
The Companion does not render a scrolling transcript during or after capture.

When a completed direct recording transcript exists, the deterministic debrief
opening becomes a gap-fill prompt. Transcript-covered targets are suppressed
and unresolved marker categories can be prioritised. Only bounded target names,
not raw transcript text, are sent through the debrief reasoning context.

## Capture truthfulness by interaction type

- **Phone call:** passive only. The browser does not claim it can record the
  same call running on the device.
- **Online meeting:** passive only. Microphone capture is not represented as
  reliable system-audio capture.
- **Executive lunch:** passive is recommended; recording remains an explicit
  consented choice where supported.
- **Presentation/workshop/site visit:** existing visual capture and provenance
  rules remain in force.

## Accessibility and mobile behaviour

Controls use semantic buttons, labels and live status regions, visible focus,
large touch targets and a single-column phone layout. No gesture, colour or
animation is required to understand capture state.

See also:

- [Mobile browser recording UX](../03-engineering/mobile-browser-recording-ux-guide.md)
- [Companion lifecycle](../03-engineering/companion-state-lifecycle-guide.md)
- [Quick markers](../03-engineering/quick-marker-guide.md)
- [Companion security review](../03-engineering/companion-security-review.md)
