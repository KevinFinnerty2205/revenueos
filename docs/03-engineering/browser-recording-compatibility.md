# Browser recording compatibility

**Status:** Feature-detected beta foundation, not a universal support claim.

| Browser            | Foundation expectation                                                                     | Important limit                                      |
| ------------------ | ------------------------------------------------------------------------------------------ | ---------------------------------------------------- |
| Chrome desktop     | WebM/Opus preferred; start/pause/resume/stop supported in automated deterministic coverage | Keep the tab open                                    |
| Edge               | Chromium WebM/Opus path expected; requires release-device verification                     | Keep the tab open                                    |
| Safari desktop     | MP4/M4A fallback when `MediaRecorder.isTypeSupported` reports it                           | Codec and pause behaviour vary by release            |
| Chrome Android     | Foreground capture expected on supported devices                                           | Backgrounding or device lock may suspend capture     |
| Safari iPhone/iPad | MP4 path only when feature detection succeeds                                              | Screen lock/background interruption is expected risk |

Automated tests cover MIME preference, unsupported state, denied permission,
consent gate, start/pause/resume/stop, chunk upload, retry/finalisation state,
processing, transcript-ready restoration and a 390×844 journey with mocked media.
They are not physical-device certification. A release owner must record browser and
OS versions used for manual smoke testing before enabling design-partner recording.

The UI asks for microphone permission only after consent, provides large accessible
controls and non-colour status, warns users to keep the page open and installs a
navigation-loss warning during active capture/upload. Unsupported or denied clients
fall back to AI Debrief, Voice Journal or typed capture. No user-agent sniffing,
native-app requirement or background/screen-lock guarantee exists.

The browser requests a speech-oriented 16 kbps audio bitrate so a three-hour session
can fit within the optional OpenAI adapter's 25 MB file limit. `MediaRecorder` may
ignore that hint, so provider-size validation remains server-authoritative and the
512 MiB private-ingestion ceiling is not a promise that every configured provider
accepts a single file of that size.
