# Mobile browser support matrix

## Support policy

RevenueOS uses runtime feature detection rather than browser-name assumptions.
The table records the current verification posture, not a permanent browser
guarantee. Any browser can lose capture when backgrounded, locked or suspended.

| Environment                              | Passive Companion | Visual selection/camera | Live audio                                    | Pause/resume           | Screen wake    | Current verification                 |
| ---------------------------------------- | ----------------- | ----------------------- | --------------------------------------------- | ---------------------- | -------------- | ------------------------------------ |
| Chromium, desktop with phone viewport    | Yes               | Yes                     | WebM/Opus when exposed                        | When exposed           | Best effort    | Automated Playwright flagship paths  |
| Chrome on Android                        | Expected          | Runtime detected        | Runtime MIME and permission detection         | Runtime detected       | Best effort    | Manual pilot device check required   |
| Safari on iPhone/iPad                    | Expected          | Runtime detected        | MP4-family format when exposed                | Runtime detected       | Best effort    | Manual pilot device check required   |
| Chrome on iPhone/iPad                    | Expected          | Runtime detected        | Uses the iOS browser engine; runtime detected | Runtime detected       | Best effort    | Manual pilot device check required   |
| Firefox on Android                       | Expected          | Runtime detected        | Runtime MIME and permission detection         | Runtime detected       | Best effort    | Manual pilot device check required   |
| Installed PWA/browser shortcut           | Yes               | Same as browser engine  | Foreground only                               | Same as browser engine | Best effort    | No background guarantee              |
| Phone call or online meeting Interaction | Yes               | Yes when enabled        | Deliberately unavailable in Companion         | Not applicable         | Not applicable | Product rule, independent of browser |

The application allowlists WebM/Opus first and MP4-family audio second. If
`getUserMedia`, `MediaRecorder` or an allowlisted MIME type is absent, recording
is unavailable and passive capture remains usable.

Before widening beta support, manually verify permission prompts, foreground
duration, lock/background behaviour, pause/resume, network loss, retry, camera
selection, file upload and assistive technology on the specific OS/browser
versions in the pilot cohort.
