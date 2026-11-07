# Browser recording compatibility

**Status:** Feature-detected beta implementation, not a universal browser/OS
support claim.

## Capture modes

| Mode                                     | Implemented behaviour                                                                                                                                                                                                | Important limit                                                                                       |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Microphone only                          | Requests `getUserMedia` after consent and a user action; verifies one live audio track                                                                                                                               | Captures only sound available to the selected microphone                                              |
| Shared tab/display audio plus microphone | Requests `getDisplayMedia`, verifies that the selected share actually returned a live audio track, requests the microphone, deduplicates an identical source and mixes one of each distinct source through Web Audio | The chooser, offered share-audio option and returned audio depend on browser, OS and selected surface |
| Unsupported or missing shared audio      | Stops the selected share, preserves typed notes and offers microphone-only, transcript import, authorised recording upload or Debrief                                                                                | Selecting a tab/window/screen is not evidence that audio was captured                                 |

The mixed recorder stream must contain exactly one live audio track and no video
track. A display video track is kept only while necessary to observe when sharing
ends; it is stopped during cleanup and is never passed to `MediaRecorder`, retained
or uploaded.

## Actual verification record

| Browser and OS                                    | Source                                                                                                          | Result                                                                                                                                                             | Date            |
| ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------- |
| Google Chrome 156.0.8078.74 on macOS 15.6 (24G84) | Controlled local browser tab with a low-volume 440 Hz Web Audio oscillator plus Chrome's fake microphone device | One shared audio track, one microphone track, non-zero energy for both, one audio-only mixed recorder track, zero mixed video tracks and a non-empty recorded blob | 31 October 2026 |

The dedicated release fixture is
`apps/web/e2e/actual-browser-media/browser-audio.spec.ts`; it is excluded from the
normal headless suite and run explicitly with
`pnpm --filter @revenueos/web test:e2e:browser-audio`. It launches installed Chrome
headfully because display capture is a real browser/OS surface. It uses no real
meeting, real microphone, customer data or external service.

Edge, Safari, Firefox, Windows, mobile browsers, physical microphones, application
window audio, whole-screen/system audio and cross-application meeting capture were
not actually verified in this change. Chromium similarity is not a substitute for
an Edge release-device result. Safari/Firefox must remain unsupported unless their
feature detection and a release record prove otherwise.

## Automated fixture coverage

Vitest media doubles cover:

- microphone-only acquisition and one-track output;
- shared audio plus microphone mixing;
- a selected display with no audio track;
- duplicate microphone identity;
- unsupported shared capture;
- permission/cancellation error mapping;
- source mute/end and display-share end;
- `devicechange`, stop and idempotent cleanup; and
- typed notes remaining mounted through media failures.

Product Playwright acceptance uses mocked media to exercise consent, source choice,
status, chunk upload/finalisation and online-meeting Companion behaviour. Those
tests do not prove real audio transport. The explicit release fixture above is the
only actual browser-media verification record for this change.

## Operational boundary

The UI requests permission only after consent and a user action, labels microphone
and shared-audio state separately, warns users to keep the page open and installs a
navigation-loss warning during active capture/upload. Track ending or a device
change safely stops and finalises available chunks before cleanup. If client-side
navigation unmounts controls for a session started by that component, it stops the
recorder/tracks and issues one authenticated idempotent keepalive cancellation; it
does not continue capturing or attempt a hidden final upload. Private typed notes
are independent of the media lifecycle.

The browser asks `MediaRecorder` for a speech-oriented bitrate, but the browser may
ignore it. Provider file limits and the server's MIME, byte, duration, chunk and
manifest validation remain authoritative. This implementation does not provide
automatic call detection, a meeting bot, background capture, native cross-app audio
capture or a guarantee that every selectable surface includes audio.

References: [MDN `getDisplayMedia`](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getDisplayMedia),
[W3C Screen Capture](https://w3c.github.io/mediacapture-screen-share/), and
[Chrome screen-sharing controls](https://developer.chrome.com/docs/web-platform/screen-sharing-controls).
