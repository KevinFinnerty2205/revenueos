# Browser phone-call workflow

The browser is a preparation, timing and post-call capture surface. It is not a
phone subsystem.

| Phase  | Browser surface                                                                 | Explicit boundary                                                        |
| ------ | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Before | Compact call brief and **Start call**                                           | No dial, call-log read or microphone request                             |
| During | Lifecycle status, end outcome controls and “Use your normal phone” guidance      | No **Record phone call**, hidden listening or same-device capture claim  |
| After  | **Capture this call while it’s fresh** and five deliberate capture/finish paths | Recording means import of an already authorised business-call recording |

## After-call actions

- **Start AI Debrief** — a bounded guided, typed-first interview;
- **Add Voice Journal** — records only the user's post-call report after separate
  safety and microphone acknowledgement;
- **Type Notes** — the same reviewed reported-evidence path without a microphone;
- **Add Recording** — uses the existing private WO-015 upload/transcription path;
- **Finish for now** — creates no customer intelligence and allows a later return.

All controls use semantic labels, keyboard-operable native controls, visible focus,
live status messages and responsive single-column layouts. The path does not need
an app installation. The normal phone-call screen does not call `getUserMedia`;
microphone permission can occur only after the user deliberately chooses Voice
Journal.

If a user manually starts and ends the Interaction, RevenueOS derives elapsed
duration from those timestamps. That number describes the RevenueOS lifecycle and
may differ from the phone system's duration.
